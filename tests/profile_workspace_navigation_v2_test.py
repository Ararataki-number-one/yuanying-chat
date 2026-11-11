"""Reject missing or misleading current navigation; these are host controls only."""
import copy
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import workspace_navigation_contract as navigation_contract
from workspace_navigation_contract import navigation, conversation_header, dashboard_entry, exercise_workspace_roundtrip
from compact_chrome_layout_v2 import address_dialog, verify_layout, verify_case
sys.path.insert(0,str(ROOT/'tests/gecko'))
from workspace_ui_v2 import capture_selection

PACKAGE='local.pocketchat.test'
NAVIGATION_DUMP_COMMAND='rm -f /sdcard/gecko-navigation-v2.xml && uiautomator dump /sdcard/gecko-navigation-v2.xml 2>&1'
NAVIGATION_DUMP_SUCCESS='UI hierchary dumped to: /sdcard/gecko-navigation-v2.xml\n'
NAVIGATION_NULL_ROOT='ERROR: null root node returned by UiTestAutomationBridge.\n'


def node(parent, text='', description='', kind='Button', bounds='[0,0][144,144]', **extra):
    attrs={'package':PACKAGE,'class':'android.widget.'+kind,'text':text,'content-desc':description,
           'bounds':bounds,'enabled':'true','clickable':'true','selected':'false','focusable':'true'}
    attrs.update(extra)
    return ET.SubElement(parent,'node',attrs)


def screen(conversation=True, stacked=False):
    root=ET.Element('hierarchy');host=node(root,kind='FrameLayout',bounds='[0,0][1080,1920]')
    capsule=node(host,description='当前环境：日常会话，点按输入网址，长按切换环境',bounds='[42,72][1038,216]',**{'long-clickable':'true'})
    node(host,description='当前环境网络：未配置',kind='LinearLayout',bounds='[42,216][1038,288]',clickable='false',focusable='false')
    if conversation:
        # Declared host geometry follows the production 360 dp native row:
        # three equally weighted destinations, centered dock, square reading.
        row_bounds='[36,1224][1044,1812]' if stacked else '[36,1596][1044,1812]'
        dock_bounds='[144,1224][936,1506]' if stacked else '[276,1596][804,1812]'
        reading_bounds='[762,1530][1044,1812]' if stacked else '[828,1596][1044,1812]'
        row=node(host,kind='LinearLayout',bounds=row_bounds);row.set('class','android.view.ViewGroup')
        dock=node(row,kind='LinearLayout',bounds=dock_bounds)
        left,width,top,bottom=(159,254,1230,1500) if stacked else (291,166,1602,1806)
        for i,label in enumerate(('环境','网络','下载')):
            x=left+width*i
            node(dock,text=label,description=label,bounds=f'[{x},{top}][{x+width},{bottom}]')
        reading=node(row,kind='FrameLayout',bounds=reading_bounds)
        node(reading,text='阅读',description='进入专注阅读模式',bounds=reading_bounds)
        return root
    assert not stacked
    row=node(host,kind='LinearLayout',bounds='[36,1640][1044,1856]')
    dock=node(row,kind='LinearLayout',bounds='[40,1640][820,1856]')
    labels=('环境','网络','下载') if conversation else ('会话','环境','下载','网络','设置')
    for i,label in enumerate(labels):
        left=40+180*i
        node(dock,text=label,description=label,bounds=f'[{left},1640][{left+170},1856]',
             selected='true' if not conversation and label=='环境' else 'false')
    if conversation:
        reading=node(row,kind='FrameLayout',bounds='[860,1640][1044,1856]')
        node(reading,text='阅读',description='进入专注阅读模式',bounds='[860,1640][1044,1856]')
    return root


def xml(tree):return ET.tostring(tree,encoding='unicode')


def dashboard_screen(environment='日常会话'):
    root=ET.Element('hierarchy')
    surface=node(root,description='环境仪表盘',kind='LinearLayout',bounds='[0,63][1080,1857]')
    scroll=node(surface,kind='ScrollView',bounds='[0,63][1080,1673]')
    centered=node(scroll,kind='FrameLayout',bounds='[0,63][1080,1673]')
    body=node(centered,kind='LinearLayout',bounds='[0,63][1080,1673]')
    header=node(body,kind='LinearLayout',bounds='[47,116][1033,185]')
    node(header,text='01',kind='TextView',bounds='[47,120][121,180]',clickable='false')
    node(header,text=environment,kind='TextView',bounds='[121,116][1033,185]',clickable='false')
    footer=node(surface,kind='LinearLayout',bounds='[0,1673][1080,1857]')
    node(footer,text='进入聊天',bounds='[47,1694][1033,1820]')
    return root


