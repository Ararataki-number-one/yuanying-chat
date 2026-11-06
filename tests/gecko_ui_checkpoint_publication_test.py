"""Actual parser/checkpoint host controls; no Android or publisher execution."""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/gecko/run_ui_visuals.py'
BEFORE_SHA256 = '65fb205cbb7a466858a0a1869cd4b5388f70026d4e09da078318827e92432f4f'
FLAG_DECLARATION = "p.add_argument('--no-checkpoint-publication',action='store_true',help='Disable checkpoint publication for nonqualifying diagnostics');"
FLAG_RETURN = '    if args.no_checkpoint_publication:return\n'


def parser_nodes(tree):
    start = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'p' for t in n.targets))
    end = next(i for i, n in enumerate(tree.body[start:], start) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'args' for t in n.targets))
    return copy.deepcopy(tree.body[start:end + 1])


def actual_checkpoint(source, *, flag=False, actions='true'):
    tree = ast.parse(source)
    checkpoint = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'checkpoint')
    module = ast.fix_missing_locations(ast.Module(body=[*parser_nodes(tree), copy.deepcopy(checkpoint)], type_ignores=[]))
    calls = []
    def publisher(argv, *, cwd):
        calls.append((argv, cwd))
        return types.SimpleNamespace(returncode=128)
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)
        namespace = dict(argparse=argparse, json=json, os=os, sys=sys, root=ROOT,
                         out=out, source='a' * 40, records=[dict(scene='controlled-scene')],
                         required_captures=lambda: range(111),
                         subprocess=types.SimpleNamespace(run=publisher))
        argv = ['run_ui_visuals.py', '--adb', 'modeled-adb', '--serial', 'modeled-serial']
        if flag:
            argv.append('--no-checkpoint-publication')
        stdout = io.StringIO()
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, {'GITHUB_ACTIONS': actions}, clear=True), contextlib.redirect_stdout(stdout):
            exec(compile(module, str(RUNNER), 'exec'), namespace)
            returned = namespace['checkpoint']()
        report = json.loads((out / 'ui-visual-results.json').read_text())
        return dict(args=namespace['args'], calls=calls, report=report,
                    stdout=stdout.getvalue(), returned=returned)


def assert_disabled_contract(case, result):
    case.assertEqual(result['calls'], [])
    case.assertEqual(result['report']['status'], 'in_progress')
    case.assertEqual(result['report']['expectedCaptures'], 111)
    case.assertEqual(result['report']['screenshots'], [dict(scene='controlled-scene')])
    case.assertEqual(result['report']['sourceCommit'], 'a' * 40)
    case.assertIsNone(result['returned'])
    case.assertNotIn('passed', result['report'].values())


class CheckpointPublicationControls(unittest.TestCase):
    def test_default_actions_behavior_still_calls_original_publisher_once(self):
        result = actual_checkpoint(RUNNER.read_text())
        self.assertFalse(result['args'].no_checkpoint_publication)
        self.assertEqual(result['calls'], [([sys.executable, str(ROOT / 'tools/gecko/publish_ci.py')], ROOT)])
        self.assertEqual(json.loads(result['stdout']), dict(event='ui-capture-checkpoint', count=1, publishExitCode=128))
        self.assertEqual(result['report']['status'], 'in_progress')

    def test_explicit_flag_suppresses_only_publication_and_preserves_checkpoint_bytes(self):
        normal = actual_checkpoint(RUNNER.read_text())
        disabled = actual_checkpoint(RUNNER.read_text(), flag=True)
        self.assertTrue(disabled['args'].no_checkpoint_publication)
        assert_disabled_contract(self, disabled)
        self.assertEqual(disabled['report'], normal['report'])
        self.assertEqual(disabled['stdout'], '')

    def test_original_local_nonactions_behavior_remains_nonpublishing(self):
        for flag in (False, True):
            with self.subTest(flag=flag):
                assert_disabled_contract(self, actual_checkpoint(RUNNER.read_text(), flag=flag, actions='false'))

    def test_parser_still_requires_actual_device_arguments_and_rejects_unknown_flag(self):
        module = ast.fix_missing_locations(ast.Module(body=parser_nodes(ast.parse(RUNNER.read_text())), type_ignores=[]))
        for argv in (['runner', '--no-checkpoint-publication'],
                     ['runner', '--adb', 'a', '--serial', 's', '--no-checkpoint-publishing']):
            with self.subTest(argv=argv), patch.object(sys, 'argv', argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    exec(compile(module, str(RUNNER), 'exec'), dict(argparse=argparse))
                self.assertEqual(error.exception.code, 2)

    def test_two_opt_in_insertions_inverse_entire_actual_runner_to_exact_before(self):
        source = RUNNER.read_text()
        self.assertEqual(source.count(FLAG_DECLARATION), 1)
        self.assertEqual(source.count(FLAG_RETURN), 1)
        before = source.replace(FLAG_DECLARATION, '', 1).replace(FLAG_RETURN, '', 1)
        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(), BEFORE_SHA256)
        workflow = ROOT / '.github/workflows/browser-2_1-acceptance.yml'
        self.assertEqual(hashlib.sha256(workflow.read_bytes()).hexdigest(),
                         'a0fdfae87d0b32ee1ab9479aacdbff81755e9e5fe45cfcaf92a8bce3e11a0069')

    def test_actual_legacy_targeted_generator_guard_contract_remains_valid(self):
        path = ROOT / 'tools/gecko/generate_experience_targeted_workflow.py'
        function = next(n for n in ast.parse(path.read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'verify_ui_checkpoint_only')
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = dict(ROOT=ROOT, ast=ast)
        exec(compile(module, str(path), 'exec'), namespace)
        namespace['verify_ui_checkpoint_only']()

    def test_actual_function_semantic_counterfeits_cannot_fake_suppression_or_preservation(self):
        source = RUNNER.read_text()
        mutants = [source.replace(FLAG_RETURN, '', 1),
                   source.replace("partial={'status':'in_progress'", "partial={'status':'passed'", 1),
                   source.replace("action='store_true',help='Disable checkpoint", "action='store_true',default=True,help='Disable checkpoint", 1)]
        for index, mutant in enumerate(mutants):
            with self.subTest(mutant=index), self.assertRaises(AssertionError):
                if index == 2:
                    result = actual_checkpoint(mutant)
                    self.assertFalse(result['args'].no_checkpoint_publication)
                else:
                    assert_disabled_contract(self, actual_checkpoint(mutant, flag=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
