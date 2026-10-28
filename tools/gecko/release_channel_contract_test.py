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

    def test_prior_explicit_authorization_remains_distinct_from_phone_acceptance(self):
        record = dict(self.record, authorizationSource='prior-explicit-user-message-in-current-task')
        self.assertEqual(verify_direct_release(record, self.identity)['physicalArmPhone'], 'not-tested')
        record['userRequest'] = '继续优化'
        with self.assertRaises(ReleaseChannelError):verify_direct_release(record, self.identity)

    def test_explicit_continue_and_publish_is_not_a_vague_continuation(self):
        record = dict(self.record, userRequest='继续，然后发布新版本')
        self.assertEqual(verify_direct_release(record, self.identity)['physicalArmPhone'], 'not-tested')
        for request in ('继续', '继续优化', '继续，然后不要发布新版本', '继续，然后发布新版本？'):
            with self.subTest(request=request), self.assertRaises(ReleaseChannelError):
                verify_direct_release(dict(record, userRequest=request), self.identity)

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
        for request in ('先做这个，然后不要发布优化后的下一版本', '先做这个，然后发布优化后的下一版本？', '不要做完上面的给我继续优化网络体验我现在的网络延迟还是400多。给我降到200左右。不管你用什么办法，用最高级的，最先进的架构也好，修修补补改进也好。然后再发布你优化后的版本', '做完上面的给我继续优化网络体验我现在的网络延迟还是400多。给我降到200左右。不管你用什么办法，用最高级的，最先进的架构也好，修修补补改进也好。然后再发布你优化后的版本？', '不要做这个然后发布', '做这个然后发布？', '以后做这个然后发布', '', '  ', '继续', '测试已通过', '以后发布正式版', '不要发布正式版',
                        '我不想发布正式版', '不要发布新版本', '发布新版本？', '以后发布新版本', '发布正式版？', '他说“发布正式版”',
                        'Do not publish the stable release', '发布正式版' + ' '*2000, None, True):
            with self.subTest(request=request), self.assertRaises(ReleaseChannelError):
                verify_direct_release(dict(self.record, userRequest=request), self.identity)

    def test_affirmative_command_preserves_original_user_text(self):
        for request in ('先做这个，然后发布优化后的下一版本', '做完上面的给我继续优化网络体验我现在的网络延迟还是400多。给我降到200左右。不管你用什么办法，用最高级的，最先进的架构也好，修修补补改进也好。然后再发布你优化后的版本', '做这个然后发布', '发布正式版', '发布新版本', '请现在发布正式版。', 'Publish the stable release',
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


# Synthetic transport controls; the original release-channel tests above remain unchanged.
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import release_channel_contract as p

SOURCE='a'*40
ARTIFACT='b'*40
RUN='40626366592'
ATTEMPT='1'
VERSION='2.0.25'
FILE='PocketChat-2.0.25-gecko-arm64.apk'
UF='PocketChat-2.0.25-arm64-v8a.apk.part00'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def ref(name,raw):return {'file':name,'bytes':len(raw),'sha256':sha(raw)}


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.inputs=self.base/'input';self.inputs.mkdir()
        self.output=self.base/'output'
        self.unsigned=bytes(range(256))*8
        self.prefix=len(self.unsigned)-8
        self.tail=b'synthetic-signature-tail'+self.unsigned[-8:]
        self.signed=self.unsigned[:self.prefix]+self.tail
        self.build={'sourceCommit':SOURCE,'runId':RUN,'runAttempt':ATTEMPT,
                    'version':VERSION,'versionCode':78,'googleLogin':'not-tested',
                    'artifacts':[{'abi':'arm64-v8a','bytes':len(self.unsigned),'sha256':sha(self.unsigned),
                                  'signing':'unsigned','chunks':[ref(UF,self.unsigned)]}]}
        self.release={'sourceCommit':SOURCE,'buildRunId':RUN,'buildRunAttempt':ATTEMPT,
                      'version':VERSION,'versionCode':78,'filename':FILE,'package':'local.pocketchat',
                      'signerSha256':p.SIGNER,'unsignedSha256':sha(self.unsigned),
                      'bytes':len(self.signed),'sha256':sha(self.signed),
                      'parts':[ref(FILE+'.part00',self.signed)]}
        self.transport={'schema':1,'kind':'unsigned-prefix-tail-v1','sourceCommit':SOURCE,
                        'runId':RUN,'runAttempt':ATTEMPT,'unsignedArtifactCommit':ARTIFACT,
                        'buildManifest':{},'prefixBytes':self.prefix,
                        'tail':ref('signed-apk-tail.bin',self.tail)}
        (self.inputs/UF).write_bytes(self.unsigned)
        (self.inputs/'signed-apk-tail.bin').write_bytes(self.tail)
        self.rewrite_build()

    def rewrite_build(self,raw=None):
        if raw is None:raw=json.dumps(self.build,separators=(',',':')).encode()
        (self.inputs/'unsigned-build-manifest.json').write_bytes(raw)
        self.transport['buildManifest']=ref('unsigned-build-manifest.json',raw)

    def run_assembly(self,**kwargs):
        return p.assemble_signed_transport(self.transport,self.release,self.inputs,self.output,
                          expected_source=SOURCE,expected_run=RUN,expected_attempt=ATTEMPT,
                          expected_artifact=ARTIFACT,**kwargs)

    def test_positive_exact_bytes_and_original_parts(self):
        original={f.name:f.read_bytes() for f in self.inputs.iterdir()}
        receipt=self.run_assembly()
        self.assertEqual((self.output/(FILE+'.part00')).read_bytes(),self.signed)
        self.assertEqual(receipt['signedSha256'],sha(self.signed))
        self.assertEqual(receipt['unsignedSha256'],sha(self.unsigned))
        self.assertFalse(receipt['releaseAcceptance'])
        self.assertFalse(receipt['physicalPhoneAcceptance'])
        self.assertEqual({f.name:f.read_bytes() for f in self.inputs.iterdir()},original)

    def test_positive_full_unsigned_prefix_then_append(self):
        self.transport['prefixBytes']=len(self.unsigned)
        data=self.unsigned+self.tail
        self.release.update(bytes=len(data),sha256=sha(data),parts=[ref(FILE+'.part00',data)])
        self.run_assembly()
        self.assertEqual((self.output/(FILE+'.part00')).read_bytes(),data)

    def test_output_collision_preserves_existing_content(self):
        self.output.mkdir();marker=self.output/'owned.txt';marker.write_bytes(b'existing-user-data')
        with self.assertRaisesRegex(p.TransportError,'Output already exists'):self.run_assembly()
        self.assertEqual(marker.read_bytes(),b'existing-user-data')

    def test_symlink_unsigned_rejected(self):
        path=self.inputs/UF;path.unlink();path.symlink_to(self.inputs/'signed-apk-tail.bin')
        with self.assertRaisesRegex(p.TransportError,'ordinary referenced file'):self.run_assembly()
        self.assertFalse(self.output.exists())

    def test_symlink_tail_rejected(self):
        path=self.inputs/'signed-apk-tail.bin';path.unlink();path.symlink_to(self.inputs/UF)
        with self.assertRaisesRegex(p.TransportError,'ordinary referenced file'):self.run_assembly()
        self.assertFalse(self.output.exists())

    def test_symlink_source_directory_rejected(self):
        link=self.base/'input-link';link.symlink_to(self.inputs,target_is_directory=True)
        with self.assertRaisesRegex(p.TransportError,'Input directory must be ordinary'):
            p.assemble_signed_transport(self.transport,self.release,link,self.output,expected_source=SOURCE,
                       expected_run=RUN,expected_attempt=ATTEMPT,expected_artifact=ARTIFACT)

    def test_fifo_unsigned_rejected_without_wait(self):
        path=self.inputs/UF;path.unlink();os.mkfifo(path)
        with self.assertRaisesRegex(p.TransportError,'not regular'):self.run_assembly()
        self.assertFalse(self.output.exists())

    def test_duplicate_json_build_keys_rejected(self):
        self.rewrite_build(b'{"sourceCommit":"'+SOURCE.encode()+b'","sourceCommit":"'+SOURCE.encode()+b'"}')
        with self.assertRaisesRegex(p.TransportError,'Duplicate JSON key'):self.run_assembly()

    def test_nonfinite_json_build_rejected(self):
        self.rewrite_build(b'{"invalid":NaN}')
        with self.assertRaisesRegex(p.TransportError,'Non-finite'):self.run_assembly()

    def test_json_byte_bound(self):
        with self.assertRaisesRegex(p.TransportError,'fixed bound'):p.transport_strict_json(b' '*(p.MAX_MANIFEST_BYTES+1))

    def test_cli_json_symlink_rejected(self):
        link=self.base/'json-link';link.symlink_to(self.inputs/'unsigned-build-manifest.json')
        with self.assertRaisesRegex(p.TransportError,'ordinary JSON file'):p.read_transport_json_file(link)

    def test_cli_json_fifo_rejected_without_wait(self):
        fifo=self.base/'json-fifo';os.mkfifo(fifo)
        with self.assertRaisesRegex(p.TransportError,'JSON file is not regular'):p.read_transport_json_file(fifo)

    def test_cli_json_oversize_rejected(self):
        path=self.base/'json-large';path.write_bytes(b' '*(p.MAX_MANIFEST_BYTES+1))
        with self.assertRaisesRegex(p.TransportError,'JSON file exceeds fixed bound'):p.read_transport_json_file(path)

    def test_negative_controls_leave_inputs_unchanged(self):
        original={f.name:f.read_bytes() for f in self.inputs.iterdir()}
        self.release['sha256']='0'*64
        with self.assertRaisesRegex(p.TransportError,'Signed final actual SHA256 differs'):self.run_assembly()
        self.assertFalse(self.output.exists())
        self.assertEqual({f.name:f.read_bytes() for f in self.inputs.iterdir()},original)


def change_build(fn):
    def mutate(t):fn(t.build);t.rewrite_build()
    return mutate


def full_hash_disagrees(t):
    t.build['artifacts'][0]['sha256']='0'*64;t.release['unsignedSha256']='0'*64;t.rewrite_build()


def truncate_tail(t):(t.inputs/'signed-apk-tail.bin').write_bytes(t.tail[:-1])
def oversize_actual_tail(t):(t.inputs/'signed-apk-tail.bin').write_bytes(b'x'*(p.MAX_TAIL_BYTES+1))
def corrupt_tail_same_length(t):(t.inputs/'signed-apk-tail.bin').write_bytes(b'x'*len(t.tail))
def corrupt_unsigned_same_length(t):(t.inputs/UF).write_bytes(b'x'*len(t.unsigned))
def truncate_unsigned(t):(t.inputs/UF).write_bytes(t.unsigned[:-1])
def grow_unsigned(t):(t.inputs/UF).write_bytes(t.unsigned+b'x')


def duplicate_unsigned_path(t):
    item=t.build['artifacts'][0]
    item['bytes']=p.CHUNK_BYTES+10
    item['chunks']=[{'file':UF,'bytes':p.CHUNK_BYTES,'sha256':'0'*64},
                    {'file':UF,'bytes':10,'sha256':'0'*64}]
    t.rewrite_build()


def duplicate_signed_path(t):
    t.release['bytes']=p.CHUNK_BYTES+10
    t.release['parts']=[{'file':FILE+'.part00','bytes':p.CHUNK_BYTES,'sha256':'0'*64},
                        {'file':FILE+'.part00','bytes':10,'sha256':'0'*64}]


CASES=[
 ('unknown_descriptor_key',lambda t:t.transport.update(command='do-not-execute'),'Invalid transport shape'),
 ('schema_boolean',lambda t:t.transport.update(schema=True),'Invalid transport schema'),
 ('unsupported_patch_kind',lambda t:t.transport.update(kind='arbitrary-delta'),'Unsupported transport kind'),
 ('wrong_source',lambda t:t.transport.update(sourceCommit='c'*40),'Transport identity differs: sourceCommit'),
 ('wrong_run',lambda t:t.transport.update(runId='999'),'Transport identity differs: runId'),
 ('wrong_attempt',lambda t:t.transport.update(runAttempt='2'),'Transport identity differs: runAttempt'),
 ('numeric_attempt',lambda t:t.transport.update(runAttempt=1),'Transport identity differs: runAttempt'),
 ('wrong_immutable_artifact',lambda t:t.transport.update(unsignedArtifactCommit='c'*40),'Transport identity differs: unsignedArtifactCommit'),
 ('build_ref_hash',lambda t:t.transport['buildManifest'].update(sha256='0'*64),'Small file SHA256 differs'),
 ('build_ref_size',lambda t:t.transport['buildManifest'].update(bytes=1),'Referenced file byte count differs'),
 ('unsafe_build_path',lambda t:t.transport['buildManifest'].update(file='../unsigned-build-manifest.json'),'Unsafe flat file name'),
 ('build_source',change_build(lambda b:b.update(sourceCommit='c'*40)),'Build identity differs: sourceCommit'),
 ('build_run',change_build(lambda b:b.update(runId='999')),'Build identity differs: runId'),
 ('build_attempt',change_build(lambda b:b.update(runAttempt='2')),'Build identity differs: runAttempt'),
 ('build_version',change_build(lambda b:b.update(version='2.0.24')),'Build/release versions differ'),
 ('build_version_code',change_build(lambda b:b.update(versionCode=77)),'Build/release versions differ'),
 ('release_source',lambda t:t.release.update(sourceCommit='c'*40),'Release identity differs: sourceCommit'),
 ('release_run',lambda t:t.release.update(buildRunId='999'),'Release identity differs: buildRunId'),
 ('release_attempt',lambda t:t.release.update(buildRunAttempt='2'),'Release identity differs: buildRunAttempt'),
 ('release_package',lambda t:t.release.update(package='local.pocketchat.test'),'Unexpected release APK identity'),
 ('release_filename',lambda t:t.release.update(filename='evil.apk'),'Unexpected release APK identity'),
 ('release_signer_declaration',lambda t:t.release.update(signerSha256='0'*64),'Unexpected original signer declaration'),
 ('unsigned_receipt_mismatch',lambda t:t.release.update(unsignedSha256='0'*64),'Unsigned/source receipt SHA256 differs'),
 ('unsigned_full_actual_hash',full_hash_disagrees,'Unsigned full actual SHA256 differs'),
 ('unsigned_chunk_actual_hash',change_build(lambda b:b['artifacts'][0]['chunks'][0].update(sha256='0'*64)),'Unsigned part actual SHA256 differs'),
 ('unsigned_chunk_bad_hash_shape',change_build(lambda b:b['artifacts'][0]['chunks'][0].update(sha256='0')),'Unsigned part SHA256 invalid'),
 ('unsigned_chunk_bad_size',change_build(lambda b:b['artifacts'][0]['chunks'][0].update(bytes=1)),'Unsigned part byte count differs'),
 ('unsigned_unsafe_path',change_build(lambda b:b['artifacts'][0]['chunks'][0].update(file='../x')),'Unsafe flat file name'),
 ('unsigned_duplicate_path',duplicate_unsigned_path,'Unsigned duplicate part path'),
 ('unsigned_wrong_part_count',change_build(lambda b:b['artifacts'][0]['chunks'].append(copy.deepcopy(b['artifacts'][0]['chunks'][0]))),'Unsigned part count differs'),
 ('unsigned_wrong_abi',change_build(lambda b:b['artifacts'][0].update(abi='x86_64')),'Unexpected unsigned artifact identity'),
 ('unsigned_oversize',change_build(lambda b:b['artifacts'][0].update(bytes=p.MAX_APK_BYTES+1)),'Invalid unsigned APK size'),
 ('unsigned_corrupt_actual',corrupt_unsigned_same_length,'Unsigned part actual SHA256 differs'),
 ('unsigned_truncated_actual',truncate_unsigned,'Referenced file byte count differs'),
 ('unsigned_extra_actual',grow_unsigned,'Referenced file byte count differs'),
 ('tail_hash',lambda t:t.transport['tail'].update(sha256='0'*64),'Small file SHA256 differs'),
 ('tail_size_boolean',lambda t:t.transport['tail'].update(bytes=True),'Invalid referenced byte count'),
 ('tail_zero_size',lambda t:t.transport['tail'].update(bytes=0),'Invalid referenced byte count'),
 ('tail_oversize_declaration',lambda t:t.transport['tail'].update(bytes=p.MAX_TAIL_BYTES+1),'Invalid referenced byte count'),
 ('tail_unsafe_path',lambda t:t.transport['tail'].update(file='/tmp/tail'),'Unsafe flat file name'),
 ('tail_truncated_actual',truncate_tail,'Referenced file byte count differs'),
 ('tail_oversize_actual',oversize_actual_tail,'Referenced file byte count differs'),
 ('tail_corrupt_same_length',corrupt_tail_same_length,'Small file SHA256 differs'),
 ('prefix_negative',lambda t:t.transport.update(prefixBytes=-1),'Invalid prefix range'),
 ('prefix_zero',lambda t:t.transport.update(prefixBytes=0),'Invalid prefix range'),
 ('prefix_boolean',lambda t:t.transport.update(prefixBytes=True),'Invalid prefix range'),
 ('prefix_outside_unsigned',lambda t:t.transport.update(prefixBytes=len(t.unsigned)+1),'Invalid prefix range'),
 ('prefix_size_equation',lambda t:t.transport.update(prefixBytes=t.prefix-1),'Prefix and tail do not match signed size'),
 ('signed_final_hash',lambda t:t.release.update(sha256='0'*64),'Signed final actual SHA256 differs'),
 ('signed_part_hash',lambda t:t.release['parts'][0].update(sha256='0'*64),'Signed final part SHA256 differs'),
 ('signed_part_size',lambda t:t.release['parts'][0].update(bytes=1),'Signed part byte count differs'),
 ('signed_part_unsafe_path',lambda t:t.release['parts'][0].update(file='../x'),'Unsafe flat file name'),
 ('signed_part_duplicate',duplicate_signed_path,'Signed duplicate part path'),
 ('signed_wrong_part_count',lambda t:t.release['parts'].append(copy.deepcopy(t.release['parts'][0])),'Signed part count differs'),
 ('signed_oversize',lambda t:t.release.update(bytes=p.MAX_APK_BYTES+1),'Invalid signed APK size'),
]


def install_case(name, mutate, message):
    def test(self):
        mutate(self)
        with self.assertRaisesRegex(p.TransportError,message):self.run_assembly()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.base.glob('.signed-transport-*')))
    test.__name__='test_reject_'+name
    setattr(Controls,test.__name__,test)