class NavigationV2Tests(unittest.TestCase):
    def test_current_conversation_and_five_item_workspace_are_distinct(self):
        for conversation in (True,False):
            result=navigation(xml(screen(conversation)),PACKAGE,conversation=conversation,selected=None if conversation else '环境')
            self.assertEqual(len(result['controls']),4 if conversation else 5)
            self.assertEqual(result['navigationContract'],2)

    def test_wrong_owner_disabled_duplicate_or_invisible_destinations_are_rejected(self):
        for key,value in (('package','foreign.application'),('enabled','false'),('clickable','false'),
                          ('bounds','[1,1][1,2]'),('content-desc','旧网络入口'),('selected','true')):
            tree=screen();target=next(n for n in tree.iter('node') if n.get('text')=='网络');target.set(key,value)
            with self.subTest(key=key),self.assertRaises(AssertionError):navigation(xml(tree),PACKAGE,conversation=True)
        tree=screen();dock=next(n for n in tree.iter('node') if any(c.get('text')=='网络' for c in n))
        dock.append(copy.deepcopy(next(c for c in dock if c.get('text')=='网络')))
        with self.assertRaises(AssertionError):navigation(xml(tree),PACKAGE,conversation=True)

    def test_overlapping_or_reordered_native_targets_are_rejected(self):
        tree=screen();next(n for n in tree.iter('node') if n.get('text')=='下载').set('bounds','[41,1640][211,1856]')
        with self.assertRaises(AssertionError):navigation(xml(tree),PACKAGE,conversation=True)

    def test_reading_cannot_be_folded_into_destination_dock(self):
        tree=screen();dock=next(n for n in tree.iter('node') if any(c.get('text')=='网络' for c in n))
        parent=next(n for n in tree.iter('node') if any(c.get('text')=='阅读' for c in n));reading=list(parent)[0];parent.remove(reading);dock.append(reading)
        with self.assertRaises(AssertionError):navigation(xml(tree),PACKAGE,conversation=True)

    def test_real_current_header_requires_address_and_long_press_semantics(self):
        value=conversation_header(xml(screen()),PACKAGE,360,640,1,'日常会话')
        self.assertTrue(value['addressTapAndEnvironmentLongPressDescribed'])
        for description in ('当前环境：日常会话，点击展开环境工具栏','当前环境：另一环境，点按输入网址，长按切换环境'):
            tree=screen();next(n for n in tree.iter('node') if n.get('content-desc','').startswith('当前环境：')).set('content-desc',description)
            with self.assertRaises(AssertionError):conversation_header(xml(tree),PACKAGE,360,640,1,'日常会话')

    def test_compact_capsule_touch_height_and_readonly_status_remain_required(self):
        for which,key,value in (('当前环境：','long-clickable','false'),('当前环境网络：','clickable','true'),('当前环境：','bounds','[42,132][1038,216]')):
            tree=screen();next(n for n in tree.iter('node') if n.get('content-desc','').startswith(which)).set(key,value)
            with self.subTest(key=key),self.assertRaises(AssertionError):conversation_header(xml(tree),PACKAGE,360,640,1,'日常会话')

    def test_roundtrip_uses_three_actual_tap_commands_and_reads_each_result(self):
        commands=[];saved=[];frames=[xml(screen(False)),xml(dashboard_screen()),xml(screen(True))]
        def adb(*parts):
            commands.append(parts)
            if parts==('shell',NAVIGATION_DUMP_COMMAND):return NAVIGATION_DUMP_SUCCESS
            return frames.pop(0) if parts[:2]==('shell','cat') else ''
        result=exercise_workspace_roundtrip(adb,xml(screen()),lambda name,value:saved.append((name,value)),PACKAGE)
        taps=[c for c in commands if c[:3]==('shell','input','tap')]
        self.assertEqual(taps[:2],[('shell','input','tap','374','1704'),('shell','input','tap','125','1748')])
        self.assertEqual(taps[2:], [('shell','input','tap','540','1757')])
        self.assertEqual([c[:3] for c in commands].count(('shell','input','tap')),3)
        self.assertEqual(len(saved),3);self.assertEqual(result['actualAndroidTaps'],3)
        self.assertEqual([name for name,_ in saved],['production-navigation-environments.xml','production-navigation-dashboard.xml','production-navigation-chat.xml'])
        self.assertEqual(result['observations'][1]['dashboardEntry']['actualAndroidTap'],dict(label='进入聊天',point=[540,1757],bounds=[47,1694,1033,1820]))
        self.assertTrue(result['returnedToSameEnvironment'])


