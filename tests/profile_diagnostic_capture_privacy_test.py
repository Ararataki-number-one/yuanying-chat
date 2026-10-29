"""Capture-privacy controls with generated keys and counterfeit IME adapters.

No actual service key, Android process, input event, account or network endpoint
is used. The existing native identity parsers remain part of these controls.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests')]
import caret_ime_guard as G
import gecko_caret_ime_guard_test as HOST

MARKER = '[REDACTED_SERVICE_API_KEY]'
GBOARD = 'AIza' + 'g'*35
SAFE = 'AIza' + 's'*35
UNKNOWN = 'AIza' + 'u'*35
MOZILLA = 'm'*36
BASE = '09488ea9a436bcd3787c7f7f45667f3344f128f7'
META_KEYS = {'schema','kind','policy','originalBytes','originalSha256',
             'finalBytes','finalSha256','changed','replacements'}
COUNT_KEYS = {'gboard','mozilla-location','google-safebrowsing','google-api-key-shape'}


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def gboard_line(key=GBOARD):
    return ('    expressive_stickers_api_key{type=String, finalValue='+key+
            ', PHENOTYPE='+key+'}\n')


def mls(key=MOZILLA):
    return 'https://location.services.mozilla.com/v1/country?key='+key+'&extra=kept'


def safebrowsing(key=SAFE):
    return 'https://safebrowsing.googleapis.com/v5/hashLists:batchGet?key='+key+'&alt=json'


class Clock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return 1_000_000_000 + self.calls*10_000


def guard_record(with_key):
    class CaptureAdb(HOST.FakeAdb):
        def __init__(self):
            super().__init__()
            self.original_dumps = []

        def __call__(self, *parts):
            value = super().__call__(*parts)
            if parts == G.METHOD_DUMP_COMMAND:
                value += '    unrelatedUnicode=\u4f60\u597d\U0001f642\n'
                if with_key:
                    value += gboard_line()
                self.original_dumps.append(value)
            return value

    fake, record, clock = CaptureAdb(), {}, Clock()
    guard = G.ControlledImeGuard(adb=fake, identity=HOST.identity(), record=record,
                                nonce='e'*32, clock=clock)
    result = guard.run(lambda: 0)
    return result, fake, record, clock


def functions(source):
    result = {}
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = ast.get_source_segment(source, node)
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[node.name+'.'+member.name] = ast.get_source_segment(source, member)
    return result


def load_bundle():
    spec=importlib.util.spec_from_file_location('capture_privacy_ci_bundle',ROOT/'tools/gecko/ci_bundle.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def publisher_scanner():
    """Load actual pure scanner nodes without executing publisher top-level Git."""
    source=(ROOT/'tools/gecko/publish_ci.py').read_text()
    tree=ast.parse(source)
    nodes=[node for node in tree.body if (isinstance(node,ast.FunctionDef) and node.name=='scan_public_diagnostics')
           or (isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DIAGNOSTIC_TEXT_SUFFIXES' for x in node.targets))]
    if len(nodes)!=2:
        raise AssertionError('Actual publisher scanner and text allowlist must exist exactly once')
    namespace={'assert_public_diagnostic_text':G.assert_public_diagnostic_text}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-publisher-privacy-scanner>','exec'),namespace)
    return namespace


class DiagnosticCapturePrivacyTest(unittest.TestCase):
    def metadata(self, original, sanitized, value, expected_counts):
        self.assertEqual(set(value), META_KEYS)
        self.assertEqual((type(value['schema']),value['schema']), (int,1))
        self.assertEqual(value['kind'], 'service-api-key-value-redaction')
        self.assertEqual(value['policy'], 'known-service-keys-v1')
        self.assertEqual(value['originalBytes'], len(original.encode('utf-8')))
        self.assertEqual(value['originalSha256'], digest(original))
        self.assertEqual(value['finalBytes'], len(sanitized.encode('utf-8')))
        self.assertEqual(value['finalSha256'], digest(sanitized))
        self.assertIs(value['changed'], original != sanitized)
        self.assertEqual(set(value['replacements']), COUNT_KEYS)
        expected = dict.fromkeys(COUNT_KEYS,0)
        expected.update(expected_counts)
        self.assertEqual(value['replacements'], expected)
        self.assertTrue(all(type(x) is int and x >= 0 for x in value['replacements'].values()))
        self.assertIs(G.verify_capture_privacy(value, sanitized), True)

    def test_no_hit_preserves_every_byte_and_explicit_zero_marker(self):
        original = 'prefix\r\n\u4f60\u597d\U0001f642 cookie=owned-fixture; password=controlled\r\nsuffix\n'
        sanitized, metadata = G.redact_service_api_keys(original)
        self.assertEqual(sanitized, original)
        self.metadata(original, sanitized, metadata, dict.fromkeys(COUNT_KEYS,0))

    def test_known_context_values_only_preserve_prefix_suffix_and_unicode(self):
        original = '\u524d\U0001f642\r\n'+gboard_line()+mls()+'\n'+safebrowsing()+'\n\u540e\r\n'
        expected = original.replace(GBOARD, MARKER).replace(MOZILLA, MARKER).replace(SAFE, MARKER)
        sanitized, metadata = G.redact_service_api_keys(original)
        self.assertEqual(sanitized, expected)
        self.metadata(original, sanitized, metadata,
                      {'gboard':2,'mozilla-location':1,'google-safebrowsing':1})
        self.assertEqual(G.service_api_key_findings(sanitized), [])
        self.assertNotIn(GBOARD, json.dumps(metadata))
        self.assertNotIn(MOZILLA, json.dumps(metadata))

    def test_duplicate_occurrences_are_counted_and_idempotent(self):
        original = gboard_line()+gboard_line()+mls()+' '+mls()+' '+safebrowsing()
        sanitized, metadata = G.redact_service_api_keys(original)
        self.metadata(original, sanitized, metadata,
                      {'gboard':4,'mozilla-location':2,'google-safebrowsing':1})
        again, second = G.redact_service_api_keys(sanitized)
        self.assertEqual(again, sanitized)
        self.metadata(sanitized, again, second, dict.fromkeys(COUNT_KEYS,0))

    def test_percent_encoded_key_values_are_sanitized_without_rewriting_url(self):
        encoded = ''.join('%%%02X'%value for value in SAFE.encode('ascii'))
        original = 'prefix '+safebrowsing(encoded)+' suffix\u4f60'
        sanitized, metadata = G.redact_service_api_keys(original)
        self.assertEqual(sanitized, original.replace(encoded,MARKER))
        self.metadata(original,sanitized,metadata,
                      {'gboard':0,'mozilla-location':0,'google-safebrowsing':1})
        self.assertEqual(G.service_api_key_findings(sanitized), [])

    def test_encoded_query_names_json_slashes_and_whole_url_preserve_other_bytes(self):
        def encoded(value):return ''.join('%%%02X'%item for item in value.encode('ascii'))
        forms=[mls().replace('?key=','?%6bey='),mls().replace('?key=','?KEY='),
               mls().replace('/',r'\/'),mls().replace('?',r'\u003f').replace('=',r'\u003d')]
        forms.append(encoded(mls()))
        for original in forms:
            with self.subTest(form=original[:50]):
                token=encoded(MOZILLA) if original.startswith('%') else MOZILLA
                sanitized,metadata=G.redact_service_api_keys(original)
                self.assertEqual(sanitized,original.replace(token,MARKER))
                self.metadata(original,sanitized,metadata,{'mozilla-location':1})
                self.assertEqual(G.service_api_key_findings(sanitized),[])

    def test_unknown_api_shape_is_found_without_exposing_value(self):
        original = 'unknown-extension-setting='+UNKNOWN
        findings = G.service_api_key_findings(original)
        self.assertIsInstance(findings,list)
        self.assertTrue(findings)
        self.assertIn(digest(UNKNOWN), {row['sha256'] for row in findings})
        for row in findings:
            self.assertEqual(set(row), {'kind','sha256'})
            self.assertIsInstance(row['kind'], str)
            self.assertRegex(row['sha256'], '^[0-9a-f]{64}$')
        self.assertNotIn(UNKNOWN,json.dumps(findings))
        encoded = ''.join('%%%02x'%value for value in UNKNOWN.encode())
        self.assertTrue(G.service_api_key_findings('unknown='+encoded))
        sanitized, metadata = G.redact_service_api_keys(original)
        self.assertEqual(sanitized,'unknown-extension-setting='+MARKER)
        self.metadata(original,sanitized,metadata,{'google-api-key-shape':1})
        self.assertEqual(G.service_api_key_findings(sanitized),[])

    def test_overlong_api_shape_identifiers_do_not_match_a_key_prefix(self):
        for tail in ('-suffix','_suffix','AlphaNumeric09'):
            with self.subTest(tail=tail):
                original='benign_setting='+UNKNOWN+tail
                self.assertEqual(G.service_api_key_findings(original),[])
                sanitized,metadata=G.redact_service_api_keys(original)
                self.assertEqual(sanitized,original)
                self.metadata(original,sanitized,metadata,dict.fromkeys(COUNT_KEYS,0))

    def test_unrelated_cookie_proxy_and_other_host_fields_are_not_broadly_redacted(self):
        original = ('cookie=controlled-cookie; proxyPassword=controlled-password; '
                    'https://location.services.mozilla.com.evil/v1/country?key=controlled; '
                    'https://example.invalid/?key=controlled')
        sanitized, metadata = G.redact_service_api_keys(original)
        self.assertEqual(sanitized, original)
        self.metadata(original,sanitized,metadata,dict.fromkeys(COUNT_KEYS,0))

    def test_utf8_original_size_is_checked_before_any_filtering(self):
        original = gboard_line()
        with self.assertRaises(ValueError):
            G.redact_service_api_keys(original,max_bytes=len(original.encode())-1)
        sanitized, metadata = G.redact_service_api_keys('\U0001f642',max_bytes=4)
        self.assertEqual(sanitized,'\U0001f642')
        self.metadata('\U0001f642',sanitized,metadata,dict.fromkeys(COUNT_KEYS,0))
        with self.assertRaises(ValueError):G.redact_service_api_keys('\U0001f642',max_bytes=3)
        for bad in (True,0,-1,1.0,None,16*1024*1024+1):
            with self.subTest(max_bytes=bad),self.assertRaises(ValueError):
                G.redact_service_api_keys('bounded',max_bytes=bad)

    def test_total_replacement_cap_is_bounded_and_not_silently_truncated(self):
        original = gboard_line()*2048
        sanitized, metadata = G.redact_service_api_keys(original)
        self.metadata(original,sanitized,metadata,
                      {'gboard':4096,'mozilla-location':0,'google-safebrowsing':0})
        with self.assertRaises(ValueError):G.redact_service_api_keys(original+gboard_line())

    def test_marker_types_extra_fields_and_final_body_tampering_are_rejected(self):
        sanitized, metadata = G.redact_service_api_keys(gboard_line())
        mutations = [('schema',True),('kind','raw-original'),('policy','unreviewed'),
                     ('originalBytes',True),('originalBytes',-1),('originalSha256','bad'),
                     ('finalBytes',True),('finalBytes',metadata['finalBytes']+1),
                     ('finalSha256','0'*64),('changed',1),('changed',False),
                     ('replacements',{'gboard':True,'mozilla-location':0,'google-safebrowsing':0,'google-api-key-shape':0}),
                     ('replacements',{'gboard':-1,'mozilla-location':0,'google-safebrowsing':0,'google-api-key-shape':0}),
                     ('replacements',{'gboard':2,'mozilla-location':0}),
                     ('replacements',{'gboard':2,'mozilla-location':0,'google-safebrowsing':0,'extra':0})]
        for key,value in mutations:
            with self.subTest(field=key,value=value):
                invalid = copy.deepcopy(metadata);invalid[key]=value
                self.assertIs(G.verify_capture_privacy(invalid,sanitized),False)
        invalid = dict(metadata,unreviewed=True)
        self.assertIs(G.verify_capture_privacy(invalid,sanitized),False)
        self.assertIs(G.verify_capture_privacy(metadata,sanitized+'\nchanged'),False)
        self.assertIs(G.verify_capture_privacy(None,sanitized),False)
        for change in ({'originalBytes':0},{'originalSha256':metadata['finalSha256']}):
            self.assertIs(G.verify_capture_privacy(dict(metadata,**change),sanitized),False)
        fewer_markers=sanitized.replace(MARKER,'controlled',1)
        changed=dict(metadata,finalBytes=len(fewer_markers.encode()),finalSha256=digest(fewer_markers))
        self.assertIs(G.verify_capture_privacy(changed,fewer_markers),False)

    def test_actual_guard_paired_capture_preserves_native_state_commands_and_clock_order(self):
        clean_result, clean_fake, clean, clean_clock = guard_record(False)
        key_result, key_fake, record, key_clock = guard_record(True)
        self.assertEqual((clean_result,key_result),(0,0))
        self.assertEqual(clean_fake.calls,key_fake.calls)
        self.assertEqual(clean_fake.mutations,key_fake.mutations)
        self.assertEqual(clean_fake.settings,clean_fake.before)
        self.assertEqual(key_fake.settings,key_fake.before)
        self.assertEqual(clean_clock.calls,key_clock.calls)
        self.assertEqual(record['workloadInvocationCount'],1)
        stamps = ('prepareStartedAtMonotonicNanos','preparedAtMonotonicNanos',
                  'workloadStartedAtMonotonicNanos','workloadCompletedAtMonotonicNanos',
                  'restoreStartedAtMonotonicNanos','restoredAtMonotonicNanos')
        self.assertEqual([clean[k] for k in stamps],[record[k] for k in stamps])
        rows=[row for row in record['commands'] if tuple(row['parts'])==G.METHOD_DUMP_COMMAND]
        self.assertEqual(len(rows),4)
        for row, original in zip(rows,key_fake.original_dumps):
            sanitized=original.replace(GBOARD,MARKER)
            self.assertEqual(row['stdout'],sanitized)
            self.assertEqual(row['stdoutChars'],len(sanitized))
            self.assertEqual(row['stdoutBytes'],len(sanitized.encode()))
            self.assertEqual(row['stdoutSha256'],digest(sanitized))
            self.metadata(original,sanitized,row['capturePrivacy'],
                          {'gboard':2,'mozilla-location':0,'google-safebrowsing':0})
            self.assertEqual(G.current_method(original),G.current_method(sanitized))
            self.assertEqual(G.active_method(original),G.active_method(sanitized))
        self.assertEqual(record['initial']['inputMethodDumpRaw'],rows[0]['stdout'])
        self.assertEqual(record['during']['inputMethodDumpRaw'],rows[1]['stdout'])
        self.assertEqual(record['activeInputMethod']['inputMethodDumpRaw'],rows[2]['stdout'])
        self.assertEqual(record['restored']['inputMethodDumpRaw'],rows[3]['stdout'])
        self.assertNotIn(GBOARD,json.dumps(record,ensure_ascii=False))
        self.assertEqual(G.service_api_key_findings(json.dumps(record,ensure_ascii=False)),[])

    def test_native_identity_parser_and_state_bodies_are_exact_accepted_source(self):
        path='tools/gecko/caret_ime_guard.py'
        original=subprocess.run(['git','show',BASE+':'+path],cwd=ROOT,capture_output=True,timeout=10)
        self.assertEqual(original.returncode,0)
        baseline=functions(original.stdout.decode('utf-8'))
        current=functions((ROOT/path).read_text())
        for name in ('canonical_component','subtype','enabled_entries','valid_history','component_list',
                     '_method_block','current_method','active_method','Snapshot.state'):
            with self.subTest(member=name):self.assertEqual(current[name],baseline[name])

    def test_sidecar_write_failure_occurs_after_actual_runner_cleanup_bodies(self):
        for runner,sidecar in (('run_gecko_performance.py','gecko-performance-capture-privacy.json'),
                               ('run_preconnect.py','preconnect-capture-privacy.json')):
            with self.subTest(runner=runner):
                tree=ast.parse((ROOT/'tests/gecko'/runner).read_text())
                blocks=[node.finalbody for node in ast.walk(tree) if isinstance(node,ast.Try)
                        and any(isinstance(child,ast.Constant) and child.value==sidecar
                                for statement in node.finalbody for child in ast.walk(statement))]
                self.assertEqual(len(blocks),1)
                events=[]
                class Target:
                    def __truediv__(self,name):
                        if name!=sidecar:raise AssertionError('Unexpected sidecar')
                        return self
                    def write_text(self,text):
                        events.append('sidecar-write')
                        raise OSError('Synthetic sidecar write failed')
                class Server:
                    def __init__(self,name):self.name=name
                    def shutdown(self):events.append(self.name+'.shutdown')
                    def server_close(self):events.append(self.name+'.close')
                class Process:
                    def terminate(self):events.append('process.terminate')
                    def communicate(self,timeout=None):
                        events.append('process.communicate:'+str(timeout))
                        if timeout is not None:raise subprocess.TimeoutExpired('synthetic-owned-child',timeout)
                    def kill(self):events.append('process.kill')
                def adb(*parts,**kwargs):events.append('adb:'+':'.join(map(str,parts)))
                namespace=dict(servers=[Server('one'),Server('two')],OUT=Target(),json=json,
                               diagnostic_privacy_summary=lambda unused:{'controlled':True},privacy_captures=[],
                               adb=adb,PACKAGE='local.pocketchat.test',PORT=8771,
                               process=Process(),subprocess=subprocess)
                body=ast.fix_missing_locations(ast.Module(body=copy.deepcopy(blocks[0]),type_ignores=[]))
                with self.assertRaisesRegex(OSError,'Synthetic sidecar write failed'):
                    exec(compile(body,'<actual-runner-finally-body>','exec'),namespace)
                if runner=='run_gecko_performance.py':
                    self.assertEqual(events,['one.shutdown','one.close','two.shutdown','two.close','sidecar-write'])
                else:
                    self.assertEqual(events,['adb:shell:am:force-stop:local.pocketchat.test',
                                             'adb:reverse:--remove:tcp:8771','process.terminate',
                                             'process.communicate:5','process.kill','process.communicate:None',
                                             'sidecar-write'])

    def test_guard_failure_and_oversize_excerpts_never_retain_service_key_values(self):
        class DiagnosticError(RuntimeError):
            def __init__(self):
                super().__init__(gboard_line())
                self.stdout=gboard_line().encode()
                self.output=gboard_line()
                self.stderr=gboard_line().encode()
        fake=HOST.FakeAdb()
        def fail(*parts):
            if parts==G.METHOD_DUMP_COMMAND:raise DiagnosticError()
            return fake(*parts)
        record={}
        guard=G.ControlledImeGuard(adb=fail,identity=HOST.identity(),record=record,nonce='e'*32,clock=Clock())
        with self.assertRaises(DiagnosticError):guard.run(lambda:0)
        self.assertNotIn(GBOARD,json.dumps(record))
        self.assertEqual(fake.mutations,[])
        self.assertEqual(G.service_api_key_findings(json.dumps(record)),[])
        large=HOST.FakeAdb()(*G.METHOD_DUMP_COMMAND)+gboard_line()+('\u4f60'*1400000)+gboard_line()
        fake=HOST.FakeAdb(dump_override=large);record={};calls=[]
        guard=G.ControlledImeGuard(adb=fake,identity=HOST.identity(),record=record,nonce='e'*32,clock=Clock())
        with self.assertRaises(ValueError):guard.run(lambda:calls.append(1))
        self.assertEqual(calls,[])
        self.assertEqual(fake.mutations,[])
        self.assertNotIn(GBOARD,json.dumps(record))
        self.assertEqual(G.service_api_key_findings(json.dumps(record)),[])


class DiagnosticPublicationPrivacyTest(unittest.TestCase):
    def test_actual_publisher_scanner_rejects_unknown_key_before_git_index(self):
        scanner=publisher_scanner()['scan_public_diagnostics']
        tree=ast.parse((ROOT/'tools/gecko/publish_ci.py').read_text())
        scans=[node for node in ast.walk(tree) if isinstance(node,ast.Call)
               and isinstance(node.func,ast.Name) and node.func.id=='scan_public_diagnostics']
        pushes=[node for node in ast.walk(tree) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Name) and node.func.id=='push_tree']
        writes=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call) or not node.args or not isinstance(node.args[0],ast.List):continue
            parts=node.args[0].elts
            if len(parts)>=2 and all(isinstance(value,ast.Constant) for value in parts[:2]) and parts[0].value=='git' and parts[1].value in ('read-tree','add','write-tree'):
                writes.append(node)
        self.assertEqual(len(scans),1);self.assertEqual(len(pushes),1)
        self.assertTrue(writes)
        self.assertLess(scans[0].lineno,min(node.lineno for node in writes))
        self.assertLess(scans[0].lineno,pushes[0].lineno)
        with tempfile.TemporaryDirectory(prefix='privacy-publisher-host-') as temporary:
            root=Path(temporary);(root/'nested').mkdir()
            path=root/'nested/unfiltered.raw'
            path.write_bytes(b'\xffunrecognized-setting='+UNKNOWN.encode())
            with self.assertRaises(ValueError) as error:scanner(root)
            message=str(error.exception)
            self.assertIn(path.name,message)
            self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(),message)
            self.assertNotIn(UNKNOWN,message)
            path.write_text('controlled diagnostic only')
            (root/'native.apk.part00').write_bytes(b'\xff'+UNKNOWN.encode())
            (root/'capture.png').write_bytes(b'\xff'+UNKNOWN.encode())
            scanner(root)
        with self.subTest(missing_local_capture_privacy_dependency=True):
            from profile_publish_bounded_history_test import BoundedPublisherTest, REF
            case=BoundedPublisherTest('test_first_publication_has_only_source_parent_and_never_fetches_artifact_history')
            try:
                case.setUp()
                case.prepare(history=False)
                module=case.client/'tools/gecko/caret_ime_guard.py'
                self.assertTrue(module.is_file())
                module.unlink()
                case.environment.pop('PYTHONPATH',None)
                case.environment['PYTHONNOUSERSITE']='1'
                result=case.publish()
                self.assertNotEqual(result.returncode,0)
                self.assertIn('ModuleNotFoundError',result.stderr)
                self.assertIn("No module named 'caret_ime_guard'",result.stderr)
                self.assertEqual(case.commands(),[])
                self.assertNotEqual(case.remote_git('show-ref','--verify',REF,check=False).returncode,0)
                self.assertFalse(any('push' in row or 'commit-tree' in row for row in case.commands()))
            finally:
                case.doCleanups()

    def test_actual_bundle_pack_rejects_unfiltered_text_before_hash_or_archive(self):
        bundle=load_bundle()
        current=dict(sourceCommit='a'*40,sourceTree='b'*40,runId='1',runAttempt='1')
        with tempfile.TemporaryDirectory(prefix='privacy-pack-host-') as temporary:
            root=Path(temporary);out=root/bundle.OUT;out.mkdir(parents=True)
            (root/bundle.BUILD_INDEX).write_text(json.dumps(dict(kind='build',**current,files=[])))
            (out/'unfiltered.json').write_text(json.dumps({'unrecognized':UNKNOWN}))
            target=root/'not-created.tar.gz'
            with patch.object(bundle,'identity',return_value=current),patch.object(bundle,'digest') as hashed,patch.object(bundle.tarfile,'open') as archive:
                with self.assertRaises(ValueError) as error:bundle.pack(root,target,'phase','editing')
                hashed.assert_not_called();archive.assert_not_called()
            self.assertNotIn(UNKNOWN,str(error.exception))
            self.assertFalse(target.exists())

    def test_bundle_binary_bytes_and_pom_text_classification_stay_explicit(self):
        bundle=load_bundle();publisher=publisher_scanner()
        self.assertEqual(bundle.DIAGNOSTIC_TEXT_SUFFIXES,publisher['DIAGNOSTIC_TEXT_SUFFIXES'])
        with tempfile.TemporaryDirectory(prefix='privacy-binary-host-') as temporary:
            root=Path(temporary)
            for name in ('runtime.apk','native.aar','classes.jar','capture.png','apk.part00'):
                path=root/name;path.write_bytes(b'\xff'+UNKNOWN.encode())
                bundle.scan_diagnostic_capture(path)
            pom=root/'dependency.pom';pom.write_text('<project><key>'+UNKNOWN+'</key></project>')
            with self.assertRaises(ValueError):bundle.scan_diagnostic_capture(pom)

    def test_exact_raw_manifest_projection_scans_keys_but_preserves_opaque_bytes(self):
        bundle=load_bundle()
        with tempfile.TemporaryDirectory(prefix='privacy-raw-manifest-host-') as temporary:
            root=Path(temporary)
            for directory in sorted(bundle.NETWORK_IDENTITY_RAW_DIRS):
                path=root/directory/'manifest.json';path.parent.mkdir()
                original=b'controlled opaque bytes\r\n\x00\xff'
                path.write_bytes(original)
                bundle.scan_diagnostic_capture(path)
                self.assertEqual(path.read_bytes(),original)
                unsafe=b'\xffunrecognized-setting='+UNKNOWN.encode()
                path.write_bytes(unsafe)
                with self.assertRaises(ValueError) as error:bundle.scan_diagnostic_capture(path)
                self.assertIn(hashlib.sha256(unsafe).hexdigest(),str(error.exception))
                self.assertNotIn(UNKNOWN,str(error.exception))
                self.assertEqual(path.read_bytes(),unsafe)
            ordinary=root/'ordinary.json';ordinary.write_bytes(b'\xffstructured data')
            with self.assertRaises(ValueError):bundle.scan_diagnostic_capture(ordinary)

    def test_publication_additions_inverse_to_exact_original_functional_code(self):
        def original(path):
            result=subprocess.run(['git','show',BASE+':'+path],cwd=ROOT,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0)
            return result.stdout.decode()
        bundle_path='tools/gecko/ci_bundle.py'
        old=functions(original(bundle_path));new=functions((ROOT/bundle_path).read_text())
        self.assertEqual(new['allowed'],old['allowed'])
        self.assertEqual(new['restore'],old['restore'])
        pack=new['pack']
        first='        scan_diagnostic_capture(path)\n'
        second="    _privacy.assert_public_diagnostic_text(Path('_ci_bundle.json'), raw)\n"
        self.assertEqual(pack.count(first),1);self.assertEqual(pack.count(second),1)
        self.assertEqual(pack.replace(first,'',1).replace(second,'',1),old['pack'])
        path='tools/gecko/publish_ci.py'
        tree=ast.parse((ROOT/path).read_text());kept=[];removed=0
        for node in tree.body:
            remove=(isinstance(node,ast.ImportFrom) and node.module=='caret_ime_guard')
            remove|=isinstance(node,ast.FunctionDef) and node.name=='scan_public_diagnostics'
            remove|=isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DIAGNOSTIC_TEXT_SUFFIXES' for x in node.targets)
            remove|=isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='scan_public_diagnostics'
            remove|=(isinstance(node,ast.For) and isinstance(node.iter,ast.Tuple)
                     and all(isinstance(x,ast.Constant) for x in node.iter.elts)
                     and tuple(x.value for x in node.iter.elts)==('gecko-performance-capture-privacy.json','preconnect-capture-privacy.json'))
            if remove:removed+=1
            else:kept.append(node)
        self.assertEqual(removed,5)
        self.assertEqual(ast.dump(ast.Module(body=kept,type_ignores=[])),ast.dump(ast.parse(original(path))))


if __name__ == '__main__':
    unittest.main()
