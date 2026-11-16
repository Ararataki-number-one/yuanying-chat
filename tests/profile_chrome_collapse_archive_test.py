"""Lossless per-case storage controls, not Android or application acceptance.

The small fixtures below exercise the archive boundary without replacing the
independent native/UI oracle. The companion replay_actual.py additionally uses
the immutable C10 Android diagnostic, including all 120 original event bytes.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import chrome_collapse_case_storage as storage
import chrome_collapse_contract as oracle
from caret_ime_guard import PRIVACY_MAX_BYTES, assert_public_diagnostic_text

SOURCE = 'a' * 40
TREE = 'b' * 40
APK = 'c' * 64
NAMES = ('chrome-collapse-case-360-1.json',
         'chrome-collapse-case-412-1.json',
         'chrome-collapse-case-360-2.json')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def fixture():
    identity = dict(sourceCommit=SOURCE, sourceTree=TREE, apkSha256=APK,
                    sdkBuildIdentity=dict(sourceCommit=SOURCE, sourceTree=TREE,
                                          runId='123456', runAttempt='1'))
    report = dict(navigationContract=3, browserChrome=True, status='passed',
                  actualAndroidExecution=True, actualGeckoExecution=True,
                  actualAndroidTouchExecution=True, sourceCommit=SOURCE,
                  buildIdentity=identity, cases=[],
                  scope='Counterfeit storage fixture only; no device execution.')
    for index, (width, scale) in enumerate(((360, 1), (412, 1), (360, 2)), 1):
        nonce = str(index) * 32
        sample = dict(command='ready', unmodified=' 照片🙂\r\n\\" ',
                      arbitraryFields=[None, False, 17, {'empty': ''}])
        event = dict(kind='collapseSnapshot', result=sample,
                     nativeContext='environment-1', processSlot=0)
        envelope = dict(schema=1, sourceCommit=SOURCE,
                        buildIdentity=dict(copy.deepcopy(identity), scope='Native explanatory scope'),
                        runNonce=nonce, fixtureAction='chromeCollapse', command=1,
                        sequence=1, nativeContext='environment-1', processSlot=0,
                        observedAtElapsedRealtime=1234, event=event)
        # Deliberate whitespace and CRLF: archive hydration may not normalize
        # these original provider bytes even though the outer JSON is compact.
        raw = json.dumps(envelope, ensure_ascii=False, indent=3).replace('\n', '\r\n') + '\n'
        receipt = {key: envelope[key] for key in
                   ('schema', 'runNonce', 'fixtureAction', 'command', 'sequence',
                    'nativeContext', 'processSlot')}
        receipt.update(kind='eventReceipt', eventKind='collapseSnapshot',
                       payloadBytes=len(raw.encode()),
                       payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
        report['cases'].append(dict(
            navigationContract=3, browserChrome=True, viewport=width, fontScale=scale,
            androidUser=0, runNonce=nonce, sourceCommit=SOURCE,
            actualAndroidExecution=True, actualGeckoExecution=True,
            actualAndroidTouchExecution=True, checks=[],
            observations={'ready': copy.deepcopy(sample)},
            nativeUi={'ready': {'rawXml': '<hierarchy>🙂</hierarchy>\r\n'}},
            actualAndroidInputs=[], opaqueEvidence={'keep': ['all', 'fields', None]},
            eventTransfer=dict(runNonce=nonce, fixtureAction='chromeCollapse',
                               processSlot=0, events=[dict(receipt=receipt, rawUtf8=raw)])))
    return report


class CaseStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.base_directory = self.directory
        self.scenario = 0
        self.original = fixture()

    def store(self, value=None):
        return storage.store_auto_collapse_cases(
            self.original if value is None else value, self.directory, SOURCE, APK)

    def load(self, manifest):
        return storage.load_auto_collapse_cases(manifest, self.directory, SOURCE, APK)

    def fresh_store(self):
        self.scenario += 1
        self.directory = self.base_directory / ('scenario-' + str(self.scenario))
        self.directory.mkdir()
        return self.store()

    def replace_case(self, manifest, index, case=None, raw=None):
        ref = manifest['caseFiles'][index]
        path = self.directory / ref['name']
        raw = encoded(case) if raw is None else raw
        path.write_bytes(raw)
        ref.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def assert_rejected(self, manifest):
        with self.assertRaises((ValueError, AssertionError, OSError)):
            self.load(manifest)

    def test_complete_cases_and_exact_provider_bytes_round_trip(self):
        before = copy.deepcopy(self.original)
        manifest = self.store()
        self.assertEqual(self.original, before, 'Writer mutated the original device object')
        self.assertEqual(storage.case_file_names(manifest), NAMES)
        self.assertNotIn('cases', manifest)
        self.assertEqual(manifest['caseStorageVersion'], 1)
        self.assertEqual(set(manifest), (set(before) - {'cases'}) | {'caseStorageVersion', 'caseFiles'})
        for case, ref, name in zip(before['cases'], manifest['caseFiles'], NAMES):
            raw = (self.directory / name).read_bytes()
            self.assertEqual(raw, encoded(case))
            self.assertEqual(ref, dict(name=name, bytes=len(raw),
                                     sha256=hashlib.sha256(raw).hexdigest(),
                                     runNonce=case['runNonce'], viewport=case['viewport'],
                                     fontScale=case['fontScale']))
            assert_public_diagnostic_text(self.directory / name, raw)
        restored = self.load(manifest)
        self.assertEqual(restored, before)
        self.assertEqual(json.dumps(restored, sort_keys=True, ensure_ascii=False),
                         json.dumps(before, sort_keys=True, ensure_ascii=False))
        for old, new in zip(before['cases'], restored['cases']):
            self.assertEqual(set(old), set(new))
            self.assertEqual(old['eventTransfer']['events'][0]['rawUtf8'].encode(),
                             new['eventTransfer']['events'][0]['rawUtf8'].encode())

    def test_legacy_inline_storage_is_not_rewritten(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                inline = copy.deepcopy(self.original)
                inline['navigationContract'] = version
                self.assertEqual(storage.case_file_names(inline), ())
                self.assertEqual(storage.load_auto_collapse_cases(
                    inline, self.directory, SOURCE, APK), inline)

    def test_three_complete_large_cases_fit_individual_unchanged_privacy_cap(self):
        self.assertEqual(PRIVACY_MAX_BYTES, 16 * 1024 * 1024)
        for case in self.original['cases']:
            case['opaqueEvidence']['largeSyntheticText'] = 'x' * (6 * 1024 * 1024)
        aggregate = encoded(self.original)
        self.assertGreater(len(aggregate), PRIVACY_MAX_BYTES)
        with self.assertRaisesRegex(ValueError, 'rejected bounded capture'):
            assert_public_diagnostic_text(Path('unsplit.json'), aggregate)
        manifest = self.store()
        self.assertEqual(self.load(manifest), self.original)
        for name in storage.case_file_names(manifest):
            raw = (self.directory / name).read_bytes()
            self.assertLessEqual(len(raw), PRIVACY_MAX_BYTES)
            assert_public_diagnostic_text(self.directory / name, raw)
        assert_public_diagnostic_text(Path('case-index.json'), encoded(manifest))

    def test_single_oversized_case_is_rejected_without_truncation(self):
        self.original['cases'][0]['opaqueEvidence']['oversized'] = 'x' * PRIVACY_MAX_BYTES
        with self.assertRaises((ValueError, AssertionError)):
            self.store()

    def test_missing_case_fails(self):
        manifest = self.store()
        (self.directory / NAMES[1]).unlink()
        self.assert_rejected(manifest)

    def test_existing_originals_are_reused_but_never_overwritten(self):
        manifest = self.store()
        before = {name: (self.directory / name).read_bytes() for name in NAMES}
        self.assertEqual(self.store(), manifest)
        changed = copy.deepcopy(self.original)
        changed['cases'][0]['opaqueEvidence']['keep'].append('different invocation data')
        with self.assertRaisesRegex(ValueError, 'refusing to replace'):
            self.store(changed)
        self.assertEqual({name: (self.directory / name).read_bytes() for name in NAMES}, before)

    def test_tampered_case_bytes_fail_exact_digest(self):
        manifest = self.store()
        path = self.directory / NAMES[0]
        raw = path.read_bytes()
        self.assertIn(b'fields', raw)
        path.write_bytes(raw.replace(b'fields', b'FIELDS', 1))
        self.assert_rejected(manifest)

    def test_hash_and_byte_count_pins_are_mandatory_and_typed(self):
        manifest = self.store()
        for key, value in (('sha256', '0' * 64), ('sha256', '0' * 63),
                           ('bytes', manifest['caseFiles'][0]['bytes'] + 1),
                           ('bytes', True), ('bytes', -1), ('bytes', 16 * 1024 * 1024 + 1)):
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(manifest)
                changed['caseFiles'][0][key] = value
                self.assert_rejected(changed)

    def test_paths_cannot_escape_or_alias_fixed_case_names(self):
        manifest = self.store()
        for name in ('../' + NAMES[0], '/tmp/' + NAMES[0], './' + NAMES[0],
                     'sub/' + NAMES[0], 'sub\\' + NAMES[0], NAMES[0] + '\x00',
                     NAMES[0].upper(), 'unrelated.json'):
            with self.subTest(name=name):
                changed = copy.deepcopy(manifest)
                changed['caseFiles'][0]['name'] = name
                self.assert_rejected(changed)

    def test_symlink_case_and_symlink_directory_are_rejected(self):
        manifest = self.store()
        target = self.directory / 'held-original.json'
        (self.directory / NAMES[0]).rename(target)
        (self.directory / NAMES[0]).symlink_to(target)
        self.assert_rejected(manifest)
        (self.directory / NAMES[0]).unlink()
        target.rename(self.directory / NAMES[0])
        alias = self.directory / 'alias'
        alias.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises((ValueError, AssertionError, OSError)):
            storage.load_auto_collapse_cases(manifest, alias, SOURCE, APK)

    def test_nonregular_case_is_rejected(self):
        manifest = self.store()
        path = self.directory / NAMES[0]
        path.unlink()
        path.mkdir()
        self.assert_rejected(manifest)

    def test_missing_extra_duplicate_or_reordered_references_fail(self):
        manifest = self.store()
        alterations = [manifest['caseFiles'][:2], manifest['caseFiles'] + [manifest['caseFiles'][0]],
                       [manifest['caseFiles'][0], manifest['caseFiles'][0], manifest['caseFiles'][2]],
                       list(reversed(manifest['caseFiles']))]
        for refs in alterations:
            with self.subTest(refs=[r['name'] for r in refs]):
                changed = copy.deepcopy(manifest)
                changed['caseFiles'] = refs
                self.assert_rejected(changed)

    def test_manifest_version_and_inline_ambiguity_are_rejected(self):
        manifest = self.store()
        for value in (0, 2, True, '1', None):
            with self.subTest(value=value):
                changed = copy.deepcopy(manifest)
                changed['caseStorageVersion'] = value
                self.assert_rejected(changed)
        for key in ('caseStorageVersion', 'caseFiles'):
            changed = copy.deepcopy(manifest)
            del changed[key]
            self.assert_rejected(changed)
        changed = copy.deepcopy(manifest)
        changed['cases'] = self.original['cases']
        self.assert_rejected(changed)

    def test_case_cohort_and_nonce_must_match_reference(self):
        manifest = self.store()
        for key, value in (('viewport', 412), ('fontScale', 2), ('runNonce', 'f' * 32),
                           ('viewport', True), ('runNonce', 'not-a-nonce')):
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(manifest)
                changed['caseFiles'][0][key] = value
                self.assert_rejected(changed)

    def test_duplicate_case_nonce_is_not_a_second_invocation(self):
        duplicate = copy.deepcopy(self.original['cases'][0])
        duplicate['viewport'] = 412
        duplicate['fontScale'] = 1
        self.original['cases'][1] = duplicate
        with self.assertRaisesRegex(ValueError, 'duplicate case invocation'):
            self.store()

    def test_duplicate_manifest_nonce_fails_before_loading_a_second_case(self):
        manifest = self.store()
        manifest['caseFiles'][1]['runNonce'] = manifest['caseFiles'][0]['runNonce']
        with self.assertRaisesRegex(ValueError, 'duplicate or invalid case invocation'):
            self.load(manifest)

    def test_malformed_duplicate_key_and_nonfinite_case_json_fail_after_rehash(self):
        for bad in (b'{', b'[]\n', b'{"sourceCommit":"a","sourceCommit":"b"}\n',
                    b'{"number":NaN}\n', b'{"number":Infinity}\n', b'\xff\n'):
            with self.subTest(raw=bad):
                manifest = self.fresh_store()
                self.replace_case(manifest, 0, raw=bad)
                self.assert_rejected(manifest)

    def test_foreign_selected_source_and_apk_are_rejected(self):
        manifest = self.store()
        for source, apk in (('f' * 40, APK), (SOURCE, 'f' * 64)):
            with self.subTest(source=source, apk=apk):
                with self.assertRaises((ValueError, AssertionError)):
                    storage.load_auto_collapse_cases(manifest, self.directory, source, apk)

    def test_case_source_and_event_owner_cannot_change_even_after_rehash(self):
        manifest = self.store()
        case = copy.deepcopy(self.original['cases'][0])
        case['sourceCommit'] = 'f' * 40
        self.replace_case(manifest, 0, case=case)
        self.assert_rejected(manifest)
        for key in ('sourceCommit', 'sourceTree', 'apkSha256', 'runId', 'runAttempt'):
            with self.subTest(key=key):
                manifest = self.fresh_store()
                case = copy.deepcopy(self.original['cases'][0])
                row = case['eventTransfer']['events'][0]
                envelope = json.loads(row['rawUtf8'])
                if key in ('runId', 'runAttempt'):
                    envelope['buildIdentity']['sdkBuildIdentity'][key] = '2'
                else:
                    envelope['buildIdentity'][key] = 'f' * (64 if key == 'apkSha256' else 40)
                row['rawUtf8'] = encoded(envelope).decode()
                row['receipt'].update(payloadBytes=len(row['rawUtf8'].encode()),
                                      payloadSha256=hashlib.sha256(row['rawUtf8'].encode()).hexdigest())
                self.replace_case(manifest, 0, case=case)
                self.assert_rejected(manifest)

    def test_event_nonce_and_raw_duplicate_keys_are_rejected(self):
        for mode in ('nonce', 'duplicate-key'):
            with self.subTest(mode=mode):
                manifest = self.fresh_store()
                case = copy.deepcopy(self.original['cases'][0])
                row = case['eventTransfer']['events'][0]
                if mode == 'nonce':
                    event = json.loads(row['rawUtf8'])
                    event['runNonce'] = 'e' * 32
                    row['rawUtf8'] = encoded(event).decode()
                else:
                    row['rawUtf8'] = row['rawUtf8'].replace('"schema": 1', '"schema": 1, "schema": 1', 1)
                row['receipt'].update(payloadBytes=len(row['rawUtf8'].encode()),
                                      payloadSha256=hashlib.sha256(row['rawUtf8'].encode()).hexdigest())
                self.replace_case(manifest, 0, case=case)
                self.assert_rejected(manifest)

    def test_unknown_reference_fields_cannot_carry_a_second_locator(self):
        manifest = self.store()
        manifest['caseFiles'][0]['path'] = NAMES[0]
        self.assert_rejected(manifest)

    def producer_block(self):
        """Execute the actual new archive boundary, excluding the Android workload."""
        path = ROOT / 'tests/gecko/run_ui_visuals.py'
        tree = ast.parse(path.read_text())
        matches = []
        for phase in tree.body:
            if not isinstance(phase, ast.Try):
                continue
            for index, node in enumerate(phase.body):
                if isinstance(node, ast.ImportFrom) and node.module == 'chrome_collapse_contract':
                    matches.append(phase.body[index:index + 5])
        self.assertEqual(len(matches), 1)
        nodes = matches[0]
        self.assertEqual(len(nodes), 5)
        self.assertIsInstance(nodes[-1], ast.Assign)
        self.assertEqual([target.id for target in nodes[-1].targets], ['auto_collapse'])
        (self.directory / 'ui-build-comparison.json').write_bytes(encoded({'currentSha256': APK}))
        program = compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                          str(path), 'exec')
        namespace = dict(json=json, out=self.directory, source=SOURCE, auto_collapse=self.original)
        return program, namespace

    def test_producer_original_oracle_rejection_prevents_any_case_write(self):
        program, namespace = self.producer_block()
        with patch.object(oracle, 'verify_auto_collapse', side_effect=ValueError('original oracle rejected')):
            with patch.object(storage, 'store_auto_collapse_cases', wraps=storage.store_auto_collapse_cases) as writer:
                with self.assertRaisesRegex(ValueError, 'original oracle rejected'):
                    exec(program, namespace)
                writer.assert_not_called()
        self.assertFalse(any((self.directory / name).exists() for name in NAMES))

    def test_producer_calls_original_oracle_before_actual_lossless_storage(self):
        # The stub verifies only ordering. It is not an Android/oracle positive;
        # replay_actual.py separately verifies the complete real C10 object.
        program, namespace = self.producer_block()
        order = []
        def gate(value, source, apk):
            self.assertIs(value, self.original)
            self.assertEqual((source, apk), (SOURCE, APK))
            self.assertFalse(any((self.directory / name).exists() for name in NAMES))
            order.append('original oracle')
        original_writer = storage.store_auto_collapse_cases
        def writer(*args):
            order.append('store complete cases')
            return original_writer(*args)
        with patch.object(oracle, 'verify_auto_collapse', side_effect=gate):
            with patch.object(storage, 'store_auto_collapse_cases', side_effect=writer):
                exec(program, namespace)
        self.assertEqual(order, ['original oracle', 'store complete cases'])
        self.assertEqual(self.load(namespace['auto_collapse']), self.original)


if __name__ == '__main__':
    unittest.main()