class AdaptiveConversationNavigationTests(unittest.TestCase):
    def parts(self,tree):
        parents={child:parent for parent in tree.iter() for child in parent}
        targets=[next(n for n in tree.iter('node') if n.get('text')==name) for name in ('环境','网络','下载','阅读')]
        dock,reading=parents[targets[0]],parents[targets[-1]]
        return targets,dock,reading,parents[dock]

    def test_inline_and_stacked_keep_three_destinations_and_independent_reading(self):
        for stacked in (False,True):
            tree=screen(stacked=stacked)
            value=conversation_header(xml(tree),PACKAGE,360,640,2 if stacked else 1,'日常会话')
            self.assertEqual([row['label'] for row in value['controls']],['环境','网络','下载','阅读'])
            parents={child:parent for parent in tree.iter() for child in parent}
            targets,*_=self.parts(tree)
            self.assertEqual(navigation_contract.conversation_layout(targets,parents,PACKAGE),'stacked' if stacked else 'inline')
            self.assertTrue(all(not row['selected'] for row in value['controls']))

    def test_three_destinations_never_overlap_reorder_or_use_different_rows(self):
        for stacked in (False,True):
            for mutation in ('overlap','reorder','different-row'):
                tree=screen(stacked=stacked);targets,dock,reading,row=self.parts(tree)
                rectangle=navigation_contract.bounds(targets[1])
                if mutation=='overlap':rectangle[0]=navigation_contract.bounds(targets[0])[0]
                elif mutation=='reorder':dock.remove(targets[1]);dock.insert(0,targets[1])
                else:rectangle[1]+=1
                targets[1].set('bounds',f'[{rectangle[0]},{rectangle[1]}][{rectangle[2]},{rectangle[3]}]')
                with self.subTest(stacked=stacked,mutation=mutation),self.assertRaises(AssertionError):
                    navigation(xml(tree),PACKAGE,conversation=True)

    def test_native_containers_require_exact_owner_parentage_and_children(self):
        for stacked in (False,True):
            for mutation in ('owner','class','other-parent','extra-child','reading-in-dock'):
                tree=screen(stacked=stacked);targets,dock,reading,row=self.parts(tree)
                if mutation=='owner':row.set('package','foreign.application')
                elif mutation=='class':row.set('class','android.widget.ScrollView')
                elif mutation=='other-parent':row.remove(reading);list(tree)[0].append(reading)
                elif mutation=='extra-child':node(row,kind='TextView',text='unowned extra')
                else:reading.remove(targets[-1]);dock.append(targets[-1])
                with self.subTest(stacked=stacked,mutation=mutation),self.assertRaises(AssertionError):
                    navigation(xml(tree),PACKAGE,conversation=True)

    def test_reading_must_fill_its_square_and_stay_inside_the_actual_row(self):
        for stacked in (False,True):
            for mutation in ('button-clipped','not-square','wrong-edge','outside-row','outside-window'):
                tree=screen(stacked=stacked);targets,dock,reading,row=self.parts(tree)
                l,t,r,b=navigation_contract.bounds(reading)
                if mutation=='button-clipped':targets[-1].set('bounds',f'[{l+1},{t}][{r},{b}]')
                elif mutation=='outside-window':list(tree)[0].set('bounds','[0,0][1080,1800]')
                else:
                    if mutation=='not-square':l+=1
                    elif mutation=='wrong-edge':l-=1;r-=1
                    else:l+=20;r+=20
                    for target in (reading,targets[-1]):target.set('bounds',f'[{l},{t}][{r},{b}]')
                with self.subTest(stacked=stacked,mutation=mutation),self.assertRaises(AssertionError):
                    navigation(xml(tree),PACKAGE,conversation=True)

    def test_destination_dock_cannot_shift_off_the_native_center(self):
        for stacked in (False,True):
            tree=screen(stacked=stacked);targets,dock,reading,row=self.parts(tree)
            for target in [dock]+targets[:-1]:
                l,t,r,b=navigation_contract.bounds(target);target.set('bounds',f'[{l+2},{t}][{r+2},{b}]')
            with self.subTest(stacked=stacked),self.assertRaisesRegex(AssertionError,'centered'):
                navigation(xml(tree),PACKAGE,conversation=True)

    def test_stacked_is_a_distinct_second_row_and_requires_insufficient_inline_room(self):
        for mutation in ('overlap','floating','unnecessary-wrap'):
            tree=screen(stacked=True);targets,dock,reading,row=self.parts(tree)
            l,t,r,b=navigation_contract.bounds(reading)
            if mutation=='overlap':t-=30;b-=30
            elif mutation=='floating':t+=1;b+=1
            else:
                row.set('bounds','[36,1224][1044,1812]')
                dock.set('bounds','[390,1224][690,1506]')
                for i,target in enumerate(targets[:-1]):target.set('bounds',f'[{395+98*i},1230][{493+98*i},1500]')
            if mutation!='unnecessary-wrap':
                for target in (reading,targets[-1]):target.set('bounds',f'[{l},{t}][{r},{b}]')
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):navigation(xml(tree),PACKAGE,conversation=True)

    def test_original_touch_size_and_explicit_viewport_bounds_still_reject_small_targets(self):
        for stacked in (False,True):
            tree=screen(stacked=stacked);targets,*_=self.parts(tree)
            l,t,r,b=navigation_contract.bounds(targets[0]);targets[0].set('bounds',f'[{l},{t}][{l+143},{b}]')
            with self.subTest(stacked=stacked),self.assertRaises(AssertionError):
                conversation_header(xml(tree),PACKAGE,360,640,2 if stacked else 1,'日常会话')
            with self.subTest(stacked=stacked,viewport='too-small'),self.assertRaises(AssertionError):
                conversation_header(xml(screen(stacked=stacked)),PACKAGE,340,640,2 if stacked else 1,'日常会话')


