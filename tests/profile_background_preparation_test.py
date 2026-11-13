"""Actual lifecycle inputs and controlled boundary cases; not Android acceptance."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import glass_ui_validation as validation
FIXTURES=ROOT/'tests/fixtures/background-api35'
PACKAGE='local.pocketchat.test'
COMPONENT=PACKAGE+'/local.pocketchat.CompactChromeIntegrationActivity'
PID=12073
ACTIVITY=(FIXTURES/'default-dark-background-activity.txt').read_text()
GFX=(FIXTURES/'default-dark-background-gfxinfo-0.txt').read_text()


def stopped():
    """Explicit host-only mutation, never relabelled as an Android observation."""
    return ACTIVITY.replace('state=PAUSED','state=STOPPED').replace(
        'mVisibleRequested=false mVisible=true mClientVisible=true',
        'mVisibleRequested=false mVisible=false mClientVisible=false')


def hidden():return GFX.replace('(visibility=0)','(visibility=8)')


def change_field(old,new):
    raw=stopped();start=re.search(r'(?m)^\s*\* Hist[^\n]*'+re.escape(COMPONENT)+r'[^\n]*$',raw).start()
    return raw[:start]+raw[start:].replace(old,new,1)


class BackgroundPreparationTest(unittest.TestCase):
    def state(self,activity=None,gfx=None,pid=PID):
        return validation.background_state(stopped() if activity is None else activity,
            hidden() if gfx is None else gfx,package=PACKAGE,component=COMPONENT,pid=pid)

    def test_actual_paused_inputs_are_pinned_and_not_ready(self):
        proof=json.loads((FIXTURES/'provenance.json').read_text())
        for row in proof['files']:
            raw=(FIXTURES/row['file']).read_bytes()
            self.assertEqual(len(raw),row['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        value=self.state(ACTIVITY,GFX);self.assertEqual(value['state'],'PAUSED');self.assertFalse(value['ready'])

    def test_declared_stopped_hidden_control_is_ready(self):
        value=self.state();self.assertTrue(value['ready']);self.assertEqual(value['pid'],PID)
        self.assertFalse(any(value['visibility'].values()))

    def test_all_lifecycle_and_visibility_conditions_are_required(self):
        for state in ('PAUSED','PAUSING','STOPPING','RESUMED'):
            with self.subTest(state=state):self.assertFalse(self.state(change_field('state=STOPPED','state='+state))['ready'])
        for key in ('mVisibleRequested','mVisible','mClientVisible'):
            with self.subTest(key=key):self.assertFalse(self.state(change_field(key+'=false',key+'=true'))['ready'])
        for v in (0,4):self.assertFalse(self.state(gfx=hidden().replace('(visibility=8)','(visibility='+str(v)+')'))['ready'])

    def test_resumed_destination_must_be_outside_the_application(self):
        for key in ('topResumedActivity=', 'Resumed: ', 'ResumedActivity: '):
            raw=re.sub(r'('+re.escape(key)+r'ActivityRecord\{[^\n]*?u0 )[^\s/]+/[^\s]+',r'\g<1>'+COMPONENT,stopped())
            self.assertNotEqual(raw,stopped())
            with self.subTest(key=key):self.assertFalse(self.state(raw)['ready'])

    def test_pid_mismatch_in_each_observation_rejects(self):
        for activity,gfx,pid in ((stopped(),hidden(),PID+1),
            (stopped().replace(str(PID)+':'+PACKAGE,str(PID+1)+':'+PACKAGE),hidden(),PID),
            (stopped(),hidden().replace('pid '+str(PID),'pid '+str(PID+1)),PID)):
            with self.subTest(pid=pid),self.assertRaises(ValueError):self.state(activity,gfx,pid)

    def test_missing_and_duplicate_activity_fields_reject(self):
        for key in ('state=STOPPED','mVisible=false','mVisibleRequested=false','mClientVisible=false'):
            for value in ('',key+' '+key):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.state(change_field(key,value))
        with self.assertRaises(ValueError):self.state(stopped().replace('* Hist  #0: ActivityRecord','* Other #0: ActivityRecord',1))

    def test_unknown_missing_duplicate_and_foreign_roots_reject(self):
        line=next(x for x in hidden().splitlines() if 'ViewRootImpl@' in x and '(visibility=' in x)
        values=(hidden().replace(line,''),hidden().replace(line,line+'\n'+line),
            hidden().replace(line,line+'\n'+COMPONENT+'/android.view.ViewRootImpl@abc (unknown=8)'),
            hidden().replace(line,line+'\nforeign.app/Foreign/android.view.ViewRootImpl@abc (visibility=8)'),
            hidden().replace('View hierarchy:','No closing boundary:'))
        for value in values:
            with self.subTest(value=value[:100]),self.assertRaises(ValueError):self.state(gfx=value)

    def test_unknown_field_values_cannot_hide_a_conflicting_observation(self):
        for token in ('state=STOPPED','mVisibleRequested=false','mVisible=false','mClientVisible=false'):
            key=token.split('=')[0]
            for value in (key+'=unknown',token+' '+key+'=unknown',token+' '+key+'='):
                with self.subTest(token=token,value=value),self.assertRaises(ValueError):self.state(change_field(token,value))

    def test_declared_root_total_matches_all_observed_roots(self):
        for token in ('', 'Total ViewRootImpl   : 2', 'Total ViewRootImpl   : unknown',
                      'Total ViewRootImpl   : 1\nTotal ViewRootImpl   : 1',
                      'Total ViewRootImpl   : 1\nTotal ViewRootImpl   : ',
                      'Total ViewRootImpl   : 1\nTotal ViewRootImpl   : 1 extra'):
            with self.subTest(token=token),self.assertRaises(ValueError):
                self.state(gfx=hidden().replace('Total ViewRootImpl   : 1',token))

    def test_every_owned_root_must_be_gone_and_hierarchy_repeats_are_separate(self):
        line=next(x for x in hidden().splitlines() if 'ViewRootImpl@' in x and '(visibility=' in x)
        for v in (0,4,8):
            value=hidden().replace(line,line+'\n'+PACKAGE+'/local.pocketchat.Other/android.view.ViewRootImpl@abc (visibility='+str(v)+')').replace('Total ViewRootImpl   : 1','Total ViewRootImpl   : 2')
            self.assertEqual(self.state(gfx=value)['ready'],v==8)
        self.assertTrue(self.state(gfx=hidden()+'\n'+COMPONENT+'/android.view.ViewRootImpl@abc\n')['ready'])

    def exercise(self,pending=1,read_delay=0,predicate_delay=0,pid=PID):
        clock=[0.0];calls=[];attempts=[0];case={'name':'controlled'}
        def adb(*parts,timeout):
            self.assertGreater(timeout,0);self.assertLessEqual(timeout,5);calls.append(parts);clock[0]+=read_delay
            if parts[:2]==('shell','pidof'):return (str(pid)+'\n').encode()
            if parts[:3]==('shell','dumpsys','activity'):return (ACTIVITY if attempts[0]<pending else stopped()).encode()
            self.assertEqual(parts,('shell','dumpsys','gfxinfo',PACKAGE))
            value=GFX if attempts[0]<pending else hidden();attempts[0]+=1;return value.encode()
        original=validation.background_state
        def interpret(*args,**kwargs):
            value=original(*args,**kwargs);clock[0]+=predicate_delay;return value
        with tempfile.TemporaryDirectory() as directory,patch.object(validation,'time',SimpleNamespace(
            monotonic=lambda:clock[0],time_ns=lambda:int(clock[0]*1e9),sleep=lambda s:clock.__setitem__(0,clock[0]+s))),patch.object(validation,'background_state',interpret):
            self.case=case
            result=validation.prepare_background(case,adb,Path(directory),package=PACKAGE,component=COMPONENT,pid=PID)
            for row in result['observations']:
                for key in ('activity','gfxinfo'):
                    self.assertEqual(hashlib.sha256((Path(directory)/row[key]['file']).read_bytes()).hexdigest(),row[key]['sha256'])
        return result,calls

    def test_actual_preparation_records_transition_without_mutating_the_device(self):
        result,calls=self.exercise();self.assertEqual(result['status'],'ready');self.assertEqual(len(result['observations']),2)
        self.assertFalse(result['observations'][0]['state']['ready']);self.assertTrue(result['observations'][1]['state']['ready'])
        self.assertFalse(result['framesUsedForReadiness']);self.assertTrue(all(c[1] in ('pidof','dumpsys') for c in calls))

    def test_late_success_and_replaced_process_never_pass(self):
        for kwargs in ({'read_delay':15,'pending':0},{'predicate_delay':15,'pending':0},{'pending':1000}):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(TimeoutError,'15 seconds'):self.exercise(**kwargs)
            self.assertEqual(self.case['backgroundPreparation']['status'],'failed')
        with self.assertRaisesRegex(ValueError,'process exited or changed'):self.exercise(pid=PID+1)

    def test_frame_counts_do_not_choose_preparation(self):
        self.assertTrue(self.state(gfx=re.sub(r'Total frames rendered: \d+','Total frames rendered: 999999999',hidden()))['ready'])

    def test_actual_quiet_window_keeps_settling_two_counts_and_zero_budget(self):
        tree=ast.parse(Path(validation.__file__).read_text())
        quiet=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='quiet')
        for frames,accepted in (([10,10],True),([10,11],False),([10,9],False)):
            with self.subTest(frames=frames),tempfile.TemporaryDirectory() as directory:
                sleeps=[];calls=[];diagnostics=[];counts=iter(frames);case={'name':'actual-quiet'}
                def adb(*parts):calls.append(parts);return ('Total frames rendered: '+str(next(counts))+'\n').encode()
                ns=dict(vars(validation),adb=adb,package=PACKAGE,args=SimpleNamespace(out=Path(directory)),
                    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(),
                    time=SimpleNamespace(sleep=sleeps.append,time_ns=lambda:len(calls)*1500000000),
                    idle_diagnostic=lambda *args:diagnostics.append(args))
                exec(compile(ast.Module(body=[quiet],type_ignores=[]),str(validation.__file__),'exec'),ns)
                if accepted:ns['quiet'](case,'background',0)
                else:
                    with self.assertRaisesRegex(ValueError,'continued drawing'):ns['quiet'](case,'background',0)
                self.assertEqual(sleeps,[1.1,1.5]);self.assertEqual(len(calls),2)
                self.assertEqual(case['idleObservations']['background']['allowedDeltaFrames'],0)
                self.assertEqual(len(diagnostics),0 if accepted else 1)


if __name__=='__main__':unittest.main()
