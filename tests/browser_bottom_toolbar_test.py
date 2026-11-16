"""Current bottom-bar selectors and bounded real-menu protocol; no Android claim."""
import ast
import copy
import hashlib
import inspect
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import capture_glass_navigation as capture
import glass_ui_validation as validation
import workspace_navigation_contract_v3 as workspace_v3
import chrome_collapse_contract_v3 as collapse_v3


def xml(tree):return ET.tostring(tree,encoding='unicode')


def node(parent,description,box,*,text='',enabled=True,kind='android.widget.Button',**extras):
    return ET.SubElement(parent,'node',{'package':capture.PACKAGE,'class':kind,'text':text,
        'content-desc':description,'bounds':'[{},{}][{},{}]'.format(*box),
        'clickable':'true','long-clickable':'false','enabled':str(enabled).lower(),
        'visible-to-user':'true',**extras})


def toolbar(width=320,density=1,rtl=False,large=False):
    capture.set_display(width*density,640*density,160*density)
    tree=ET.Element('hierarchy')
    height=60 if large else 48
    if width>=280:
        boxes={'back':[4,520+(height-48)//2,52,568+(height-48)//2],
               'home':[52,520+(height-48)//2,100,568+(height-48)//2],
               'address':[104,520,width-104,520+height],
               'reload':[width-100,520+(height-48)//2,width-52,568+(height-48)//2],
               'menu':[width-52,520+(height-48)//2,width-4,568+(height-48)//2]}
    else:
        boxes={'address':[4,490,width-4,490+height]}
        for i,key in enumerate(('back','home','reload','menu')):
            x=4+(width-8-48)*i//3;boxes[key]=[x,494+height,x+48,542+height]
    descriptions={'back':'后退','home':'打开当前环境主页','reload':'刷新网页','menu':'浏览器菜单',
                  'address':'当前网址 https://chatgpt.com/c/long-url，点击输入网址或搜索'}
    for key in ('back','home','address','reload','menu'):
        left,top,right,bottom=boxes[key]
        if rtl:left,right=width-right,width-left
        node(tree,descriptions[key],[v*density for v in (left,top,right,bottom)],
             text='chatgpt.com/c/long-url' if key=='address' else '',enabled=key!='back')
    return tree


class CurrentBottomBarTests(unittest.TestCase):
    def setUp(self):self.display=capture.WIDTH,capture.HEIGHT,capture.DENSITY
    def tearDown(self):capture.set_display(*self.display)

    def test_current_controls_fit_narrow_large_font_and_rtl_without_fake_tabs(self):
        for width in (240,320,360,412):
            for density in (1,3):
                for rtl in (False,True):
                    with self.subTest(width=width,density=density,rtl=rtl):
                        value=xml(toolbar(width,density,rtl,large=True))
                        result=capture.browser_toolbar_geometry(value)
                        self.assertEqual(result['navigationContract'],3)
                        self.assertEqual(result['layoutMode'],'stacked' if width==240 else 'inline')
                        self.assertEqual(result['layoutDirection'],'rtl' if rtl else 'ltr')
                        self.assertEqual(set(result['actions']),{'back','home','reload','menu'})
                        self.assertFalse(result['actions']['back']['enabled'])
                        self.assertIsNotNone(capture.browser_address_node(value))
                        self.assertEqual(capture.current_observed_navigation_geometry(value)['layout'],'browser-bottom')

    def test_missing_duplicate_foreign_or_untappable_controls_cannot_pass(self):
        for index in range(5):
            for change in ('missing','duplicate','foreign','hidden','class','unclickable','small'):
                tree=toolbar();target=tree[index]
                if change=='missing':tree.remove(target)
                elif change=='duplicate':tree.append(copy.deepcopy(target))
                elif change=='foreign':target.set('package','other.application')
                elif change=='hidden':target.set('visible-to-user','false')
                elif change=='class':target.set('class','android.widget.TextView')
                elif change=='unclickable':target.set('clickable','false')
                else:target.set('bounds','[4,520][40,560]')
                with self.subTest(index=index,change=change):
                    self.assertIsNone(capture.browser_toolbar_geometry(xml(tree)))
        for index in (1,2,3,4):
            tree=toolbar();tree[index].set('enabled','false')
            self.assertIsNone(capture.browser_toolbar_geometry(xml(tree)))

    def test_overlap_wrong_order_wrong_authority_and_empty_address_fail(self):
        for change in ('overlap','order','address','authority','unknown-state'):
            tree=toolbar()
            if change=='overlap':tree[3].set('bounds','[212,520][260,568]')
            elif change=='order':tree[0].set('content-desc','打开当前环境主页');tree[0].set('enabled','true');tree[1].set('content-desc','后退')
            elif change=='address':tree[2].set('text','')
            elif change=='authority':tree[2].set('content-desc','当前网址 ，点击输入网址或搜索')
            else:tree[0].set('enabled','unknown')
            with self.subTest(change=change):self.assertIsNone(capture.browser_toolbar_geometry(xml(tree)))

    def test_page_words_are_not_mistaken_for_retired_native_navigation(self):
        tree=toolbar();node(tree,'下载',[10,300,100,348],text='下载')
        self.assertIsNotNone(capture.current_navigation(xml(tree)))
        # The original, complete four-destination chrome is rejected explicitly.
        tree=toolbar()
        capture.set_display(412,640,160)
        for label,box in zip(capture.LABELS,[(92,420,168,488),(168,420,244,488),(244,420,320,488),(340,418,412,490)]):
            node(tree,label,box,text=label)
        self.assertIsNone(capture.current_navigation(xml(tree)))

    def test_current_device_producers_do_not_call_legacy_navigation(self):
        for function in (capture.capture_motion,capture.capture_native_backdrop_preview,
                         capture.capture_navigation_typography,capture.main):
            calls=[n.func.id for n in ast.walk(ast.parse(inspect.getsource(function)))
                   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
            self.assertNotIn('navigation',calls);self.assertNotIn('navigation_geometry',calls)
            self.assertNotIn('observed_navigation_geometry',calls)
        self.assertIn("api['browser_address_node'](xml)",inspect.getsource(validation.capture_acceptance_suite))


class MenuDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.display=capture.WIDTH,capture.HEIGHT,capture.DENSITY
        capture.set_display(320,640,160)
    def tearDown(self):capture.set_display(*self.display)

    def menu(self,action=False,*,enabled=True,clipped=False):
        tree=ET.Element('hierarchy')
        node(tree,'关闭浏览器菜单',[264,120,312,168])
        node(tree,'',[8,170,312,600],kind='android.widget.ScrollView',scrollable='true')
        if action:node(tree,'下载管理',[20,210,300,230 if clipped else 266],text='下载管理',enabled=enabled)
        return xml(tree)

    def run_menu(self,initial,read,*,now=10,deadline=30):
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(capture.time,'monotonic',return_value=now):
            adb=mock.Mock();reader=mock.Mock();reader.read.side_effect=read;inputs=[]
            result=capture.menu_action(reader,adb,initial,'下载管理',directory,'host',deadline,inputs)
            files={path.name:path.read_text() for path in Path(directory).glob('*.xml')}
            return result,adb,reader,inputs,files

    def test_scroll_uses_current_native_bounds_and_one_original_deadline(self):
        result,adb,reader,inputs,files=self.run_menu(self.menu(),[self.menu(action=True)])
        self.assertEqual(result[1].get('text'),'下载管理')
        reader.read.assert_called_once_with(deadline=30)
        self.assertEqual(adb.call_args.args,('shell','input','touchscreen','swipe','160','576','160','194','300'))
        self.assertEqual(len(inputs),1);self.assertEqual(inputs[0]['action'],'menu-scroll')
        self.assertEqual(len(files),2)
        self.assertEqual(files['host-menu-0.xml'],self.menu())

    def test_expired_menu_cannot_scroll_or_accept_visible_target(self):
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(capture.time,'monotonic',return_value=30):
            adb=mock.Mock();reader=mock.Mock()
            with self.assertRaises(TimeoutError):capture.menu_action(reader,adb,self.menu(action=True),'下载管理',directory,'host',30,[])
            adb.assert_not_called();reader.read.assert_not_called()

    def test_late_read_and_failed_read_cannot_reuse_old_or_partial_coordinates(self):
        for failure in ('late','error','closed'):
            clock=[10]
            reader=mock.Mock();adb=mock.Mock();inputs=[]
            def read(**options):
                self.assertEqual(options,{'deadline':30})
                if failure=='error':raise TimeoutError('bounded hierarchy failed')
                if failure=='late':clock[0]=31
                return '<hierarchy/>' if failure=='closed' else self.menu(action=True)
            reader.read.side_effect=read
            with tempfile.TemporaryDirectory() as directory,mock.patch.object(capture.time,'monotonic',side_effect=lambda:clock[0]):
                with self.subTest(failure=failure),self.assertRaises((TimeoutError,ValueError)):
                    capture.menu_action(reader,adb,self.menu(action=True,clipped=True),'下载管理',directory,'host',30,inputs)
                self.assertEqual(adb.call_count,1)
                self.assertEqual(reader.read.call_count,1)


class MotionProtocolTests(unittest.TestCase):
    """Execute the actual recorder protocol with explicit process/ADB boundaries."""
    def run_motion(self,*,recorder_dies_on_scroll=False,cancel_opens_menu=False):
        display=capture.WIDTH,capture.HEIGHT,capture.DENSITY
        self.addCleanup(lambda:capture.set_display(*display))
        tree=toolbar()
        node(tree,'当前环境：环境，点按输入网址，长按切换环境',[80,24,240,76],text='环境')
        chat=xml(tree);clock=[10.0];state={'screen':'chat','scrolled':False};calls=[]
        nonce='a'*32;remote='/data/local/tmp/pocketchat-glass-motion-'+nonce+'.mp4'
        video=b'controlled host video boundary, not an Android recording'
        process=SimpleNamespace(returncode=None,args=['controlled-screenrecord'])
        process.poll=lambda:process.returncode
        def stop(timeout=None):return process.returncode
        process.wait=stop
        process.terminate=lambda:setattr(process,'returncode',-15)
        process.kill=lambda:setattr(process,'returncode',-9)
        def hierarchy():
            if state['screen']=='chat':return chat
            if state['screen']=='menu':return MenuDeadlineTests().menu(action=state['scrolled'])
            tree=ET.Element('hierarchy')
            for i,label in enumerate(capture.WORKSPACE_LABELS):
                node(tree,label,[10+60*i,520,70+60*i,580],text=label,selected=str(label==state['screen']).lower())
            return xml(tree)
        def read(**options):clock[0]+=.1;return hierarchy()
        reader=SimpleNamespace(read=read)
        def wait_for(reader,predicate,name,seconds=30):
            value=read(deadline=clock[0]+seconds)
            (args.out/(name+'.xml')).write_text(value)
            if not predicate(value):raise TimeoutError('Controlled observed route mismatch: '+name)
            return value
        def adb(*parts,**options):
            calls.append(parts)
            if parts==('shell','input 2>&1'):return b'touchscreen swipe motionevent CANCEL'
            if parts==('shell','screenrecord --help 2>&1'):return b'--size --bit-rate --time-limit'
            if parts[:4]==('shell','settings','get','global'):return b'1'
            if parts[:2]==('shell','cat'):
                return (b'screenrecord\0'+remote.encode()+b'\0') if '/proc/' in parts[2] else b'4321'
            if parts[:4]==('shell','input','touchscreen','swipe'):
                duration=int(parts[-1]);clock[0]+=duration/1000
                if duration==300:
                    state['scrolled']=True
                    if recorder_dies_on_scroll:process.returncode=7
                elif duration==900:
                    if cancel_opens_menu:state['screen']='menu'
                elif state['screen']=='chat':state['screen']='menu'
                elif state['screen']=='menu':state['screen']='下载'
                elif state['screen']=='下载':state['screen']='网络'
                else:raise AssertionError('Unexpected native short press')
                return b''
            if parts[:3]==('shell','input','keyevent'):state['screen']='chat';return b''
            if parts[:2]==('shell','kill'):process.returncode=0;return b''
            if parts[:2]==('shell','sha256sum'):return hashlib.sha256(video).hexdigest().encode()+b'  '+remote.encode()
            if parts[0]=='pull':Path(parts[2]).write_bytes(video);return b''
            if parts[:3]==('shell','rm','-f'):return b''
            raise AssertionError('Unexpected ADB protocol: '+repr(parts))
        with tempfile.TemporaryDirectory() as directory:
            args=SimpleNamespace(out=Path(directory),adb='controlled-adb',serial='controlled-emulator')
            report=dict(motionReport={},runNonce=nonce,buildIdentity=dict(sourceCommit='b'*40),
                        installedApk=dict(sha256='c'*64),inputs=[],commands=[])
            with mock.patch.object(capture.time,'monotonic',side_effect=lambda:clock[0]),\
                 mock.patch.object(capture.time,'time_ns',side_effect=lambda:round(clock[0]*1e9)),\
                 mock.patch.object(capture.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),\
                 mock.patch.object(capture.subprocess,'Popen',return_value=process),\
                 mock.patch.object(capture,'mp4_metadata',return_value=dict(width=618,height=1338,durationSeconds=20)):
                capture.capture_motion(args,report,reader,adb,wait_for)
            return report,calls

    def test_five_actual_actions_and_every_menu_scroll_stay_inside_live_recording(self):
        report,calls=self.run_motion();motion=report['motionReport']
        self.assertEqual(motion['status'],'captured',motion.get('errors'))
        self.assertEqual([row['action'] for row in report['inputs']],
                         ['short-press','menu-scroll','short-press','short-press','keyevent','swipe-to-cancel'])
        self.assertTrue(all(row['completedWhileRecorderRunning'] for row in report['inputs']))
        self.assertGreaterEqual(motion['recordingWallSecondsAtStopRequest'],20)
        self.assertTrue(motion['menuGestureReleasedOutsideObservedButton'])
        self.assertEqual(motion['navigationContract'],3)
        self.assertEqual(motion['menuBoundsSource']['observedBounds'],[268,520,316,568])

    def test_recorder_exit_during_scroll_cannot_claim_complete_interactions(self):
        report,_=self.run_motion(recorder_dies_on_scroll=True)
        self.assertEqual(report['motionReport']['status'],'failed')
        self.assertFalse(report['motionReport']['interactionsComplete'])

    def test_cancel_that_really_opens_a_menu_fails_post_recording_state_check(self):
        report,_=self.run_motion(cancel_opens_menu=True)
        self.assertEqual(report['motionReport']['status'],'failed')
        self.assertFalse(report['motionReport']['interactionsComplete'])


class CollapseMenuReobservationTests(unittest.TestCase):
    """Run the actual nested device consumer across a moving menu boundary."""
    OLD_BOUNDS=[36,480,972,642]
    NEW_BOUNDS=[36,264,972,426]

    @staticmethod
    def menu(box=None):
        tree=ET.Element('hierarchy')
        node(tree,'浏览器菜单',[36,72,972,216],text='浏览器菜单',kind='android.widget.TextView')
        scroller=node(tree,'',[24,216,1008,1728],kind='android.widget.ScrollView',scrollable='true')
        if box is not None:node(scroller,'当前环境网络',box,text='当前环境网络')
        return xml(tree)

    def execute(self,*,snapshot_seconds=3,fresh_read_seconds=.25,late_ui_return=False):
        path=ROOT/'tests/gecko/run_chrome_collapse_v3.py'
        source=ast.parse(path.read_text())
        owner=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='run_v3')
        function=next(n for n in ast.walk(owner) if isinstance(n,ast.FunctionDef) and n.name=='menu_destination')
        clock=[100.0];events=[];inputs=[];deadlines=[];snapshot_complete=[False]
        def tap(before,label,key,**values):
            events.append(('tap',label,clock[0]));inputs.append(dict(before=before,label=label,key=key,**values))
            clock[0]+=.1
        def ui(phase,*,deadline=None):
            events.append(('ui',phase,clock[0]))
            if phase!='networkMenu':return {}
            deadlines.append(deadline)
            if clock[0]>=deadline:raise TimeoutError('Existing menu deadline expired before another native read')
            clock[0]+=fresh_read_seconds if snapshot_complete[0] else .25
            box=self.NEW_BOUNDS if snapshot_complete[0] else self.OLD_BOUNDS
            value=workspace_v3.menu_action(self.menu(box),capture.PACKAGE,'当前环境网络')
            if clock[0]>=deadline and not late_ui_return:
                raise TimeoutError('Existing menu deadline expired during native read')
            return value
        def snapshot(phase):
            events.append(('snapshot',phase,clock[0]))
            if phase=='networkMenu':clock[0]+=snapshot_seconds;snapshot_complete[0]=True
            return {}
        bindings=dict(tap=tap,ui=ui,snapshot=snapshot,MENU_TARGETS=collapse_v3.MENU_TARGETS,
                      time=SimpleNamespace(monotonic=lambda:clock[0]))
        exec(compile(ast.Module(body=[copy.deepcopy(function)],type_ignores=[]),str(path),'exec'),bindings)
        error=None
        try:bindings['menu_destination']('upBeforeNative','networkMenu','network')
        except Exception as failure:error=failure
        return dict(error=error,events=events,inputs=inputs,deadlines=deadlines,clock=clock[0])

    def test_snapshot_movement_uses_only_fresh_menu_coordinates_in_one_budget(self):
        result=self.execute()
        self.assertIsNone(result['error'])
        self.assertEqual(result['deadlines'],[120.1,120.1])
        self.assertEqual([(kind,phase) for kind,phase,_ in result['events']],
            [('tap','networkMenu'),('ui','networkMenu'),('snapshot','networkMenu'),
             ('ui','networkMenu'),('tap','network'),('ui','network'),('snapshot','network')])
        self.assertEqual(len(result['inputs']),2)
        target=result['inputs'][1]
        self.assertEqual(target['bounds'],self.NEW_BOUNDS)
        self.assertEqual(target['point'],[504,345])
        self.assertNotEqual(target['point'],workspace_v3.center(self.OLD_BOUNDS))

    def test_late_snapshot_never_grants_another_twenty_seconds_or_destination_tap(self):
        for delay in (19.75,20,40):
            with self.subTest(snapshot_seconds=delay):
                result=self.execute(snapshot_seconds=delay)
                self.assertIsInstance(result['error'],TimeoutError)
                self.assertEqual(result['deadlines'],[120.1,120.1])
                self.assertEqual([row['label'] for row in result['inputs']],['networkMenu'])
                self.assertFalse(any(phase=='network' for _,phase,_ in result['events']))

    def test_late_fresh_read_cannot_return_a_target_to_the_real_tap_consumer(self):
        # The UI boundary deliberately returns late rather than raising, so the
        # real caller's final deadline guard must prevent the destination input.
        result=self.execute(snapshot_seconds=1,fresh_read_seconds=20,late_ui_return=True)
        self.assertIsInstance(result['error'],TimeoutError)
        self.assertEqual(result['deadlines'],[120.1,120.1])
        self.assertEqual([row['label'] for row in result['inputs']],['networkMenu'])
        self.assertFalse(any(phase=='network' for _,phase,_ in result['events']))


class RepeatedMenuScrollBudgetTests(unittest.TestCase):
    """Both observations of one menu spend the same recorded scroll allowance."""
    def seek(self,frames,scrolls,adb):
        reader=mock.Mock(side_effect=frames)
        with mock.patch.object(workspace_v3.time,'monotonic',return_value=10):
            value=workspace_v3.seek_menu_action(adb,reader,capture.PACKAGE,'当前环境网络',
                                              deadline=30,scrolls=scrolls)
        return value,reader

    def test_second_observation_cannot_inject_a_ninth_scroll(self):
        empty=CollapseMenuReobservationTests.menu()
        target=CollapseMenuReobservationTests.menu(CollapseMenuReobservationTests.NEW_BOUNDS)
        scrolls=[];adb=mock.Mock()
        self.seek([empty]*7+[target],scrolls,adb)
        self.assertEqual(len(scrolls),7)
        with self.assertRaises(AssertionError):self.seek([empty,empty,target],scrolls,adb)
        self.assertEqual(len(scrolls),8)
        self.assertEqual(adb.call_count,8)
        self.assertTrue(workspace_v3.verify_menu_scrolls(scrolls,capture.PACKAGE,'当前环境网络'))

    def test_last_allowed_scroll_and_later_read_only_reobservation_are_available(self):
        empty=CollapseMenuReobservationTests.menu()
        target=CollapseMenuReobservationTests.menu(CollapseMenuReobservationTests.NEW_BOUNDS)
        scrolls=[];adb=mock.Mock()
        self.seek([empty]*7+[target],scrolls,adb)
        (raw,found),reader=self.seek([empty,target],scrolls,adb)
        self.assertEqual(found['bounds'],CollapseMenuReobservationTests.NEW_BOUNDS)
        self.assertEqual(adb.call_count,8);self.assertEqual(len(scrolls),8)
        self.assertEqual([call.kwargs for call in reader.call_args_list],[{'deadline':30},{'deadline':30}])
        (raw,found),reader=self.seek([target],scrolls,adb)
        self.assertEqual(found['bounds'],CollapseMenuReobservationTests.NEW_BOUNDS)
        self.assertEqual(adb.call_count,8);self.assertEqual(len(scrolls),8)
        self.assertTrue(workspace_v3.verify_menu_scrolls(scrolls,capture.PACKAGE,'当前环境网络'))


if __name__=='__main__':unittest.main(verbosity=2)
