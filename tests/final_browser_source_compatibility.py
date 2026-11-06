"""Finite historical metadata inputs for the combined browser candidate.

Only retained source-metadata consumers call this module. Actual behavior tests,
hosts, publishing tools and browser code always execute current source bytes.
The current Gecko image is checked whole, then the actual TLS and canonical CPU
inverses restore B8 before the unchanged IP layer applies its seven old rows.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
B = 'e20667d7e407e28645a59617683211fdd1345039'
B_TREE = '744dbee43dd4721a026f391b8874c3b7c72d9634'
S = 'e4a20469326f16dc8ff8cfabd4fe67bf3d0148de'
S_TREE = 'cdbe45cb204a655781f4719598ec3d7e88735a6a'
GV = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
CHAT = 'app/src/main/java/local/pocketchat/ChatSession.java'
IP = '972b7767300587af98b3f4a2088a44dd30af8098'
IP_TREE = '7da3a44c2b9c1f2d85623ac908a23154144ea045'
CPU_FIXTURE = 'tests/fixtures/cpu-ip-source-deltas.json'
DELTA_PATH = ROOT / 'tests/fixtures/final-browser-source-deltas.json'
DELTA_SHA256 = '8bb0bb6580879fcef6258f48e57fbdce19304c0d3ea0061131d993b815877a16'
P2_PREVIOUS_SHA256 = '98c648b06ef28cd35e01ea0ad8128258d3f171706cc3ef23087bd102f545a510'
P2_PREVIOUS_BYTES = 128741
P2_CONTEXT_ID = 'context-08'
# BEGIN_BUILD_BUDGET_METADATA
BUILD_BUDGET_PATH = 'tests/browser_acceptance_workflow_test.py'
BUILD_BUDGET_PREVIOUS_SHA256 = '2792c0919de89b13eb9040660be96f7c3ba55cf689e54abd075646f103e479bf'
BUILD_BUDGET_PREVIOUS_BYTES = 7205
BUILD_BUDGET_CURRENT_SHA256 = '655d7a4a385aa9d0d6684807a177035ee177a8470eb396a6f7da3efe0759db71'
BUILD_BUDGET_CURRENT_BYTES = 7668
BUILD_BUDGET_PREVIOUS = b"        for name,job in self.old['jobs'].items():\n            with self.subTest(job=name):\n                current=self.new['jobs'][name];position=0\n                for step in job['steps']:\n                    found=next((at for at in range(position,len(current['steps'])) if current['steps'][at]==step),None)\n                    self.assertIsNotNone(found,(name,step.get('name')));position=found+1\n                for key,value in job.items():\n                    if key=='steps':continue\n                    self.assertEqual(current[key],value+['browser','tls'] if name=='verify' and key=='needs' else value)\n    def test_single_pipeline_shares_actual_apk_and_gates_browser(self):\n        self.assertEqual(self.new['on']['push']['branches'],['release/browser-2.1.0','release/browser-2.1.0-*','release/browser-2.1.1','release/browser-2.1.1-*','release/browser-2.1.2','release/browser-2.1.2-*','release/browser-2.1.3','release/browser-2.1.3-*','release/browser-2.1.4','release/browser-2.1.4-*'])\n        self.assertIn('browser',self.new['jobs']['verify']['needs'])\n        self.assertEqual(self.new['jobs']['browser']['needs'],'build')\n        browser=self.new['jobs']['browser'];self.assertNotIn('continue-on-error',browser)\n        body='\\n'.join(step.get('run','') for step in browser['steps'])\n"
BUILD_BUDGET_CURRENT = b"        for name,job in self.old['jobs'].items():\n            with self.subTest(job=name):\n                current=self.new['jobs'][name];position=0\n                for step in job['steps']:\n                    found=next((at for at in range(position,len(current['steps'])) if current['steps'][at]==step),None)\n                    self.assertIsNotNone(found,(name,step.get('name')));position=found+1\n                if name=='build':\n                    self.assertIn('timeout-minutes',job)\n                for key,value in job.items():\n                    if key=='steps':continue\n                    if name=='build' and key=='timeout-minutes':\n                        self.assertIs(type(value),int)\n                        self.assertEqual(value,40)\n                        self.assertIn(key,current)\n                        self.assertIs(type(current[key]),int)\n                        self.assertEqual(current[key],60)\n                    else:\n                        self.assertEqual(current[key],value+['browser','tls'] if name=='verify' and key=='needs' else value)\n    def test_single_pipeline_shares_actual_apk_and_gates_browser(self):\n        self.assertEqual(self.new['on']['push']['branches'],['release/browser-2.1.0','release/browser-2.1.0-*','release/browser-2.1.1','release/browser-2.1.1-*','release/browser-2.1.2','release/browser-2.1.2-*','release/browser-2.1.3','release/browser-2.1.3-*','release/browser-2.1.4','release/browser-2.1.4-*'])\n        self.assertIn('browser',self.new['jobs']['verify']['needs'])\n        self.assertEqual(self.new['jobs']['browser']['needs'],'build')\n        browser=self.new['jobs']['browser'];self.assertNotIn('continue-on-error',browser)\n        body='\\n'.join(step.get('run','') for step in browser['steps'])\n"
# END_BUILD_BUDGET_METADATA
MAX_FIXTURE_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024
MAX_METADATA_BYTES = 4 * 1024 * 1024
PROVENANCE = {
    GV: (B, B_TREE),
    'tests/ip_timezone_source_compatibility.py': (B, B_TREE),
    'tests/profile_ip_timezone_source_compatibility_test.py': (B, B_TREE),
    'tests/baselines/public-source-history.json': (B, B_TREE),
    'tools/browser/source_history.py': (B, B_TREE),
    'tests/cpu_ip_source_compatibility.py': (S, S_TREE),
    CPU_FIXTURE: (S, S_TREE),
    'tests/profile_cpu_ip_source_compatibility_test.py': (S, S_TREE),
    'tests/browser_acceptance_workflow_test.py': (S, S_TREE),
    'tests/gecko-addon-lifecycle-host/AddonHost.java.in': (S, S_TREE),
    'tests/gecko-addon-lifecycle-host/run.py': (S, S_TREE),
    'tests/worker_timezone_host_source_compatibility.py': (S, S_TREE),
    'tests/profile_worker_timezone_host_source_compatibility_test.py': (S, S_TREE),
    CHAT: (IP, IP_TREE),
    'tests/worker_timezone_source_compatibility.py': (S, S_TREE),
    'tests/profile_worker_timezone_source_compatibility_test.py': (S, S_TREE),
    'tests/profile_dual_browser_source_compatibility_test.py': (S, S_TREE),
    'tests/browser_fingerprint_publish_gate_test.py': (S, S_TREE),
    'tests/browser_environment_publish_gate_test.py': (S, S_TREE),
}
PATHS = frozenset(PROVENANCE)
IP_PATHS = frozenset((GV, 'tests/profile_native_protection_test.py',
    'tests/phase1_context_fix_source_compatibility.py',
    'tests/worker_timezone_host_source_compatibility.py',
    'tests/profile_phase1_context_fix_source_compatibility_test.py',
    'tests/profile_worker_timezone_host_source_compatibility_test.py',
    'tests/profile_page_bridge_budget_source_compatibility_test.py'))
TEMPLATE_PATHS = frozenset(('tests/native-protection-host/NativeProtectionControllerHost.java.in',
    'tests/native-runtime-capabilities-host/NativeRuntimeCapabilitiesHost.java'))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate final historical fixture metadata')
        value[key] = item
    return value


def _constant(value):
    raise ValueError('Non-finite final historical fixture value')


def manifest():
    expected = ROOT / 'tests/fixtures/final-browser-source-deltas.json'
    if DELTA_PATH != expected or DELTA_PATH.is_symlink() or not DELTA_PATH.is_file() or DELTA_PATH.resolve() != expected.absolute():
        raise ValueError('Final browser fixture requires the exact ordinary source path')
    if not 0 < DELTA_PATH.stat().st_size <= MAX_FIXTURE_BYTES:
        raise ValueError('Final browser historical fixture bound')
    return _decode(DELTA_PATH.read_bytes())


def _decode(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_FIXTURE_BYTES or _sha(raw) != DELTA_SHA256:
        raise ValueError('Final browser historical fixture is not the reviewed whole bytes')
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_constant)
    if (type(value) is not dict or set(value) != {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance', 'files'}
            or type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('kind') != 'final-browser-historical-source-input-only'
            or value.get('actualAndroidExecution') is not False or value.get('runtimeAcceptance') is not False
            or type(value.get('files')) is not dict or set(value['files']) != PATHS or len(PATHS) != 19):
        raise ValueError('Final browser historical fixture identity differs')
    total = 0
    for relative, row in value['files'].items():
        if (type(row) is not dict or set(row) != {'previousCommit', 'previousTree', 'previousSha256', 'previousBytes', 'reviewedSha256', 'reviewedBytes', 'contextLines', 'deltas'}
                or (row.get('previousCommit'), row.get('previousTree')) != PROVENANCE[relative]
                or any(type(row.get(k)) is not int or not 0 < row[k] <= MAX_SOURCE_BYTES for k in ('previousBytes', 'reviewedBytes'))
                or any(type(row.get(k)) is not str or re.fullmatch('[0-9a-f]{64}', row[k]) is None for k in ('previousSha256', 'reviewedSha256'))
                or row['previousSha256'] == row['reviewedSha256']
                or type(row.get('contextLines')) is not int or not 3 <= row['contextLines'] <= 16
                or type(row.get('deltas')) is not list or not 0 < len(row['deltas']) <= 64):
            raise ValueError('Final browser historical row is not exact and bounded')
        total += len(row['deltas'])
        for index, delta in enumerate(row['deltas']):
            if (type(delta) is not dict or set(delta) != {'id', 'previous', 'current', 'previousSha256', 'currentSha256'}
                    or delta.get('id') != 'context-%02d' % index
                    or any(type(delta.get(k)) is not str or not 0 < len(delta[k].encode('utf-8')) <= 32 * 1024
                           or _sha(delta[k].encode('utf-8')) != delta.get(k+'Sha256') for k in ('previous', 'current'))
                    or delta['previous'] == delta['current']):
                raise ValueError('Final browser historical contextual edit differs')
    if not 0 < total <= 256:
        raise ValueError('Final browser historical contexts exceed the finite scope')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        raise ValueError('Final browser inverse requires exact complete bytes and an owned relative path')
    row = manifest()['files'][relative]
    digest = _sha(raw)
    if (relative == BUILD_BUDGET_PATH and (digest, len(raw)) not in
            ((row['previousSha256'], row['previousBytes']), (row['reviewedSha256'], row['reviewedBytes']))):
        raw = build_budget_input(raw, relative)
        digest = _sha(raw)
    if (digest, len(raw)) == (row['previousSha256'], row['previousBytes']):
        return raw
    if (digest, len(raw)) != (row['reviewedSha256'], row['reviewedBytes']):
        raise ValueError('Final browser inverse rejects unknown whole source bytes')
    layered = None
    if relative in (GV, CHAT):
        from tls_cpu_ip_source_compatibility import source_input as tls_input
        from cpu_ip_source_compatibility import source_input as cpu_input
        layered = cpu_input(tls_input(p2_input(raw, relative), relative), relative)
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if raw.count(current) != 1:
            raise ValueError('Final browser inverse requires each contextual edit exactly once')
        raw = raw.replace(current, previous, 1)
    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:
        raise ValueError('Final browser inverse did not restore the complete public predecessor')
    if layered is not None:
        if layered != raw:
            raise ValueError('Final browser TLS and canonical CPU inverse did not restore B8')
        return layered
    return raw


def _metadata_path(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or len(raw) > MAX_METADATA_BYTES:
        raise ValueError('Final historical metadata requires bounded bytes and a relative string')
    path = PurePosixPath(relative)
    if (not relative or str(path) != relative or path.is_absolute() or len(path.parts) < 2 or '..' in path.parts
            or '\\' in relative or '\0' in relative or path.parts[0] not in ('app', 'tests', 'tools', '.github')):
        raise ValueError('Final historical metadata path is not canonical')


def build_budget_input(raw, relative):
    """Exact metadata bytes for the approved40-to60 build-envelope guard only."""
    _metadata_path(raw, relative)
    if relative != BUILD_BUDGET_PATH:
        return raw
    digest = (_sha(raw), len(raw))
    if digest == (BUILD_BUDGET_PREVIOUS_SHA256, BUILD_BUDGET_PREVIOUS_BYTES):
        return raw
    if digest != (BUILD_BUDGET_CURRENT_SHA256, BUILD_BUDGET_CURRENT_BYTES):
        raise ValueError('Build budget metadata rejects unknown complete test source')
    if raw.count(BUILD_BUDGET_CURRENT) != 1:
        raise ValueError('Build budget metadata requires the unique approved guard context')
    restored = raw.replace(BUILD_BUDGET_CURRENT, BUILD_BUDGET_PREVIOUS, 1)
    if (_sha(restored), len(restored)) != (BUILD_BUDGET_PREVIOUS_SHA256, BUILD_BUDGET_PREVIOUS_BYTES):
        raise ValueError('Build budget metadata did not restore the exact frozen test')
    return restored


def p2_input(raw, relative):
    """Only the exact P2 Gecko image can restore the frozen TLS left input."""
    _metadata_path(raw, relative)
    if relative != GV:
        return raw
    digest = (_sha(raw), len(raw))
    if digest == (P2_PREVIOUS_SHA256, P2_PREVIOUS_BYTES):
        return raw
    row = manifest()['files'][GV]
    if digest != (row['reviewedSha256'], row['reviewedBytes']):
        raise ValueError('P2 metadata input rejects unknown whole Gecko bytes')
    delta = row['deltas'][-1]
    if delta['id'] != P2_CONTEXT_ID:
        raise ValueError('P2 metadata input requires its final declared context')
    current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
    if raw.count(current) != 1:
        raise ValueError('P2 metadata input requires its exact contextual edit once')
    restored = raw.replace(current, previous, 1)
    if (_sha(restored), len(restored)) != (P2_PREVIOUS_SHA256, P2_PREVIOUS_BYTES):
        raise ValueError('P2 metadata input did not restore the exact frozen TLS image')
    return restored


def metadata_input(raw, relative):
    """Finite left inputs only; unowned bytes still face the original golden."""
    _metadata_path(raw, relative)
    from profile_fixture_root_source_compatibility import PATHS as fixture_root_paths, source_input as fixture_root_input
    if relative in fixture_root_paths:
        raw = fixture_root_input(raw, relative)
    if relative in PATHS:
        return source_input(raw, relative)
    if relative in TEMPLATE_PATHS:
        from tls_cpu_ip_source_compatibility import source_input as tls_input
        return tls_input(raw, relative)
    return raw


def ip_input(raw, relative):
    """Return B8 only for the final whole Gecko image; keep other old IP bytes."""
    _metadata_path(raw, relative)
    if relative not in IP_PATHS:
        raise ValueError('Final IP historical input path differs')
    return source_input(raw, relative) if relative == GV else raw


def producer_input(raw, relative):
    """Two exact producers only; no other historical or runtime source view."""
    _metadata_path(raw, relative)
    if relative not in (GV, CHAT):
        raise ValueError('Final historical producer input path differs')
    return source_input(raw, relative)


def canonical_cpu_fixture_sha(current_pin):
    """Verify actual canonical bytes before restoring the old metadata digest."""
    import cpu_ip_source_compatibility as cpu
    if type(current_pin) is not str or current_pin != cpu.DELTA_SHA256:
        raise ValueError('Canonical CPU fixture does not match its actual complete pin')
    cpu.manifest()
    raw = cpu.DELTA_PATH.read_bytes()
    if _sha(raw) != current_pin:
        raise ValueError('Canonical CPU fixture changed after ordinary-path validation')
    return _sha(source_input(raw, CPU_FIXTURE))
