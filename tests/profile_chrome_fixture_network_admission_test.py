"""Execute actual fixture/production admission and recovery with explicit JVM edges.

The C5 API 32 Wi-Fi loss remains a failed Android observation. These controls
prove the missing fixture route identity and the narrow prerequisite repair;
they do not emulate a protected Android network or qualify device continuity.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / 'app/src/main/java/local/pocketchat'
FIXTURE = ROOT / 'tests/gecko/ChromeCollapseIntegration.java'
TEMPLATE = ROOT / 'tests/chrome-fixture-network-host/FixtureNetworkHost.java.in'
EXTRACTOR = ROOT / 'tests/gecko-navigation-host/run.py'
spec = importlib.util.spec_from_file_location('fixture_network_java_extractor', EXTRACTOR)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

SESSION_MEMBERS = (
    'long beginNetworkApplication(', 'boolean adoptNetworkApplication(',
    'boolean internalNetwork(', 'String networkIdentity(', 'boolean ownsConnectionPage(',
    'void applyProxy(String proxy,long epoch)', 'void invalidateConnection(',
    'void networkChanged(', 'static long retryDelay(', 'void scheduleRecovery(',
    'void runRecovery(', 'void openConnection(', 'static boolean resumable(',
)
WHOLE_PRODUCTION = ('J.java', 'EnvironmentSpec.java', 'GeckoNavigationPolicy.java',
                    'BrowserAddressPolicy.java', 'BrowserRuntimePolicy.java', 'LoginPagePolicy.java')


def member(source, signature):
    if source.count(signature) != 1:
        raise ValueError('Review actual Java declaration: ' + signature)
    return extractor.member_at(source, source.index(signature))


class ChromeFixtureNetworkAdmissionTests(unittest.TestCase):
    def test_actual_fixture_ready_and_production_network_recovery_with_negative_controls(self):
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        jar = Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar'))
        self.assertTrue(java.is_file() and jar.is_file(), 'Actual JDK and JSON dependency required')
        paths = [FIXTURE, TEMPLATE, EXTRACTOR, Path(__file__).resolve(),
                 PROD / 'ChatSession.java', PROD / 'MainActivity.java', PROD / 'RequestIdentityAudit.java']
        paths += [PROD / name for name in WHOLE_PRODUCTION]
        hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        fixture = FIXTURE.read_text()
        session = (PROD / 'ChatSession.java').read_text()
        actual = {
            'FIXTURE': '\n'.join(member(fixture, sig) for sig in ('boolean admitFixtureNetwork(', 'void ready(long deadline)')),
            'SESSION': '\n'.join(member(session, sig) for sig in SESSION_MEMBERS),
            'ACTIVITY': '\n'.join(member((PROD / 'MainActivity.java').read_text(), sig) for sig in ('static boolean validProxy(', 'static boolean chatUrl(')),
            'DIAGNOSTIC': '\n'.join(member((PROD / 'RequestIdentityAudit.java').read_text(), sig) for sig in ('static boolean namespace(', 'static boolean diagnosticUrl(')),
        }
        # Compile the exact current ready callback as well as its admission helper.
        # A matching-looking standalone helper cannot satisfy these controls if
        # the Android fixture forgets to invoke it before the actual receipt.
        mutations = [
            ('missing-admission', 'FIXTURE', 'if(!admitFixtureNetwork())', 'if(false)', 'readiness', 'actual ready callback admits before creating the retention task'),
            ('fake-admission', 'FIXTURE', 'return a.session.adoptNetworkApplication(lease,null);', 'return true;', 'admission', 'admission records the actual external proxy identity'),
            ('foreign-document', 'FIXTURE', '!TARGET.equals(current.getUrl())||', '', 'admission', 'foreign document or unprepared route rejected: virtual'),
            ('wrong-owner', 'SESSION', 'expected.generation!=environmentGeneration||', '', 'admission', 'wrong actual owner rejected: generation'),
            ('unprotected-adoption', 'SESSION', '||!web.protectionAllowsNetwork()', '', 'admission', 'original production adoption guard rejects: protection'),
            ('retention-without-identity', 'SESSION', 'keepPageCandidate&&sameIdentity&&', 'keepPageCandidate&&', 'recovery', 'original missing applied identity actually dispatches replacement navigation'),
            ('suppressed-network-stop', 'SESSION', '    web.stopLoading();', '    /* removed original stop */', 'recovery', 'actual network switch still stops and blocks the route: false'),
            ('premature-ready', 'FIXTURE', '||!a.remote.protectionAllowsNetwork()', '', 'readiness', 'original bounded readiness polling remains 100 ms: protection'),
        ]
        with tempfile.TemporaryDirectory(prefix='chrome-fixture-network-') as temporary:
            base = Path(temporary)

            def execute(name, bodies, focus='all'):
                folder = base / name
                folder.mkdir()
                text = TEMPLATE.read_text()
                for key, value in bodies.items():
                    self.assertEqual(text.count('@' + key + '_MEMBERS@'), 1)
                    text = text.replace('@' + key + '_MEMBERS@', value)
                source = folder / 'FixtureNetworkHost.java'
                source.write_text(text)
                command = [str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                           '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(folder), str(source)]
                command += [str(PROD / name) for name in WHOLE_PRODUCTION]
                compiled = subprocess.run(command, capture_output=True, text=True, timeout=35)
                self.assertEqual(compiled.returncode, 0, name + '\n' + compiled.stdout + compiled.stderr)
                return subprocess.run([str(java), '-cp', str(folder) + os.pathsep + str(jar),
                                       'local.pocketchat.FixtureNetworkHost', focus], capture_output=True,
                                      text=True, timeout=15)

            current = execute('current', actual)
            self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
            receipt = json.loads(current.stdout)
            self.assertEqual(receipt['status'], 'passed')
            self.assertGreaterEqual(receipt['checks'], 80)
            controls = []
            for name, owner, before, after, focus, expected in mutations:
                with self.subTest(mutation=name):
                    self.assertEqual(actual[owner].count(before), 1, name)
                    changed = dict(actual)
                    changed[owner] = changed[owner].replace(before, after, 1)
                    result = execute(name, changed, focus)
                    self.assertNotEqual(result.returncode, 0, name + ' was accepted')
                    self.assertIn(expected, result.stderr)
                    controls.append({'name': name, 'compiled': True, 'rejectedAt': expected})
        self.assertTrue(all(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[str(path.relative_to(ROOT))] for path in paths))
        output = ROOT / 'work/chrome-fixture-network/host-results.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            'schema': 1, 'status': 'passed', 'checks': receipt['checks'], 'controls': controls,
            'sourceFiles': hashes, 'executionInputsUnchanged': True,
            'actualAndroidExecution': False, 'actualGeckoExecution': False, 'nativeReadbackVerified': False,
            'selectedSessionMembers': list(SESSION_MEMBERS),
            'scope': 'Verbatim current Java fixture ready/admission and production lease/recovery/proxy members; full environment identity and address/runtime/login policies. Explicit catalogue, preferences, SDK document/protection, Handler, native core, navigation-dispatch, file-import, observer and diagnostic-probe boundaries. Original missing-identity baseline dispatches navigation; same admitted route preserves it while real network invalidation still stops. No Android, SDK, actual network, native privacy or measured document-continuity acceptance.',
        }, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
