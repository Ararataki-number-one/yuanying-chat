"""Host-only transfer integrity controls; no Android or application acceptance."""
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ci_bundle', ROOT / 'tools/gecko/ci_bundle.py')
BUNDLE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BUNDLE)


class CiBundleTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pocket-ci-bundle-')
        self.addCleanup(temporary.cleanup); self.base = Path(temporary.name)
        self.env = patch.dict(os.environ, GITHUB_RUN_ID='123456', GITHUB_RUN_ATTEMPT='1')
        self.env.start(); self.addCleanup(self.env.stop)
        self.root = self.base / 'source'; self.root.mkdir()
        self.git(self.root, 'init', '-q')
        (self.root / '.gitignore').write_text('work/\napp/build/\n')
        self.git(self.root, 'add', '.gitignore'); self.git(self.root, 'commit', '-qm', 'Fixture source')
        for name, data in {
            BUNDLE.INTEGRATION:b'exact synthetic integration bytes',
            BUNDLE.RELEASE:b'exact synthetic release bytes',
            BUNDLE.INPUT_DRIVER:b'exact synthetic input driver bytes',
            BUNDLE.INPUT_DRIVER_BUILD:b'{"scope":"input-driver transport fixture only"}',
            BUNDLE.SDK/'geckoview-caret.aar':b'exact synthetic SDK bytes',
            BUNDLE.SDK/'sdk-build-receipt.json':b'{"scope":"transport fixture only"}',
            BUNDLE.OUT/'host-results.json':b'{"synthetic":true}',
            BUNDLE.OUT/'integration-test.jks':b'must never transfer this key',
            BUNDLE.OUT/'network-fixture.p12':b'must never transfer this key either',
        }.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        for name in BUNDLE.INPUT_DRIVER_EVIDENCE:
            path = self.root / name
            if not path.exists(): path.write_bytes(b'original synthetic signature evidence\r\n')
        self.build = self.base / 'build.tar.gz'
        BUNDLE.pack(self.root,self.build,'build')

    def git(self, root, *args):
        return subprocess.check_output(['git','-c','user.name=CI fixture','-c','user.email=fixture@example.invalid',*args],cwd=root,stderr=subprocess.DEVNULL,text=True)

    def clone(self, name):
        target=self.base/name
        subprocess.run(['git','clone','-q','--no-hardlinks',str(self.root),str(target)],check=True,stderr=subprocess.DEVNULL)
        return target

    def phase(self, name, files):
        target=self.clone('phase-'+name);BUNDLE.restore(target,self.build,'build')
        for file,data in files.items():
            path=target/BUNDLE.OUT/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        archive=self.base/(name+'.tar.gz');BUNDLE.pack(target,archive,'phase',name)
        return archive

    def test_exact_build_roundtrip_excludes_keys_and_restores_same_ui_bytes(self):
        target=self.clone('consumer');manifest=BUNDLE.restore(target,self.build,'build')
        self.assertEqual((target/BUNDLE.INTEGRATION).read_bytes(),(self.root/BUNDLE.INTEGRATION).read_bytes())
        self.assertEqual((target/BUNDLE.OUT/'ui-current.apk').read_bytes(),(self.root/BUNDLE.INTEGRATION).read_bytes())
        self.assertFalse((target/BUNDLE.OUT/'integration-test.jks').exists())
        self.assertFalse((target/BUNDLE.OUT/'network-fixture.p12').exists())
        self.assertEqual(manifest['runId'],'123456')

    def test_input_driver_and_failed_raw_events_keep_exact_bytes_without_keys(self):
        target=self.clone('input-consumer');BUNDLE.restore(target,self.build,'build')
        for name in BUNDLE.INPUT_DRIVER_EVIDENCE:
            self.assertEqual((target/name).read_bytes(), (self.root/name).read_bytes())
        evidence={'native-input-baseline-scroll-results.json':b'{"status":"failed","lagMs":319}\r\n',
                  'native-input-baseline-scroll-stdout.log':b'raw output \xc2\n',
                  'native-input-baseline-scroll-stderr.log':b'',
                  'native-input-current-scroll-failure.txt':b'timeout with original evidence\n'}
        phase=self.phase('editing', evidence)
        BUNDLE.restore(target,phase,'phase','editing')
        for name,data in evidence.items():
            self.assertEqual((target/BUNDLE.OUT/name).read_bytes(),data)

    def test_event_sequence_failure_namespace_has_only_six_phase_files(self):
        expected = {'device-event-sequence-failure.json', 'device-event-sequence-filtered.log',
                    'device-event-sequence-expected.stdout.log', 'device-event-sequence-expected.stderr.log',
                    'device-event-sequence-current.stdout.log', 'device-event-sequence-current.stderr.log'}
        self.assertEqual(BUNDLE.EVENT_SEQUENCE_FAILURE_FILES, expected)
        for name in expected:
            self.assertTrue(BUNDLE.allowed(str(BUNDLE.OUT/name), 'phase'), name)
            self.assertFalse(BUNDLE.allowed(str(BUNDLE.OUT/name), 'build'), name)
            for folder in ('nested', 'caret-compat', 'ui-visuals'):
                self.assertFalse(BUNDLE.allowed(str(BUNDLE.OUT/folder/name), 'phase'), name)
        for name in ('device-event-sequence-private.txt', 'device-event-sequence-private.json',
                     'device-event-sequence-private.log', 'device-event-sequence-filtered.txt',
                     'device-event-sequence-expected.stdout.log.bak', 'device-event-sequence.json',
                     'DEVICE-EVENT-SEQUENCE-filtered.log', 'device-event-sequence-fixture.apk',
                     'device-event-sequence-fixture.jks', 'device-event-sequence-fixture.p12'):
            for kind in ('build', 'phase'):
                self.assertFalse(BUNDLE.allowed(str(BUNDLE.OUT/name), kind), (name, kind))

    def test_original_event_sequence_failure_bytes_survive_phase_roundtrip(self):
        evidence = {
            'device-event-sequence-failure.json': b'{"status":"failed","diagnosticOnly":true}\r\n',
            'device-event-sequence-filtered.log': 'original filtered snapshot\r\n原始\n'.encode(),
            'device-event-sequence-expected.stdout.log': b'\x00\xffunparsed original provider bytes\r\n',
            'device-event-sequence-expected.stderr.log': b'',
            'device-event-sequence-current.stdout.log': b'{"sequence":2}\n',
            'device-event-sequence-current.stderr.log': b'original error \xc2\n',
        }
        excluded = {'device-event-sequence-private.txt': b'not declared',
                    'device-event-sequence-private.log': b'not declared',
                    'device-event-sequence-fixture.jks': b'synthetic key excluded',
                    'device-event-sequence-fixture.apk': b'synthetic executable excluded'}
        phase = self.phase('files', {**evidence, **excluded})
        with tarfile.open(phase, 'r:gz') as archive:
            index = json.loads(archive.extractfile('_ci_bundle.json').read())
            rows = {row['path']: row for row in index['files']}
            self.assertEqual(index['phase'], 'files')
            self.assertEqual(index['runId'], '123456')
            self.assertEqual(index['runAttempt'], '1')
            for name, data in evidence.items():
                row = rows[str(BUNDLE.OUT/name)]
                self.assertEqual((row['bytes'], row['sha256']),
                                 (len(data), hashlib.sha256(data).hexdigest()))
                self.assertEqual(archive.extractfile(str(BUNDLE.OUT/name)).read(), data)
            self.assertFalse({str(BUNDLE.OUT/name) for name in excluded} & rows.keys())
        target = self.clone('sequence-failure-collector')
        BUNDLE.restore(target, self.build, 'build')
        BUNDLE.restore(target, phase, 'phase', 'files')
        for name, data in evidence.items():
            self.assertEqual((target/BUNDLE.OUT/name).read_bytes(), data)
        for name in excluded:
            self.assertFalse((target/BUNDLE.OUT/name).exists())

    def test_restore_rejects_undeclared_event_sequence_file_before_any_phase_write(self):
        phase = self.phase('files', {'device-event-sequence-failure.json': b'{"synthetic":true}'})
        for number, extra in enumerate(('device-event-sequence-private.txt',
                                         'device-event-sequence-private.log',
                                         'device-event-sequence-private.json',
                                         'device-event-sequence-fixture.jks')):
            forged = self.base/('forged-sequence-%d.tar.gz' % number)
            path = str(BUNDLE.OUT/extra); data = b'undeclared synthetic transport bytes'
            with tarfile.open(phase, 'r:gz') as original, tarfile.open(forged, 'w:gz') as output:
                for item in original.getmembers():
                    raw = original.extractfile(item).read()
                    if item.name == '_ci_bundle.json':
                        index = json.loads(raw)
                        index['files'].append(dict(path=path, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
                        raw = json.dumps(index).encode(); item.size = len(raw)
                    output.addfile(item, io.BytesIO(raw))
                item = tarfile.TarInfo(path); item.size = len(data)
                output.addfile(item, io.BytesIO(data))
            target = self.clone('sequence-failure-reject-%d' % number)
            BUNDLE.restore(target, self.build, 'build')
            with self.assertRaisesRegex(AssertionError, 'CI archive path outside'):
                BUNDLE.restore(target, forged, 'phase', 'files')
            self.assertFalse((target/BUNDLE.OUT/'device-event-sequence-failure.json').exists())
            self.assertFalse((target/BUNDLE.OUT/extra).exists())

    def test_build_cannot_omit_input_driver(self):
        for name in BUNDLE.INPUT_DRIVER_EVIDENCE:
            path=self.root/name;data=path.read_bytes();path.unlink()
            with self.assertRaises(AssertionError):
                BUNDLE.pack(self.root,self.base/'incomplete.tar.gz','build')
            path.write_bytes(data)

    def test_restore_rejects_each_missing_signature_artifact_before_extracting(self):
        for number, missing in enumerate(BUNDLE.INPUT_DRIVER_EVIDENCE):
            incomplete = self.base / ('missing-signature-%d.tar.gz' % number)
            with tarfile.open(self.build, 'r:gz') as original, tarfile.open(incomplete, 'w:gz') as output:
                for item in original.getmembers():
                    if item.name == str(missing): continue
                    data = original.extractfile(item).read()
                    if item.name == '_ci_bundle.json':
                        index = json.loads(data)
                        index['files'] = [row for row in index['files'] if row['path'] != str(missing)]
                        data = json.dumps(index).encode(); item.size = len(data)
                    output.addfile(item, io.BytesIO(data))
            target = self.clone('missing-signature-consumer-%d' % number)
            with self.subTest(missing=missing), self.assertRaisesRegex(AssertionError, 'Input driver build is missing'):
                BUNDLE.restore(target, incomplete, 'build')
            self.assertFalse((target / BUNDLE.INTEGRATION).exists())

    def test_network_settings_evidence_survives_build_and_connections_roundtrip_without_keys(self):
        # These bytes exercise transport only; they are not Android results.
        host_names = [f'network-settings-{kind}-{platform}-host-results.json'
                      for kind in ('receipt', 'provider', 'retry', 'ui')
                      for platform in ('desktop', 'android')]
        device_names = [f'network-settings-{kind}-{suffix}'
                        for kind in ('application', 'internal', 'retry')
                        for suffix in ('results.json', 'log.txt', 'final.png')]
        names = host_names + device_names + ['network-settings-parser-negative-results.json',
                                             'network-settings-application-failure.xml']
        evidence = {name: ('Host-only transport fixture: ' + name + '\n').encode() for name in names}
        build_files = {name: data for name, data in evidence.items()
                       if '-desktop-' in name or name == 'network-settings-parser-negative-results.json'}
        phase_files = {name: data for name, data in evidence.items() if name not in build_files}
        keys = {'network-settings-fixture.jks': b'private synthetic JKS fixture',
                'network-settings-fixture.p12': b'private synthetic PKCS12 fixture'}
        for name, data in {**build_files, **keys}.items():
            (self.root/BUNDLE.OUT/name).write_bytes(data)
        BUNDLE.pack(self.root, self.build, 'build')
        connections = self.phase('connections', {**phase_files, **keys})

        for archive, expected in ((self.build, build_files), (connections, phase_files)):
            with self.subTest(archive=archive.name), tarfile.open(archive, 'r:gz') as contents:
                members = set(contents.getnames())
                self.assertTrue({str(BUNDLE.OUT/name) for name in expected} <= members)
                self.assertFalse({str(BUNDLE.OUT/name) for name in keys} & members)
        target = self.clone('network-settings-collector')
        BUNDLE.restore(target, self.build, 'build')
        BUNDLE.restore(target, connections, 'phase', 'connections')
        for name, data in evidence.items():
            with self.subTest(file=name):
                self.assertEqual((target/BUNDLE.OUT/name).read_bytes(), data)
                self.assertFalse((target/BUNDLE.OUT/'ci-phases/connections'/name).exists())
        for name in keys:
            self.assertFalse((target/BUNDLE.OUT/name).exists())

    def test_original_upload_logs_survive_build_phase_and_final_collection(self):
        # Preserve even empty original stderr/compile streams, rather than
        # reconstructing logs from the summary after the build is restored.
        logs = {name: (b'' if '.stderr.' in name or '-compile.' in name
                       else ('synthetic original ' + name + '\n').encode())
                for name in BUNDLE.UPLOAD_LOGS}
        for name, data in logs.items():
            (self.root/BUNDLE.OUT/name).write_bytes(data)
        unrelated = ('upload-state-private.txt', 'upload-state-browser.stdout.txt.bak',
                     'private-notes.txt', 'network-settings-private.txt')
        for name in unrelated:
            (self.root/BUNDLE.OUT/name).write_bytes(b'not a declared build log')
        BUNDLE.pack(self.root, self.build, 'build')
        with tarfile.open(self.build, 'r:gz') as archive:
            indexed = json.loads(archive.extractfile('_ci_bundle.json').read())
            rows = {row['path']: row for row in indexed['files']}
            for name, data in logs.items():
                self.assertEqual(rows[str(BUNDLE.OUT/name)]['bytes'], len(data))
            self.assertFalse({str(BUNDLE.OUT/name) for name in unrelated} & rows.keys())
        phase = self.phase('connections', {'network-settings-retry-results.json': b'{"synthetic":true}'})
        with tarfile.open(phase, 'r:gz') as archive:
            self.assertFalse({str(BUNDLE.OUT/name) for name in logs} & set(archive.getnames()))
        target = self.clone('upload-log-collector')
        BUNDLE.restore(target, self.build, 'build')
        BUNDLE.restore(target, phase, 'phase', 'connections')
        for name, data in logs.items():
            self.assertEqual((target/BUNDLE.OUT/name).read_bytes(), data)

    def test_other_ci_attempt_is_rejected_before_writing_apks(self):
        target=self.clone('other-attempt')
        with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'),self.assertRaises(AssertionError):
            BUNDLE.restore(target,self.build,'build')
        self.assertFalse((target/BUNDLE.INTEGRATION).exists())

    def test_settings_build_logs_have_only_the_nineteen_declared_names(self):
        expected = {f'network-settings-{kind}-{implementation}-{stream}.txt'
                    for kind in ('receipt', 'provider', 'retry', 'ui')
                    for implementation in ('desktop', 'android')
                    for stream in ('stdout', 'stderr')}
        expected.update({'network-settings-gecko_settings_retry_gate_test-stdout.txt',
                         'network-settings-gecko_settings_application_gate_test-stdout.txt',
                         'network-settings-gecko_settings_internal_gate_test-stdout.txt'})
        self.assertEqual(len(expected), 19)
        self.assertEqual(BUNDLE.SETTINGS_LOGS, expected)
        for name in expected:
            self.assertTrue(BUNDLE.allowed(str(BUNDLE.OUT/name), 'build'), name)
        for name in ('network-settings-private.txt', 'network-settings-retry-desktop-private.txt',
                     'network-settings-retry-other-stdout.txt', 'network-settings-other-desktop-stdout.txt',
                     'network-settings-gecko_settings_internal_gate_test-stderr.txt',
                     'network-settings-retry-desktop-stdout.txt.bak', 'private-notes.txt',
                     'nested/network-settings-retry-desktop-stdout.txt'):
            self.assertFalse(BUNDLE.allowed(str(BUNDLE.OUT/name), 'build'), name)

    def test_original_settings_logs_survive_build_phase_and_final_collection(self):
        # These are synthetic transport bytes, including original empty streams;
        # they must survive the real pack/restore path without reconstruction.
        logs = {name: (b'' if name.endswith('-stderr.txt') else
                       ('original synthetic settings output: ' + name + '\n').encode())
                for name in BUNDLE.SETTINGS_LOGS}
        unrelated = {'network-settings-private.txt': b'never transfer undeclared text',
                     'network-settings-gecko_settings_other_gate_test-stdout.txt': b'not declared'}
        for name, data in {**logs, **unrelated}.items():
            (self.root/BUNDLE.OUT/name).write_bytes(data)
        BUNDLE.pack(self.root, self.build, 'build')
        with tarfile.open(self.build, 'r:gz') as archive:
            rows = {row['path']: row for row in json.loads(archive.extractfile('_ci_bundle.json').read())['files']}
            for name, data in logs.items():
                self.assertEqual(rows[str(BUNDLE.OUT/name)]['bytes'], len(data))
                self.assertEqual(rows[str(BUNDLE.OUT/name)]['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(archive.extractfile(str(BUNDLE.OUT/name)).read(), data)
            self.assertFalse({str(BUNDLE.OUT/name) for name in unrelated} & rows.keys())
        phase = self.phase('connections', {'network-settings-internal-results.json': b'{"synthetic":true}'})
        with tarfile.open(phase, 'r:gz') as archive:
            self.assertFalse({str(BUNDLE.OUT/name) for name in logs} & set(archive.getnames()))
        target = self.clone('settings-log-collector')
        BUNDLE.restore(target, self.build, 'build')
        BUNDLE.restore(target, phase, 'phase', 'connections')
        for name, data in logs.items():
            self.assertEqual((target/BUNDLE.OUT/name).read_bytes(), data)
        for name in unrelated:
            self.assertFalse((target/BUNDLE.OUT/name).exists())

    def test_other_source_is_rejected_before_writing_apks(self):
        target=self.clone('other-source');(target/'changed.txt').write_text('another source')
        self.git(target,'add','changed.txt');self.git(target,'commit','-qm','Different source')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,self.build,'build')
        self.assertFalse((target/BUNDLE.INTEGRATION).exists())

    def test_changed_archive_bytes_are_rejected_before_any_extraction(self):
        corrupt=self.base/'corrupt.tar.gz'
        with tarfile.open(self.build,'r:gz') as original,tarfile.open(corrupt,'w:gz') as output:
            for item in original.getmembers():
                raw=original.extractfile(item).read()
                if item.name==str(BUNDLE.INTEGRATION):raw=b'X'+raw[1:]
                output.addfile(item,io.BytesIO(raw))
        target=self.clone('corrupt-consumer')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,corrupt,'build')
        self.assertFalse((target/BUNDLE.INTEGRATION).exists())

    def test_phase_requires_the_same_compiled_build_index(self):
        phase=self.phase('ui',{'ui-visual-results.json':b'{"synthetic":true}'})
        target=self.clone('different-build');BUNDLE.restore(target,self.build,'build')
        path=target/BUNDLE.BUILD_INDEX;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,phase,'phase','ui')
        self.assertFalse((target/BUNDLE.OUT/'ui-visual-results.json').exists())

    def test_distinct_phase_reports_merge_and_device_preflight_remains_canonical(self):
        ui=self.phase('ui',{'ui-visual-results.json':b'{"ui":true}','emulator-bootstrap-results.json':b'{"vm":"ui"}'})
        files=self.phase('files',{'device-results.json':b'{"device":true}','emulator-bootstrap-results.json':b'{"vm":"files"}'})
        target=self.clone('collector');BUNDLE.restore(target,self.build,'build')
        BUNDLE.restore(target,ui,'phase','ui');BUNDLE.restore(target,files,'phase','files')
        self.assertTrue((target/BUNDLE.OUT/'ui-visual-results.json').exists())
        self.assertTrue((target/BUNDLE.OUT/'device-results.json').exists())
        self.assertEqual(json.loads((target/BUNDLE.OUT/'emulator-bootstrap-results.json').read_text())['vm'],'files')
        self.assertEqual(json.loads((target/BUNDLE.OUT/'ci-phases/ui/emulator-bootstrap-results.json').read_text())['vm'],'ui')

    def test_phases_cannot_replace_another_phase_evidence(self):
        ui=self.phase('ui',{'shared-results.json':b'first'})
        other=self.phase('connections',{'shared-results.json':b'second'})
        target=self.clone('collision');BUNDLE.restore(target,self.build,'build');BUNDLE.restore(target,ui,'phase','ui')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,other,'phase','connections')
        self.assertEqual((target/BUNDLE.OUT/'shared-results.json').read_bytes(),b'first')

    def test_traversal_and_symbolic_link_entries_are_rejected(self):
        for name, link in (('../escape',False),('work/gecko-integration/link.json',True)):
            archive=self.base/('link.tar.gz' if link else 'traversal.tar.gz')
            with tarfile.open(self.build,'r:gz') as original,tarfile.open(archive,'w:gz') as output:
                for item in original.getmembers():output.addfile(item,original.extractfile(item))
                item=tarfile.TarInfo(name)
                if link:item.type=tarfile.SYMTYPE;item.linkname='/tmp/outside'
                else:item.size=1
                output.addfile(item,None if link else io.BytesIO(b'x'))
            target=self.clone('link-consumer' if link else 'traversal-consumer')
            with self.assertRaises(AssertionError):BUNDLE.restore(target,archive,'build')
            self.assertFalse((target/BUNDLE.INTEGRATION).exists())


if __name__=='__main__':unittest.main()