class RoundtripDashboardTests(unittest.TestCase):
    def exercise(self, frames, durations=None, entry_seconds=0):
        self.commands=[];self.saved=[];clock=[0.0];reads=[0]
        durations=durations or [0.0]*len(frames)
        def adb(*parts):
            self.commands.append(parts)
            if parts==('shell',NAVIGATION_DUMP_COMMAND):return NAVIGATION_DUMP_SUCCESS
            if parts[:3]==('shell','input','tap'):
                if sum(c[:3]==('shell','input','tap') for c in self.commands)==3:
                    clock[0]+=entry_seconds
            if parts[:2]==('shell','cat'):
                index=reads[0];reads[0]+=1
                clock[0]+=durations[min(index,len(durations)-1)]
                return xml(frames[min(index,len(frames)-1)])
            return ''
        def sleep(seconds):clock[0]+=seconds
        with mock.patch.object(navigation_contract.time,'monotonic',lambda:clock[0]),mock.patch.object(navigation_contract.time,'sleep',sleep):
            return exercise_workspace_roundtrip(adb,xml(screen()),lambda name,value:self.saved.append((name,value)),PACKAGE)

    def test_dashboard_requires_its_own_unique_native_surface_and_header(self):
        for mutation in ('owner','duplicate','missing-header','wrong-header-owner'):
            tree=dashboard_screen();surface=list(tree)[0]
            header=surface[0][0][0][0]
            if mutation=='owner':surface.set('package','foreign.application')
            elif mutation=='duplicate':tree.append(copy.deepcopy(surface))
            elif mutation=='missing-header':header.remove(header[1])
            else:header[1].set('package','foreign.application')
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):
                dashboard_entry(xml(tree),PACKAGE,'日常会话')

    def test_wrong_environment_cannot_be_hidden_by_matching_body_text(self):
        tree=dashboard_screen('另一环境');body=list(tree)[0][0][0][0]
        node(body,text='日常会话',kind='TextView',bounds='[80,500][900,560]')
        with self.assertRaisesRegex(AssertionError,'another environment'):
            self.exercise([screen(False),tree,screen()])
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),2)

    def test_entry_requires_one_enabled_native_button_inside_its_footer(self):
        changes=(('package','foreign.application'),('class','android.widget.TextView'),
                 ('enabled','false'),('clickable','false'),('content-desc','删除环境'),
                 ('bounds','[47,1694][47,1820]'),('bounds','[47,1694][1100,1820]'))
        for key,value in changes:
            tree=dashboard_screen();list(tree)[0][1][0].set(key,value)
            with self.subTest(key=key,value=value),self.assertRaises(AssertionError):
                dashboard_entry(xml(tree),PACKAGE,'日常会话')
        for mutation in ('duplicate','outside-footer'):
            tree=dashboard_screen();surface=list(tree)[0];footer=surface[1];button=footer[0]
            if mutation=='duplicate':footer.append(copy.deepcopy(button))
            else:footer.remove(button);surface[0][0][0].append(button)
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):
                dashboard_entry(xml(tree),PACKAGE,'日常会话')

    def test_disabled_entry_never_causes_a_third_input(self):
        tree=dashboard_screen();list(tree)[0][1][0].set('enabled','false')
        with self.assertRaises(AssertionError):self.exercise([screen(False),tree,screen()])
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),2)

    def test_dashboard_and_final_chat_share_the_original_twenty_second_budget(self):
        cases=(('no-dashboard',[screen(False),screen()],[0,10],0,2),
               ('late-dashboard',[screen(False),dashboard_screen(),screen()],[0,20.1,0],0,2),
               ('late-chat',[screen(False),dashboard_screen(),screen()],[0,19.8,.3],0,3),
               ('late-entry-command',[screen(False),dashboard_screen(),screen()],[0,19.8,0],.3,3))
        for name,frames,durations,entry_seconds,inputs in cases:
            with self.subTest(case=name),self.assertRaisesRegex(AssertionError,'20 second budget'):
                self.exercise(frames,durations,entry_seconds)
            self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),inputs)

    def test_same_environment_capsule_remains_required_after_dashboard_entry(self):
        final=screen();next(n for n in final.iter('node') if n.get('content-desc','').startswith('当前环境：')).set('content-desc','当前环境：另一环境，点按输入网址，长按切换环境')
        with self.assertRaises(AssertionError):self.exercise([screen(False),dashboard_screen(),final])
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),3)


