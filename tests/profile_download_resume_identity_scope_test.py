"""Exercise the real Android identity shape without changing original F06 controls."""
import copy
import hashlib
import json
import unittest

from profile_download_resume_contract_test import bound_metadata, contract

SCOPE = 'Installed synthetic integration APK bytes and embedded source stamp only'


def reseal(device):
    """Bind mutations into complete provider bytes, so identity checks must reject them."""
    value = device['savedFileDeletion']['downloadResume']
    record = device['eventTransport']['invocations'][0]['events'][0]
    envelope = json.loads(record['rawUtf8'])
    envelope['event']['result'] = copy.deepcopy(value)
    envelope['buildIdentity'] = copy.deepcopy(value['buildIdentity'])
    device['steps'] = [copy.deepcopy(envelope['event'])]
    raw = json.dumps(envelope, ensure_ascii=False, separators=(',', ':')) + '\n'
    record['rawUtf8'] = raw
    record['receipt'].update(payloadBytes=len(raw.encode()),
                             payloadSha256=hashlib.sha256(raw.encode()).hexdigest())


def actual_identity_shape():
    device = bound_metadata()
    device['savedFileDeletion']['downloadResume']['buildIdentity']['scope'] = SCOPE
    reseal(device)
    return device


class DownloadResumeIdentityScopeTest(unittest.TestCase):
    def test_android_reader_explanation_with_complete_original_bytes(self):
        device = actual_identity_shape()
        self.assertNotEqual(device['savedFileDeletion']['downloadResume']['buildIdentity'],
                            device['eventTransport']['buildIdentity'])
        before = copy.deepcopy(device)
        self.assertEqual(contract.verify_download_resume_invocation(device, 'a'*40)['checks'], 20)
        self.assertEqual(device, before, 'Verifier must not normalize original evidence in place')
        device['eventTransport']['buildIdentity']['scope'] = SCOPE
        self.assertEqual(contract.verify_download_resume_invocation(device, 'a'*40)['checks'], 20)

    def test_only_the_exact_explanation_is_optional(self):
        for value in ('other scope', '', None, True, 1, {}, []):
            for side in ('result', 'transport'):
                device = actual_identity_shape()
                identity = (device['savedFileDeletion']['downloadResume']['buildIdentity']
                            if side == 'result' else device['eventTransport']['buildIdentity'])
                identity['scope'] = value
                reseal(device)
                with self.subTest(value=value, side=side), self.assertRaises(ValueError):
                    contract.verify_download_resume_invocation(device, 'a'*40)

    def test_all_other_identity_fields_remain_exact_and_typed(self):
        mutations = [('extra', 'unexpected'), ('schema', True), ('dirtySource', 0),
                     ('versionCode', 71.0), ('apkBytes', True), ('version', '2.0.19'),
                     ('sourceCommit', 'f'*40), ('sourceTree', 'f'*40),
                     ('apkSha256', 'f'*64), ('buildStampSha256', 'f'*64),
                     ('sdkCoordinate', 'foreign'), ('package', 'local.pocketchat')]
        for key, value in mutations:
            device = actual_identity_shape()
            device['savedFileDeletion']['downloadResume']['buildIdentity'][key] = value
            reseal(device)
            with self.subTest(key=key), self.assertRaises(ValueError):
                contract.verify_download_resume_invocation(device, 'a'*40)
        for key in bound_metadata()['eventTransport']['buildIdentity']:
            device = actual_identity_shape()
            del device['savedFileDeletion']['downloadResume']['buildIdentity'][key]
            reseal(device)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                contract.verify_download_resume_invocation(device, 'a'*40)

    def test_explanation_cannot_replace_original_event_binding(self):
        device = actual_identity_shape()
        device['savedFileDeletion']['downloadResume']['buildIdentity'].pop('scope')
        with self.assertRaises(ValueError):
            contract.verify_download_resume_invocation(device, 'a'*40)


if __name__ == '__main__':
    unittest.main()
