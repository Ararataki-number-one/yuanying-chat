"""Synthetic projector/whole-workflow controls, never emulator acceptance."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import native_setup11_workflow_contract as contract

ROOT = Path(__file__).resolve().parents[1]
EMITTER = ROOT / 'tests/gecko/print_native_setup11_diagnostic.py'
WORKFLOW = ROOT / '.github/workflows/gecko-integration.yml'
NORMALIZERS = ROOT / 'tests/profile_display_sampling_gate_test.py'
FRONTEND = ROOT / 'tests/gecko/source11_targeted_generator_compat.py'
TARGETED_TEST = ROOT / 'tests/gecko_experience_targeted_workflow_test.py'
REBINDING = b'from native_setup11_workflow_contract import wrap_history_inverse as _native_setup11_wrap_history_inverse\nreverse_reviewed_history_checkout_addition = _native_setup11_wrap_history_inverse(reverse_reviewed_history_checkout_addition)\n\n'
spec = importlib.util.spec_from_file_location('native_setup11_projector', EMITTER)
emitter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emitter)
SOURCE, TREE = 'a' * 40, 'b' * 40


def environment():
    return dict(GITHUB_SHA=SOURCE, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_JOB='android',
                POCKET_NATIVE_SETUP_PHASE='editing', POCKET_NATIVE_SETUP_BOOT_OUTCOME='failure')


def identity():
    return emitter.identity_from_environment(environment(), SOURCE, TREE)


def record():
    return dict(schema=1, status='failed', sourceCommit=SOURCE, sourceTree=TREE, runId='123', runAttempt='1',
                failureType='TimeoutError', preparationBudgetSeconds=45, endpointDeadlineSeconds=8,
                endpointProtocolReachable=False, nativeReady=False, confirmedQemu=True,
                actualAndroidCommands=True, actualIntegrationProviderExecution=True,
                actualConnectivityManagerExecution=True, applicationOrInputPolicyModified=False,
                originalWorkloadInvoked=False, normalPreflightStillRequired=True,
                tcpipCommand=dict(invocations=1, exitCode=0, timedOut=False, elapsedMs=12.5),
                nativeWifiPathPreparation=dict(status='passed', repairAttempted=False, repairAttempts=0,
                                               observations=[{}, {}]),
                endpointProbeAttempts=[dict(tcpAccepted=True, payloadRead=False, authResponseSent=False,
                                           applicationCommandsSent=False, elapsedMs=1000, errorType='TimeoutError')
                                       for _ in range(18)])


def encoded(value):
    return json.dumps(value, separators=(',', ':')).encode()


class NativeSetupDiagnostic11Tests(unittest.TestCase):
    def test_single_addition_whole_inverse_keeps_every_old_function_body_and_golden(self):
        current = WORKFLOW.read_bytes()
        self.assertEqual(hashlib.sha256(current).hexdigest(), contract.CURRENT_SHA256)
        old = contract.restore_previous_workflow(current)
        self.assertEqual(hashlib.sha256(old).hexdigest(), contract.PREVIOUS_SHA256)
        self.assertEqual(old.replace(contract.BEFORE + contract.AFTER,
                                     contract.BEFORE + contract.STEP + contract.AFTER, 1), current)
        self.assertEqual(current.count(contract.STEP), 1)
        raw = NORMALIZERS.read_bytes()
        self.assertEqual(raw.count(REBINDING), 1)
        previous = raw.replace(REBINDING, b'', 1)
        self.assertEqual(hashlib.sha256(previous).hexdigest(),
                         'a461ce63d1c70e679507a6c881ca6c22c6c69ff000e849ed556863c417438a36')
        def functions(source):
            text = source.decode()
            return {(n.name, n.lineno): ast.get_source_segment(text, n)
                    for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef)}
        self.assertEqual(sorted(functions(raw).values()), sorted(functions(previous).values()))
        from profile_display_sampling_gate_test import reverse_reviewed_history_checkout_addition
        self.assertTrue(hasattr(reverse_reviewed_history_checkout_addition, '__wrapped__'))
        result = reverse_reviewed_history_checkout_addition(self, current.decode())
        self.assertEqual(hashlib.sha256(result.encode()).hexdigest(),
                         '10e35f9884e6eac2ea2fc2e0e6d6f6d5d14c55dc7e776cd0128019c75ab3f2f5')

    def test_missing_duplicate_relocated_changed_step_and_old_workload_changes_are_rejected(self):
        current = WORKFLOW.read_bytes()
        removed = current.replace(contract.STEP, b'', 1)
        # The exact old SOURCE10 bytes are deliberately accepted unchanged.
        self.assertEqual(contract.restore_previous_workflow(removed), removed)
        invalid = [current.replace(contract.STEP, contract.STEP * 2, 1),
                   removed + contract.STEP, current.replace(contract.STEP, contract.STEP.replace(b'if: always()', b'if: success()'), 1),
                   current.replace(contract.STEP, contract.STEP.replace(b'print_native_setup11', b'print_changed_setup11'), 1),
                   removed + b' ', current + b'\n', b'unknown workflow']
        for before, after in [(b'timeout 180 adb', b'timeout 181 adb'),
                              (b' -cores 4 ', b' -cores 2 '),
                              (b'checks_failed=1', b'checks_failed=0'),
                              (b"sample: ['1', '2']", b"sample: ['1', '2', '3']")]:
            self.assertIn(before, current)
            invalid.append(current.replace(before, after, 1))
        for raw in invalid:
            with self.subTest(sha256=hashlib.sha256(raw).hexdigest()), self.assertRaises(AssertionError):
                contract.restore_previous_workflow(raw)

    def test_realistic_failed_and_successful_synthetic_setup_projection_is_not_acceptance(self):
        original = record()
        raw = encoded(original)
        value = emitter.project(raw, identity())
        self.assertEqual(value['status'], 'available')
        self.assertEqual(value['setup']['status'], 'failed')
        self.assertEqual(value['setup']['failureType'], 'TimeoutError')
        self.assertEqual(value['input'], dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(value['protocolProbe']['totalCount'], 18)
        self.assertEqual(value['protocolProbe']['selectedCount'], 16)
        self.assertEqual(value['protocolProbe']['omittedCount'], 2)
        self.assertEqual([x['index'] for x in value['protocolProbe']['samples']], list(range(8)) + list(range(10, 18)))
        self.assertEqual(encoded(original), raw)
        for key in ('releaseAcceptance', 'applicationAcceptance', 'actualGeckoExecution', 'physicalPhoneAcceptance'):
            self.assertIs(value[key], False)
        successful = record()
        successful.update(status='passed', endpointProtocolReachable=True, nativeReady=True)
        successful['endpointProbeAttempts'] = [dict(tcpAccepted=True, responseCommand='AUTH', elapsedMs=1)]
        self.assertEqual(emitter.project(encoded(successful), identity())['setup']['status'], 'passed')
        self.assertTrue(value['diagnosticOnly'])

    def test_untrusted_text_payloads_commands_headers_and_environment_never_reach_public_output(self):
        secret = 'PRIVATE_SENTINEL_DO_NOT_PRINT_TOKEN'
        value = record()
        value.update(reason=secret, commands=[secret], stdout=secret, diagnostics={'headers': secret},
                     expectedBuildIdentity={'private': secret}, failureType=secret)
        value['tcpipCommand'].update(command=[secret], stdout=secret, stderr=secret)
        value['nativeWifiPathPreparation']['observations'] = [{'raw': secret}]
        value['endpointProbeAttempts'][0].update(error=secret, errorType=secret, payload=secret,
                                                responseCommand=secret, stdout=secret)
        result = emitter.project(encoded(value), identity())
        output = emitter.render(result)
        self.assertNotIn(secret, output)
        self.assertEqual(result['setup']['failureType'], 'other')
        self.assertNotIn('responseCommand', result['protocolProbe']['samples'][0])
        self.assertEqual(result['protocolProbe']['samples'][0]['errorType'], 'other')
        self.assertTrue(output.startswith(emitter.PREFIX))
        self.assertNotIn('EMULATOR_BACKGROUND_ISOLATION ', output)

    def test_missing_malformed_duplicate_nonfinite_and_foreign_identity_are_unavailable(self):
        values = [b'', b'{', b'[]', b'null', encoded(dict(record(), schema=True)),
                  encoded(dict(record(), sourceCommit='c' * 40)),
                  encoded(dict(record(), runId=123)), encoded(dict(record(), runAttempt='2')),
                  encoded(dict(record(), status='SECRET_UNKNOWN_STATUS')),
                  encoded(record())[:-1] + b',"schema":1}',
                  encoded(record())[:-1] + b',"unknown":NaN}']
        for raw in values:
            with self.subTest(rawSha=hashlib.sha256(raw).hexdigest()):
                result = emitter.project(raw, identity())
                self.assertEqual(result['status'], 'unavailable')
                self.assertIs(result['applicationAcceptance'], False)
        self.assertEqual(emitter.project(encoded(record()), None)['reasonCode'], 'identity-unavailable')
        raw = encoded(record())
        with patch.object(emitter, 'MAX_INPUT_BYTES', 10), \
                patch.object(emitter.hashlib, 'sha256', side_effect=AssertionError('Oversized input must not be hashed')):
            self.assertEqual(emitter.project(raw, identity())['reasonCode'], 'input-bound')
        for field, value in [('GITHUB_SHA', 'changed'), ('GITHUB_JOB', 'build'),
                             ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ATTEMPT', '1\nTOKEN'),
                             ('POCKET_NATIVE_SETUP_PHASE', 'not-a-phase'),
                             ('POCKET_NATIVE_SETUP_BOOT_OUTCOME', 'unknown')]:
            env = environment(); env[field] = value
            self.assertIsNone(emitter.identity_from_environment(env, SOURCE, TREE))

    def test_invalid_primitives_are_omitted_without_coercion_and_missing_is_distinct_from_zero(self):
        value = record()
        value.update(actualAndroidCommands=1, preparationBudgetSeconds=True)
        value['tcpipCommand']['elapsedMs'] = 10 ** 100
        value['endpointProbeAttempts'][0].update(tcpAccepted='true', elapsedMs=-1, payloadBytesAdvertised=True)
        result = emitter.project(encoded(value), identity())
        self.assertNotIn('actualAndroidCommands', result['setup'])
        self.assertNotIn('preparationBudgetSeconds', result['setup'])
        self.assertNotIn('elapsedMs', result['setup']['tcpipCommand'])
        self.assertNotIn('tcpAccepted', result['protocolProbe']['samples'][0])
        missing = record(); missing.pop('endpointProbeAttempts')
        self.assertEqual(emitter.project(encoded(missing), identity())['protocolProbe']['status'], 'unavailable')
        empty = record(); empty['endpointProbeAttempts'] = []
        self.assertEqual(emitter.project(encoded(empty), identity())['protocolProbe']['totalCount'], 0)

    def test_ordinary_bounded_reader_rejects_symlinks_and_does_not_write_original(self):
        with tempfile.TemporaryDirectory(prefix='native-setup11-control-') as directory:
            folder = Path(directory); path = folder/'setup.json'; raw = encoded(record()); path.write_bytes(raw)
            loaded, meta, error = emitter.read_setup(path)
            self.assertIsNone(error); self.assertEqual(loaded, raw)
            self.assertEqual(meta['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)
            link = folder/'symlink.json'; link.symlink_to(path)
            self.assertEqual(emitter.read_setup(link)[2], 'unsafe-input')
            parent = folder/'linked'; parent.symlink_to(folder, target_is_directory=True)
            self.assertEqual(emitter.read_setup(parent/'setup.json')[2], 'unsafe-input')
            self.assertEqual(emitter.read_setup(folder/'missing')[2], 'missing-input')
            with (folder/'large.json').open('wb') as stream:
                stream.truncate(emitter.MAX_INPUT_BYTES + 1)
            self.assertEqual(emitter.read_setup(folder/'large.json')[2], 'input-bound')

    def test_main_uses_only_fixed_file_read_and_two_readonly_git_queries(self):
        with tempfile.TemporaryDirectory(prefix='native-setup11-main-') as directory:
            path = Path(directory)/'existing.json'; raw = encoded(record()); path.write_bytes(raw)
            stdout = io.StringIO(); env = environment(); env['UNRELATED_PRIVATE_TOKEN'] = 'NEVER_PRINT_THIS'
            with patch.object(emitter, 'SETUP_FILE', path), patch.dict(os.environ, env, clear=True), \
                    patch.object(emitter.subprocess, 'check_output', side_effect=[SOURCE + '\n', TREE + '\n']) as git, \
                    contextlib.redirect_stdout(stdout):
                emitter.main()
            self.assertEqual([c.args[0] for c in git.call_args_list],
                             [['git', 'rev-parse', 'HEAD'], ['git', 'rev-parse', 'HEAD^{tree}']])
            self.assertTrue(all(c.kwargs['env']['GIT_NO_LAZY_FETCH'] == '1'
                                and c.kwargs['env']['GIT_OPTIONAL_LOCKS'] == '0'
                                for c in git.call_args_list))
            self.assertEqual(path.read_bytes(), raw)
            self.assertNotIn('NEVER_PRINT_THIS', stdout.getvalue())
            self.assertEqual(len(stdout.getvalue().splitlines()), 1)
            self.assertEqual(json.loads(stdout.getvalue()[len(emitter.PREFIX):])['identity']['phase'], 'editing')

    def test_output_cap_has_explicit_unavailable_scope(self):
        value = emitter.project(encoded(record()), identity())
        self.assertLessEqual(len(emitter.render(value).encode()), emitter.MAX_OUTPUT_BYTES)
        with patch.object(emitter, 'MAX_OUTPUT_BYTES', 800):
            result = json.loads(emitter.render(value)[len(emitter.PREFIX):])
        self.assertEqual((result['status'], result['reasonCode']), ('unavailable', 'output-bound'))
        self.assertFalse(result['applicationAcceptance'])

    def test_historical_tests_use_the_actual_frontend_and_keep_all_fifteen_method_bodies(self):
        raw = TARGETED_TEST.read_bytes()
        old = b"spec=importlib.util.spec_from_file_location('experience_targeted_generator',ROOT/'tools/gecko/generate_experience_targeted_workflow.py')\ng=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)\n"
        new = b"spec=importlib.util.spec_from_file_location('source11_targeted_generator_frontend',ROOT/'tests/gecko/source11_targeted_generator_compat.py')\nfrontend=importlib.util.module_from_spec(spec);spec.loader.exec_module(frontend)\ng=frontend.load_generator()\n"
        self.assertEqual(raw.count(new), 1)
        previous = raw.replace(new, old, 1)
        self.assertEqual(hashlib.sha256(previous).hexdigest(),
                         'efe5fca5549cf451c590ae3155c3b0f2528db90e016fd93e03711649e16abb32')
        def methods(value):
            text = value.decode()
            return {n.name: ast.get_source_segment(text, n) for n in ast.walk(ast.parse(text))
                    if isinstance(n, ast.FunctionDef)}
        self.assertEqual(methods(raw), methods(previous))
        self.assertEqual(sum(name.startswith('test') for name in methods(raw)), 15)

    def test_real_frontend_check_is_readonly_and_rejects_unknown_workflow_while_old_cli_stays_closed(self):
        generator = ROOT / 'tools/gecko/generate_experience_targeted_workflow.py'
        target = ROOT / '.github/workflows/gecko-experience-targeted.yml'
        before = {p: p.read_bytes() for p in (WORKFLOW, generator, target)}
        command = [sys.executable, str(FRONTEND), '--check']
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        proof = json.loads(result.stdout)
        self.assertEqual(proof['status'], 'checked-historical-diagnostic-graph-only')
        self.assertTrue(proof['diagnosticOnly'])
        for key in ('workflowWritten', 'ciTriggered', 'formalFourteenQualification',
                    'applicationAcceptance', 'physicalPhoneAcceptance', 'originalCliSupportsChangedMain'):
            self.assertIs(proof[key], False)
        with tempfile.TemporaryDirectory(prefix='native-setup11-frontend-') as directory:
            wrong = Path(directory)/'unknown.yml'; wrong.write_bytes(WORKFLOW.read_bytes() + b'\n')
            result = subprocess.run(command + ['--workflow-input', str(wrong)], cwd=ROOT,
                                    text=True, capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
        original = subprocess.run([sys.executable, str(generator), '--check'], cwd=ROOT,
                                  text=True, capture_output=True, timeout=15)
        self.assertNotEqual(original.returncode, 0)
        self.assertIn('AssertionError', original.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == '__main__':
    unittest.main(verbosity=2)
