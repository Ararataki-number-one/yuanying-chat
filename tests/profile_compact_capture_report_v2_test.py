"""Strict source-only inverse controls; no Android or latency execution."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/compact-chrome-capture-host/run.py'
spec = importlib.util.spec_from_file_location('compact_capture_report_contract', RUNNER)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
SYNTHETIC_DECLARATION = '"syntheticPresentation",true,"actualLatencyMeasurement",false,'
ORIGINAL_SHA256 = '200192382212fee9889cd9905b837d551a27c75fcc4b777acdab3dd9982e63b7'


def current_body():
    return capture.member((ROOT / 'tests/gecko/CompactChromeIntegrationActivity.java').read_text(),
                          'void report(String event,')


class CompactCaptureReportV2Tests(unittest.TestCase):
    def reject(self, body):
        with self.assertRaises(AssertionError):
            capture.historical_report_body(body)

    def test_complete_current_inverse_retains_both_historical_byte_identities(self):
        body = current_body()
        self.assertEqual(capture.report_pin(body),
                         (3982, '4cfa806c09c40ad3dcac9f3217b744f6d9d88b6acb0611e506f24939cc6b2e39'))
        restored = capture.restore_v2_report_body(body)
        self.assertEqual(capture.report_pin(restored),
                         (3507, '8de01adca0ba191e634a90aa8dc125fbe91e22172f4894ad32d0590ca9af8fd0'))
        self.assertEqual(restored.count(SYNTHETIC_DECLARATION), 1)
        original = restored.replace(SYNTHETIC_DECLARATION, '')
        self.assertEqual(capture.report_pin(original), (3445, ORIGINAL_SHA256))
        self.assertEqual(capture.ORIGINAL_REPORT_SHA256, ORIGINAL_SHA256)

    def test_only_exact_old_bodies_keep_original_acceptance_and_cannot_reenter_v2(self):
        previous = capture.restore_v2_report_body(current_body())
        for body in (previous, previous.replace(SYNTHETIC_DECLARATION, '')):
            with self.subTest(bytes=len(body.encode())):
                self.assertEqual(capture.historical_report_body(body), body)
                with self.assertRaises(AssertionError):
                    capture.restore_v2_report_body(body)
                self.reject(body.replace('hit.bottom-1', 'hit.bottom-2', 1))

    def test_added_measurements_roles_dot_top_bounds_and_navigation_are_locked(self):
        mutations = (
            ('int[] textRoles={16,12,12,11}', 'int[] textRoles={15,12,12,11}'),
            ('int textRole=0;', 'int textRole=1;'),
            ('"lineCount",text.getLayout()==null?0:text.getLayout().getLineCount()', '"lineCount",1'),
            ('"layoutHeight",text.getLayout()==null?0:text.getLayout().getHeight()', '"layoutHeight",text.getHeight()'),
            ('"maxLines",text.getMaxLines()', '"maxLines",2'),
            ('"textSizePx",text.getTextSize()', '"textSizePx",16'),
            ('textRoles[textRole++]', 'textRoles[0]'),
            ('android.util.TypedValue.COMPLEX_UNIT_SP', 'android.util.TypedValue.COMPLEX_UNIT_DIP'),
            ('"height",dot.getHeight()', '"height",dot.getHeight()+1'),
            ('"navigationContract",2,', '"navigationContract",1,'),
            ('"navigationContract",2,', '"navigationContract",3,'),
            ('"topBounds",bounds(top),', '"topBounds",bounds(toolbar),'),
        )
        for before, after in mutations:
            body = current_body()
            self.assertEqual(body.count(before), 1, before)
            with self.subTest(field=before):
                self.reject(body.replace(before, after, 1))

    def test_original_geometry_touches_text_and_declared_scope_cannot_drift(self):
        mutations = (
            ('hit.bottom-1', 'hit.bottom-2'),
            ('hit.width()/density()', 'hit.width()/2'),
            ('hit.offset(origin[0],origin[1])', 'hit.offset(0,0)'),
            ('"fontHeight",font.bottom-font.top', '"fontHeight",font.bottom'),
            ('"networkTap",J.arr(networkBounds.centerX(),networkBounds.centerY())', '"networkTap",J.arr(0,0)'),
            ('"latency",latency.getText().toString()', '"latency","42 ms"'),
            ('"syntheticPresentation",true,', '"syntheticPresentation",false,'),
            ('"actualLatencyMeasurement",false,', '"actualLatencyMeasurement",true,'),
        )
        for before, after in mutations:
            body = current_body()
            self.assertEqual(body.count(before), 1, before)
            with self.subTest(field=before):
                self.reject(body.replace(before, after, 1))

    def test_missing_duplicate_moved_or_reordered_additions_are_not_normalized(self):
        for index, (left, addition, right) in enumerate(capture.V2_REPORT_INSERTIONS):
            body = current_body()
            self.assertEqual(body.count(left + addition + right), 1)
            mutations = (
                body.replace(left + addition + right, left + right, 1),
                body.replace(left + addition + right, left + addition + addition + right, 1),
                body.replace(left + addition + right, left + right, 1) + addition,
                body.replace(left + addition + right, left + right + addition, 1),
            )
            for change, candidate in enumerate(mutations):
                with self.subTest(addition=index, mutation=change):
                    self.reject(candidate)

    def test_unknown_fields_bytes_comments_and_pre_normalized_current_body_fail(self):
        body = current_body()
        for candidate in (body + ' ', body + '\n', body + '//extra', body.replace('\n', '\r\n'),
                          body.replace('"actions",actionCount,', '"unknown",true,"actions",actionCount,', 1),
                          body.replace(SYNTHETIC_DECLARATION, '', 1),
                          body.replace(SYNTHETIC_DECLARATION, SYNTHETIC_DECLARATION * 2, 1)):
            with self.subTest(bytes=len(candidate.encode())):
                self.reject(candidate)

    def test_source_types_are_not_coerced(self):
        for value in (None, 2, True, current_body().encode(), bytearray(current_body().encode())):
            with self.subTest(kind=type(value).__name__):
                self.reject(value)

    def test_context_and_restored_pins_still_reject_if_only_current_hash_is_replaced(self):
        # A blind after-hash replacement cannot bypass the exact inverse or the
        # unchanged old body identity. These are adversarial host-only controls.
        original = current_body()
        mutations = (
            original.replace('"navigationContract",2,', '"navigationContract",3,', 1),
            original.replace('"navigationContract",2,', '"navigationContract",2,"navigationContract",2,', 1),
            original.replace('hit.bottom-1', 'hit.bottom-2', 1),
        )
        for candidate in mutations:
            with self.subTest(body=hashlib.sha256(candidate.encode()).hexdigest()), \
                    patch.object(capture, 'V2_REPORT_BYTES', len(candidate.encode())), \
                    patch.object(capture, 'V2_REPORT_SHA256', hashlib.sha256(candidate.encode()).hexdigest()), \
                    self.assertRaises(AssertionError):
                capture.restore_v2_report_body(candidate)

    def test_adapter_only_feeds_the_original_body_assert_not_java_execution(self):
        tree = ast.parse(RUNNER.read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        assignments = [node for node in ast.walk(main) if isinstance(node, ast.Assign)]
        final = next(node for node in assignments if any(isinstance(target, ast.Name) and target.id == 'final_report'
                                                       for target in node.targets))
        inverse_calls = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Name) and node.func.id in
                         ('historical_report_body', 'restore_v2_report_body')]
        self.assertEqual(len(inverse_calls), 1)
        self.assertEqual(ast.unparse(inverse_calls[0]),
                         "historical_report_body(member(fixture, 'void report(String event,'))")
        self.assertIn(inverse_calls[0], list(ast.walk(final)))
        java = [node for node in assignments if any(isinstance(target, ast.Name) and target.id == 'java'
                                                   for target in node.targets)]
        self.assertTrue(java)
        self.assertTrue(all(inverse_calls[0] not in list(ast.walk(node)) for node in java))
        assertions = [node for node in ast.walk(main) if isinstance(node, ast.Assert)]
        report_assert = next(node for node in assertions if isinstance(node.msg, ast.Constant)
                             and node.msg.value == 'Original geometry/touch/text report body changed')
        expected = ast.parse("assert hashlib.sha256(final_report.encode()).hexdigest()==ORIGINAL_REPORT_SHA256,'Original geometry/touch/text report body changed'").body[0]
        self.assertEqual(ast.dump(report_assert, include_attributes=False),
                         ast.dump(expected, include_attributes=False))
        self.assertIn('pathlib.Path(__file__).resolve()', ast.unparse(main))
        self.assertIn("contract.verify_shared_ui_source(selected['tests/gecko/run_ui_visuals.py'])", ast.unparse(main))


if __name__ == '__main__':
    unittest.main()
