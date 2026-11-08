"""Failure-derived host controls for actual DOM/native reading coordinates.

The immutable a9 fixture contains original failure/native-readiness evidence.
Pre-gesture DOM rectangles were not retained by that failed run. Rectangles in
these controls are explicit host DOM boundary data, never Android acceptance.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tests/gecko'),str(ROOT/'tools/gecko')]
import chrome_collapse_contract_v2 as contract
import profile_chrome_collapse_v2_test as packets
import profile_chrome_collapse_v2_driver_test as whole

FIXTURE=ROOT/'tests/fixtures/chrome-v2-readable-failure-a9.json'
FIXTURE_SHA='78c464b3c2621ef84727b94269e20d624e64eb33e42179cbe7db502c4a75c39f'

def original_failure():
    raw=FIXTURE.read_bytes()
    assert len(raw)<=8192 and hashlib.sha256(raw).hexdigest()==FIXTURE_SHA
    return json.loads(raw)

def set_dom(sample,*,form_top=170,visual=None):
    width=sample['webWidth']/3;height=sample['webHeight']/3
    sample.update(innerWidth=width,innerHeight=height)
    sample['readingViewport']=dict(schema=1,coordinateSpace='layout-viewport-css',document=sample['document'],
        layoutWidth=width,layoutHeight=height,visualBounds=visual or [0,0,width,height],
        mainBounds=[8,-200,width-8,11800],composerBounds=[8,form_top,8+(width-16)*.9,height],
        composerTag='FORM',composerId='composer')
    return sample

def captured_native_sample():
    observed=original_failure()['scenarios'][0]['nativeSnapshot']
    left,top,right,bottom=observed['webBounds']
    sample=copy.deepcopy(packets.make_case(360,2,'e'*32)['observations']['ready'])
    sample.update(webX=left,webY=top,webWidth=right-left,webHeight=bottom-top)
    return set_dom(sample)


class CapturedViewportDevice(whole.ControlledDevice):
    """Real run with recorded font2 native size and controlled DOM observations."""
    def __init__(self):
        super().__init__()
        case=self.cases[2];observed=original_failure()['scenarios'][0]['nativeSnapshot']
        x,y,right,bottom=observed['webBounds'];collapsed_height=bottom-y
        for sample in case['observations'].values():
            # Only the collapsed native bounds are original. The other packet
            # dimensions are a consistent host geometry model of this viewport.
            height=collapsed_height if not sample['expanded'] else collapsed_height-50
            if sample['readingActive']:height=collapsed_height+100
            sample.update(webX=x,webY=bottom-height,webWidth=right-x,webHeight=height)
            set_dom(sample,form_top=height/3-88)
        phases={'up':('initial','up'),'down':('up','down'),
            'horizontal':('compactReturn','horizontal'),'short':('horizontal','short'),
            'upBeforeLongPress':('short','up'),'upBeforeNetwork':('environmentReturn','up'),
            'upBeforeResume':('readingReturn','up')}
        for before,after in [('initial','up'),('up','down'),('compactReturn','horizontal'),
                ('horizontal','short'),('short','upBeforeLongPress'),
                ('environmentReturn','upBeforeNetwork'),('readingReturn','upBeforeResume')]:
            previous=case['observations'][before]
            for touch in case['observations'][after]['touches']:
                touch.update(width=previous['webWidth'],height=previous['webHeight'])
        for touch in case['observations']['headerUp']['nativeTouches']:touch['height']=collapsed_height-50
        for action in case['actualAndroidInputs']:
            if action['label'] in phases:
                phase,direction=phases[action['label']]
                action['from'],action['to']=contract.reading_swipe_points(case['observations'][phase],direction)
        packets.bind_events(case)

class MissingCompactDevice(whole.ControlledDevice):
    """Keep the observed terminal state a failure, never invent a capsule."""
    def __init__(self):
        super().__init__()
        terminal=self.cases[2]['observations']['upBeforeLongPress']
        terminal.update(compactTap=None,expanded=True,keyboard=True)
        packets.bind_events(self.cases[2])


class ChromeReadingRegionControls(unittest.TestCase):
    def test_original_two_failure_artifacts_and_captured_native_rectangles_are_fixed(self):
        value=original_failure()
        self.assertEqual((value['runId'],value['runAttempt']),(42509705450,1))
        self.assertEqual(value['sourceCommit'],'a9daefb514a4e47126cc51c79813a0daedae779a')
        self.assertIs(value['originalPreGestureDomRectanglesRetained'],False)
        self.assertIs(value['fixDeviceAcceptance'],False)
        self.assertEqual(value['terminalError'],"TypeError: 'NoneType' object is not subscriptable")
        self.assertIs(value['legacyRawRunnerMatchesBothOriginalFailedArtifactSourceReports'],True)
        self.assertEqual([s['scenario'] for s in value['scenarios']],['cold','after-reload'])
        for row in value['scenarios']:
            self.assertEqual(row['nativeSnapshot']['webBounds'],[0,420,1080,1194])
            self.assertEqual(row['nativeSnapshot']['compactBounds'],[48,72,1032,216])
            self.assertEqual(row['nativeSnapshot']['sourceCommit'],value['sourceCommit'])
            self.assertEqual(len(row['zipSha256']),64)
            self.assertEqual(row['originalRunnerSha256'],value['legacyRawRunnerSha256'])

    def test_actual_old_swipe_can_enter_the_complete_form_in_the_captured_native_viewport(self):
        value=original_failure();source=value['legacySwipeFunction']
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),value['legacySwipeFunctionSha256'])
        commands=[];namespace=dict(inputs=[],send=lambda value:None,adb=lambda *args:commands.append(args),
            snapshot=lambda value:dict(keyboard=True,compactTap=None,expanded=True))
        exec(compile(ast.parse(source),'<original-whole-web-swipe-negative>','exec'),namespace)
        sample=captured_native_sample();result=namespace['swipe'](sample,'short','short')
        self.assertEqual(commands,[('shell','input','swipe','540','936','540','924','320')])
        # Controlled form top=170 CSS maps to y=930. This demonstrates the
        # whole-view percentage defect, not an unretained original DOM rectangle.
        self.assertGreaterEqual(int(commands[0][4]),930)
        self.assertIsNone(result['compactTap'])
        start,end=contract.reading_swipe_points(sample,'short')
        self.assertEqual((start,end),([540,866],[540,854]))
        self.assertLess(max(start[1],end[1]),930)

    def test_measured_visual_offset_maps_once_and_long_swipes_keep_the_native_40dp_threshold(self):
        sample=captured_native_sample();set_dom(sample,form_top=130,visual=[10,20,190,149])
        self.assertEqual(contract.reading_swipe_points(sample,'up'),([540,997],[540,503]))
        self.assertEqual(contract.reading_swipe_points(sample,'down'),([540,503],[540,997]))
        self.assertEqual(contract.reading_swipe_points(sample,'horizontal'),([270,750],[809,750]))
        self.assertEqual(contract.reading_swipe_points(sample,'short'),([540,997],[540,985]))
        self.assertGreaterEqual(997-503,40*480/160)

    def test_complete_form_is_excluded_even_where_its_textarea_would_not_cover(self):
        sample=captured_native_sample();sample['readingViewport']['composerBounds'][1]=120
        start,end=contract.reading_swipe_points(sample,'horizontal')
        self.assertLess(max(start[1],end[1]),420+120*3)
        self.assertGreater(min(start[0],end[0]),sample['webWidth']/5)
        self.assertLess(max(start[0],end[0]),sample['webWidth']*4/5)

    def test_unobserved_invalid_ime_occluded_or_too_small_regions_fail_without_a_fallback(self):
        for change in ('missing','bool','nan','zero','reversed','wrong-document','wrong-form',
                       'mapping','keyboard','covered','no-main-strip','below-40dp'):
            sample=captured_native_sample();r=sample['readingViewport']
            if change=='missing':r['composerBounds']=None
            if change=='bool':r['visualBounds'][0]=False
            if change=='nan':r['mainBounds'][0]=float('nan')
            if change=='zero':r['visualBounds'][2]=r['visualBounds'][0]
            if change=='reversed':r['composerBounds'][3]=r['composerBounds'][1]-1
            if change=='wrong-document':r['document']='f'*32
            if change=='wrong-form':r['composerTag']='TEXTAREA'
            if change=='mapping':sample['webHeight']+=5
            if change=='keyboard':sample['keyboard']=True
            if change=='covered':sample['visibleDocument']=False
            if change=='no-main-strip':r['composerBounds'][1]=-1
            if change=='below-40dp':r['composerBounds'][1]=40
            with self.subTest(change=change),self.assertRaises(AssertionError):
                contract.reading_swipe_points(sample,'up')

    def test_actual_fixture_observer_reads_full_form_and_visual_viewport_without_dom_mutation(self):
        java=(ROOT/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        match=re.search(r'static final String READING_VIEWPORT=("(?:[^"\\]|\\.)*");',java)
        self.assertIsNotNone(match);script=json.loads(match[1])
        program=r'''
const vm=require('node:vm');const source=JSON.parse(process.argv[1]);const queries=[];
const deny={set(){throw Error('DOM mutation is forbidden');},defineProperty(){throw Error('DOM mutation is forbidden');}};
const element=(tag,id,bounds)=>new Proxy(Object.freeze({tagName:tag,id,getBoundingClientRect(){return Object.freeze({left:bounds[0],top:bounds[1],right:bounds[2],bottom:bounds[3]});}}),deny);
const main=element('MAIN','',[8,-200,352,11800]),form=element('FORM','composer',[8,170,317.6,258]);
const document=new Proxy(Object.freeze({documentElement:Object.freeze({dataset:Object.freeze({reloadDocument:'d'.repeat(32)})}),querySelector(s){queries.push(s);if(s!=='main')throw Error('unexpected selector');return main;},getElementById(s){queries.push(s);if(s!=='composer')throw Error('observe the whole form');return form;}}),deny);
const result=vm.runInNewContext(source,{document,window:Object.freeze({visualViewport:Object.freeze({offsetLeft:0,offsetTop:0,width:360,height:258})}),innerWidth:360,innerHeight:258});
process.stdout.write(JSON.stringify({result,queries}));
'''
        run=subprocess.run(['node','-e',program,json.dumps(script)],check=True,capture_output=True,text=True,timeout=10)
        observed=json.loads(run.stdout)
        self.assertEqual(observed['queries'],['main','composer'])
        self.assertEqual(observed['result'],captured_native_sample()['readingViewport'])

    def test_real_current_run_retains_all_actions_and_oracles_with_the_captured_font2_viewport(self):
        device=CapturedViewportDevice()
        harness=whole.ChromeV2DriverBoundaryTests()
        with tempfile.TemporaryDirectory(prefix='chrome-font2-reading-host-') as temporary:
            result=harness.run_driver(device,Path(temporary))
        self.assertEqual(len(result['cases']),3)
        self.assertEqual(len(device.emissions),90)
        self.assertEqual(len(device.snapshots),87)
        self.assertEqual(len(device.provider_reads),87)
        self.assertEqual(device.final_verifications[0]['checks'],48)
        self.assertEqual(len([r for r in device.emissions if r[1]=='swipe']),24)
        for case in result['cases']:
            self.assertEqual(len(case['actualAndroidInputs']),30)
            self.assertEqual(len(case['eventTransfer']['events']),29)
            self.assertEqual([g['durationMs'] for g in case['actualAndroidInputs'] if g['kind']=='swipe'],[320]*8)

    def test_original_no_capsule_terminal_state_cannot_emit_a_fallback_long_press(self):
        device=MissingCompactDevice();harness=whole.ChromeV2DriverBoundaryTests()
        with tempfile.TemporaryDirectory(prefix='chrome-no-capsule-host-') as temporary:
            with self.assertRaisesRegex(AssertionError,'no long press emitted'):
                harness.run_driver(device,Path(temporary))
        self.assertEqual([(kind,label) for owner,kind,label,_ in device.emissions if owner==2],list(whole.INPUT_SPEC[:9]))
        self.assertEqual(device.action_index,9)
        self.assertEqual(len(device.provider_reads),68)
        self.assertFalse(any(owner==2 and phase=='environmentMenu' for owner,phase,_ in device.snapshots))
        self.assertEqual(device.final_verifications,[])


if __name__=='__main__':unittest.main(verbosity=2)