for case in CASES:install_case(*case)


class ChunkBoundaries(unittest.TestCase):
    def test_exact_sixty_million_split_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);inputs=base/'inputs';inputs.mkdir()
            data=b'u'*p.CHUNK_BYTES+b'end-of-unsigned'
            tail=b'new-synthetic-tail'
            prefix=len(data)-3;signed=data[:prefix]+tail
            chunks=[ref(f'PocketChat-{VERSION}-arm64-v8a.apk.part{i:02d}',data[x:x+p.CHUNK_BYTES])
                    for i,x in enumerate(range(0,len(data),p.CHUNK_BYTES))]
            for part in chunks:
                i=int(part['file'][-2:]);(inputs/part['file']).write_bytes(data[i*p.CHUNK_BYTES:(i+1)*p.CHUNK_BYTES])
            build={'sourceCommit':SOURCE,'runId':RUN,'runAttempt':ATTEMPT,'version':VERSION,'versionCode':78,
                   'artifacts':[{'abi':'arm64-v8a','bytes':len(data),'sha256':sha(data),'signing':'unsigned','chunks':chunks}]}
            raw=json.dumps(build).encode();(inputs/'unsigned-build-manifest.json').write_bytes(raw)
            (inputs/'signed-apk-tail.bin').write_bytes(tail)
            parts=[ref(FILE+f'.part{i:02d}',signed[x:x+p.CHUNK_BYTES]) for i,x in enumerate(range(0,len(signed),p.CHUNK_BYTES))]
            release={'sourceCommit':SOURCE,'buildRunId':RUN,'buildRunAttempt':ATTEMPT,'version':VERSION,
                     'versionCode':78,'filename':FILE,'package':'local.pocketchat','signerSha256':p.SIGNER,
                     'unsignedSha256':sha(data),'sha256':sha(signed),'bytes':len(signed),'parts':parts}
            descriptor={'schema':1,'kind':'unsigned-prefix-tail-v1','sourceCommit':SOURCE,'runId':RUN,
                        'runAttempt':ATTEMPT,'unsignedArtifactCommit':ARTIFACT,
                        'buildManifest':ref('unsigned-build-manifest.json',raw),'prefixBytes':prefix,
                        'tail':ref('signed-apk-tail.bin',tail)}
            output=base/'output'
            result=p.assemble_signed_transport(descriptor,release,inputs,output,expected_source=SOURCE,expected_run=RUN,
                              expected_attempt=ATTEMPT,expected_artifact=ARTIFACT)
            self.assertEqual(result['parts'],parts)
            self.assertEqual(b''.join((output/x['file']).read_bytes() for x in parts),signed)
            self.assertEqual(parts[0]['bytes'],60_000_000)


