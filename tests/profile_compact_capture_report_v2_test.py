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
    def run_current_menu_segment(self, *, old_label=False, action='more'):
        source = (ROOT/'tests/gecko/compact_chrome_v2.py').read_text()
        tree = ast.parse(source)
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_case')
        start = next(index for index, node in enumerate(run.body) if isinstance(node, ast.Assign)
                     and ast.unparse(node) == "before = snapshot('more')")
        end = next(index for index, node in enumerate(run.body) if isinstance(node, ast.AugAssign)
                   and ast.unparse(node) == "command += '-performance'")
        fragment = ast.unparse(ast.Module(body=run.body[start:end], type_ignores=[]))
        if old_label:
            self.assertEqual(fragment.count('浏览器菜单'), 2)
            fragment = fragment.replace('浏览器菜单', '会话选项')
        calls = []
        control = dict(tap=[960,156], touch=[900,80,1020,230])
        def visible(label, shown=True):
            self.assertEqual(label, '浏览器菜单', 'Actual current menu must be observed')
            calls.append(('visible',label,shown))
        scope = dict(command='controlled-current',
            snapshot=lambda name: dict(controls=[None,None,control],actions=4),
            tap=lambda *args: calls.append(('tap',)+args),
            event=lambda command,kind: dict(action=action,actions=5,page=0),
            visible=visible,adb=lambda *args: calls.append(('adb',)+args))
        exec(compile(fragment,'<actual-current-menu>','exec'),scope)
        return calls

    def test_actual_current_compact_menu_segment_observes_browser_menu_and_one_back(self):
        calls = self.run_current_menu_segment()
        self.assertEqual(calls, [
            ('tap','more',[960,156],[900,80,1020,230],'more'),
            ('visible','浏览器菜单',True),('adb','shell','input','keyevent','KEYCODE_BACK'),
            ('visible','浏览器菜单',False)])

    def test_old_menu_label_is_rejected_by_the_same_current_ui_boundary(self):
        with self.assertRaisesRegex(AssertionError, 'Actual current menu'):
            self.run_current_menu_segment(old_label=True)

    def test_wrong_action_cannot_claim_the_browser_menu_was_opened_and_closed(self):
        with self.assertRaises(AssertionError):
            self.run_current_menu_segment(action='environment')

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

    def test_current_compact_consumer_and_fixed_history_are_separate_proofs(self):
        path = 'tests/gecko/run_ui_visuals.py'
        source = (ROOT / path).read_text()
        released = capture.history.historical_bytes(path).decode('utf-8')
        with patch.object(capture.contract, 'verify_shared_ui_source',
                          wraps=capture.contract.verify_shared_ui_source) as old_proof:
            report = capture.verify_current_compact_ui_source(source)
        old_proof.assert_called_once_with(released)
        self.assertNotEqual(source, released)
        self.assertEqual(report['historicalSource'], capture.history.historical_identity(path))
        self.assertTrue(report['historicalProofOnly'])
        self.assertTrue(report['originalWorkloadSemanticsPreserved'])
        self.assertTrue(report['currentCompactWorkloadPreserved'])
        self.assertFalse(report['currentWholeUiWorkloadClaimed'])
        self.assertFalse(report['actualAndroidExecution'])
        self.assertEqual(report['currentMenuLabel'], '浏览器菜单')
        self.assertEqual(report['currentCompactSourceSha256'], hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(set(report['currentCompactMembersAstSha256']),
                         {'adb', 'dump', 'chrome_event', 'focus', 'visible', 'quick_environment_sheet',
                          'compactWorkload', 'compactImport', 'UI_NAVIGATION_CONTRACT', 'ui_capture'})

    def test_current_compact_deadlines_touches_labels_and_callback_wiring_reject_drift(self):
        source = (ROOT / 'tests/gecko/run_ui_visuals.py').read_text()
        changes = (
            ('def chrome_event(command,event):\n        deadline=time.monotonic()+20',
             'def chrome_event(command,event):\n        deadline=time.monotonic()+21'),
            ("after['actions']==sample['actions']==0", "after['actions']==sample['actions']>=0"),
            ("str(control['tap'][0])", "str(control['tap'][0]+1)"),
            ("performance['status']=='passed'", "performance['status']!='failed'"),
            ("label='浏览器菜单'", "label='会话选项'"),
            ("label='浏览器菜单'", "label='其它菜单'"),
            ('capture_compact_v2(adb,lambda', 'capture_compact_v2(dump,lambda'),
            ('UI_NAVIGATION_CONTRACT=2', 'UI_NAVIGATION_CONTRACT=1'),
            ('from compact_chrome_v2 import run_case as capture_compact_v2',
             'from compact_chrome_v2 import other_case as capture_compact_v2'),
            ('return ui_capture.read(deadline=deadline)', 'return ui_capture.read(deadline=None)'),
        )
        for before, after in changes:
            self.assertEqual(source.count(before), 1, before)
            with self.subTest(change=before), self.assertRaises(AssertionError):
                capture.verify_current_compact_ui_source(source.replace(before, after, 1))
        with self.assertRaises(AssertionError):
            capture.verify_current_compact_ui_source(source + '\ndef chrome_event(command,event): return {}\n')

    def test_current_compact_proof_is_the_default_and_before_ref_keeps_its_original_guard(self):
        tree = ast.parse(RUNNER.read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        selected = next(node.value for node in ast.walk(main) if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == 'runner_contract' for target in node.targets))
        expected = ast.parse("contract.verify_shared_ui_source(selected['tests/gecko/run_ui_visuals.py']) if a.before_ref else verify_current_compact_ui_source(selected['tests/gecko/run_ui_visuals.py'])", mode='eval').body
        self.assertEqual(ast.dump(selected, include_attributes=False), ast.dump(expected, include_attributes=False))


if __name__ == '__main__':
    unittest.main()
