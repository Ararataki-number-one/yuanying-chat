"""Compare executable host declarations, independently of whole-file history.

This collects argv before the runner's execution loop; it does not report any
host, compiler, SDK or Android workload as having run.
"""
import ast
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from historical_source_inputs import historical_bytes


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools/browser/run_host_checks.py'


def declared_cases(raw, output, sdk=False):
    tree = ast.parse(raw)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    boundaries = [index for index, node in enumerate(main.body)
                  if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'names' for target in node.targets)]
    if len(boundaries) != 1:
        raise ValueError('Exactly one boundary between declarations and source/execution work is required')
    main.body = main.body[:boundaries[0]] + [ast.Return(value=ast.Name(id='cases', ctx=ast.Load()))]
    tree.body = [node for node in tree.body if not isinstance(node, ast.If)]
    namespace = dict(__name__='controlled_host_declarations', __file__=str(RUNNER))
    arguments = [str(RUNNER), '--output', str(output)]
    for name in ('java-home', 'json-jar', 'android-json-jar', 'android-jar', 'webkit-jar', 'jsdom-module'):
        arguments += ['--' + name, str(output / name)]
    if sdk:
        arguments += ['--gecko-sdk-jar', str(output / 'actual-sdk.jar'),
                      '--gecko-sdk-receipt', str(output / 'actual-sdk-receipt.json')]
    with patch.object(sys, 'argv', arguments):
        exec(compile(ast.fix_missing_locations(tree), str(RUNNER), 'exec'), namespace)
        return [(name, list(command), str(report) if report is not None else None)
                for name, command, report in namespace['main']()]


class BrowserHostRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        self.original = historical_bytes('tools/browser/run_host_checks.py')
        self.current = RUNNER.read_bytes()

    def preserved(self, raw):
        original = declared_cases(self.original, self.out)
        current = declared_cases(raw, self.out)
        self.assertEqual(len(original), 190)
        self.assertEqual(current[:190], original)
        self.assertEqual(len(current), 191)
        name, command, report = current[-1]
        self.assertEqual(name, 'gecko-texture-surface')
        self.assertEqual(command[1], 'tests/gecko-texture-surface-host/run.py')
        self.assertIn('--require-sdk', command)
        self.assertEqual(report, str(self.out / 'gecko-texture-surface.json'))
        self.assertEqual(len({row[0] for row in current}), len(current))
        executions = [node for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and node.func.attr == 'run'
                      and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess']
        self.assertEqual(len(executions), 1)
        timeout = [keyword.value for keyword in executions[0].keywords if keyword.arg == 'timeout']
        self.assertEqual(len(timeout), 1)
        self.assertIsInstance(timeout[0], ast.Constant)
        self.assertEqual(timeout[0].value, 300)

    def test_current_runner_preserves_all_original_commands_and_adds_actual_sdk_control(self):
        self.preserved(self.current)

    def test_explicit_local_sdk_paths_reach_the_same_required_control(self):
        cases = declared_cases(self.current, self.out, sdk=True)
        command = cases[-1][1]
        self.assertEqual(command[command.index('--sdk-classes') + 1], str(self.out / 'actual-sdk.jar'))
        self.assertEqual(command[command.index('--sdk-receipt') + 1], str(self.out / 'actual-sdk-receipt.json'))
        self.assertIn('--require-sdk', command)

    def test_removed_legacy_command_optional_sdk_or_relaxed_budget_is_rejected(self):
        address = next(line for line in self.current.splitlines(keepends=True) if b"add('address'," in line)
        for changed in (self.current.replace(address, b'', 1),
                        self.current.replace(b",'--require-sdk'", b'', 1),
                        self.current.replace(b'timeout=300', b'timeout=600', 1)):
            with self.subTest(change=changed != self.current):
                self.assertNotEqual(changed, self.current)
                with self.assertRaises(AssertionError):
                    self.preserved(changed)


if __name__ == '__main__':
    unittest.main()
