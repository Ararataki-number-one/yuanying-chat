"""Synthetic negative controls for the candidate observer, not Android proof."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/browser'))
import input_delivery_diagnostics as D

SOURCE, TREE, NONCE = 'a'*40, 'b'*40, 'c'*32
IDENTITY = {'syntheticHostBoundary': True, 'sourceCommit': SOURCE, 'sourceTree': TREE,
            'apkSha256': 'd'*64, 'apkBytes': 123,
            'sdkBuildIdentity': {'runId': '1', 'runAttempt': '1', 'sourceCommit': SOURCE,
                                 'sdkBuildKind': 'source-derived-java', 'sdkAarSha256': 'e'*64}}
NATIVE_SCOPE = 'Installed synthetic integration APK bytes and embedded source stamp only'
COMPONENT = 'local.pocketchat.test/local.pocketchat.BrowserIntegrationActivity'


def current():
    return dict(sourceCommit=SOURCE, runNonce=NONCE, buildIdentity=copy.deepcopy(IDENTITY),
        stage='download-click', foreground=True, pendingChooser=False, routeAllowed=True,
        nativeInputEvents=[dict(stage='download-click', action=0, x=160, y=493,
                               eventTime=12345, handled=True, payload='DO_NOT_RETAIN_DOCUMENT')])


class DeviceBoundary:
    def __init__(self, failure=None, observations_fail=False, stdout=b'', stderr=b'', post_report=None):
        self.calls=[]; self.failure=failure; self.observations_fail=observations_fail
        self.stdout, self.stderr=stdout, stderr
        self.post_report = post_report
    def __call__(self, *parts, **kwargs):
        self.calls.append((parts,kwargs))
        if parts[:3] == ('shell','input','tap'):
            if kwargs:
                raise AssertionError('Original tap kwargs changed')
            if self.failure:
                raise self.failure
            return subprocess.CompletedProcess(parts,0,self.stdout,self.stderr)
        if kwargs != dict(check=False,timeout=D.OBSERVATION_TIMEOUT):
            raise AssertionError('Diagnostic budget changed')
        if self.observations_fail:
            raise subprocess.TimeoutExpired(parts,2,output=b'not a complete observation')
        if parts == ('shell','dumpsys','-t','1','window','windows'):
            raw=('mTopFocusedDisplayId=0\nmCurrentFocus=Window{abc u0 '+COMPONENT+'}\n'
                 'mFocusedApp=ActivityRecord{abc u0 '+COMPONENT+'}\n'
                 'title=DO_NOT_RETAIN_ACCOUNT_OR_DOCUMENT\n').encode()
        elif parts == ('shell','dumpsys','-t','1','input'):
            raw=('DispatchEnabled: true\nDispatchFrozen: false\n'
                 "  name='abc "+COMPONENT+"' displayId=0 ownerPid=123 ownerUid=10001 visible=true secret=DO_NOT_RETAIN_ACCOUNT_OR_DOCUMENT\n").encode()
        elif parts[:3] == ('exec-out','content','read'):
            raw=json.dumps(current() if self.post_report is None else self.post_report).encode()
        elif parts[0] == 'logcat':
            raw=("11-09 15:23:10.123  500  501 W InputDispatcher: Window 'abc "+COMPONENT+"' is not ready for input\n"
                 "11-09 15:23:10.125  500  501 W InputDispatcher: DO_NOT_RETAIN_ACCOUNT_OR_DOCUMENT\n").encode()
        elif parts[:2] == ('shell','getprop'):
            raw=b'35\n' if parts[2].endswith('.sdk') else b'15\n'
        else:
            raise AssertionError('Unexpected observation: '+repr(parts))
        return subprocess.CompletedProcess(parts,0,raw,b'')


class InputDeliveryDiagnosticsTests(unittest.TestCase):
    def run_case(self, device, operation):
        with tempfile.TemporaryDirectory() as temporary:
            counter=iter(range(1000,10000))
            d=D.InputDeliveryDiagnostics(adb=device,output=temporary,source=SOURCE,tree=TREE,
                nonce=NONCE,identity=IDENTITY,clock=lambda:next(counter))
            result=operation(d)
            files={p.name:p.read_bytes() for p in Path(temporary).iterdir() if p.is_file()}
            return result,files,json.loads(files['browser-input-delivery-diagnostics.json'])

    def test_exactly_one_original_tap_and_actual_raw_return_are_preserved(self):
        device=DeviceBoundary(stdout=b'actual stdout\x00\xff\n',stderr=b'actual stderr\r\n')
        _,files,receipt=self.run_case(device,lambda d:(d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity']),d.finish('failed')))
        taps=[x for x in device.calls if x[0][:3]==('shell','input','tap')]
        self.assertEqual(taps,[(('shell','input','tap','160','493'),{})])
        row=receipt['taps'][0]
        self.assertEqual(row['returnCode'],0);self.assertEqual(row['commandInvocations'],1)
        self.assertLess(row['startedMonotonicNs'],row['completedMonotonicNs'])
        self.assertEqual(files[row['stdout']['file']],device.stdout)
        self.assertEqual(files[row['stderr']['file']],device.stderr)
        self.assertTrue(row['stdout']['complete']);self.assertEqual(receipt['workloadStatus'],'failed')
        self.assertFalse(receipt['acceptanceResultOverridden']);self.assertFalse(receipt['retryPerformed'])

    def test_same_nonzero_exception_survives_post_observation_failure(self):
        original=subprocess.CalledProcessError(7,['original'],output=b'out',stderr=b'rejected')
        device=DeviceBoundary(failure=original,observations_fail=True)
        def operation(d):
            with self.assertRaises(subprocess.CalledProcessError) as caught:d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity'])
            self.assertIs(caught.exception,original)
            d.finish('failed')
        _,files,r=self.run_case(device,operation)
        self.assertEqual(r['taps'][0]['returnCode'],7)
        self.assertEqual(files[r['taps'][0]['stderr']['file']],b'rejected')
        self.assertEqual(len([x for x in device.calls if x[0][:3]==('shell','input','tap')]),1)

    def test_timeout_keeps_partial_bytes_and_never_replays(self):
        original=subprocess.TimeoutExpired(['original'],30,output=b'partial',stderr=b'partial error')
        device=DeviceBoundary(failure=original)
        def operation(d):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity'])
            self.assertIs(caught.exception,original)
            d.finish('failed')
        _,files,r=self.run_case(device,operation);row=r['taps'][0]
        self.assertIsNone(row['returnCode']);self.assertFalse(row['stdout']['complete'])
        self.assertEqual(files[row['stdout']['file']],b'partial')
        self.assertEqual(len([x for x in device.calls if x[0][:3]==('shell','input','tap')]),1)

    def test_ordinary_observation_failure_does_not_skip_original_tap(self):
        device=DeviceBoundary(observations_fail=True)
        _,_,r=self.run_case(device,lambda d:(d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity']),d.finish('failed')))
        row=r['taps'][0];self.assertEqual(row['returnCode'],0)
        self.assertTrue(all(x.get('status')=='observation-failed' for x in row['before'][1:]))
        self.assertTrue(all(x.get('status')=='observation-failed' for x in row['after']))

    def test_duplicate_stage_rejected_without_second_input(self):
        device=DeviceBoundary()
        def operation(d):
            d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity'])
            with self.assertRaises(ValueError):d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity'])
            d.finish('failed')
        self.run_case(device,operation)
        self.assertEqual(len([x for x in device.calls if x[0][:3]==('shell','input','tap')]),1)

    def test_unknown_stage_or_coordinate_never_reaches_input(self):
        device=DeviceBoundary()
        def operation(d):
            for stage,x in [('retry-download',160),('download-click',True),('download-click',-1)]:
                with self.assertRaises(ValueError):d.tap(stage,x,493,current(),verified_identity=current()['buildIdentity'])
            d.finish('failed')
        self.run_case(device,operation)
        self.assertFalse(any(x[0][:3]==('shell','input','tap') for x in device.calls))

    def test_document_and_account_fields_are_not_retained_by_projections(self):
        device=DeviceBoundary()
        _,files,r=self.run_case(device,lambda d:(d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity']),d.failure(),d.finish('failed')))
        self.assertNotIn(b'DO_NOT_RETAIN',b'\n'.join(files.values()))
        self.assertEqual(r['failureLog']['stdout']['retainedLines'],1)
        self.assertEqual(r['failureLog']['stdout']['excludedLines'],1)
        self.assertIn(COMPONENT.encode(),files['browser-input-failure-system-lines.txt'])

    def test_log_unknown_format_and_foreign_activity_are_not_fabricated(self):
        raw=(b'11-09 15:23:10.123  500  501 W InputDispatcher: account=user@example.invalid\n'
             b'11-09 15:23:10.123  500  501 W WindowManager: Window {abc other.app/PrivateDocument} is unresponsive\n')
        selected,meta=D.selected_failure_log(raw)
        self.assertEqual(selected,b'');self.assertEqual(meta['excludedLines'],2)
        self.assertEqual(meta['originalSha256'],hashlib.sha256(raw).hexdigest())

    def test_output_size_limit_is_explicit_and_hashes_actual_complete_capture(self):
        raw=b'x'*(D.RAW_LIMIT+17);device=DeviceBoundary(stdout=raw)
        _,files,r=self.run_case(device,lambda d:(d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity']),d.finish('failed')))
        item=r['taps'][0]['stdout'];self.assertFalse(item['complete'])
        self.assertEqual(item['originalBytes'],len(raw));self.assertEqual(item['bytes'],D.RAW_LIMIT)
        self.assertEqual(item['originalSha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(files[item['file']]),D.RAW_LIMIT)

    def test_wrong_source_nonce_or_installed_identity_cannot_create_activity_observation(self):
        for key,value in [('sourceCommit','d'*40),('runNonce','e'*32),('buildIdentity',{})]:
            with self.subTest(key=key):
                report=current();report[key]=value
                result=D.activity_projection(json.dumps(report).encode(),source=SOURCE,nonce=NONCE,identity=IDENTITY)
                self.assertEqual(result['status'],'binding-rejected');self.assertNotIn('nativeInputEvents',result)

    def test_actual_native_scope_survives_full_verified_identity_binding(self):
        observed=current();observed['buildIdentity']['scope']=NATIVE_SCOPE
        device=DeviceBoundary(post_report=observed)
        _,_,receipt=self.run_case(device,lambda d:(d.tap('download-click',160,493,observed,
            verified_identity=observed['buildIdentity']),d.finish('failed')))
        row=receipt['taps'][0]
        self.assertEqual(row['identityBinding'],'exact-already-verified-installed-identity')
        self.assertEqual(row['before'][0]['observation']['status'],'projected')
        self.assertEqual(row['after'][-1]['stdout']['status'],'projected')
        self.assertEqual(row['after'][-1]['stdout']['nativeInputEvents'][0]['eventTime'],12345)
        self.assertEqual(len([x for x in device.calls if x[0][:3]==('shell','input','tap')]),1)

    def test_changed_actual_apk_source_or_sdk_cannot_be_bound_as_verified_baseline(self):
        for field,value in [('sourceCommit','f'*40),('apkSha256','f'*64),
                            ('sdkBuildIdentity',dict(IDENTITY['sdkBuildIdentity'],runAttempt='2'))]:
            with self.subTest(field=field):
                observed=current();observed['buildIdentity']['scope']=NATIVE_SCOPE
                observed['buildIdentity'][field]=value;device=DeviceBoundary(post_report=observed)
                def operation(d):
                    with self.assertRaises(ValueError):d.tap('download-click',160,493,observed,
                        verified_identity=observed['buildIdentity'])
                    d.finish('failed')
                self.run_case(device,operation)
                self.assertFalse(any(x[0][:3]==('shell','input','tap') for x in device.calls))

    def test_scope_and_sdk_changes_after_one_tap_reject_only_the_diagnostic_projection(self):
        observed=current();observed['buildIdentity']['scope']=NATIVE_SCOPE
        for field,value in [('scope','changed scope'),('sourceCommit','f'*40),('apkSha256','f'*64),
                            ('sdkBuildIdentity',dict(IDENTITY['sdkBuildIdentity'],sdkAarSha256='f'*64))]:
            with self.subTest(field=field):
                after=copy.deepcopy(observed);after['buildIdentity'][field]=value
                device=DeviceBoundary(post_report=after)
                _,_,receipt=self.run_case(device,lambda d:(d.tap('download-click',160,493,observed,
                    verified_identity=observed['buildIdentity']),d.finish('failed')))
                row=receipt['taps'][0]
                self.assertEqual(row['returnCode'],0)
                self.assertEqual(row['after'][-1]['stdout']['status'],'binding-rejected')
                self.assertNotIn('nativeInputEvents',row['after'][-1]['stdout'])
                self.assertEqual(len([x for x in device.calls if x[0][:3]==('shell','input','tap')]),1)

    def test_over_limit_or_invalid_dump_is_marked_and_not_projected(self):
        for raw,status in [(b'x'*(D.STATE_LIMIT+1),'over-limit'),(b'\xff','invalid-utf8')]:
            result=D.state_projection(raw,'input');self.assertEqual(result['status'],status)
            self.assertEqual(result['controlledComponents'],[]);self.assertEqual(result['controlledWindowFields'],[])

    def test_failure_logs_are_post_failure_only_and_use_only_two_tags(self):
        device=DeviceBoundary()
        def operation(d):
            d.tap('download-click',160,493,current(),verified_identity=current()['buildIdentity'])
            self.assertFalse(any(p[0][0]=='logcat' for p in device.calls))
            d.failure();d.finish('failed')
        self.run_case(device,operation)
        calls=[p for p in device.calls if p[0][0]=='logcat'];self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0][-3:],('InputDispatcher:I','WindowManager:I','*:S'))
        self.assertEqual(calls[0][1],dict(check=False,timeout=2))


if __name__=='__main__':unittest.main(verbosity=2)
