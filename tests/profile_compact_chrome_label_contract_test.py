"""Keep capture timing controls while selecting the approved exact label oracle."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/compact-chrome-capture-host/run.py'
TEMPLATE = ROOT / 'tests/compact-chrome-capture-host/CompactChromeCaptureHost.java'
SPEC = importlib.util.spec_from_file_location('compact_capture_label_contract', RUNNER)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class CompactChromeLabelContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Compile the actual two host methods and constants. The adapter only
        # provides text values; it does not execute Android or replace getters.
        cls.temporary = tempfile.TemporaryDirectory(prefix='compact-label-contract-')
        cls.directory = Path(cls.temporary.name)
        text = TEMPLATE.read_text()
        constants = [line.strip() for line in text.splitlines()
                     if line.strip().startswith('static final String LEGACY_REAL_LATENCY=')]
        if len(constants) != 1:
            raise AssertionError('One explicit current/legacy label constant pair is required')
        java_home = os.environ.get('JAVA_HOME')
        cls.java = str(Path(java_home) / 'bin/java') if java_home else shutil.which('java')
        javac = str(Path(java_home) / 'bin/javac') if java_home else shutil.which('javac')
        if not cls.java or not javac:
            raise RuntimeError('The capture contract requires the existing JDK')
        source = ('public class StrictCompactLabel {\n' + constants[0] + '\n'
                  + CAPTURE.member(text, 'static String expectedRealLatency(') + '\n'
                  + CAPTURE.member(text, 'static boolean realState(') + '\n'
                  + 'public static void main(String[] args){CompactChromeIntegrationActivity a=new CompactChromeIntegrationActivity();'
                    'a.designChrome.latencyWord.text=args[0];a.designChrome.stateWord.text=args[1];System.out.println(realState(a));}\n}\n'
                    'class CompactChromeIntegrationActivity{final DesignChrome designChrome=new DesignChrome();}\n'
                    'class DesignChrome{final TextView latencyWord=new TextView(),stateWord=new TextView();}\n'
                    'class TextView{String text;String getText(){return text;}}\n')
        path = cls.directory / 'StrictCompactLabel.java'
        path.write_text(source)
        subprocess.run([javac, '-encoding', 'UTF-8', '-d', str(cls.directory), str(path)],
                       check=True, capture_output=True, text=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def observe(self, mode, text, state='未配置'):
        return subprocess.run([self.java, '-Dcompact.captureLabel=' + mode, '-cp',
                               str(self.directory), 'StrictCompactLabel', text, state],
                              capture_output=True, text=True, timeout=10)

    def test_approved_whole_source_selects_only_the_approved_fixed_expectation(self):
        raw = (ROOT / 'app/src/main/java/local/pocketchat/DesignChrome.java').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '9a923e78a2fea39f55a50da3a37ac5bf42c35fa2b26b0fa6a7397b4dcc7533da')
        contract = CAPTURE.label_contract(raw.decode())
        self.assertEqual(contract['approvedBaseline'], '4363dbc04df80d5c82ba966248e47a3fd69cbcc8')
        self.assertEqual(contract['mode'], 'approved-glass')
        self.assertEqual(contract['expectedRealLatency'], '延迟未测')
        self.assertEqual(contract['legacyExpectedRealLatency'], '延迟未测（等待连接）')

    def test_unknown_and_mutated_production_sources_fail_closed(self):
        raw = (ROOT / 'app/src/main/java/local/pocketchat/DesignChrome.java').read_text()
        for mutant in (raw + '\n', raw.replace('class DesignChrome', 'class AlteredChrome', 1),
                       raw.replace('DesignUi.GLASS_INK', 'ReferenceUi.TEXT', 1), ''):
            with self.subTest(mutant=hashlib.sha256(mutant.encode()).hexdigest()):
                with self.assertRaisesRegex(ValueError, 'Unreviewed DesignChrome'):
                    CAPTURE.label_contract(mutant)

    def test_only_the_two_documented_original_sources_select_the_legacy_oracle(self):
        self.assertEqual(CAPTURE.LEGACY_CHROME_SOURCES, {
            '5b682f613f26c48be896f4623599ae38f7369a35e58aa0709bff45c75e2115f1': '62a0ff6e44ba08e4bbf28149a11d3f47a4f6a642',
            '1ee7c2762c3b077166db3cbea363bd4481e527fc33c2b2491b8db7bffcf9ae43': '4644e90b0f00507f15da9b223b808cf19d345e58',
        })
        self.assertNotIn(CAPTURE.APPROVED_CHROME_SHA256, CAPTURE.LEGACY_CHROME_SOURCES)

    def test_actual_current_presentation_passes_only_its_selected_oracle(self):
        approved = self.observe('approved-glass', '延迟未测')
        self.assertEqual((approved.returncode, approved.stdout.strip()), (0, 'true'))
        legacy = self.observe('legacy', '延迟未测')
        self.assertEqual((legacy.returncode, legacy.stdout.strip()), (0, 'false'))

    def test_wrong_or_legacy_text_cannot_satisfy_the_approved_oracle(self):
        for text in ('延迟未测（等待连接）', '42 ms（02:00）', '', '延迟未测 '):
            with self.subTest(text=text):
                result = self.observe('approved-glass', text)
                self.assertEqual((result.returncode, result.stdout.strip()), (0, 'false'))
        legacy = self.observe('legacy', '延迟未测（等待连接）')
        self.assertEqual((legacy.returncode, legacy.stdout.strip()), (0, 'true'))

    def test_wrong_network_state_and_unselected_contract_cannot_pass(self):
        state = self.observe('approved-glass', '延迟未测', '已连接')
        self.assertEqual((state.returncode, state.stdout.strip()), (0, 'false'))
        for mode in ('', 'unknown'):
            result = self.observe(mode, '延迟未测')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('exact source-selected', result.stderr)

    def test_all_original_cases_callbacks_deadlines_and_synthetic_expectations_remain_exact(self):
        # These immutable method digests were read from approved commit4363.
        # No Git/history read or expectation derived from current reports is used.
        expected = {
            'static void current()': '29530fb8cdb6981f4782808a9b70040867c30b34e18072df9e3e836bfa2c900c',
            'static void before()': '2488436320f94d8774fdbc0a6b4792eed3758bd39b33d1eec695b7d0e319958a',
            'static boolean syntheticState(': 'f8aec055d2aee4d426d4d352837b08e88ae46866adf4c1387639e4eec566dbfa',
            'static CompactChromeIntegrationActivity overwritten(': '3100e47719d607bdfc5fca81048d1540b816bce5e51383be18ce4f767592dde0',
            'public static void main(': 'c780fff37f639a16616d9c62d3618520407d640d168eb80dd27f2dc05258e938',
        }
        text = TEMPLATE.read_text()
        for name, digest in expected.items():
            with self.subTest(method=name):
                self.assertEqual(hashlib.sha256(CAPTURE.member(text, name).encode()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
