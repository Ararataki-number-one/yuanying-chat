#!/usr/bin/env python3
"""Checked-apksigner output parsing; no APK/device/signature acceptance claim.

The two complete outputs below are the original failed capture artifacts from
source 4e99, run 42469821239/a1: API32 artifact 13612709710 and API35
artifact 13613646032. Their public temporary certificates differ by design.
"""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'gecko'))
from capture_glass_navigation import parse_single_signing_certificate

API32_OUTPUT = b'Verifies\nVerified using v1 scheme (JAR signing): false\nVerified using v2 scheme (APK Signature Scheme v2): true\nVerified using v3 scheme (APK Signature Scheme v3): false\nVerified using v3.1 scheme (APK Signature Scheme v3.1): false\nVerified using v3.2 scheme (APK Signature Scheme v3.2): false\nVerified using v4 scheme (APK Signature Scheme v4): false\nVerified for SourceStamp: false\nNumber of signers: 1\nV2 Signer: certificate DN: CN=SyntheticIntegration\nV2 Signer: certificate SHA-256 digest: 0532902edbe96f71bcb202edb5bc661d96fd912d00f66817c54994dec64be334\nV2 Signer: certificate SHA-1 digest: 3790644553071275d65b8dd7ba09516d3c520cf7\nV2 Signer: certificate MD5 digest: 95409234e49e3362c01e4b92bf937e56\nV2 Signer: key algorithm: RSA\nV2 Signer: key size (bits): 2048\nV2 Signer: public key SHA-256 digest: 21e6150bcfd43d9b564209d391dd0d00a85efd4753524180ec5f6a21effa3d33\nV2 Signer: public key SHA-1 digest: e273ae662f4c5a081d7aa4fa0f874fa22c979848\nV2 Signer: public key MD5 digest: ecd1ba456ccac6012c529c1e7dca0c1d\n'
API32_RAW_SHA256 = 'f29181436870f220bfd9955d45c2a590a2c1bd7c09dd9a3b38072e6a03149fa5'

API35_OUTPUT = b'Verifies\nVerified using v1 scheme (JAR signing): false\nVerified using v2 scheme (APK Signature Scheme v2): true\nVerified using v3 scheme (APK Signature Scheme v3): false\nVerified using v3.1 scheme (APK Signature Scheme v3.1): false\nVerified using v3.2 scheme (APK Signature Scheme v3.2): false\nVerified using v4 scheme (APK Signature Scheme v4): false\nVerified for SourceStamp: false\nNumber of signers: 1\nV2 Signer: certificate DN: CN=SyntheticIntegration\nV2 Signer: certificate SHA-256 digest: ea87bbfb19c3b8bdcdb78956730e9cd3a600e9e2bd59be09ecedcc2990c8884e\nV2 Signer: certificate SHA-1 digest: e4a1b6b7ddafd7b802d8b3e378a62ea160c5fca0\nV2 Signer: certificate MD5 digest: 0287de1ff10f8892eb01b5e09425d8f0\nV2 Signer: key algorithm: RSA\nV2 Signer: key size (bits): 2048\nV2 Signer: public key SHA-256 digest: f0801e42a6f967cb8a3462ec77f872449ffeaf978a8f9961eba1cb8f48ee9cf1\nV2 Signer: public key SHA-1 digest: 117a5b6d62a8b3469790a76a1c2f7aa54e651f72\nV2 Signer: public key MD5 digest: 6483685323039cb95b1f714ca185eec9\n'
API35_RAW_SHA256 = '2012950278b6ed151d1962ee1d1b4005c34594eda4b0d35f13924b945b58bd7d'

