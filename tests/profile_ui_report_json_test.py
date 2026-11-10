"""Execute the actual final writers and retain the original source/privacy gates.

All payloads here are small synthetic values or deterministic size controls.
No host result represents Android execution or replaces an original capture.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import ui_report_json_source_compatibility as current
import ui_visual_preservation_contract as original


ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
               "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
_guard_spec = importlib.util.spec_from_file_location('report_json_privacy_guard', ROOT/'tools/gecko/caret_ime_guard.py')
guard = importlib.util.module_from_spec(_guard_spec)
sys.modules[_guard_spec.name] = guard
_guard_spec.loader.exec_module(guard)


def raw_runner():
    return (ROOT/current.RUNNER).read_bytes()


def final_writers():
    """Select actual statements at the original workload and cleanup boundaries."""
    tree = ast.parse(raw_runner())
    outer = [node for node in tree.body if isinstance(node, ast.Try) and node.finalbody]
    assert len(outer) == 1
    cleanup = [node for node in outer[0].finalbody if isinstance(node, ast.Try)]
    assert len(cleanup) == 1

    def selected(parts, name):
        rows = [node for node in parts if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == 'write_text'
                and isinstance(node.value.func.value, ast.BinOp)
                and isinstance(node.value.func.value.left, ast.Name)
                and node.value.func.value.left.id == 'out'
                and isinstance(node.value.func.value.right, ast.Constant)
                and node.value.func.value.right.value == name]
        assert len(rows) == 1
        return rows[0]

    return (selected(outer[0].body, 'compact-chrome-results.json'),
            selected(cleanup[0].finalbody, 'ui-visual-results.json'))


def write_actual(report):
    """Real json.dumps and Path.write_text, without executing any device code."""
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory)
        namespace = dict(json=json, out=out, source='synthetic-source',
                         compact=report.get('compactChrome', []),
                         reload_confirmation=report.get('reloadConfirmation'),
                         auto_collapse=report.get('autoCollapse'), report=report)
        for node in final_writers():
            module = ast.Module(body=[copy.deepcopy(node)], type_ignores=[])
            exec(compile(ast.fix_missing_locations(module), str(ROOT/current.RUNNER), 'exec'), namespace)
        return {name: (out/name).read_bytes()
                for name in ('compact-chrome-results.json', 'ui-visual-results.json')}


def expected_compact(report):
    return dict(status='passed', actualAndroidExecution=True, sourceCommit='synthetic-source',
                cases=report.get('compactChrome', []), reloadConfirmation=report.get('reloadConfirmation'),
                autoCollapse=report.get('autoCollapse'))


class FinalReportJsonTests(unittest.TestCase):
    def assert_exact_values(self, before, after):
        self.assertIs(type(after), type(before))
        if isinstance(before, dict):
            self.assertEqual(list(after), list(before))
            for key in before:
                self.assert_exact_values(before[key], after[key])
        elif isinstance(before, list):
            self.assertEqual(len(after), len(before))
            for left, right in zip(before, after):
                self.assert_exact_values(left, right)
        elif isinstance(before, float):
            self.assertEqual(struct.pack('!d', before), struct.pack('!d', after))
        elif isinstance(before, str):
            self.assertEqual(before.encode('utf-8'), after.encode('utf-8'))
        else:
            self.assertEqual(before, after)

    def test_actual_two_writers_keep_all_fields_raw_strings_types_and_float_bits(self):
        raw = ' { "text": "中文\\nvalue", "values": [0, -0.0] } \r\n'
        payload = dict(status='in_progress', sourceCommit='synthetic-source',
                       captures=[dict(rawUtf8=raw, rawXml='<node text="synthetic &amp; only"/>\n',
                                      sha256=hashlib.sha256(raw.encode()).hexdigest())],
                       compactChrome=[dict(value=[None, False, True, 0, 1, -3, -0.0, 1.25e-19])],
                       reloadConfirmation=dict(text=' spaces  \t\r\nquotes " \\ end '),
                       autoCollapse=dict(cases=[dict(events=[dict(rawUtf8=raw)], unicode='字\u2028尾')]),
                       unusedButPreserved={'nested': [[], {}, '']})
        files = write_actual(payload)
        for name, expected in (('ui-visual-results.json', payload),
                               ('compact-chrome-results.json', expected_compact(payload))):
            with self.subTest(name=name):
                self.assert_exact_values(expected, json.loads(files[name]))
                self.assertEqual(files[name], (json.dumps(expected, ensure_ascii=False, separators=(',', ':'))+'\n').encode())
                guard.assert_public_diagnostic_text(Path(name), files[name])

    def test_final_cleanup_writer_keeps_failure_and_partial_status(self):
        for status in ('failed', 'in_progress', 'passed'):
            value = dict(status=status, failure={'kind': 'synthetic-error', 'detail': 'kept\nverbatim'},
                         captures=[], autoCollapse=None)
            self.assert_exact_values(value, json.loads(write_actual(value)['ui-visual-results.json']))

    def test_pretty_over_limit_becomes_equivalent_compact_without_losing_samples(self):
        row = [[[[dict(rawUtf8='synthetic raw\n  text', bounds=[1, 2, 3, 4], present=True)]]]]
        payload = dict(status='in_progress', captures=[row] * 60000, autoCollapse={'cases': [row] * 60000})
        files = write_actual(payload)
        self.assertEqual(guard.PRIVACY_MAX_BYTES, 16*1024*1024)
        for name, expected in (('ui-visual-results.json', payload),
                               ('compact-chrome-results.json', expected_compact(payload))):
            pretty = (json.dumps(expected, ensure_ascii=False, indent=2)+'\n').encode()
            with self.subTest(name=name):
                self.assertGreater(len(pretty), guard.PRIVACY_MAX_BYTES)
                self.assertLess(len(files[name]), guard.PRIVACY_MAX_BYTES)
                self.assertEqual(json.loads(files[name]), expected)
                self.assertEqual(files[name].count(b'"rawUtf8"'), pretty.count(b'"rawUtf8"'))
                guard.assert_public_diagnostic_text(Path(name), files[name])
                with self.assertRaises(ValueError):
                    guard.assert_public_diagnostic_text(Path(name), pretty)

    def test_compact_still_rejects_oversized_payload_and_secret_shape_at_end(self):
        value = dict(status='failed', content='x' * guard.PRIVACY_MAX_BYTES)
        oversized = write_actual(value)['ui-visual-results.json']
        self.assertGreater(len(oversized), guard.PRIVACY_MAX_BYTES)
        with self.assertRaises(ValueError):
            guard.assert_public_diagnostic_text(Path('ui-visual-results.json'), oversized)
        value = dict(status='failed', padding='x'*(1024*1024), finalField='AIza'+'A'*35)
        sensitive = write_actual(value)['ui-visual-results.json']
        self.assertLess(len(sensitive), guard.PRIVACY_MAX_BYTES)
        with self.assertRaisesRegex(ValueError, 'rejected file=ui-visual-results.json'):
            guard.assert_public_diagnostic_text(Path('ui-visual-results.json'), sensitive)


class ReportSourceInputs(unittest.TestCase):
    def test_three_complete_reviewed_images_restore_fixed_before_blobs_and_roundtrip(self):
        self.assertEqual(set(current.IDENTITIES), {current.RUNNER, current.PORT, current.HOST})
        self.assertEqual((current.BASE_COMMIT, current.BASE_TREE),
                         ('89729eb2c079d40237ecd466c7444da934206d98', '583db08f6595ddc8e5a387e5cc035de1e70cb690'))
        for path, identities in current.IDENTITIES.items():
            raw = (ROOT/path).read_bytes()
            with self.subTest(path=path):
                self.assertEqual(current.identity(raw), identities[3:])
                before = current.source_input(raw, path)
                self.assertEqual(current.identity(before), identities[:3])
                self.assertEqual(current.historical_input(raw, path), before)
                self.assertIs(current.historical_input(before, path), before)
                for old, new in current.DELTAS[path]:
                    self.assertEqual(before.count(old.encode()), 1)
                    before = before.replace(old.encode(), new.encode(), 1)
                self.assertEqual(before, raw)

    def test_only_final_writers_change_no_functions_assertions_checkpoints_or_old_pins(self):
        def functions(raw):
            text = raw.decode()
            return [ast.get_source_segment(text, n) for n in ast.walk(ast.parse(text))
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        def assertions(raw):
            return [ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(raw))
                    if isinstance(n, ast.Assert) or isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert')]

        for path in current.IDENTITIES:
            after = (ROOT/path).read_bytes(); before = current.source_input(after, path)
            self.assertEqual(functions(after), functions(before), path)
            self.assertEqual(assertions(after), assertions(before), path)
        raw = raw_runner()
        self.assertNotIn(b'ui_report_json_source_compatibility', raw)
        self.assertEqual(raw.count(b"separators=(',',':')"), 2)
        self.assertEqual(current.sha((ROOT/'tests/fixtures/ui-download-workspace-v2-source-deltas.json').read_bytes()),
                         '474a0aa459c92a94cdbc3fe4f89bf738e7dc5fc1f8bc14ab871100c1984fe479')

    def test_missing_duplicate_moved_modified_and_previous_whole_images_fail_closed(self):
        for path in current.IDENTITIES:
            raw = (ROOT/path).read_bytes()
            values = [b'', raw[:1024], raw+b' ', current.source_input(raw, path)]
            for _, new in current.DELTAS[path]:
                block = new.encode(); remaining = raw.replace(block, b'', 1)
                moved = remaining+block
                if moved == raw:
                    moved = block+remaining
                values.extend((remaining, moved, raw.replace(block, block*2, 1), raw.replace(block, block+b' ', 1)))
            for value in values:
                with self.subTest(path=path, digest=current.sha(value)), self.assertRaises(AssertionError):
                    current.source_input(value, path)
                self.assertIs(current.historical_input(value, path), value)

    def test_both_complete_ast_forms_and_formatting_keep_original_ui_oracles(self):
        raw = raw_runner().decode(); before = current.source_input(raw.encode(), current.RUNNER).decode()
        self.assertEqual(raw.count(PREPARATION), 1)
        for selected, old in ((raw, before), (raw.replace(PREPARATION, '', 1), before.replace(PREPARATION, '', 1))):
            for text in (selected, '# formatting only\n'+ast.unparse(ast.parse(selected))+'\n'):
                tree = ast.parse(text)
                self.assertIs(current.original_runner_tree(tree), tree)
                self.assertEqual(ast.dump(tree, include_attributes=False), ast.dump(ast.parse(old), include_attributes=False))
                result = original.verify_shared_ui_source(text)
                self.assertEqual(result['normalizedModuleAstSha256'], '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
                self.assertEqual(result['normalizedCaptureAstSha256'], '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')
                self.assertFalse(result['actualAndroidExecution'])

    def test_writer_ast_removal_duplication_movement_or_change_rejects_before_mutation(self):
        raw = raw_runner()
        for writer in current.WRITERS_AFTER:
            expected = ast.dump(ast.parse(writer).body[0], include_attributes=False)
            for kind in ('missing', 'duplicate', 'moved', 'changed'):
                tree = ast.parse(raw)
                matches = [(parts, index) for parts in current._statement_lists(tree)
                           for index, node in enumerate(parts) if ast.dump(node, include_attributes=False) == expected]
                self.assertEqual(len(matches), 1)
                parts, index = matches[0]; node = parts[index]
                if kind == 'missing':
                    del parts[index]
                elif kind == 'duplicate':
                    parts.insert(index, copy.deepcopy(node))
                elif kind == 'moved':
                    del parts[index]; tree.body.append(node)
                else:
                    parts[index] = ast.parse(writer.replace("(',',':')", "(',',': ')" )).body[0]
                before = ast.dump(tree, include_attributes=False)
                with self.subTest(kind=kind, writer=writer[:45]), self.assertRaises(AssertionError):
                    current.original_runner_tree(tree)
                self.assertEqual(ast.dump(tree, include_attributes=False), before)
                self.assertIs(current.historical_tree(tree), tree)
                with self.assertRaises(AssertionError):
                    original.verify_shared_ui_source(ast.unparse(tree))

    def test_original_threshold_fields_and_other_writer_changes_never_normalize(self):
        raw = raw_runner().decode()
        changes = ((current.WRITERS_AFTER[0], current.WRITERS_AFTER[0].replace("'autoCollapse':auto_collapse", "'autoCollapse':None")),
                   (current.WRITERS_AFTER[1], current.WRITERS_AFTER[1].replace('json.dumps(report,', "json.dumps({**report,'rawUtf8':report['rawUtf8'].strip()},")),
                   ('json.dumps(report,ensure_ascii=False', 'json.dumps({},ensure_ascii=False'),
                   ('json.dumps(partial,ensure_ascii=False,indent=2)', "json.dumps(partial,ensure_ascii=False,separators=(',',':'))"),
                   ('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0'),
                   ("assert '已选 8 个' in xml", 'assert True'),
                   ('verify_captures(records,source)', 'verify_captures(records)'),
                   ('UI_NAVIGATION_CONTRACT=2', 'UI_NAVIGATION_CONTRACT=1'))
        for old, new in changes:
            self.assertEqual(raw.count(old), 1, old)
            selected = raw.replace(old, new, 1).encode()
            self.assertIs(current.historical_input(selected, current.RUNNER), selected)
            with self.subTest(old=old), self.assertRaises(AssertionError):
                current.source_input(selected, current.RUNNER)
            with self.assertRaises(AssertionError):
                original.verify_shared_ui_source(selected.decode())

    def test_invalid_types_paths_excerpts_and_unrecognized_asts_do_not_gain_a_mapping(self):
        raw = raw_runner()
        for value in (None, raw.decode(), bytearray(raw), memoryview(raw), True):
            with self.assertRaises(AssertionError):
                current.source_input(value, current.RUNNER)
        for path in (None, Path(current.RUNNER), '/'+current.RUNNER, '../'+current.RUNNER, 'other.py'):
            with self.assertRaises(AssertionError):
                current.source_input(raw, path)
        for tree in (None, ast.Module(body=[], type_ignores=[]), ast.parse(current.WRITERS_AFTER[0])):
            with self.assertRaises(AssertionError):
                current.original_runner_tree(tree)

    def test_named_historical_port_preserves_real_bytes_and_unknowns_without_global_patch(self):
        read = Path.read_bytes
        view = current.historical_root(ROOT)
        self.assertIsInstance(view, Path)
        self.assertEqual(view, ROOT)
        self.assertEqual(os.fspath(view), os.fspath(ROOT))
        raw = raw_runner(); selected = view/current.RUNNER
        self.assertEqual(selected.read_bytes(), current.source_input(raw, current.RUNNER))
        self.assertEqual(selected.read_text().encode(), current.source_input(raw, current.RUNNER))
        self.assertFalse(hasattr(selected, 'write_bytes'))
        self.assertEqual(raw_runner(), raw)
        self.assertIs(Path.read_bytes, read)
        self.assertIs(type(view/current.PORT), type(ROOT))
        for root in (str(ROOT), ROOT.parent, view):
            with self.assertRaises(AssertionError):
                current.historical_root(root)
        unknown = raw+b' '
        def changed(path):
            return unknown if path == ROOT/current.RUNNER else read(path)
        with patch.object(Path, 'read_bytes', changed):
            self.assertIs(selected.read_bytes(), unknown)
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory)/'linked.py'; link.symlink_to(ROOT/current.RUNNER)
            with self.assertRaises(AssertionError):
                current._HistoricalSource(link).read_bytes()


if __name__ == '__main__':
    unittest.main()
