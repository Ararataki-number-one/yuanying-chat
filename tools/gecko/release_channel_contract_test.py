"""Publication boundaries: candidates never become automatic updates."""
import copy
import unittest
from release_channel_contract import (ReleaseChannelError, advances_update_channel,
    release_tag, requires_manual_acceptance, verify_manual_acceptance)


class ReleaseChannelTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(sourceCommit='a'*40, sha256='b'*64, version='1.6.0', versionCode=51)
        self.record = dict(self.identity, schema=1, status='passed', reportedBy='user',
            actualPhysicalPhoneExecution=True, abi='arm64-v8a', deviceModel='Physical test phone',
            androidVersion='16', reportedAt='2026-10-13T00:00:00Z', checks=[dict(name=n, **{'pass': True}) for n in
            ('upgrade-data','login-session','chinese-input','attachments','downloads','long-reply',
             'background-resume','environment-isolation','fixed-exit','independent-subscriptions')])

    def test_existing_stable_tags_keep_identity(self):
        self.assertEqual(release_tag(dict(version='1.5.23')), 'v1.5.23-gecko')
        self.assertTrue(advances_update_channel(dict(version='1.5.23')))

    def test_candidate_is_public_but_not_an_update(self):
        m=dict(version='1.6.0',channel='candidate',candidateNumber=1)
        self.assertEqual(release_tag(m), 'v1.6.0-candidate1-gecko')
        self.assertFalse(advances_update_channel(m))
        self.assertFalse(requires_manual_acceptance(m))

    def test_stable_roadmap_needs_manual_acceptance(self):
        self.assertTrue(requires_manual_acceptance(dict(version='1.6.0')))
        self.assertFalse(requires_manual_acceptance(dict(version='1.5.24')))

    def test_invalid_channel_and_sequence_are_rejected(self):
        for m in [dict(version='1.6.0',channel='other'),dict(version='1.6.0',channel='stable',candidateNumber=1),
                  *[dict(version='1.6.0',channel='candidate',candidateNumber=n) for n in (None,True,0,-1,1000,'1')]]:
            with self.subTest(manifest=m),self.assertRaises(ReleaseChannelError):release_tag(m)

    def test_manual_checklist_remains_manual(self):
        result=verify_manual_acceptance(self.record,self.identity)
        self.assertEqual(result['reportedBy'],'user')
        self.assertNotIn('actualAndroidExecution',result)

    def test_another_apk_or_source_cannot_promote(self):
        for key,value in [('sha256','c'*64),('sourceCommit','c'*40),('versionCode',52),('version','1.7.0')]:
            record=copy.deepcopy(self.record);record[key]=value
            with self.subTest(key=key),self.assertRaises(ReleaseChannelError):verify_manual_acceptance(record,self.identity)

    def test_missing_failed_or_duplicate_checks_cannot_promote(self):
        for kind in ('missing','failed','duplicate'):
            record=copy.deepcopy(self.record)
            if kind=='missing':record['checks'].pop()
            elif kind=='failed':record['checks'][0]['pass']=False
            else:record['checks'].append(record['checks'][0])
            with self.subTest(kind=kind),self.assertRaises(ReleaseChannelError):verify_manual_acceptance(record,self.identity)

    def test_host_or_emulator_does_not_satisfy_manual_gate(self):
        for key,value in [('reportedBy','automation'),('actualPhysicalPhoneExecution',False),('abi','x86_64'),('deviceModel','')]:
            record=copy.deepcopy(self.record);record[key]=value
            with self.subTest(key=key),self.assertRaises(ReleaseChannelError):verify_manual_acceptance(record,self.identity)

    def test_later_versions_require_their_additional_checks(self):
        for version in ('1.7.0','2.0.0'):
            identity=dict(self.identity,version=version);record=dict(self.record,version=version)
            with self.subTest(version=version),self.assertRaises(ReleaseChannelError):verify_manual_acceptance(record,identity)


if __name__ == '__main__':
    unittest.main()
