"""Host negative controls for a read-only HOME focus observation, not Android acceptance."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
spec = importlib.util.spec_from_file_location('tested_resume_readiness', ROOT/'tools/gecko/chrome_resume_readiness.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
from profile_chrome_first_tap_readiness_test import before as original_before, packet as original_packet
from profile_chrome_first_tap_readiness_test import SOURCE, TREE, APK, NONCE, OWNER, IDENTITY

COMPONENT = module.gate.COMPONENT
FOCUS = 'Window{abc u0 '+COMPONENT+'}'


def before():
    return dict(original_before(), command='upBeforeResume', expanded=False, keyboard=False,
                toolbarVisibility=0, compactVisibility=0, page=0, webX=0, webY=210, webWidth=1080, webHeight=1455,
                nativeTouches=[dict(action=0), dict(action=2), dict(action=1)])


def packet(request=NONCE+'-801', sequence=3):
    return dict(original_packet(request, sequence), nativeTouchCount=3)


def first(binding, additional, compiled):
    return dict(status='passed', reason='clear', scope='chrome-initial-compact-tap-only', tapInvocations=1,
        diagnosticOnly=True, releaseAcceptance=False, sourceCommit=SOURCE, sourceTree=TREE, runNonce=NONCE,
        sourceSha256=dict(binding['sourceSha256'], **{k:v for k,v in additional.items() if k != module.ADAPTER}),
        parserClassesSha256=compiled['parserClassesSha256'], processIdentity=dict(OWNER),
        nativeSnapshots=[original_packet(NONCE+'-1',1), original_packet(NONCE+'-2',2)],
        windowObservations=[dict(currentFocus=FOCUS, parserState='CLEAR')])


class SnapshotPolicyTest(unittest.TestCase):
    def invoke(self, value):
        return module._validate_snapshot(value, source=SOURCE, identity=IDENTITY, nonce=NONCE,
            request=NONCE+'-801', owner=OWNER, initial=original_packet(NONCE+'-2',2), before=before())

    def test_nonzero_original_touch_count_and_exact_geometry_are_preserved(self):
        self.assertEqual(self.invoke(packet())['webBounds'], [0,210,1080,1665])
        with self.assertRaises(module.gate.HeaderReadinessFailure): self.invoke(dict(packet(), nativeTouchCount=0))

    def test_owned_unfocused_frame_is_not_fabricated_as_ready(self):
        for key, value in [('windowFocus',False),('decorFocus',False),('attached',False),('shown',False),
                           ('layoutRequested',True),('globallyVisible',False),('laidOut',False)]:
            with self.subTest(key=key): self.assertIsNone(self.invoke(dict(packet(), **{key:value})))

    def test_changed_source_process_activity_session_document_and_geometry_fail(self):
        changes = dict(sourceCommit='f'*40, sourceTree='f'*40, apkSha256='f'*64, runNonce='f'*32,
            request=NONCE+'-802', pid=9999, uid=10210, activityRef=14, surface=15, sdkSession=16, attachedSession=16,
            appearanceDocument='f'*32, documentPort=16, currentPort=16, pendingId='foreign', pendingConfirmed=False,
            expanded=True, page=1, nativeTouchCount=4, webBounds=[0,210,1080,1664], point=[541,114])
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(module.gate.HeaderReadinessFailure):
                self.invoke(dict(packet(), **{key:value}))

    def test_missing_unknown_and_type_confused_native_fields_fail_closed(self):
        for key in module.SNAPSHOT_FIELDS:
            value=packet(); del value[key]
            with self.subTest(key=key), self.assertRaises(module.gate.HeaderReadinessFailure): self.invoke(value)
        for key,value in [('schema',True),('sequence',True),('windowFocus',1),('pid',True),('unexpected','text')]:
            with self.subTest(key=key), self.assertRaises(module.gate.HeaderReadinessFailure):
                self.invoke(dict(packet(), **{key:value}))


class Transport:
    """Strict allowed-command transport; any Android input or launch is a failure."""
    def __init__(self):
        self.now=107.; self.commands=[]; self.requests=0; self.current=None
        self.frames=[]; self.focuses=[]; self.states=[]; self.owner=dict(OWNER)
        self.transport_pid=4242; self.duplicate=False; self.identity_reads=0
        self.identity_change=False; self.never_focus=False; self.missing_packet=False

    def clock(self): return self.now

    def sleep(self, seconds):
        assert 0 <= seconds <= .2
        self.now += seconds

    def identity(self, prefix, identity, deadline):
        assert deadline == 120. and identity == IDENTITY
        self.identity_reads += 1; self.now += .01
        module.gate.need(self.now < deadline, 'deadline')
        return dict(self.owner, pid='9999') if self.identity_change and self.identity_reads > 1 else self.owner

    def checked(self, parts, deadline, **kwargs):
        self.commands.append((list(parts), deadline, self.now)); self.now += .03
        module.gate.need(self.now < deadline, 'deadline')
        if parts[0] == 'controlled-parser': return self.states.pop(0) if self.states else b'CLEAR\n'
        assert parts[:3] == ['controlled-adb','-s','emulator-5554']
        values=parts[3:]
        fixed={('shell','getprop','ro.kernel.qemu'):b'1\n',('shell','getprop','ro.build.version.sdk'):b'35\n',
               ('shell','am','get-current-user'):b'0\n',('shell','getprop','ro.hardware'):b'ranchu\n'}
        if tuple(values) in fixed: return fixed[tuple(values)]
        if values == ['shell','dumpsys','window']:
            focus=self.focuses.pop(0) if self.focuses else FOCUS
            return ('WINDOW MANAGER\n mCurrentFocus='+focus+'\n').encode()
        if values[:3] == ['shell','am','broadcast']:
            assert values[values.index('eventNonce')+1] == NONCE
            assert 'collapseCommand' not in values
            request=values[values.index('collapseReadiness')+1]; self.requests += 1
            assert request == NONCE+'-'+str(800+self.requests)
            self.current=packet(request,2+self.requests)
            if self.frames: self.current.update(self.frames.pop(0))
            if self.never_focus: self.current['windowFocus']=False
            return b'Broadcast completed: result=0\n'
        if values[:3] == ['logcat','-d','-v']:
            if self.missing_packet: return b''
            line=f'11-09 17:03:01.001 {self.transport_pid:5} {self.transport_pid:5} I {module.TAG}: '+json.dumps(self.current)+'\n'
            return (line*(2 if self.duplicate else 1)).encode()
        raise AssertionError(('Unexpected or mutating readiness command', parts))


class ResumeObservationControlTest(unittest.TestCase):
    def invoke(self, transport, *, expected_error=None, mutate_first=None, diagnostic_output=False,
               receipt_expires=False, source_changes=False, deadline=120.):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory); report_out=out/'diagnostic' if diagnostic_output else out
            report_out.mkdir(exist_ok=True)
            binding=dict(sourceCommit=SOURCE, sourceTree=TREE, sourceSha256={'original-header':'f'*64})
            additional={name:hashlib.sha256(name.encode()).hexdigest() for name in module.DEPENDENCIES}
            classes={'one.class':'c'*64}; compiled=dict(cache=out, classes=classes, parserClassesSha256='d'*64)
            original=first(binding, additional, compiled)
            if mutate_first: mutate_first(original)
            argv=['--adb','controlled-adb','--serial','emulator-5554']+(['--out',str(report_out)] if diagnostic_output else [])
            saved=module._save_record
            def save(path, record):
                saved(path, record)
                if receipt_expires and record['status']=='passed': transport.now=120.01
            bindings=[(binding,additional),(dict(binding,sourceTree='e'*40),additional)] if source_changes else None
            with mock.patch.object(module,'_sources',side_effect=bindings,return_value=(binding,additional)),\
                 mock.patch.object(module.gate,'_compile_parser',return_value=(['controlled-parser'],compiled)),\
                 mock.patch.object(module.gate,'_identity',side_effect=transport.identity),\
                 mock.patch.object(module.gate,'_checked',side_effect=transport.checked),\
                 mock.patch.object(module.gate,'_class_hashes',return_value=classes),\
                 mock.patch.object(module,'_save_record',side_effect=save):
                result=None; error=None
                try:
                    result=module.wait_resume_focus(argv=argv,source=SOURCE,identity=IDENTITY,before=before(),nonce=NONCE,
                        first_readiness=original,deadline=deadline,out=out,root=out,clock=transport.clock,sleep=transport.sleep)
                except module.gate.HeaderReadinessFailure as caught: error=caught
            report_path=report_out/('chrome-resume-readiness-'+NONCE+'.json')
            report=json.loads(report_path.read_text()) if report_path.exists() else None
            if expected_error is None:
                self.assertIsNone(error); self.assertEqual(result,report); self.assertEqual(report['status'],'passed')
                self.assertLess(transport.now,deadline)
            else:
                self.assertIsNotNone(error); self.assertEqual(error.reason,expected_error)
                if report is not None: self.assertEqual(report['status'],'failed')
            if report is not None:
                self.assertEqual(report['inputInvocations'],0); self.assertEqual(report['authoritativeSnapshotInvocations'],0)
                self.assertLessEqual(len(report['nativeSnapshots']),4); self.assertLessEqual(len(report['windowObservations']),8)
                self.assertEqual(report['deadlineMonotonic'],deadline)
            self.assertTrue(all(d==deadline for _,d,_ in transport.commands))
            if diagnostic_output: self.assertFalse((out/report_path.name).exists())
            return report

    def test_two_fresh_frames_are_observed_with_only_remaining_home_budget(self):
        t=Transport(); r=self.invoke(t)
        self.assertEqual(t.requests,2); self.assertEqual(r['originalNativeTouchCount'],3)
        self.assertEqual(r['originalRoundtripStartedMonotonic'],100.)
        self.assertEqual(r['observerStartedMonotonic'],107.)
        self.assertGreaterEqual(r['originalRoundtripElapsedMs'],7000)

    def test_unfocused_frame_then_two_stable_frames_without_extra_input(self):
        t=Transport(); t.frames=[dict(windowFocus=False),{},{}]; r=self.invoke(t)
        self.assertEqual(t.requests,3); self.assertFalse(r['nativeSnapshots'][0]['windowFocus'])

    def test_persistent_missing_native_focus_expires_in_original_budget(self):
        t=Transport(); t.never_focus=True; self.invoke(t,expected_error='deadline')
        self.assertLess(t.now,120.04)

    def test_foreign_window_is_observed_without_actions_and_cannot_pass(self):
        t=Transport(); t.focuses=['Window{def u0 com.android.systemui/NotificationShade}']*101
        r=self.invoke(t,expected_error='deadline'); self.assertEqual(t.requests,0)
        self.assertIn('NotificationShade',r['windowObservations'][-1]['currentFocus'])

    def test_shade_and_temporarily_foreign_focus_require_new_observations(self):
        t=Transport(); t.focuses=['null']; t.states=[b'SHADE_VISIBLE\n']; r=self.invoke(t)
        self.assertEqual(t.requests,2)
        self.assertTrue(any(x['currentFocus']=='null' for x in r['windowObservations']))
        self.assertTrue(any(x.get('parserState')=='SHADE_VISIBLE' for x in r['windowObservations']))

    def test_changed_process_or_native_identity_cannot_pass(self):
        for fault in ('process','surface','session','activity','native-count'):
            with self.subTest(fault=fault):
                t=Transport()
                if fault=='process': t.identity_change=True
                else: t.frames=[{dict(surface='surface',session='sdkSession',activity='activityRef',**{'native-count':'nativeTouchCount'})[fault]:999}]
                self.invoke(t,expected_error='identity-changed')

    def test_forged_transport_pid_duplicate_and_stale_sequence_fail(self):
        for fault,reason in [('pid','identity-changed'),('duplicate','invalid-observation'),('sequence','invalid-observation'),('time','invalid-observation')]:
            with self.subTest(fault=fault):
                t=Transport()
                if fault=='pid': t.transport_pid=9999
                elif fault=='duplicate': t.duplicate=True
                elif fault=='sequence': t.frames=[dict(sequence=2)]
                else: t.frames=[dict(observedAtElapsedRealtime=1002)]
                self.invoke(t,expected_error=reason)

    def test_missing_native_packet_times_out_without_second_action(self):
        t=Transport(); t.missing_packet=True; self.invoke(t,expected_error='deadline'); self.assertEqual(t.requests,1)

    def test_changed_original_first_tap_identity_or_source_cannot_be_normalized(self):
        for mutate,reason in [(lambda r:r.update(sourceCommit='e'*40),'identity-changed'),
                              (lambda r:r['processIdentity'].update(pid='9999'),'identity-changed'),
                              (lambda r:r['sourceSha256'].update(extra='f'*64),'source-unverified'),
                              (lambda r:r['nativeSnapshots'][-1].update(sequence=128),'identity-changed')]:
            with self.subTest(reason=reason): self.invoke(Transport(),expected_error=reason,mutate_first=mutate)

    def test_sources_changed_during_observation_fail_closed(self):
        self.invoke(Transport(),expected_error='identity-changed',source_changes=True)

    def test_expired_or_new_budget_is_rejected_before_any_device_command(self):
        for deadline in (107.,127.01,True,float('inf')):
            with self.subTest(deadline=deadline):
                t=Transport(); self.invoke(t,expected_error='deadline',deadline=deadline); self.assertEqual(t.commands,[])

    def test_late_receipt_keeps_original_timeout_and_failed_status(self):
        t=Transport(); r=self.invoke(t,expected_error='deadline',receipt_expires=True)
        self.assertEqual(r['reason'],'deadline'); self.assertGreater(r['originalRoundtripElapsedMs'],20000)

    def test_diagnostic_output_uses_original_archived_directory(self):
        self.invoke(Transport(),diagnostic_output=True)


class SourceAndIntegrationControlTest(unittest.TestCase):
    def test_own_and_provider_sources_must_match_actual_git_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); expected={name:('source '+name).encode() for name in module.DEPENDENCIES}
            for name,raw in expected.items():
                path=root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
            def git(parts,deadline,**kwargs):
                self.assertEqual(parts[:2],['git','show']); self.assertEqual(deadline,120.)
                return expected[parts[2].split(':',1)[1]]
            with mock.patch.object(module.gate,'_source_bindings',return_value={'sourceSha256':{}}),\
                 mock.patch.object(module.gate,'_checked',side_effect=git):
                _, hashes=module._sources(root,SOURCE,IDENTITY,120.)
                self.assertEqual(set(hashes),set(module.DEPENDENCIES))
                for name in module.DEPENDENCIES:
                    path=root/name; path.write_bytes(expected[name]+b' changed')
                    with self.subTest(name=name),self.assertRaises(module.gate.HeaderReadinessFailure):
                        module._sources(root,SOURCE,IDENTITY,120.)
                    path.write_bytes(expected[name])

    def test_original_home_first_tap_and_header_helpers_are_byte_unchanged(self):
        from historical_source_inputs import historical_bytes
        expected={'tests/gecko/run_chrome_collapse.py':'edaa810f470717a45092cce966d451506d2817f9a41def33d62a1d83ed200acf',
                  'tools/gecko/chrome_first_tap_readiness.py':'27628987c416146274fc37bcc48a0537e5906b1d25e28def8d43dafe6be92216',
                  'tools/gecko/chrome_header_readiness.py':'77590576542e0e5faeb88beaab59ae6950361dee88cb6c974260f611a92b26be'}
        for name,sha in expected.items():
            raw = historical_bytes(name) if name == 'tools/gecko/chrome_first_tap_readiness.py' else (ROOT/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),sha)

    def test_current_runner_uses_one_original_roundtrip_then_observer_then_one_snapshot(self):
        tree=ast.parse((ROOT/'tests/gecko/run_chrome_collapse_v2.py').read_text())
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_v2')
        calls=[n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        home=[n for n in calls if n.func.id=='resume_after_home']; self.assertEqual(len(home),1)
        observe=[n for n in calls if n.func.id=='wait_resume_focus']; self.assertEqual(len(observe),1)
        snap=[n for n in calls if n.func.id=='snapshot' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='activityResume']
        self.assertEqual(len(snap),1); self.assertEqual(ast.unparse(home[0]),'resume_after_home(ACTIVITY)')
        definitions=[n for n in ast.walk(run) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='resume_deadline' for t in n.targets)]
        self.assertEqual(len(definitions),1); self.assertEqual(ast.unparse(definitions[0].value),'time.monotonic() + 20')
        self.assertEqual(home[0].lineno,definitions[0].lineno+1)
        self.assertLess(home[0].lineno,observe[0].lineno); self.assertLess(observe[0].lineno,snap[0].lineno)
        self.assertEqual({x.arg:ast.unparse(x.value) for x in observe[0].keywords},
            dict(argv='sys.argv[1:]',source='source',identity='identity',before="observations['upBeforeResume']",
                 nonce='nonce',first_readiness='first_readiness',deadline='resume_deadline',out='out'))


if __name__ == '__main__': unittest.main()
