"""The single authorized publication must not become a general gate bypass."""
import copy
import unittest
from release_203_authorization import (SOURCE, ARTIFACT, UNSIGNED, SIGNER, EXCEPTION,
                                       ISSUES, IDENTITY, verify_record)


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = dict(version='2.0.3', versionCode=56, sourceCommit=SOURCE,
            unsignedSha256=UNSIGNED, signerSha256=SIGNER, package='local.pocketchat',
            filename='PocketChat-2.0.3-gecko-arm64.apk', channel='stable',
            releaseException=EXCEPTION, nativeRegression='incomplete-with-known-issue',
            physicalArmPhone='not-tested', knownIssues=ISSUES, buildArtifactCommit=ARTIFACT,
            sha256='a'*64, bytes=119000000)
        self.record = {key: self.manifest[key] for key in IDENTITY}
        self.record.update(schema=1, kind=EXCEPTION, requestedBy='user', userRequest='发布',
            disclosedIssues=ISSUES, recordedAt='2026-10-15T12:00:00Z', physicalPhoneAcceptance='not-reported')

    def test_explicit_request_keeps_failed_status(self):
        self.assertEqual(verify_record(self.manifest, self.record), self.record)
        self.assertNotEqual(self.manifest['nativeRegression'], 'passed')

    def test_different_release_source_build_signer_and_identity_rejected(self):
        for key, value in [('version','2.0.4'),('versionCode',57),('sourceCommit','b'*40),
            ('unsignedSha256','b'*64),('signerSha256','b'*64),('buildArtifactCommit','b'*40),
            ('sha256','b'*64),('bytes',123),('package','other'),('channel','candidate')]:
            m = dict(self.manifest, **{key:value})
            with self.subTest(key=key), self.assertRaises(ValueError): verify_record(m,self.record)

    def test_no_false_acceptance_or_hidden_issues(self):
        for key, value in [('nativeRegression','passed'),('physicalArmPhone','passed'),
                           ('knownIssues',[]),('manualAcceptance',{}),
                           ('controlledCaretCompatibilityRegression',{'status':'passed'})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_record(dict(self.manifest, **{key:value}),self.record)

    def test_authorization_must_preserve_actual_request_and_scope(self):
        for key, value in [('userRequest','继续'),('userRequest','不要发布'),('requestedBy','automation'),
            ('disclosedIssues',[]),('physicalPhoneAcceptance','passed'),('recordedAt','2026-10-15'),
            ('kind','general-override'),('sha256','b'*64)]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                verify_record(self.manifest,dict(self.record, **{key:value}))
        extra=copy.deepcopy(self.record);extra['actualPhysicalPhoneExecution']=True
        with self.assertRaises(ValueError): verify_record(self.manifest,extra)


if __name__ == '__main__':
    unittest.main()
