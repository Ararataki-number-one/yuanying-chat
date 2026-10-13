"""Negative controls for source/APK/invocation proof; no Android execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import warnings
from copy import deepcopy
from zipfile import ZipFile
from profile_guard_metadata import prototype_metadata

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('profile_runner', ROOT / 'tests/gecko/run_profile_features.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FixtureProvenanceTest(unittest.TestCase):
    def stamp(self):
        return dict(schema=1, sourceCommit='a'*40, sourceTree='b'*40, dirtySource=False,
                    version='1.6.0', versionCode=51,
                    sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250')

    def identity(self):
        return dict(self.stamp(), package='local.pocketchat.test', apkSha256='c'*64,
                    apkBytes=100, buildStampSha256='d'*64)

    def test_expected_apk_rejects_stale_dirty_and_wrong_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'fixture.apk'
            def write(stamp):
                with ZipFile(apk,'w') as archive:
                    archive.writestr(runner.STAMP,json.dumps(stamp)+'\n')
            stamp=self.stamp();write(stamp)
            value=runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',51)
            self.assertEqual(value['apkSha256'],hashlib.sha256(apk.read_bytes()).hexdigest())
            for key, other in [('sourceCommit','e'*40),('sourceTree','f'*40),('dirtySource',True),
                               ('version','1.5.24'),('versionCode',50),('sdkCoordinate','unbound')]:
                with self.subTest(key=key):
                    write(dict(stamp,**{key:other}))
                    with self.assertRaises(ValueError):
                        runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',51)

    def test_duplicate_stamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'duplicate.apk'
            with ZipFile(apk,'w') as archive:
                archive.writestr(runner.STAMP,json.dumps(self.stamp()))
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',UserWarning)
                    archive.writestr(runner.STAMP,json.dumps(self.stamp()))
            with self.assertRaises(ValueError):
                runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',51)

    def test_each_installed_identity_field_is_required_and_matched(self):
        expected=self.identity()
        runner.verify_installed(expected,expected)
        for key in expected:
            with self.subTest(key=key):
                changed=dict(expected);changed.pop(key)
                with self.assertRaises(ValueError):runner.verify_installed(changed,expected)

    def test_host_cannot_fill_missing_device_source_or_identity(self):
        identity=self.identity(); report=dict(sourceCommit='a'*40,buildIdentity=identity,runNonce='e'*32)
        runner.verify_invocation(report,identity,'e'*32)
        for key in ['sourceCommit','buildIdentity','runNonce']:
            with self.subTest(key=key):
                changed=dict(report);changed.pop(key)
                with self.assertRaises(ValueError):runner.verify_invocation(changed,identity,'e'*32)
        with self.assertRaises(ValueError):runner.verify_invocation(report,identity,'f'*32)
        with self.assertRaises(ValueError):runner.verify_invocation(report,identity,'invalid')

    def test_partial_or_failed_device_assertions_are_rejected(self):
        valid=dict(status='passed',actualAndroidExecution=True,synthetic=True,passed=1,total=1,
                   checks=[{'name':'controlled check','pass':True}])
        runner.verify(valid,1,True)
        for edit in [dict(status='failed'),dict(actualAndroidExecution=False),dict(synthetic=False),
                     dict(passed=0),dict(total=2),dict(checks=[]),dict(error='fixture failed'),
                     dict(checks=[{'name':'controlled check','pass':False}])]:
            with self.subTest(edit=edit):
                with self.assertRaises(ValueError):runner.verify(dict(valid,**edit),1,True)

    def test_prototype_cannot_be_promoted_to_template_acceptance(self):
        report=prototype_metadata(self.identity())
        runner.verify_diagnostic(report)
        for edit in [dict(diagnosticOnly=False),dict(releaseAcceptance=True),dict(actualGeckoExecution=False),
                     dict(publicNetworkTraffic=True),dict(cases=report['cases'][:3]),dict(uncovered=[]),
                     dict(independentTimezone='enabled')]:
            with self.subTest(edit=edit):
                with self.assertRaises(ValueError):runner.verify_diagnostic(dict(report,**edit))

    def reject_guard_edits(self, edits):
        # These are counterfeit metadata controls, not device executions or SDK ACKs.
        for name, edit in edits:
            with self.subTest(name=name):
                report=prototype_metadata(self.identity());edit(report)
                with self.assertRaises(ValueError):runner.verify_diagnostic(report)

    def test_guard_requires_every_ordered_unique_true_check(self):
        def drop(report):
            report['checks'].pop(129);report['checks'].insert(0,dict(name='metadata-only replacement',**{'pass':True}))
        def duplicate(report):report['checks'][0]=deepcopy(report['checks'][129])
        def reorder(report):report['checks'][129],report['checks'][130]=report['checks'][130],report['checks'][129]
        self.reject_guard_edits([
            ('missing evidence',lambda r:r.pop('guardEvidence')),
            ('failed evidence',lambda r:r['guardEvidence'].update(status='failed')),
            ('missing assertion',drop),('duplicate assertion',duplicate),('reordered assertions',reorder),
            ('numeric pass',lambda r:r['checks'][129].update({'pass':1})),
            ('string pass',lambda r:r['checks'][129].update({'pass':'true'})),
            ('false pass',lambda r:r['checks'][129].update({'pass':False})),
        ])

    def test_guard_binds_source_invocation_document_and_native_sender(self):
        self.reject_guard_edits([
            ('wrong installed source',lambda r:r['buildIdentity'].update(sourceCommit='b'*40)),
            ('dirty installed source',lambda r:r['buildIdentity'].update(dirtySource=True)),
            ('bad source',lambda r:r.update(sourceCommit='unbound')),
            ('stale guard nonce',lambda r:r['guardEvidence'].update(nonce=r['runNonce'])),
            ('wrong original nonce',lambda r:r.update(runNonce='a'*32)),
            ('wrong guard document',lambda r:r['guardEvidence'].update(document=r['origin']+'/page?run=other')),
            ('foreign sender',lambda r:r['guardEvidence']['nativePort'].update(senderUrl='http://example.invalid/')),
            ('wrong sender session',lambda r:r['guardEvidence']['nativePort'].update(nativeSession=5002)),
            ('subframe sender',lambda r:r['guardEvidence']['nativePort'].update(topLevel=False)),
            ('numeric top level',lambda r:r['guardEvidence']['nativePort'].update(topLevel=1)),
            ('extension sender',lambda r:r['guardEvidence']['nativePort'].update(environmentType=1)),
            ('wrong primary session',lambda r:r['cases'][0]['sessions'][0]['native'].update(session=5002)),
            ('wrong runtime',lambda r:r['cases'][0]['sessions'][0]['native'].update(runtime=9002)),
            ('reused secondary session',lambda r:r['cases'][3]['sessions'][1]['native'].update(session=5001)),
            ('wrong context nonce',lambda r:r['cases'][3]['sessions'][0]['observed'].update(run='a'*32)),
            ('wrong event nonce',lambda r:r['guardEvidence']['observed'].update(nonce='a'*32)),
            ('wrong event worker',lambda r:r['guardEvidence']['observed'].update(workerUrl=r['origin']+'/worker')),
            ('boolean arm callback',lambda r:r['guardEvidence'].update(armCallback=True)),
            ('unquoted arm callback',lambda r:r['guardEvidence'].update(armCallback='guard-armed')),
            ('extra URI query',lambda r:r['guardEvidence'].update(fetchUrl=r['guardEvidence']['fetchUrl']+'&extra=1')),
            ('foreign origin',lambda r:r.update(origin='http://example.invalid:43123')),
        ])

    def test_guard_requires_real_rejections_and_both_complete_blocked_routes(self):
        self.reject_guard_edits([
            ('HTTP response',lambda r:r['guardEvidence']['observed']['fetch'].update(outcome='http-response')),
            ('worker constructed failure',lambda r:r['guardEvidence']['observed']['worker'].update(outcome='constructor-error')),
            ('worker message',lambda r:r['guardEvidence']['observed']['worker'].update(outcome='message')),
            ('untrusted worker',lambda r:r['guardEvidence']['observed']['worker'].update(trusted=False)),
            ('numeric trusted worker',lambda r:r['guardEvidence']['observed']['worker'].update(trusted=1)),
            ('one route',lambda r:r['guardEvidence']['blockedRoutes'].pop()),
            ('same route twice',lambda r:r['guardEvidence']['blockedRoutes'].__setitem__(1,deepcopy(r['guardEvidence']['blockedRoutes'][0]))),
            ('route overflow',lambda r:r['guardEvidence'].update(blockedRoutesDropped=1)),
            ('unbounded routes',lambda r:r['guardEvidence'].update(blockedRoutes=r['guardEvidence']['blockedRoutes']*5)),
            ('allowed route',lambda r:r['guardEvidence']['blockedRoutes'][0].update(guardAllowed=True)),
            ('numeric blocked flag',lambda r:r['guardEvidence']['blockedRoutes'][0].update(guardAllowed=0)),
            ('direct route',lambda r:r['guardEvidence']['blockedRoutes'][0]['route'].update(type='direct')),
            ('wrong proxy port',lambda r:r['guardEvidence']['blockedRoutes'][0]['route'].update(port=10)),
            ('wrong proxy host',lambda r:r['guardEvidence']['blockedRoutes'][0]['route'].update(host='example.invalid')),
        ])

    def test_guard_detects_listener_leakage_and_wrong_listener_identity(self):
        self.reject_guard_edits([
            ('new connection',lambda r:r['guardEvidence']['afterServer'].update(acceptedConnections=36)),
            ('new parsed request',lambda r:r['guardEvidence']['afterServer'].update(parsedRequests=36)),
            ('new header',lambda r:r['guardEvidence'].update(afterHeaderCount=31)),
            ('rewritten header array',lambda r:r['allRequestHeaders'].pop()),
            ('wrong listener port',lambda r:r['guardEvidence']['afterServer'].update(port=43124)),
            ('unbound listener',lambda r:r['guardEvidence']['afterServer'].update(bound=False)),
            ('closed listener',lambda r:r['guardEvidence']['afterServer'].update(closed=True)),
            ('boolean counter',lambda r:r['guardEvidence']['afterServer'].update(acceptedConnections=True)),
            ('negative counter',lambda r:r['guardEvidence']['beforeServer'].update(parsedRequests=-1)),
        ])

    def test_guard_clock_domains_are_separate_and_finite(self):
        report=prototype_metadata(self.identity());guard=report['guardEvidence']
        for key in ('requestedAt','nativeCallbackAt','completedAt'):guard[key]+=10**9
        guard['nativePort']['connectedAt']+=10**9
        for row in guard['blockedRoutes']:row['at']+=10**9
        # JS performance timestamps retain their own origin; completed handlers may increase.
        runner.verify_diagnostic(report)
        self.reject_guard_edits([
            ('native order',lambda r:r['guardEvidence']['nativePort'].update(connectedAt=99)),
            ('callback before port',lambda r:r['guardEvidence'].update(nativeCallbackAt=109)),
            ('completion before callback',lambda r:r['guardEvidence'].update(completedAt=119)),
            ('guard before original cases',lambda r:r['cases'][3].update(completedAt=101)),
            ('route after callback',lambda r:r['guardEvidence']['blockedRoutes'][0].update(at=121)),
            ('boolean native clock',lambda r:r['guardEvidence'].update(requestedAt=True)),
            ('negative JS clock',lambda r:r['guardEvidence']['observed']['fetch'].update(at=-1)),
            ('NaN JS clock',lambda r:r['guardEvidence']['observed']['worker'].update(at=float('nan'))),
            ('infinite JS clock',lambda r:r['guardEvidence']['observed'].update(at=float('inf'))),
            ('reversed JS clock',lambda r:r['guardEvidence']['observed'].update(at=29)),
            ('stale original document clock',lambda r:r['cases'][3]['sessions'][0]['observed']['parent'].update(at=31.5)),
        ])

    def test_user_agent_default_is_independent_sdk_build_scope(self):
        # Counterfeit metadata mutations test the validator, not SDK execution.
        self.reject_guard_edits([
            ('missing independent default',lambda r:r.pop('sdkUserAgentBaseline')),
            ('session API substituted',lambda r:r['sdkUserAgentBaseline'].update(api='GeckoSession.getUserAgent()')),
            ('runtime ACK claim',lambda r:r['sdkUserAgentBaseline'].update(runtimeAcknowledgement=True)),
            ('override-sensitive claim',lambda r:r['sdkUserAgentBaseline'].update(ignoresSessionOverrides=False)),
            ('desktop default substituted',lambda r:r['sdkUserAgentBaseline'].update(userAgent=r['cases'][1]['sessions'][0]['native']['userAgent'])),
            ('wrong SDK default',lambda r:r['sdkUserAgentBaseline'].update(userAgent=r['sdkUserAgentBaseline']['userAgent'].replace('157.0','158.0'))),
            ('wrong SDK pin',lambda r:r['sdkUserAgentBaseline'].update(sdkAarSha256='0'*64)),
            ('wrong Android release',lambda r:r['sdkUserAgentBaseline'].update(androidRelease='14')),
            ('wrong Android SDK',lambda r:r['sdkUserAgentBaseline'].update(androidSdk=28)),
            ('numeric scope flag',lambda r:r['sdkUserAgentBaseline'].update(runtimeAcknowledgement=0)),
            ('runtime setter claim',lambda r:r['userAgentCapability'].update(runtimeUserAgentSetterAvailable=True)),
            ('template acceptance claim',lambda r:r['userAgentCapability'].update(fullTemplateAcceptance=True)),
        ])
        # The pinned pre-Q API returns Android 10 even on a different device release.
        report=prototype_metadata(self.identity());report['androidSdk']=28
        report['sdkUserAgentBaseline'].update(androidSdk=28,androidRelease='9')
        old=report['sdkUserAgentBaseline']['userAgent'];new=old.replace('Android 15','Android 10')
        report['sdkUserAgentBaseline']['userAgent']=new
        for case in report['cases']:
            for session in case['sessions']:
                if session['native']['userAgent']==old:
                    session['native']['userAgent']=new
                    for context in ('parent','frame','worker','blobWorker'):session['observed'][context]['ua']=new
                for row in session['requestHeaders']:
                    if row['userAgent']==old:row['userAgent']=new
        for row in report['allRequestHeaders']:
            if row['userAgent']==old:row['userAgent']=new
        runner.verify_diagnostic(report)

    def test_user_agent_role_rules_use_real_headers_and_preserve_language(self):
        def edit_row(report,target_role,**values):
            session=report['cases'][1]['sessions'][0]
            row=next(row for row in session['requestHeaders'] if row['role']==target_role)
            row.update(values);report['allRequestHeaders'][row['sequence']-1].update(values)
        self.reject_guard_edits([
            ('desktop Worker fetch header emulation',lambda r:edit_row(r,'worker-fetch',userAgent=r['cases'][1]['sessions'][0]['native']['userAgent'])),
            ('desktop Blob Worker header emulation',lambda r:edit_row(r,'blob-worker-fetch',userAgent=r['cases'][1]['sessions'][0]['native']['userAgent'])),
            ('document forced to default',lambda r:edit_row(r,'page',userAgent=r['sdkUserAgentBaseline']['userAgent'])),
            ('wrong actual language',lambda r:edit_row(r,'worker-fetch',acceptLanguage='en-US')),
            ('JS Worker default substituted',lambda r:r['cases'][1]['sessions'][0]['observed']['worker'].update(ua=r['sdkUserAgentBaseline']['userAgent'])),
            ('missing real header',lambda r:r['cases'][1]['sessions'][0]['requestHeaders'].pop()),
            ('duplicate role',lambda r:edit_row(r,'worker-fetch',role='page-fetch')),
            ('unchanged raw row requirement',lambda r:r['cases'][1]['sessions'][0]['requestHeaders'][0].update(userAgent='modified')),
        ])

    def test_user_agent_raw_headers_bind_exact_case_and_request(self):
        def edit_row(report,**values):
            row=report['cases'][1]['sessions'][0]['requestHeaders'][4]
            row.update(values);report['allRequestHeaders'][row['sequence']-1].update(values)
        self.reject_guard_edits([
            ('foreign nonce',lambda r:edit_row(r,path='/echo?run='+'a'*32+'&case=2&session=primary&kind=worker-fetch')),
            ('extra query',lambda r:edit_row(r,path=r['cases'][1]['sessions'][0]['requestHeaders'][4]['path']+'&extra=1')),
            ('foreign absolute origin',lambda r:edit_row(r,path='http://example.invalid'+r['cases'][1]['sessions'][0]['requestHeaders'][4]['path'])),
            ('wrong case',lambda r:edit_row(r,case=1)),
            ('wrong session',lambda r:edit_row(r,session='secondary')),
            ('wrong method',lambda r:edit_row(r,method='POST')),
            ('capture before case',lambda r:edit_row(r,at=9)),
            ('capture after case',lambda r:edit_row(r,at=16)),
            ('duplicate raw sequence',lambda r:r['allRequestHeaders'][1].update(sequence=1)),
        ])

    def test_user_agent_mismatch_claims_are_derived_not_trusted(self):
        self.reject_guard_edits([
            ('desktop claimed uniform',lambda r:r['cases'][1]['sessions'][0]['userAgentScope'].update(observedUserAgentUniform=True)),
            ('desktop claimed same header',lambda r:r['cases'][1]['sessions'][0]['userAgentScope'].update(workerFetchHeadersMatchSession=True)),
            ('desktop mismatch hidden',lambda r:r['cases'][1]['sessions'][0]['userAgentScope'].update(workerFetchHeaderMismatch=False)),
            ('mobile mismatch invented',lambda r:r['cases'][0]['sessions'][0]['userAgentScope'].update(workerFetchHeaderMismatch=True)),
            ('case mismatch removed',lambda r:r['cases'][1].update(workerFetchMismatchSessions=[])),
            ('secondary mismatch hidden',lambda r:r['cases'][3].update(workerFetchMismatchSessions=[])),
            ('numeric truth claim',lambda r:r['cases'][1]['sessions'][0]['userAgentScope'].update(documentHeadersMatchSession=1)),
            ('case template claim',lambda r:r['cases'][1].update(fullTemplateAcceptance=True)),
            ('session template claim',lambda r:r['cases'][1]['sessions'][0]['userAgentScope'].update(fullTemplateAcceptance=True)),
        ])


if __name__=='__main__':
    unittest.main()
