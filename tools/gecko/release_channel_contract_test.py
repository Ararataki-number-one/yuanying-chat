"""Publication boundaries: candidates never become automatic updates."""
import copy
import unittest
from release_channel_contract import (ReleaseChannelError, advances_update_channel,
    release_tag, requires_manual_acceptance, verify_direct_release, verify_manual_acceptance)


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


class DirectReleaseTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(channel='stable', sourceCommit='a'*40, sha256='b'*64,
            version='2.0.2', versionCode=55, signerSha256='c'*64, bytes=119000000)
        self.record = {key: value for key, value in self.identity.items() if key != 'channel'}
        self.record.update(schema=1, kind='user-requested-stable-release', status='authorized',
            requestedBy='user', authorizationSource='current-user-message', userRequest='发布正式版',
            requestedChannel='stable', scope='publish-existing-signed-apk-to-stable',
            physicalPhoneAcceptanceStatus='not-reported', recordedAt='2026-10-15T15:00:00+09:00')

    def test_explicit_request_records_authorization_not_phone_acceptance(self):
        before = copy.deepcopy(self.record)
        result = verify_direct_release(self.record, self.identity)
        self.assertEqual(result, dict(self.record, physicalArmPhone='not-tested'))
        self.assertEqual(result['physicalPhoneAcceptanceStatus'], 'not-reported')
        self.assertNotIn('manualAcceptance', result)
        self.assertNotIn('actualPhysicalPhoneExecution', result)
        self.assertEqual(self.record, before)
        self.assertTrue(requires_manual_acceptance(self.identity))
        with self.assertRaises(ReleaseChannelError):verify_manual_acceptance(self.record, self.identity)

    def test_each_exact_apk_identity_field_is_bound(self):
        changed = dict(sourceCommit='d'*40, sha256='d'*64, version='2.0.3', versionCode=56,
                       signerSha256='d'*64, bytes=119000001)
        for key, value in changed.items():
            record = dict(self.record, **{key: value})
            with self.subTest(key=key), self.assertRaises(ReleaseChannelError):
                verify_direct_release(record, self.identity)

    def test_candidate_or_implicit_channel_cannot_use_direct_stable_release(self):
        for identity in (dict(self.identity, channel='candidate', candidateNumber=1),
                         {key:value for key,value in self.identity.items() if key != 'channel'},
                         dict(self.identity, channel='unknown')):
            with self.subTest(identity=identity), self.assertRaises(ReleaseChannelError):
                verify_direct_release(self.record, identity)

    def test_all_authorization_metadata_is_explicit(self):
        invalid = dict(schema=True, kind='manual-acceptance', status='passed', requestedBy='automation',
            authorizationSource='inferred-user-intent', requestedChannel='candidate',
            scope='publish-new-apk', physicalPhoneAcceptanceStatus='passed')
        for key, value in invalid.items():
            with self.subTest(key=key), self.assertRaises(ReleaseChannelError):
                verify_direct_release(dict(self.record, **{key:value}), self.identity)

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ReleaseChannelError):
            verify_direct_release(dict(self.record, status='pending'), self.identity)

    def test_phone_or_manual_acceptance_cannot_be_added_to_authorization(self):
        additions = dict(manualAcceptance={'status':'passed'}, actualPhysicalPhoneExecution=True,
            physicalArmPhone='user-reported-passed', checks=[{'name':'attachments','pass':True}],
            deviceModel='Claimed phone', reportedBy='user', manualAcceptanceArtifact={})
        for key, value in additions.items():
            with self.subTest(key=key), self.assertRaises(ReleaseChannelError):
                verify_direct_release(dict(self.record, **{key:value}), self.identity)

    def test_manual_record_cannot_impersonate_direct_release(self):
        record = dict(self.identity, schema=1, status='passed', reportedBy='user',
            actualPhysicalPhoneExecution=True, checks=[])
        with self.assertRaises(ReleaseChannelError):verify_direct_release(record, self.identity)

    def test_vague_negative_or_question_text_is_not_explicit_publication(self):
        for request in ('', '  ', '继续', '测试已通过', '以后发布正式版', '不要发布正式版',
                        '我不想发布正式版', '不要发布新版本', '发布新版本？', '以后发布新版本', '发布正式版？', '他说“发布正式版”',
                        'Do not publish the stable release', '发布正式版' + ' '*2000, None, True):
            with self.subTest(request=request), self.assertRaises(ReleaseChannelError):
                verify_direct_release(dict(self.record, userRequest=request), self.identity)

    def test_affirmative_command_preserves_original_user_text(self):
        for request in ('发布正式版', '发布新版本', '请现在发布正式版。', 'Publish the stable release',
                        'Please promote the existing signed APK to stable.'):
            record = dict(self.record, userRequest=request)
            with self.subTest(request=request):
                self.assertEqual(verify_direct_release(record, self.identity)['userRequest'], request)

    def test_recording_time_must_be_valid_iso8601_with_timezone(self):
        for recorded_at in ('', '2026-10-15', '2026-10-15T15:00:00', '2026-02-30T00:00:00Z',
                            '2026-10-15T25:00:00Z', '2026-10-15T15:00:00+24:00', None):
            with self.subTest(recorded_at=recorded_at), self.assertRaises(ReleaseChannelError):
                verify_direct_release(dict(self.record, recordedAt=recorded_at), self.identity)
        for recorded_at in ('2026-10-15T06:00:00Z', '2026-10-15T06:00:00.123456+00:00'):
            with self.subTest(recorded_at=recorded_at):
                self.assertEqual(verify_direct_release(dict(self.record, recordedAt=recorded_at),
                    self.identity)['recordedAt'], recorded_at)

    def test_missing_fields_and_non_record_input_are_rejected(self):
        for key in self.record:
            record = dict(self.record);record.pop(key)
            with self.subTest(key=key), self.assertRaises(ReleaseChannelError):
                verify_direct_release(record, self.identity)
        for record in (None, [], '发布正式版'):
            with self.subTest(record=record), self.assertRaises(ReleaseChannelError):
                verify_direct_release(record, self.identity)

    def test_invalid_identity_values_do_not_become_authorization(self):
        for key, value in (('sourceCommit','short'),('sha256','B'*64),('signerSha256','invalid'),
                           ('version','2.0'),('versionCode',True),('versionCode',0),('bytes',0),('bytes',True)):
            identity = dict(self.identity, **{key:value});record = dict(self.record, **{key:value})
            with self.subTest(key=key, value=value), self.assertRaises(ReleaseChannelError):
                verify_direct_release(record, identity)


if __name__ == '__main__':
    unittest.main()