class OptionalTransportTests(unittest.TestCase):
    setUp = Controls.setUp
    rewrite_build = Controls.rewrite_build

    def attach(self):
        raw=json.dumps(self.transport,separators=(',',':')).encode()
        (self.inputs/'signed-transport.json').write_bytes(raw)
        self.release['signedTransportArtifact']=dict(ref('signed-transport.json',raw),unsignedArtifactCommit=ARTIFACT)

    def restore(self):
        return p.restore_signed_transport(self.release,self.inputs)

    def assert_absent(self):
        self.assertFalse((self.inputs/(FILE+'.part00')).exists())

    def test_absent_transport_is_the_unchanged_legacy_path(self):
        self.assertIsNone(self.restore())
        self.assert_absent()

    def test_optional_transport_restores_original_parts(self):
        self.attach();result=self.restore()
        self.assertEqual((self.inputs/(FILE+'.part00')).read_bytes(),self.signed)
        self.assertEqual(result['parts'],self.release['parts'])
        self.assertEqual(result['signedSha256'],self.release['sha256'])
        self.assertEqual(result['transportArtifactSha256'],self.release['signedTransportArtifact']['sha256'])
        self.assertFalse(result['releaseAcceptance'])

    def test_present_null_is_not_a_legacy_fallback(self):
        self.release['signedTransportArtifact']=None
        with self.assertRaisesRegex(p.TransportError,'Invalid signed transport artifact shape'):self.restore()
        self.assert_absent()

    def test_optional_record_rejects_additional_fields(self):
        self.attach();self.release['signedTransportArtifact']['command']='never-execute'
        with self.assertRaisesRegex(p.TransportError,'Invalid signed transport artifact shape'):self.restore()
        self.assert_absent()

    def test_optional_record_rejects_unsafe_path(self):
        self.attach();self.release['signedTransportArtifact']['file']='../signed-transport.json'
        with self.assertRaisesRegex(p.TransportError,'Unsafe flat file name'):self.restore()
        self.assert_absent()

    def test_optional_record_rejects_corrupt_descriptor(self):
        self.attach();self.release['signedTransportArtifact']['sha256']='0'*64
        with self.assertRaisesRegex(p.TransportError,'Small file SHA256 differs'):self.restore()
        self.assert_absent()

    def test_optional_record_binds_immutable_artifact(self):
        self.attach();self.release['signedTransportArtifact']['unsignedArtifactCommit']='c'*40
        with self.assertRaisesRegex(p.TransportError,'Transport identity differs: unsignedArtifactCommit'):self.restore()
        self.assert_absent()

    def test_optional_record_rejects_invalid_artifact_commit(self):
        self.attach();self.release['signedTransportArtifact']['unsignedArtifactCommit']='short'
        with self.assertRaisesRegex(p.TransportError,'Invalid transport artifact commit'):self.restore()
        self.assert_absent()

    def test_optional_record_binds_original_release_run(self):
        self.attach();self.release['buildRunId']='999'
        with self.assertRaisesRegex(p.TransportError,'Transport identity differs: runId'):self.restore()
        self.assert_absent()

    def test_optional_record_binds_original_release_attempt(self):
        self.attach();self.release['buildRunAttempt']='2'
        with self.assertRaisesRegex(p.TransportError,'Transport identity differs: runAttempt'):self.restore()
        self.assert_absent()

    def test_existing_signed_part_is_never_overwritten(self):
        self.attach();path=self.inputs/(FILE+'.part00');path.write_bytes(b'existing-part-data')
        with self.assertRaisesRegex(p.TransportError,'Signed destination already exists'):self.restore()
        self.assertEqual(path.read_bytes(),b'existing-part-data')

    def test_existing_signed_part_symlink_is_never_followed(self):
        self.attach();path=self.inputs/(FILE+'.part00');path.symlink_to(self.inputs/UF)
        with self.assertRaisesRegex(p.TransportError,'Signed destination already exists'):self.restore()
        self.assertTrue(path.is_symlink())
        self.assertEqual((self.inputs/UF).read_bytes(),self.unsigned)

    def test_unsigned_corruption_never_exposes_parts(self):
        self.attach();(self.inputs/UF).write_bytes(b'x'*len(self.unsigned))
        with self.assertRaisesRegex(p.TransportError,'Unsigned part actual SHA256 differs'):self.restore()
        self.assert_absent()

    def test_final_hash_corruption_never_exposes_parts(self):
        self.attach();self.release['sha256']='0'*64
        with self.assertRaisesRegex(p.TransportError,'Signed final actual SHA256 differs'):self.restore()
        self.assert_absent()