class NavigationAcquisitionControls(unittest.TestCase):
    """Substitute command I/O only; execute the real roundtrip and XML readers."""
    def exercise(self, attempts, stale=None):
        self.commands=[];self.saved=[];self.output=io.StringIO();self.clock=0.0
        self.dumps=0;self.reads=0;self.remote=stale;current={}
        def adb(*parts):
            nonlocal current
            self.commands.append(parts)
            if parts[:3]==('shell','input','tap'):return ''
            if parts==('shell',NAVIGATION_DUMP_COMMAND):
                # Model the fixed command's rm before every real dump outcome.
                self.remote=None
                current=attempts[min(self.dumps,len(attempts)-1)];self.dumps+=1
                self.clock+=current.get('seconds',0)
                if 'error' in current:raise current['error']
                self.remote=current.get('xml')
                return current.get('output',NAVIGATION_DUMP_SUCCESS)
            if parts==('shell','cat','/sdcard/gecko-navigation-v2.xml'):
                self.reads+=1;self.clock+=current.get('catSeconds',0)
                if 'catError' in current:raise current['catError']
                if self.remote is None:
                    raise subprocess.CalledProcessError(1,parts,output='',stderr='No such file or directory')
                return self.remote
            raise AssertionError(('Unexpected device command',parts))
        def sleep(seconds):
            self.assertGreaterEqual(seconds,0);self.assertLessEqual(seconds,.2)
            self.clock+=seconds
        with mock.patch.object(navigation_contract.time,'monotonic',lambda:self.clock), \
                mock.patch.object(navigation_contract.time,'sleep',sleep),redirect_stdout(self.output):
            return exercise_workspace_roundtrip(adb,xml(screen()),
                lambda name,value:self.saved.append((name,value)),PACKAGE)

    @staticmethod
    def current_frames():
        return [dict(xml=xml(screen(False))),dict(xml=xml(dashboard_screen())),dict(xml=xml(screen()))]

    def test_exact_null_root_then_fresh_frames_keeps_three_taps_and_raw_output(self):
        for phase in range(3):
            frames=self.current_frames();frames.insert(phase,dict(output=NAVIGATION_NULL_ROOT))
            with self.subTest(phase=phase):
                result=self.exercise(frames,stale=xml(screen(False)))
                self.assertEqual(result['actualAndroidTaps'],3)
                self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),3)
                self.assertEqual((self.dumps,self.reads),(4,3))
                self.assertEqual([name for name,_ in self.saved],['production-navigation-environments.xml',
                    'production-navigation-dashboard.xml','production-navigation-chat.xml'])
                expected=[NAVIGATION_DUMP_SUCCESS]*4;expected[phase]=NAVIGATION_NULL_ROOT
                self.assertEqual(self.output.getvalue(),''.join(expected))
                self.assertEqual(self.clock,.2)

    def test_persistent_null_root_exhausts_original_deadline_without_cat_or_retap(self):
        with self.assertRaisesRegex(AssertionError,'original 20 second budget'):
            self.exercise([dict(output=NAVIGATION_NULL_ROOT)],stale=xml(screen(False)))
        self.assertEqual(self.clock,20)
        self.assertEqual(self.reads,0)
        self.assertEqual(self.saved,[])
        self.assertIsNone(self.remote)
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),1)
        self.assertEqual(self.output.getvalue(),NAVIGATION_NULL_ROOT*self.dumps)

    def test_late_dump_or_cat_success_is_not_admitted(self):
        for phase in range(3):
            for field in ('seconds','catSeconds'):
                frames=self.current_frames();frames[phase][field]=20
                with self.subTest(phase=phase,command=field),self.assertRaisesRegex(AssertionError,'original 20 second budget'):
                    self.exercise(frames)
                self.assertEqual(self.dumps,phase+1)
                self.assertEqual(self.reads,phase+(field=='catSeconds'))
                self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),phase+1)

    def test_unknown_empty_similar_or_mixed_dump_output_cannot_read_old_xml(self):
        outputs=['','ERROR: could not get idle state.\n',NAVIGATION_NULL_ROOT+'unexpected\n',
                 'prefix '+NAVIGATION_NULL_ROOT,NAVIGATION_NULL_ROOT+NAVIGATION_DUMP_SUCCESS,
                 NAVIGATION_DUMP_SUCCESS.replace('gecko-navigation-v2.xml','another.xml'),
                 NAVIGATION_DUMP_SUCCESS+'unexpected\n']
        for output in outputs:
            with self.subTest(output=output),self.assertRaisesRegex(AssertionError,'Unexpected native hierarchy dump'):
                self.exercise([dict(output=output)],stale=xml(screen(False)))
            self.assertEqual((self.dumps,self.reads),(1,0))
            self.assertEqual(self.saved,[])
            self.assertEqual(self.output.getvalue(),output)

    def test_nonzero_timeout_or_missing_new_file_are_not_readiness(self):
        faults=[dict(error=subprocess.CalledProcessError(1,['adb'],output=NAVIGATION_NULL_ROOT)),
                dict(error=subprocess.TimeoutExpired(['adb'],20,output=NAVIGATION_DUMP_SUCCESS)),
                dict(output=NAVIGATION_DUMP_SUCCESS),
                dict(xml=xml(screen(False)),catError=subprocess.TimeoutExpired(['adb'],20,output=xml(screen(False))))]
        for number,fault in enumerate(faults):
            expected=type(fault.get('error',fault.get('catError',subprocess.CalledProcessError(1,['adb']))))
            with self.subTest(fault=number),self.assertRaises(expected):
                self.exercise([fault],stale=xml(screen(False)))
            self.assertEqual(self.dumps,1)
            self.assertEqual(self.saved,[])
            self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),1)

    def test_malformed_fresh_xml_is_not_replaced_by_later_good_or_diagnostic_xml(self):
        frames=[dict(xml='<hierarchy><node>'),*self.current_frames()]
        with self.assertRaises(ET.ParseError):self.exercise(frames,stale=xml(screen(False)))
        self.assertEqual((self.dumps,self.reads),(1,1))
        self.assertEqual(self.saved,[])
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),1)

    def test_null_root_wait_shares_dashboard_entry_deadline_with_final_chat(self):
        frames=self.current_frames();frames[1]['catSeconds']=19.9
        frames.insert(2,dict(output=NAVIGATION_NULL_ROOT))
        with self.assertRaisesRegex(AssertionError,'original 20 second budget'):
            self.exercise(frames)
        self.assertEqual(self.clock,20)
        self.assertEqual((self.dumps,self.reads),(3,2))
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in self.commands),3)
        self.assertNotIn('production-navigation-chat.xml',[name for name,_ in self.saved])