class GlassCaptureSignatureTest(unittest.TestCase):
    def test_original_build_tools37_outputs_keep_one_actual_certificate(self):
        for raw, expected_raw, expected_cert in (
            (API32_OUTPUT, API32_RAW_SHA256, '0532902edbe96f71bcb202edb5bc661d96fd912d00f66817c54994dec64be334'),
            (API35_OUTPUT, API35_RAW_SHA256, 'ea87bbfb19c3b8bdcdb78956730e9cd3a600e9e2bd59be09ecedcc2990c8884e'),
        ):
            with self.subTest(expected_cert=expected_cert):
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_raw)
                self.assertEqual(parse_single_signing_certificate(raw), expected_cert)

    def test_legacy_numbered_signer_format_stays_supported(self):
        legacy = API35_OUTPUT.replace(b'V2 Signer:', b'Signer #1')
        self.assertEqual(parse_single_signing_certificate(legacy),
                         'ea87bbfb19c3b8bdcdb78956730e9cd3a600e9e2bd59be09ecedcc2990c8884e')

    def test_crlf_output_keeps_the_same_certificate(self):
        self.assertEqual(parse_single_signing_certificate(API32_OUTPUT.replace(b'\n', b'\r\n')),
                         parse_single_signing_certificate(API32_OUTPUT))

    def test_missing_or_conflicting_verifier_summary_cannot_pass(self):
        for raw in (
            API35_OUTPUT.replace(b'Verifies\n', b''),
            API35_OUTPUT.replace(b'Verifies\n', b'DOES NOT VERIFY\n'),
            b'Verifies\n' + API35_OUTPUT,
            API35_OUTPUT.replace(b'Number of signers: 1\n', b''),
            API35_OUTPUT.replace(b'Number of signers: 1', b'Number of signers: 0'),
            API35_OUTPUT.replace(b'Number of signers: 1', b'Number of signers: 2'),
            API35_OUTPUT + b'Number of signers: 1\n',
            API35_OUTPUT + b'Number of signers: 2\n',
        ):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                parse_single_signing_certificate(raw)

    def test_duplicate_records_cannot_be_deduplicated_into_one_signer(self):
        record = next(line for line in API35_OUTPUT.splitlines() if b'certificate SHA-256 digest:' in line)
        for extra in (record, record.replace(b'V2 Signer:', b'Signer #1'),
                      record.replace(b'ea87bbfb', b'0a87bbfb')):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_single_signing_certificate(API35_OUTPUT + extra + b'\n')

    def test_multiple_legacy_signers_cannot_pass_even_with_forged_count(self):
        record = next(line for line in API35_OUTPUT.splitlines() if b'certificate SHA-256 digest:' in line)
        multi = API35_OUTPUT + record.replace(b'V2 Signer:', b'Signer #2') + b'\n'
        with self.assertRaises(ValueError):
            parse_single_signing_certificate(multi)

    def test_unknown_prefix_cannot_supply_a_fingerprint(self):
        for prefix in (b'Unknown Signer:', b'V3 Signer:', b'Signer #2', b'V2 Signer #1:'):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                parse_single_signing_certificate(API35_OUTPUT.replace(b'V2 Signer:', prefix))

    def test_unknown_extra_certificate_record_is_not_ignored(self):
        extra = b'Unknown Signer: certificate SHA-256 digest: ' + b'f' * 64 + b'\n'
        with self.assertRaises(ValueError):
            parse_single_signing_certificate(API35_OUTPUT + extra)

    def test_truncated_nonhex_or_contaminated_digest_cannot_pass(self):
        fingerprint = b'ea87bbfb19c3b8bdcdb78956730e9cd3a600e9e2bd59be09ecedcc2990c8884e'
        for damaged in (fingerprint[:-1], fingerprint + b'f', b'g' + fingerprint[1:],
                        fingerprint + b' injected', fingerprint.upper()):
            with self.subTest(damaged=damaged), self.assertRaises(ValueError):
                parse_single_signing_certificate(API35_OUTPUT.replace(fingerprint, damaged))

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaises(UnicodeDecodeError):
            parse_single_signing_certificate(API35_OUTPUT + b'\xff')


if __name__ == '__main__':
    unittest.main()