class TransportProvenanceTests(unittest.TestCase):
    setUp = Controls.setUp
    rewrite_build = Controls.rewrite_build
    attach = OptionalTransportTests.attach

    def invoke(self,local=None,remote=None,parents=None,actual=ARTIFACT):
        self.attach()
        raw=(self.inputs/'unsigned-build-manifest.json').read_bytes()
        return p.verify_unsigned_transport_provenance(self.release,raw if local is None else local,
                    raw if remote is None else remote,[SOURCE,'c'*40] if parents is None else parents,actual)

    def test_independently_selected_immutable_metadata_matches(self):
        result=self.invoke()
        self.assertTrue(result['firstParentVerified'])
        self.assertEqual(result['artifactCommit'],ARTIFACT)
        self.assertEqual(result['unsignedSha256'],self.release['unsignedSha256'])

    def test_other_fetched_commit_rejected(self):
        with self.assertRaisesRegex(p.TransportError,'Fetched immutable artifact differs'):self.invoke(actual='d'*40)

    def test_empty_parent_list_rejected(self):
        with self.assertRaisesRegex(p.TransportError,'Invalid artifact parent list'):self.invoke(parents=[])

    def test_source_must_be_first_not_later_parent(self):
        with self.assertRaisesRegex(p.TransportError,'Artifact first parent differs'):self.invoke(parents=['c'*40,SOURCE])

    def test_invalid_parent_shape_rejected(self):
        with self.assertRaisesRegex(p.TransportError,'Invalid artifact parent identity'):self.invoke(parents=['short'])

    def test_overlong_parent_list_rejected(self):
        with self.assertRaisesRegex(p.TransportError,'Invalid artifact parent list'):self.invoke(parents=[SOURCE]*9)

    def test_semantically_equal_but_different_manifest_bytes_rejected(self):
        raw=(self.inputs/'unsigned-build-manifest.json').read_bytes()
        with self.assertRaisesRegex(p.TransportError,'Immutable artifact manifest bytes differ'):self.invoke(remote=raw+b'\n')

    def test_remote_manifest_byte_bound(self):
        raw=b' '*(p.MAX_MANIFEST_BYTES+1)
        with self.assertRaisesRegex(p.TransportError,'Immutable artifact manifest bytes differ'):self.invoke(local=raw,remote=raw)

    def test_duplicate_remote_json_key_rejected(self):
        raw=b'{"sourceCommit":"'+SOURCE.encode()+b'","sourceCommit":"'+SOURCE.encode()+b'"}'
        with self.assertRaisesRegex(p.TransportError,'Duplicate JSON key'):self.invoke(local=raw,remote=raw)

    def test_immutable_source_must_match_release(self):
        self.build['sourceCommit']='d'*40;self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable artifact identity differs: sourceCommit'):self.invoke()

    def test_immutable_run_must_match_release(self):
        self.build['runId']='999';self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable artifact identity differs: runId'):self.invoke()

    def test_immutable_attempt_must_match_release(self):
        self.build['runAttempt']='2';self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable artifact identity differs: runAttempt'):self.invoke()

    def test_immutable_version_must_match_release(self):
        self.build['versionCode']=77;self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable artifact version differs'):self.invoke()

    def test_immutable_unsigned_sha_must_match_release_receipt(self):
        self.build['artifacts'][0]['sha256']='0'*64;self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable unsigned artifact SHA256 differs'):self.invoke()

    def test_immutable_unsigned_size_bound(self):
        self.build['artifacts'][0]['bytes']=p.MAX_APK_BYTES+1;self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable unsigned artifact size invalid'):self.invoke()

    def test_immutable_single_arm64_artifact_required(self):
        self.build['artifacts'][0]['abi']='x86_64';self.rewrite_build()
        with self.assertRaisesRegex(p.TransportError,'Immutable unsigned artifact identity differs'):self.invoke()


if __name__ == '__main__':
    unittest.main()
