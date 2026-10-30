"""Permit the reviewed CI precondition without weakening any original UI gate."""
import ast
import hashlib
from pathlib import Path
import unittest

import ui_visual_preservation_contract as contract


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/gecko/run_ui_visuals.py'
CONTRACT = ROOT / 'tests/ui_visual_preservation_contract.py'
BLOCK = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
         "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")


class UiVisualDeviceCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.source = RUNNER.read_text()
        self.assertEqual(self.source.count(BLOCK), 1)

    def rejected_change(self, before, after):
        self.assertEqual(self.source.count(before), 1)
        with self.assertRaises(AssertionError):
            contract.verify_shared_ui_source(self.source.replace(before, after, 1))

    def test_reviewed_preparation_and_legacy_without_it_preserve_original_digests(self):
        for source in (self.source, self.source.replace(BLOCK, '', 1)):
            with self.subTest(with_preparation=source == self.source):
                report = contract.verify_shared_ui_source(source)
                self.assertEqual(report['normalizedModuleAstSha256'],
                    '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
                self.assertEqual(report['normalizedCaptureAstSha256'],
                    '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')
                self.assertTrue(report['authorizedDownloadLabelAddition'])
                self.assertTrue(report['originalWorkloadSemanticsPreserved'])

    def test_nonsemantic_formatting_and_utf8_cookie_still_pass(self):
        for source in (self.source, self.source.replace(BLOCK, '', 1)):
            formatted = '# coding: utf-8\n# Nonsemantic comment.\n' + ast.unparse(ast.parse(source)) + '\n'
            self.assertTrue(contract.verify_shared_ui_source(formatted)['originalWorkloadSemanticsPreserved'])

    def test_encoding_cookie_still_uses_real_utf8_bytes(self):
        with self.assertRaises(AssertionError):
            contract.verify_shared_ui_source('# coding: latin-1\n' + self.source)

    def test_import_module_function_alias_and_extra_names_are_not_whitelisted(self):
        before = 'from ui_test_device import prepare_workflow as prepare_ui_test_device'
        for after in ('from other_device import prepare_workflow as prepare_ui_test_device',
                      'from ui_test_device import prepare as prepare_ui_test_device',
                      'from ui_test_device import prepare_workflow as other_preparation',
                      'from ui_test_device import prepare_workflow as prepare_ui_test_device, extra',
                      'from .ui_test_device import prepare_workflow as prepare_ui_test_device'):
            with self.subTest(after=after):
                self.rejected_change(before, after)

    def test_all_call_arguments_report_path_and_serialization_are_exact(self):
        changes = [
            ('ui-test-device-isolation.json', 'other-report.json'),
            ('prepare_ui_test_device(adb,serial=args.serial,environment=os.environ)',
             "prepare_ui_test_device(adb,serial='physical-device',environment=os.environ)"),
            ('prepare_ui_test_device(adb,serial=args.serial,environment=os.environ)',
             'prepare_ui_test_device(other_adb,serial=args.serial,environment=os.environ)'),
            ('prepare_ui_test_device(adb,serial=args.serial,environment=os.environ)',
             'prepare_ui_test_device(adb,serial=args.serial,environment={})'),
            ('prepare_ui_test_device(adb,serial=args.serial,environment=os.environ)',
             "prepare_ui_test_device(adb,serial=args.serial,environment=os.environ,extra=adb('shell','pm','clear','local.pocketchat.test'))"),
            ('sort_keys=True,indent=2', 'sort_keys=False,indent=2'),
            ("+'\\n')", "+'')"),
        ]
        # Select the exact new block so unchanged old JSON serialization stays protected too.
        for before, after in changes:
            with self.subTest(before=before):
                self.assertEqual(BLOCK.count(before), 1)
                mutated = self.source.replace(BLOCK, BLOCK.replace(before, after, 1), 1)
                with self.assertRaises(AssertionError):
                    contract.verify_shared_ui_source(mutated)

    def test_duplicate_partial_and_reordered_preparation_are_rejected(self):
        imported, call = BLOCK.splitlines(keepends=True)
        for replacement in (BLOCK + BLOCK, imported + imported + call,
                            imported, call, call + imported,
                            imported + "adb('shell','getprop','unreviewed')\n" + call):
            with self.subTest(replacement=replacement):
                with self.assertRaises(AssertionError):
                    contract.verify_shared_ui_source(self.source.replace(BLOCK, replacement, 1))

    def test_preparation_must_remain_immediately_between_original_adb_and_dump(self):
        original = self.source.replace(BLOCK, '', 1)
        for marker in ('def adb(', 'def click(', 'def capture('):
            with self.subTest(marker=marker):
                moved = original.replace(marker, BLOCK + marker, 1)
                with self.assertRaises(AssertionError):
                    contract.verify_shared_ui_source(moved)
        with self.assertRaises(AssertionError):
            contract.verify_shared_ui_source(self.source.replace(BLOCK, BLOCK + 'extra_read = os.environ.get("EXTRA")\n', 1))

    def test_nested_import_or_alias_rebinding_is_not_normalized_away(self):
        moved = self.source.replace(BLOCK, '', 1)
        nested = 'def unreviewed_preparation():\n' + ''.join('    ' + line for line in BLOCK.splitlines(keepends=True))
        for source in (nested + moved,
                       self.source.replace(BLOCK, 'prepare_ui_test_device = other_preparation\n' + BLOCK, 1),
                       self.source + '\nimport ui_test_device\n'):
            with self.subTest(source=source[:80]):
                with self.assertRaises(AssertionError):
                    contract.verify_shared_ui_source(source)

    def test_old_capture_assertions_transport_and_download_guards_still_reject_drift(self):
        changes = [
            ("assert '已选 8 个' in xml", 'assert True'),
            ("timeout=90).decode(errors='replace')", "timeout=91).decode(errors='replace')"),
            ('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0'),
            ('verify_captures(records,source)', 'verify_captures(records)'),
            ('        verify_download_location(record,source)', '        pass'),
            ("if value.get('nonce')==label_nonce:payloads.append(raw)", 'payloads.append(raw)'),
        ]
        for before, after in changes:
            with self.subTest(before=before):
                self.rejected_change(before, after)

    def test_original_verifier_assertions_and_expected_digests_are_unchanged(self):
        tree = ast.parse(CONTRACT.read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'verify_shared_ui_source')
        function = contract.original_ui_privacy_verifier_function(function)
        added = ast.parse('remove_reviewed_ui_device_preparation(tree)').body[0]
        positions = [i for i, node in enumerate(function.body)
                     if ast.dump(node, include_attributes=False) == ast.dump(added, include_attributes=False)]
        self.assertEqual(len(positions), 1)
        del function.body[positions[0]]
        self.assertEqual(hashlib.sha256(ast.dump(function, include_attributes=False).encode()).hexdigest(),
                         '9a04ddb0829797388945c022a73959ab674614915e168183d8316dd471260491')
        self.assertEqual(contract.ORIGINAL_MODULE_AST,
                         '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
        self.assertEqual(contract.ORIGINAL_CAPTURE_AST,
                         '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')



    def test_diagnostic_additions_restore_the_entire_previous_runner(self):
        raw = contract.original_ui_diagnostic_privacy_bytes(self.source.encode())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '1f50898788396c90500f2f70737fb5a5bd6eed6aeb2d2d989c97a24bf0f05913')
        self.assertTrue(contract.verify_shared_ui_source(raw.decode())['originalWorkloadSemanticsPreserved'])

    def test_only_complete_exact_diagnostic_import_and_writes_are_normalized(self):
        source = self.source
        imported = contract.DIAGNOSTIC_PRIVACY_IMPORT
        changed = [source.replace(imported, '', 1), source.replace(imported, imported + imported, 1),
                   source.replace('from diagnostic_capture_privacy import checked_text',
                                  'from other_capture import checked_text', 1),
                   source.replace('from diagnostic_capture_privacy import checked_text',
                                  'from diagnostic_capture_privacy import checked_text as other', 1),
                   source.replace("checked_text(adb('logcat','-d'))[0]",
                                  "checked_text(adb('logcat','-d'))[1]", 1)]
        for previous, added in contract.DIAGNOSTIC_PRIVACY_WRITES:
            changed.extend((source.replace(added, previous, 1), source.replace(added, added + ';' + added, 1)))
        moved = source.replace(imported, '', 1)
        changed.append(moved.replace('def adb(', imported + 'def adb(', 1))
        previous, added = contract.DIAGNOSTIC_PRIVACY_WRITES[0]
        changed.append(source.replace(added, previous, 1) + '\n' + added + '\n')
        for index, value in enumerate(changed):
            with self.subTest(mutation=index), self.assertRaises(AssertionError):
                contract.verify_shared_ui_source(value)

    def test_diagnostic_verifier_call_normalizer_rejects_missing_duplicate_and_moved(self):
        original = CONTRACT.read_text()
        statement = '    remove_reviewed_diagnostic_privacy(tree)\n'
        self.assertEqual(original.count(statement), 1)
        values = [original.replace(statement, '', 1), original.replace(statement, statement + statement, 1)]
        moved = original.replace(statement, '', 1)
        values.append(moved.replace('    remove_reviewed_ui_device_preparation(tree)\n',
                                    '    remove_reviewed_ui_device_preparation(tree)\n' + statement, 1))
        for value in values:
            tree = ast.parse(value)
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                            and node.name == 'verify_shared_ui_source')
            with self.assertRaises(AssertionError):
                contract.original_ui_privacy_verifier_function(function)


if __name__ == '__main__':
    unittest.main()