def layout():
    controls=[]
    for name,bounds in zip(('drawer','environment','more'),([42,78,198,234],[260,78,820,234],[882,78,1038,234])):
        l,t,r,b=bounds;controls.append(dict(name=name,visible=bounds[:],touch=bounds[:],widthDp=(r-l)/3,heightDp=(b-t)/3,tap=[(l+r)//2,b-1]))
    texts=[]
    for i,(name,bounds,pixels) in enumerate(zip(('测试环境','日本 · 203.0.113.25','42 ms（02:00）','已连接'),
        ([260,78,820,234],[80,246,630,294],[650,246,900,294],[900,246,1020,294]),(48,36,36,33))):
        texts.append(dict(text=name,bounds=bounds,fontHeight=42,contentHeight=156 if i==0 else 48,
                          inkWidth=100,contentWidth=bounds[2]-bounds[0],ellipsized=False,
                          lineCount=1,maxLines=(1,2,2,1)[i],layoutHeight=48,textSizePx=pixels,expectedTextSizePx=pixels))
    return dict(navigationContract=2,geckoOnly=True,pageMode=True,noNativeChat=True,systemWebViews=0,
        viewportDp=360,fontScale=1,syntheticPresentation=True,actualLatencyMeasurement=False,
        latency='42 ms（02:00）',expectedLatency='42 ms（02:00）',networkClickable=False,networkFocusable=False,
        networkBackground='none',networkDescription='当前环境网络：日本 · 已连接',toolbar=[0,72,1080,312],
        topBounds=[42,72,1038,240],networkBounds=[42,240,1038,312],toolbarHeightDp=80,topHeightDp=56,networkHeightDp=24,
        controls=controls,decorativeDot=dict(textSizeDp=9,inkWidth=12,contentWidth=36,fontHeight=28,contentHeight=60,height=60),
        texts=texts,networkTap=[540,276],stateTap=[960,270])


def complete_case():
    value=layout();taps=[]
    for name,index,action in (('drawer',0,'activity:local.pocketchat.WindowHomeActivity'),('address',1,'address-dialog')):
        c=value['controls'][index];taps.append(dict(control=name,point=c['tap'][:],bounds=c['touch'][:],action=action,actualAndroidTap=True))
    controls=[dict(label=label,bounds=[i*160,300,i*160+150,450],point=[i*160+75,375]) for i,label in enumerate(('取消','主页','前往'))]
    taps.append(dict(control='cancel-address',point=controls[0]['point'],bounds=controls[0]['bounds'],action='cancel-address-dialog',actualAndroidTap=True))
    c=value['controls'][2];taps.append(dict(control='more',point=c['tap'][:],bounds=c['touch'][:],action='more',actualAndroidTap=True))
    return dict(navigationContract=2,viewport=360,fontScale=1,layout=value,readOnlyStatus=True,
        statusObservation=dict(beforeActions=0,afterActions=0,afterPage=0,points=[value['networkTap'],value['stateTap']]),
        actualAndroidTaps=taps,managementNavigation=dict(activity='local.pocketchat.WindowHomeActivity',actualDrawerTap=True,resumedThenReturned=True),
        addressDialog=dict(title='打开网址',editableFields=1,controls=controls,cancelled=True,actionsBefore=1,actionsAfter=1),
        actualAndroidLongPress=dict(control='environment',action='environment',durationMs=700,point=[540,150],bounds=[260,78,820,234],actionsBefore=1,actionsAfter=2),
        environmentSheet=dict(title='快速切换环境',currentSlot=0,searchDescription='搜索要切换的环境',closeDescription='关闭快速切换环境'),
        menuDismissedByBack=True,environmentDismissedByBack=True)


class CompactGeometryV2Tests(unittest.TestCase):
    def test_complete_actual_tap_and_long_press_receipts_are_separate(self):
        self.assertTrue(verify_case(complete_case()))
        mutations=(lambda v:v['actualAndroidTaps'].pop(1),
            lambda v:v['actualAndroidTaps'][1].update(control='environment'),
            lambda v:v['actualAndroidTaps'][1].update(actualAndroidTap=False),
            lambda v:v['actualAndroidTaps'][0].update(point=[0,0]),
            lambda v:v['actualAndroidTaps'][1].update(point=[30,30],bounds=[0,0,60,60]),
            lambda v:v['actualAndroidLongPress'].update(point=[30,30],bounds=[0,0,60,60]),
            lambda v:v['actualAndroidLongPress'].update(durationMs=0),
            lambda v:v['actualAndroidLongPress'].update(actionsAfter=1),
            lambda v:v['addressDialog'].update(cancelled=False),
            lambda v:v['addressDialog'].update(actionsAfter=2),
            lambda v:v['statusObservation'].update(afterActions=1),
            lambda v:v['statusObservation'].update(afterPage=False),
            lambda v:v['managementNavigation'].update(resumedThenReturned=False),
            lambda v:v['environmentSheet'].update(currentSlot=1),
            lambda v:v.update(menuDismissedByBack=False))
        for index,mutate in enumerate(mutations):
            value=complete_case();mutate(value)
            with self.subTest(mutation=index),self.assertRaises(AssertionError):verify_case(value)

    def test_geometry_uses_actual_capsule_row_and_native_font_layout(self):
        self.assertTrue(verify_layout(layout(),360,1))

    def test_all_original_touch_font_status_and_readonly_constraints_remain_effective(self):
        mutations=(lambda v:v.update(navigationContract=True),lambda v:v.update(navigationContract=3),
            lambda v:v.update(networkClickable=True),lambda v:v.update(networkFocusable=True),
            lambda v:v.update(actualLatencyMeasurement=True),lambda v:v.update(latency='40 ms'),
            lambda v:v.update(topHeightDp=80),lambda v:v.update(toolbarHeightDp=101),
            lambda v:v['controls'][0].update(heightDp=40),lambda v:v['controls'][1].update(touch=[100,78,820,300]),
            lambda v:v['texts'][2].update(ellipsized=True),lambda v:v['texts'][3].update(inkWidth=400),
            lambda v:v['texts'][1].update(lineCount=3),lambda v:v['texts'][1].update(fontHeight=65),
            lambda v:v['texts'][1].update(layoutHeight=70),lambda v:v['texts'][1].update(textSizePx=45),
            lambda v:v['decorativeDot'].update(textSizeDp=10),lambda v:v.update(systemWebViews=1))
        for index,mutate in enumerate(mutations):
            value=layout();mutate(value)
            with self.subTest(mutation=index),self.assertRaises(AssertionError):verify_layout(value,360,1)

    def test_explicit_wrong_viewport_or_font_scale_are_rejected(self):
        for width,scale in ((412,1),(360,2)):
            with self.assertRaises(AssertionError):verify_layout(layout(),width,scale)

    def test_address_requires_one_native_editor_and_all_three_real_actions(self):
        tree=ET.Element('hierarchy');node(tree,text='打开网址',kind='TextView');node(tree,description='网址或搜索',kind='EditText')
        for index,label in enumerate(('取消','主页','前往')):node(tree,text=label,bounds=f'[{index*160},300][{index*160+150},450]')
        value=address_dialog(xml(tree),PACKAGE);self.assertEqual([x['label'] for x in value['controls']],['取消','主页','前往'])
        for label in ('取消','主页','前往'):
            candidate=copy.deepcopy(tree);candidate.remove(next(n for n in candidate if n.get('text')==label))
            with self.assertRaises(AssertionError):address_dialog(xml(candidate),PACKAGE)
        next(n for n in tree if n.get('class')=='android.widget.EditText').set('content-desc','网站输入框')
        with self.assertRaises(AssertionError):address_dialog(xml(tree),PACKAGE)


def selection_frame(stage, *, clipped=False, disabled=False, count=8):
    tree=ET.Element('hierarchy')
    node(tree,text='8 个环境',kind='TextView',bounds='[0,0][300,80]')
    if stage=='initial':
        node(tree,text='多选',bounds='[700,200][1000,344]')
    elif stage=='choosing':
        node(tree,text='全选',bounds='[0,1450][220,1594]')
    else:
        node(tree,text=f'已选 {count} 个',kind='TextView',bounds='[0,100][500,180]')
        node(tree,text='取消全选',bounds='[0,1450][220,1594]')
        scroller=node(tree,kind='HorizontalScrollView',bounds='[230,1450][1080,1594]',scrollable='true')
        for i,label in enumerate(('批量分组','收藏','取消收藏')):
            if clipped and label=='取消收藏':continue
            node(scroller,text=label,bounds=f'[{240+270*i},1450][{500+270*i},1594]',
                 enabled='false' if disabled and label=='收藏' else 'true')
    return xml(tree)


class EnvironmentSelectionV2Tests(unittest.TestCase):
    def exercise(self, selected, after_scroll=()):
        commands=[];frames=[selection_frame('choosing'),selected,*after_scroll,selection_frame('initial')];record={}
        def adb(*parts):commands.append(parts);return ''
        def dump():
            self.assertTrue(frames,'Unexpected extra observation or input replay')
            return frames.pop(0)
        with tempfile.TemporaryDirectory() as directory:
            capture_selection(adb,lambda *parts:b'host-only-screenshot-placeholder',dump,
                selection_frame('initial'),PACKAGE,360,640,Path(directory),'host-control',record)
        self.assertEqual(frames,[])
        return commands,record['selectionCheck']

    def test_all_eight_records_and_four_actions_require_actual_commands(self):
        commands,result=self.exercise(selection_frame('selected'))
        self.assertEqual(sum(c[:3]==('shell','input','tap') for c in commands),2)
        self.assertEqual(commands[-1],('shell','input','keyevent','4'))
        self.assertEqual(result['selectedCount'],8)
        self.assertEqual(set(result['actions']),{'取消全选','批量分组','收藏','取消收藏'})
        self.assertEqual(result['actualAndroidSwipes'],[])

    def test_clipped_large_font_actions_require_observed_horizontal_scroll(self):
        commands,result=self.exercise(selection_frame('selected',clipped=True),[selection_frame('selected')])
        gestures=[c for c in commands if c[:3]==('shell','input','swipe')]
        self.assertEqual(len(gestures),1);self.assertEqual(gestures[0][-1],'350')
        self.assertEqual(len(result['actualAndroidSwipes']),1)
        self.assertEqual(len(result['images']),2)
        self.assertTrue(result['allFourFooterActionsReachable'])

    def test_disabled_action_or_incomplete_selection_cannot_pass(self):
        for selected in (selection_frame('selected',disabled=True),selection_frame('selected',count=7)):
            with self.subTest(selected=selected),self.assertRaises(AssertionError):self.exercise(selected)


if __name__=='__main__':unittest.main()
