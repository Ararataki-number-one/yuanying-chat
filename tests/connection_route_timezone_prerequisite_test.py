"""Actual route-fixture setup and shared prerequisite with explicit JVM boundaries.

This does not execute Android, Gecko, a native timezone call or a network route.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / 'tests/gecko/NetworkSourcesRouteIntegrationActivity.java'
POOL = ROOT / 'tests/gecko/GeckoConnectionPoolIntegrationActivity.java'
TEMPLATE = ROOT / 'tests/connection-route-timezone-host/RoutePrerequisiteHost.java.in'
J = ROOT / 'app/src/main/java/local/pocketchat/J.java'
# This file is byte-identical in C0F and 1a06. C0F is already restored by the
# mandatory baseline preparation, including on a fresh shallow CI checkout.
BEFORE = 'c0f04eb7cc328a97d7a79210f2bf6a1166123ae5'
BEFORE_SHA = '578f0871db1b269dd080cef58cd68e506980a822a7f770ad5e1e6ede6ff682a6'
FIELD = '  final GeckoConnectionPoolIntegrationActivity.NativeTimeZonePrerequisite nativeTimeZonePrerequisite=new GeckoConnectionPoolIntegrationActivity.NativeTimeZonePrerequisite();\n'
TERM = '&&nativeTimeZonePrerequisite.readyFor(view)'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def member(text, marker):
    if text.count(marker) != 1:
        raise ValueError('Unique actual member required: ' + marker)
    start = text.index(marker)
    at = text.index('{', start)
    depth = 1
    end = at + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def setup(text):
    start = text.index('      await("Official Gecko and actual default network"')
    end = text.index('\n      await("Protected real H2 page"', start)
    return text[start:end]


class ConnectionRouteTimezonePrerequisiteTest(unittest.TestCase):
    def test_only_two_declared_setup_changes_preserve_the_complete_prior_fixture(self):
        before = subprocess.check_output(['git', 'show', BEFORE + ':' + str(ROUTE.relative_to(ROOT))], cwd=ROOT)
        self.assertEqual(sha(before), BEFORE_SHA)
        current = ROUTE.read_text()
        self.assertEqual(current.count(FIELD), 1)
        self.assertEqual(current.count(TERM), 1)
        restored = current.replace(FIELD, '', 1).replace(TERM, '', 1).encode()
        self.assertEqual(restored, before)
        prior = setup(before.decode())
        self.assertEqual(setup(current).replace(TERM, '', 1), prior)
        self.assertIn(',60000);', prior)
        self.assertIn('after.optString("queued").isEmpty()&&after.optLong("epoch",-1)==before.optLong("epoch")', prior)

    def test_actual_startup_predicate_and_shared_typed_proof_control_dispatch(self):
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        self.assertTrue(java.is_file(), 'A real JDK is required')
        inputs = [ROUTE, POOL, TEMPLATE, J, Path(__file__).resolve()]
        hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in inputs}
        route, pool = ROUTE.read_text(), POOL.read_text()
        helper = member(pool, 'static final class NativeTimeZonePrerequisite')
        settled = member(pool, 'static boolean startupSettled(')
        original = setup(route)
        variants = [
            ('current', original, helper, None),
            ('old-missing-prerequisite', original.replace(TERM, '', 1), helper,
             'One controlled subscribed document load is dispatched without protection or connection queueing'),
            ('untyped-native-readback', original,
             helper.replace('Boolean.TRUE.equals(status.opt("nativeSettingReadback"))&&', 'true&&', 1),
             'Setup cannot dispatch without its exact typed native confirmation: missing'),
            ('replaced-native-gate', original,
             helper.replace('(gate==null||view.timeZoneGates.get(expected)==gate)', 'true', 1),
             'Setup cannot dispatch without its exact typed native confirmation: replaced-gate'),
        ]
        reports, controls = [], []
        for label, variable, default in [('desktop', 'PROFILE_JSON_JAR', 'json.jar'),
                                          ('android-json', 'PROFILE_ANDROID_JSON_JAR', 'android-json.jar')]:
            jar = Path(os.environ.get(variable, ROOT / 'work/profile-host' / default))
            self.assertTrue(jar.is_file())
            for name, actual_setup, actual_helper, assertion in variants:
                text = TEMPLATE.read_text().replace('@@FIELD@@', FIELD.strip()).replace('@@SETUP@@', actual_setup).replace('@@HELPER@@', actual_helper).replace('@@SETTLED@@', settled)
                with tempfile.TemporaryDirectory(prefix='route-native-prerequisite-') as temporary:
                    folder = Path(temporary)
                    source, classes = folder / 'RoutePrerequisiteHost.java', folder / 'classes'
                    source.write_text(text)
                    compiled = subprocess.run([str(java), '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(classes), str(source), str(J)], capture_output=True, text=True, timeout=35)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    ran = subprocess.run([str(java), '-cp', str(classes) + os.pathsep + str(jar), 'local.pocketchat.RoutePrerequisiteHost'], capture_output=True, text=True, timeout=20)
                    if assertion is not None:
                        self.assertNotEqual(ran.returncode, 0, 'Removed actual boundary was accepted: ' + name)
                        self.assertIn('java.lang.AssertionError: ' + assertion, ran.stderr)
                        controls.append(dict(json=label, variant=name, compileSucceeded=True, runtimeRejected=True, assertion=assertion, generatedSourceSha256=sha(text.encode())))
                    else:
                        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                        reports.append(dict(json=label, jsonJarSha256=sha(jar.read_bytes()), generatedSourceSha256=sha(text.encode()), report=json.loads(ran.stdout)))
        stable = all(sha(path.read_bytes()) == hashes[str(path.relative_to(ROOT))] for path in inputs)
        self.assertTrue(stable)
        report = dict(schema=1, status='passed', sourceFiles=hashes, executionInputsUnchanged=stable,
                      runs=reports, mutationControls=controls, priorFixtureSha256=BEFORE_SHA,
                      actualAndroidExecution=False, actualGeckoExecution=False, actualNativeReadback=False,
                      scope='Exact current subscribed-route setup statements, unchanged original load assertions, shared native prerequisite class and startupSettled predicate. Explicit session/runtime/native-callback/route/template/queue boundaries; actual Gecko load/prepare semantics are independently covered by timezone-routing-host. No SDK, Android, route, HTTP or native timezone operation executes here.')
        out = Path(os.environ.get('CONNECTION_ROUTE_TIMEZONE_REPORT', ROOT / 'work/connection-route-timezone-prerequisite/results.json'))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
