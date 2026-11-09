"""Reject missing or misleading current navigation; these are host controls only."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from workspace_navigation_contract import navigation, conversation_header, exercise_workspace_roundtrip
from compact_chrome_layout_v2 import address_dialog, verify_layout, verify_case
sys.path.insert(0,str(ROOT/'tests/gecko'))
from workspace_ui_v2 import capture_selection

PACKAGE='local.pocketchat.test'


def node(parent, text='', description='', kind='Button', bounds='[0,0][144,144]', **extra):
    attrs={'package':PACKAGE,'class':'android.widget.'+kind,'text':text,'content-desc':description,
           'bounds':bounds,'enabled':'true','clickable':'true','selected':'false','focusable':'true'}
    attrs.update(extra)
    return ET.SubElement(parent,'node',attrs)


def screen(conversation=True):
    root=ET.Element('hierarchy');host=node(root,kind='FrameLayout',bounds='[0,0][1080,1920]')
    capsule=node(host,description='当前环境：日常会话，点按输入网址，长按切换环境',bounds='[42,72][1038,216]',**{'long-clickable':'true'})
    node(host,description='当前环境网络：未配置',kind='LinearLayout',bounds='[42,216][1038,288]',clickable='false',focusable='false')
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

    def test_roundtrip_uses_two_actual_tap_commands_and_reads_each_result(self):
        commands=[];saved=[];frames=[xml(screen(False)),xml(screen(True))]
        def adb(*parts):
            commands.append(parts)
            return frames.pop(0) if parts[:2]==('shell','cat') else ''
        result=exercise_workspace_roundtrip(adb,xml(screen()),lambda name,value:saved.append((name,value)),PACKAGE)
        self.assertEqual([c[:3] for c in commands].count(('shell','input','tap')),2)
        self.assertEqual(len(saved),2);self.assertEqual(result['actualAndroidTaps'],2)
        self.assertTrue(result['returnedToSameEnvironment'])


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
