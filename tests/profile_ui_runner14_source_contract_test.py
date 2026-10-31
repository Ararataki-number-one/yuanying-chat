"""Finite source and declared device boundaries, never Android UI acceptance."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import ui_runner14_source_contract as contract
import ui_settings_services11_contract as lease_contract
import ui_visual_preservation_contract as original_ui

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'tests/gecko/run_ui_visuals.py'
SHARING = ROOT / 'tests/gecko/run_network_sharing.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


with patch.object(sys, 'path', [str(ROOT / 'tests/gecko'), *sys.path]):
    composer = load('selected_sharing_lease14', ROOT / 'tests/gecko/network_sharing_lease14.py')
capture = load('selected_original_ui_capture14', ROOT / 'tools/gecko/ui_visual_capture.py')
SOURCE = 'a' * 40
ENV = dict(CI='true', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_SHA=SOURCE)


class UiRunner14SourceTests(unittest.TestCase):
    def test_actual_current_ui_fix_and_sharing_lease_are_required_without_historical_bypass(self):
        ui, sharing = UI.read_bytes(), SHARING.read_bytes()
        old_ui = contract.require_current_ui14(ui)
        old_sharing = contract.require_current_sharing14(sharing)
        self.assertEqual(contract.digest(old_ui), contract.UI_PREVIOUS_SHA256)
        self.assertEqual(contract.digest(old_sharing), contract.SHARING_PREVIOUS_SHA256)
        self.assertEqual(ui.count(contract.UI_AFTER.encode()), 1)
        self.assertNotIn(contract.UI_BEFORE.encode(), ui)
        # Historical inputs retain their own identities; they cannot pass a
        # current-source gate after deleting the new behavior wholesale.
        self.assertEqual(contract.original_ui13_bytes(old_ui), old_ui)
        self.assertEqual(contract.original_sharing13_bytes(old_sharing), old_sharing)
        with self.assertRaises(AssertionError): contract.require_current_ui14(old_ui)
        with self.assertRaises(AssertionError): contract.require_current_sharing14(old_sharing)

    def test_real_ui_chain_preserves_formatted_and_no_old_preparation_positives(self):
        source = UI.read_text()
        adapter = (ROOT/'tests/ui_settings_services11_contract.py').read_bytes()
        marker = b'\n\n# Source14 binds the pre-existing30-second readiness budget'
        self.assertEqual(adapter.count(marker), 1)
        self.assertEqual(contract.digest(adapter.split(marker, 1)[0]),
                         'a8e69a5c4a5ad62bb9d3830d6e9032b99a0b5793fc3ff22f9fcd4006fadc5f0a')
        old_preparation = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
                           "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
        self.assertEqual(source.count(old_preparation), 1)
        for value in (source, source.replace(old_preparation, '', 1)):
            for text in (value, '# coding: utf-8\n# Formatting only\n' + ast.unparse(ast.parse(value)) + '\n'):
                result = original_ui.verify_shared_ui_source(text)
                self.assertTrue(result['originalWorkloadSemanticsPreserved'])
                self.assertEqual(result['normalizedModuleAstSha256'], original_ui.ORIGINAL_MODULE_AST)
                self.assertEqual(result['normalizedCaptureAstSha256'], original_ui.ORIGINAL_CAPTURE_AST)
        self.assertEqual(hashlib.sha256(lease_contract.require_runner_source(source.encode())).hexdigest(), lease_contract.PREVIOUS_SHA256)
        # Standalone host entrypoints load this chain by actual file path, with
        # no tests directory on sys.path. Verify that real import closure too.
        script = '''import importlib.util,pathlib,sys
root=pathlib.Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('selected_ui',root/'tests/ui_visual_preservation_contract.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert module.verify_shared_ui_source((root/'tests/gecko/run_ui_visuals.py').read_text())['originalWorkloadSemanticsPreserved']
print('UI14_STANDALONE_REAL_INPUT_CHAIN')
'''
        result = subprocess.run([sys.executable, '-I', '-c', script, str(ROOT)], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b'UI14_STANDALONE_REAL_INPUT_CHAIN', result.stdout)

    def test_ui_inverse_rejects_threshold_deadline_identity_duplicates_and_moved_calls(self):
        raw = UI.read_bytes(); source = raw.decode()
        loop = contract.UI_AFTER
        variants = [source + '\n# unknown\n', source.replace(loop, loop + loop, 1),
                    source.replace(loop, loop.replace('deadline=deadline', 'deadline=None'), 1),
                    source.replace(loop, loop.replace('+30', '+31'), 1),
                    source.replace(loop, loop.replace('xml=dump(deadline=deadline)', 'pass'), 1),
                    source.replace(loop, contract.UI_BEFORE, 1).replace('xml=dump();collected.append(xml)', 'xml=dump(deadline=deadline);collected.append(xml)', 1),
                    source.replace("timeout=90).decode(errors='replace')", "timeout=91).decode(errors='replace')", 1),
                    source.replace("assert '自动优选' in xml and '重新随机' not in xml", 'assert True', 1)]
        for index, value in enumerate(variants):
            self.assertNotEqual(value, source)
            with self.subTest(sha256=contract.digest(value.encode())), self.assertRaises(AssertionError):
                contract.original_ui13_bytes(value.encode())
            if index == 0:
                # Whole-byte current inputs reject added comments; the old AST
                # contract deliberately permits nonsemantic formatting.
                self.assertTrue(original_ui.verify_shared_ui_source(value)['originalWorkloadSemanticsPreserved'])
            else:
                with self.assertRaises(AssertionError): original_ui.verify_shared_ui_source(value)
        tree = ast.parse(source)
        outer = next(n for n in tree.body if isinstance(n, ast.Try) and n.finalbody)
        loop = contract.optimization_loop(tree)
        position = outer.body.index(loop); outer.body[position], outer.body[position + 1] = outer.body[position + 1], loop
        with self.assertRaises(AssertionError): contract.remove_reviewed_ui14_deadline(tree)

    def test_sharing_whole_flow_and_all_methods_survive_raw_and_formatted_ast_inverse(self):
        raw = SHARING.read_bytes(); old = contract.original_sharing13_bytes(raw)
        def methods(value):
            text = value.decode()
            return {n.name: ast.get_source_segment(text, n) for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef)}
        self.assertEqual(methods(raw), methods(old))
        for text in (raw.decode(), ast.unparse(ast.parse(raw)) + '\n', old.decode()):
            tree = contract.original_sharing13_tree(ast.parse(text))
            self.assertEqual(contract.tree_digest(tree), contract.SHARING_OLD_AST)
        before, after = ast.parse(old), ast.parse(raw)
        original = next(n for n in before.body if isinstance(n, ast.Try))
        current = next(n for n in after.body if isinstance(n, ast.Try))
        self.assertEqual(ast.dump(ast.Module(body=original.body + original.handlers + original.orelse, type_ignores=[]), include_attributes=False),
                         ast.dump(ast.Module(body=current.body + current.handlers + current.orelse, type_ignores=[]), include_attributes=False))
        calls = [n for n in ast.walk(after) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'verify_network_sharing']
        self.assertEqual(len(calls), 2)

    def test_sharing_inverse_rejects_partial_moved_cleanup_changed_taps_or_original_limits(self):
        raw = SHARING.read_bytes(); text = raw.decode()
        old = contract.original_sharing13_bytes(raw).decode()
        invalid = [text.replace(contract.SHARING_IMPORT, '', 1), text.replace(contract.SHARING_IMPORT, contract.SHARING_IMPORT * 2, 1),
                   text.replace(contract.SHARING_PREPARE, '', 1), text.replace(contract.SHARING_PREPARE, contract.SHARING_PREPARE * 2, 1),
                   text.replace(contract.SHARING_FINALLY, '', 1), text.replace(contract.SHARING_FINALLY, 'finally:\n pass\n', 1),
                   text.replace(contract.SHARING_IMPORT, '', 1) + contract.SHARING_IMPORT,
                   text.replace('seconds=90', 'seconds=91', 1), text.replace("tap('取消')", "tap('导入')", 1),
                   text.replace('verify_tap_accounting(r)', 'pass', 1), old + '\n# unknown\n']
        for index, value in enumerate(invalid):
            self.assertNotEqual(value, text)
            with self.subTest(sha256=contract.digest(value.encode())), self.assertRaises(AssertionError):
                contract.original_sharing13_bytes(value.encode())
            if index == len(invalid) - 1:
                self.assertEqual(contract.tree_digest(contract.original_sharing13_tree(ast.parse(value))), contract.SHARING_OLD_AST)
            else:
                with self.assertRaises(AssertionError): contract.original_sharing13_tree(ast.parse(value))

    def test_real_capture_acquires_null_then_xml_only_under_the_unchanged_existing_deadline(self):
        raw = UI.read_bytes(); old = contract.original_ui13_bytes(raw)
        xml = b'<hierarchy rotation="0"><node text="controlled current hierarchy"/></hierarchy>'
        for selected, succeeds in ((old, False), (raw, True)):
            tree = ast.parse(selected)
            dump = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'dump')
            loop = contract.optimization_loop(tree)
            wait = next(n for n in loop.body if isinstance(n, ast.While))
            with tempfile.TemporaryDirectory(prefix='ui14-read-boundary-') as directory:
                actual = capture.UiVisualCapture(adb='controlled-adb', serial='emulator-5554', source=SOURCE,
                                                diagnostics=Path(directory)/'observations.json')
                responses = [subprocess.CompletedProcess([], 1, stdout=capture.NULL_ROOT.encode(), stderr=b''),
                             subprocess.CompletedProcess([], 0, stdout=b'', stderr=b''),
                             subprocess.CompletedProcess([], 0, stdout=xml, stderr=b'')]
                namespace = dict(ui_capture=actual, deadline=30)
                program = compile(ast.Module(body=[dump, wait.body[0]], type_ignores=[]), '<actual-ui14-acquisition>', 'exec')
                with patch.object(capture.subprocess, 'run', side_effect=responses) as commands, \
                        patch.object(capture.time, 'monotonic', return_value=0), patch.object(capture.time, 'sleep'):
                    if succeeds:
                        exec(program, namespace); self.assertEqual(namespace['xml'], xml.decode())
                    else:
                        with self.assertRaises(capture.CaptureNotReady): exec(program, namespace)
                self.assertEqual(commands.call_count, 3 if succeeds else 1)
                self.assertTrue(all('input' not in x.args[0] for x in commands.call_args_list))
                self.assertTrue(all(x.kwargs['timeout'] == (30 if succeeds else 90) for x in commands.call_args_list))
                self.assertEqual(actual.report['attemptCount'], 2 if succeeds else 1)


class SharingLease14BoundaryTests(unittest.TestCase):
    def files(self, root, *, same=True):
        apk = root/'app/build/outputs/apk/integration/app-x86_64-integration.apk'; apk.parent.mkdir(parents=True)
        out = root/'work/gecko-integration'; out.mkdir(parents=True)
        apk.write_bytes(b'controlled-not-a-real-apk'); (out/'ui-current.apk').write_bytes(apk.read_bytes() if same else b'other')
        return apk, out

    def test_only_equal_real_file_bytes_delegate_once_to_the_existing_source_and_device_guard(self):
        with tempfile.TemporaryDirectory(prefix='sharing14-compose-') as directory:
            root = Path(directory); apk, out = self.files(root); args = types.SimpleNamespace(adb='controlled-adb', serial='emulator-5554')
            lease = types.SimpleNamespace(record={})
            with patch.dict(os.environ, ENV, clear=True), patch.object(sys, 'path', list(sys.path)), \
                    patch.object(composer.subprocess, 'check_output', return_value=(SOURCE+'\n')) as git, \
                    patch.object(composer, 'prepare_workflow', return_value=lease) as guard:
                self.assertIs(composer.prepare(root, out, args), lease)
                self.assertEqual(guard.call_count, 1)
                self.assertIs(guard.call_args.kwargs['environment'], os.environ)
            self.assertEqual(git.call_args.args[0], ['git', 'rev-parse', 'HEAD'])
            expected = guard.call_args.kwargs
            self.assertEqual((expected['serial'], expected['root'], expected['source']), (args.serial, root, SOURCE))
            self.assertEqual(expected['record_path'], out/'network-sharing-settings-services-isolation.json')
            self.assertNotEqual(expected['record_path'], out/'ui-settings-services-isolation.json')
            self.assertEqual(lease.record['sharingIntegrationApkSha256'], hashlib.sha256(apk.read_bytes()).hexdigest())
            self.assertIs(lease.record['fullQualificationAcceptance'], False)

    def test_missing_mismatched_or_symlink_current_apk_never_reaches_git_guard_or_device(self):
        for mode in ('different', 'missing', 'symlink', 'empty'):
            with tempfile.TemporaryDirectory(prefix='sharing14-rejected-') as directory:
                root = Path(directory); apk, out = self.files(root, same=mode!='different'); staged=out/'ui-current.apk'
                if mode == 'missing': staged.unlink()
                elif mode == 'symlink': staged.unlink(); staged.symlink_to(apk)
                elif mode == 'empty': apk.write_bytes(b'')
                with patch.dict(os.environ, ENV, clear=True), patch.object(composer, 'prepare_workflow') as guard, \
                        patch.object(composer.subprocess, 'check_output', side_effect=AssertionError('No Git/ADB before byte identity')):
                    with self.assertRaises((OSError, RuntimeError)):
                        composer.prepare(root, out, types.SimpleNamespace(adb='controlled-adb', serial='emulator-5554'))
                guard.assert_not_called()

    def test_non_ci_retains_no_apk_no_git_no_device_guard_path(self):
        with tempfile.TemporaryDirectory(prefix='sharing14-nonci-') as directory:
            root = Path(directory); out=root/'out';out.mkdir()
            with patch.dict(os.environ, {}, clear=True), patch.object(composer, 'file_digest', side_effect=AssertionError('No APK read')), \
                    patch.object(composer.subprocess, 'check_output', side_effect=AssertionError('No Git/ADB')):
                lease = composer.prepare(root, out, types.SimpleNamespace(adb='controlled-adb', serial='physical-device'))
            self.assertEqual(lease.record['status'], 'not-ci-unchanged')
            self.assertEqual(lease.record['commands'], [])
            self.assertEqual(lease.path, out/'network-sharing-settings-services-isolation.json')

    def test_finish_preserves_original_failure_and_restore_failure_is_never_success(self):
        original = ValueError('controlled original failure')
        lease = types.SimpleNamespace(record={})
        with patch.object(composer, 'finish_workflow') as finish, self.assertRaises(ValueError) as observed:
            try: raise original
            finally: composer.finish(lease)
        self.assertIs(observed.exception, original); finish.assert_called_once()
        self.assertIs(lease.record['sharingFlowReturnedWithoutError'], False)
        restoration = RuntimeError('controlled restoration failure')
        with patch.object(composer, 'finish_workflow', side_effect=restoration), self.assertRaises(RuntimeError) as observed:
            try: raise original
            finally: composer.finish(lease)
        self.assertIs(observed.exception, restoration); self.assertIs(observed.exception.__cause__, original)
        with patch.object(composer, 'finish_workflow', side_effect=restoration), self.assertRaises(RuntimeError): composer.finish(lease)
        self.assertIs(lease.record['sharingFlowReturnedWithoutError'], True)

    def test_natural_sharing_import_path_reaches_real_selected_validator_and_rejects_bad_zip(self):
        with tempfile.TemporaryDirectory(prefix='sharing14-import-closure-') as directory:
            root = Path(directory); apk,out=self.files(root); tools=root/'tools/gecko';tools.mkdir(parents=True)
            for name in ('profile_invocation_contract.py', 'sdk_identity_contract.py'):
                raw=(ROOT/'tools/gecko'/name).read_bytes(); (tools/name).write_bytes(raw)
                self.assertEqual((tools/name).read_bytes(), raw)
            (root/'app/build.gradle').write_text("versionName '2.0.46'\nversionCode 99\n")
            script = '''import importlib,os,pathlib,sys,types,zipfile
from unittest.mock import patch
actual=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2]);source='a'*40;tree='b'*40
sys.path.insert(0,str(actual/'tests/gecko'));sys.path.insert(0,str(actual/'tools'))
assert str(root/'tools/gecko') not in sys.path and 'profile_invocation_contract' not in sys.modules
module=importlib.import_module('network_sharing_lease14')
env=dict(CI='true',GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA=source)
calls=[]
def git(command,**kwargs):
 calls.append(command);assert command[0]=='git', 'No Android command before bad ZIP rejection'
 return {('git','rev-parse','HEAD'):source+'\\n',('git','status','--porcelain','--untracked-files=no'):'',('git','rev-parse','HEAD^{tree}'):tree+'\\n'}[tuple(command)]
with patch.dict(os.environ,env,clear=True),patch.object(module.subprocess,'check_output',side_effect=git):
 try:module.prepare(root,root/'work/gecko-integration',types.SimpleNamespace(adb='controlled-adb',serial='emulator-5554'))
 except zipfile.BadZipFile:pass
 else:raise AssertionError('Real selected validator must reject the synthetic invalid ZIP')
assert pathlib.Path(sys.modules['profile_invocation_contract'].__file__)==root/'tools/gecko/profile_invocation_contract.py'
assert len(calls)==4
print('SHARING14_REAL_IMPORT_CLOSURE_BAD_ZIP_REJECTED')
'''
            result = subprocess.run([sys.executable, '-I', '-c', script, str(ROOT), str(root)], cwd=root,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertIn(b'SHARING14_REAL_IMPORT_CLOSURE_BAD_ZIP_REJECTED', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
