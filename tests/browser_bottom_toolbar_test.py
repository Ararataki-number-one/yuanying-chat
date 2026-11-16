"""Current bottom-bar selectors and bounded real-menu protocol; no Android claim."""
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
sys.path.insert(0,str(ROOT/'tests/gecko'))
import capture_glass_navigation as capture
import glass_ui_validation as validation
import workspace_navigation_contract_v3 as workspace_v3
import chrome_collapse_contract_v3 as collapse_v3
import compact_chrome_v3 as compact_runner


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


class CurrentBrowserMenuTests(unittest.TestCase):
    def test_actual_menu_preserves_actions_and_prioritizes_common_destinations(self):
        source_path=ROOT/'app/src/main/java/local/pocketchat/MainActivity.java'
        source=source_path.read_text()
        spec=importlib.util.spec_from_file_location('browser_menu_member_parser',ROOT/'tests/gecko-navigation-host/run.py')
        parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
        menu=parser.member_at(source,source.index('void moreSheet('))
        option=parser.member_at(source,source.index('void option('))
        template=(ROOT/'tests/browser-address-host/BrowserMenuHost.java.in').read_text()
        java_home=Path(os.environ.get('JAVA_HOME',str(ROOT/'work/browser-ci-jdk/jdk-17.0.21+9')))
        with tempfile.TemporaryDirectory(prefix='browser-menu-host-') as directory:
            directory=Path(directory);path=directory/'BrowserMenuHost.java';classes=directory/'classes'
            def execute(current_menu,current_option=option):
                path.write_text(template.replace('/* PRODUCTION_MENU */',current_menu)
                    .replace('/* PRODUCTION_OPTION */',current_option))
                compiled=subprocess.run([str(java_home/'bin/javac'),'--release','17','-encoding','UTF-8',
                    '-d',str(classes),str(path)],capture_output=True,text=True,timeout=30)
                self.assertEqual(compiled.returncode,0,compiled.stderr)
                return subprocess.run([str(java_home/'bin/java'),'-cp',str(classes),
                    'local.pocketchat.BrowserMenuHost'],capture_output=True,text=True,timeout=20)
            passed=execute(menu);self.assertEqual(passed.returncode,0,passed.stderr)
            report=json.loads(passed.stdout);self.assertGreaterEqual(report['checks'],500)
            downloads='option(d,"下载管理",()->hub.select(AppHub.DOWNLOADS));'
            settings='option(d,"应用设置",()->hub.select(AppHub.SETTINGS));'
            self.assertEqual(menu.count(downloads),1);self.assertEqual(menu.count(settings),1)
            moved=menu.replace(downloads,'',1).replace('d.show();',downloads+'\n    d.show();',1)
            controls=[(menu.replace(downloads,'',1),option,'Every original action remains exactly once'),
                (moved,option,'Common browser and workspace actions precede secondary options'),
                (menu.replace(settings,settings.replace('AppHub.SETTINGS','AppHub.DOWNLOADS'),1),option,
                    'Every callback dismisses before its original action: 应用设置'),
                (menu,option.replace('d.dismiss();','',1),'Every callback dismisses before its original action'),
                (menu.replace('forward.setEnabled(GeckoAddressUi.canForward(this));','forward.setEnabled(true);',1),option,
                    'The real forward control reflects native history')]
            for changed_menu,changed_option,message in controls:
                with self.subTest(mutation=message):
                    self.assertNotEqual((changed_menu,changed_option),(menu,option))
                    failed=execute(changed_menu,changed_option)
                    self.assertNotEqual(failed.returncode,0);self.assertIn('AssertionError: '+message,failed.stderr)
        self.assertEqual(source_path.read_text(),source)


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


class GlassFixtureLaunchTests(unittest.TestCase):
    """Run the actual launch/ready boundary; the native event is a host mock."""
    def boundary(self):
        tree=ast.parse(inspect.getsource(validation.capture_acceptance_suite))
        sequences=[]
        for owner in ast.walk(tree):
            for _,statements in ast.iter_fields(owner):
                if not isinstance(statements,list):continue
                for index,statement in enumerate(statements):
                    if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name)
                            and t.id=='start_output' for t in statement.targets):
                        sequences.append(statements[index:index+2])
        self.assertEqual(len(sequences),1)
        launch,ready=sequences[0]
        self.assertIsInstance(ready,ast.Try)
        self.assertEqual(ast.dump(ready.body[0],include_attributes=False),ast.dump(
            ast.parse("observed_event(case,'ready',request=False)").body[0],include_attributes=False))
        return ast.Module(body=copy.deepcopy([launch,ready]),type_ignores=[])

    def run_boundary(self,module):
        nonce='e'*32;case=dict(name='actual-launch-host',runNonce=nonce)
        identity=dict(sourceCommit='f'*40);start=b'controlled native launch output\n'
        transport=mock.Mock(return_value=start);collector=mock.Mock()
        unsupported=ValueError('Host native boundary rejects a non-v3 launch')
        accepted=[]
        def observe(actual_case,command,*,request):
            self.assertIs(actual_case,case)
            self.assertEqual((command,request),('ready',False))
            parts=transport.call_args.args
            values=[parts[index+1] for index,value in enumerate(parts) if value=='chromeNavigationVersion']
            if values!=['3']:raise unsupported
            accepted.append(command)
        observer=mock.Mock(side_effect=observe)
        component=capture.PACKAGE+'/local.pocketchat.CompactChromeIntegrationActivity'
        namespace=dict(adb=transport,component=component,case=case,
            observed_event=observer,capture_ready_failure=collector,
            args=SimpleNamespace(out=Path('controlled-launch-output')),identity=identity)
        error=None
        try:exec(compile(module,validation.__file__,'exec'),namespace)
        except Exception as failure:error=failure
        return SimpleNamespace(namespace=namespace,error=error,unsupported=unsupported,
            transport=transport,collector=collector,observer=observer,accepted=accepted,start=start)

    def test_actual_current_launcher_passes_v3_nonce_and_renderer_options(self):
        result=self.run_boundary(self.boundary())
        self.assertIsNone(result.error)
        result.transport.assert_called_once_with('shell','am','start','-W','--activity-clear-task',
            '-n',result.namespace['component'],'--es','compactAction','collapseStart',
            '--ei','chromeNavigationVersion','3','--es','eventNonce','e'*32,
            '--ez','longName','false','--ez','observeGlassRenderer','true')
        self.assertEqual(result.accepted,['ready'])
        self.assertIs(result.namespace['start_output'],result.start)
        result.collector.assert_not_called()

    def test_previous_v2_launch_cannot_bypass_ready_failure_or_its_diagnostics(self):
        module=self.boundary();arguments=module.body[0].value.args
        at=[i for i,arg in enumerate(arguments) if isinstance(arg,ast.Constant)
            and arg.value=='chromeNavigationVersion']
        self.assertEqual(len(at),1)
        self.assertEqual(arguments[at[0]+1].value,'3')
        arguments[at[0]+1].value='2'
        result=self.run_boundary(module)
        self.assertIs(result.error,result.unsupported)
        self.assertEqual(result.accepted,[])
        self.assertEqual(result.transport.call_count,1)
        result.observer.assert_called_once_with(result.namespace['case'],'ready',request=False)
        result.collector.assert_called_once_with(result.namespace['args'].out,result.namespace['case'],
            result.namespace['identity'],result.transport,result.start)


class CurrentAcceptanceGeometryTests(unittest.TestCase):
    """Current producer bindings and geometry checks across real API boundaries."""
    def setUp(self):
        self.display=capture.WIDTH,capture.HEIGHT,capture.DENSITY
        self.request=capture.DISPLAY_REQUEST
        capture.set_display(1236,2676,480)
    def tearDown(self):capture.set_display(*self.display,requested=self.request)

    def actual_api(self):
        calls=[n for n in ast.walk(ast.parse(inspect.getsource(capture.main)))
               if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=='capture_acceptance_suite']
        self.assertEqual(len(calls),1)
        module=ast.fix_missing_locations(ast.Module(body=[ast.Assign(
            targets=[ast.Name(id='bound_api',ctx=ast.Store())],value=copy.deepcopy(calls[0]))],type_ignores=[]))
        namespace=dict(capture.__dict__,args=object(),report=object(),capture=object(),
            adb=object(),wait_for=object(),tap=object(),screenshot=object(),capture_acceptance_suite=lambda *args:args[-1])
        exec(compile(module,capture.__file__,'exec'),namespace)
        return namespace['bound_api']

    def landscape(self):
        tree=ET.Element('hierarchy')
        frame=node(tree,'',[0,0,2676,1236],kind='android.widget.FrameLayout')
        capsule=node(frame,'当前环境：日常会话，点按输入网址，长按切换环境',
            [1098,78,1578,234],text='日常会话',kind='android.widget.TextView')
        scroller=node(frame,'',[84,258,2592,960],kind='android.widget.ScrollView',scrollable='true')
        row=node(scroller,'',[1026,456,1650,636],kind='android.widget.LinearLayout')
        actions=[node(row,label,box,text=label) for label,box in (
            ('检查网络',[1026,492,1320,636]),('重新加载',[1356,492,1650,636]))]
        for label,box in (
            ('后退',[12,996,156,1140]),('打开当前环境主页',[156,996,300,1140]),
            ('当前网址 https://chatgpt.com/，点击输入网址或搜索',[312,996,2364,1140]),
            ('刷新网页',[2376,996,2520,1140]),('浏览器菜单',[2520,996,2664,1140])):
            node(frame,label,box,text='chatgpt.com/' if label.startswith('当前网址 ') else '',enabled=label!='后退')
        return tree,capsule,scroller,actions

    def test_actual_suite_bindings_follow_rotation_width_and_density_changes(self):
        api=self.actual_api()
        self.assertIs(api['navigation'],capture.current_navigation)
        self.assertIs(api['navigation_geometry'],capture.browser_navigation_geometry)
        self.assertIs(api['observed_navigation_geometry'],capture.current_observed_navigation_geometry)
        for display in ((2676,1236,480),(960,1920,480),(720,1280,320),(1236,2676,480)):
            with self.subTest(display=display):
                api['set_display'](*display)
                self.assertEqual(tuple(api[key] for key in ('WIDTH','HEIGHT','DENSITY')),display)
                self.assertEqual((capture.WIDTH,capture.HEIGHT,capture.DENSITY),display)
                self.assertEqual(api['DISPLAY_REQUEST'],display)

    def test_old_copied_globals_negative_preserves_the_observed_rotation_failure(self):
        api=self.actual_api();stale=dict(api)
        api['set_display'](2676,1236,480)
        tree,*_=self.landscape()
        current=validation.loading_actions_geometry(xml(tree),api)
        self.assertTrue(current['valid'])
        self.assertEqual((current['screenWidthPx'],current['screenHeightPx']),(2676,1236))
        self.assertEqual(current['topCapsuleCenterOffsetPx'],0)
        old=validation.loading_actions_geometry(xml(tree),stale)
        self.assertFalse(old['valid'])
        self.assertEqual(old['topCapsuleCenterOffsetPx'],720)
        self.assertFalse(old['checks']['topCapsuleCentered'])
        self.assertTrue(all(value for key,value in old['checks'].items() if key!='topCapsuleCentered'))

    def test_live_bindings_still_reject_real_off_center_clipped_or_small_actions(self):
        api=self.actual_api();api['set_display'](2676,1236,480)
        for failure in ('off-center','clipped','small-target'):
            tree,capsule,scroller,actions=self.landscape()
            if failure=='off-center':capsule.set('bounds','[1128,78][1608,234]')
            elif failure=='clipped':scroller.set('bounds','[84,258][1600,960]')
            else:actions[0].set('bounds','[1026,492][1320,635]')
            with self.subTest(failure=failure):
                value=validation.loading_actions_geometry(xml(tree),api)
                self.assertIsNotNone(value);self.assertFalse(value['valid'])


class MenuDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.display=capture.WIDTH,capture.HEIGHT,capture.DENSITY
        capture.set_display(320,640,160)
    def tearDown(self):capture.set_display(*self.display)

    def menu(self,action=False,*,enabled=True,clipped=False):
        tree=ET.Element('hierarchy')
        node(tree,'浏览器菜单',[8,120,264,168],text='浏览器菜单',kind='android.widget.TextView')
        node(tree,'关闭浏览器菜单',[264,120,312,168])
        scroller=node(tree,'',[8,170,312,600],kind='android.widget.ScrollView',scrollable='true')
        # A declared host menu with a real action body, including when the
        # requested action is absent from this viewport.
        node(scroller,'快速切换环境',[20,300,300,356],text='快速切换环境')
        if action:node(scroller,'下载管理',[20,210,300,230 if clipped else 266],text='下载管理',enabled=enabled)
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


class PartialMenuScrollTests(unittest.TestCase):
    """Replay original C5 XML at mocked transport boundaries, not on Android."""
    LABEL='管理全部环境'
    VIEWPORT=[666,455,2010,1044]
    HASHES={'start':'08381b45942fabf4c95bb063f9a1d84adfcd10c9ae0cc4dfddd1912d65498da6',
        'bottom':'4a7dab9879a2e864cd840b0bcbae3d748f6be9560784cbfb9af453c60cd1236d',
        'top':'6cf545585c452b51e7ed85bb5a01fbf04f5d00ebe67da16ded2e49ad10d1735f'}

    def setUp(self):
        self.display=capture.WIDTH,capture.HEIGHT,capture.DENSITY
        capture.set_display(2676,1236,480)
        self.frames={}
        for name,digest in self.HASHES.items():
            raw=(ROOT/'tests/browser-address-host'/('c5-menu-'+name+'.xml')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),digest)
            self.frames[name]=raw.decode('utf-8')

    def tearDown(self):capture.set_display(*self.display)

    def visible_host_frame(self):
        # Explicit synthetic response after a corrective gesture. The three
        # original failure observations above remain byte-for-byte unchanged.
        tree=ET.Element('hierarchy')
        node(tree,'浏览器菜单',[666,311,1866,455],text='浏览器菜单',kind='android.widget.TextView')
        node(tree,'关闭浏览器菜单',[1866,311,2010,455])
        scroller=node(tree,'',self.VIEWPORT,kind='android.widget.ScrollView',scrollable='true')
        node(scroller,self.LABEL,[666,650,2010,812],text=self.LABEL)
        return xml(tree)

    def seek(self,frames):
        reader=mock.Mock(side_effect=frames);adb=mock.Mock();scrolls=[]
        with mock.patch.object(workspace_v3.time,'monotonic',return_value=10):
            result=workspace_v3.seek_menu_action(adb,reader,capture.PACKAGE,self.LABEL,deadline=30,scrolls=scrolls)
        return result,reader,adb,scrolls

    def test_both_actual_producers_reobserve_the_original_clipped_sequence(self):
        initial,bottom,top=[self.frames[k] for k in ('start','bottom','top')]
        full=self.visible_host_frame()
        self.assertEqual(capture.bounds(capture.button(bottom,self.LABEL)),(666,908,2010,1044))
        self.assertEqual(capture.bounds(capture.button(top,self.LABEL)),(666,455,2010,577))
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(capture.time,'monotonic',return_value=10):
            reader=mock.Mock();reader.read.side_effect=[bottom,top,full];adb=mock.Mock();inputs=[]
            raw,target=capture.menu_action(reader,adb,initial,self.LABEL,directory,'c5',30,inputs)
            self.assertEqual(raw,full);self.assertEqual(capture.bounds(target),(666,650,2010,812))
            self.assertEqual([c.kwargs for c in reader.read.call_args_list],[{'deadline':30}]*3)
            self.assertEqual([c.args[4:] for c in adb.call_args_list],
                [('1338','972','1338','527','300'),('1338','972','1338','828','300'),('1338','527','1338','671','300')])
            self.assertEqual([r['hierarchySha256'] for r in inputs],[self.HASHES[k] for k in ('start','bottom','top')])
            for index,original in enumerate((initial,bottom,top)):
                self.assertEqual((Path(directory)/('c5-menu-'+str(index)+'.xml')).read_text(),original)
        (raw,target),reader,adb,scrolls=self.seek([initial,bottom,top,full])
        self.assertEqual(raw,full);self.assertEqual(target['bounds'],[666,650,2010,812])
        self.assertEqual([c.kwargs for c in reader.call_args_list],[{'deadline':30}]*4)
        self.assertEqual([c.args[3:] for c in adb.call_args_list],
            [('1338','926','1338','572','320'),('1338','926','1338','782','320'),('1338','572','1338','716','320')])
        self.assertEqual([r['rawXml'] for r in scrolls],[initial,bottom,top])
        self.assertTrue(workspace_v3.verify_menu_scrolls(scrolls,capture.PACKAGE,self.LABEL))

    def test_shared_geometry_keeps_coarse_inputs_and_rejects_out_of_bounds_targets(self):
        arguments=dict(coarse_start=[1338,972],coarse_end=[1338,527],minimum_target=144)
        self.assertEqual(workspace_v3.menu_scroll_points(self.VIEWPORT,None,**arguments),([1338,972],[1338,527]))
        for changed in ({'coarse_start':[1338,1044]},{'coarse_end':[1338,454]},
                        {'coarse_start':[666,972]},{'minimum_target':True}):
            with self.subTest(changed=changed),self.assertRaises(AssertionError):
                workspace_v3.menu_scroll_points(self.VIEWPORT,None,**dict(arguments,**changed))
        for target in ([665,908,2010,1044],[666,454,2010,577],[666,908,2010,1045],[666,577,2010,455]):
            with self.subTest(target=target),self.assertRaises(AssertionError):
                workspace_v3.menu_scroll_points(self.VIEWPORT,target,**arguments)

    def test_reader_recomputes_directions_and_rejects_forged_touch_coordinates(self):
        _,_,_,original=self.seek([self.frames[k] for k in ('start','bottom','top')]+[self.visible_host_frame()])
        def replace_xml(row,value):
            row['rawXml']=value;row['xmlSha256']=hashlib.sha256(value.encode()).hexdigest()
        def forged_outside(row):
            tree=ET.fromstring(row['rawXml'])
            target=next(n for n in tree.iter('node') if n.get('text')==self.LABEL)
            target.set('bounds','[666,908][2010,1045]')
            replace_xml(row,xml(tree))
        changes=[lambda r:r[1].update({'from':[1338,572],'to':[1338,716]}),
            lambda r:r[1].update({'from':[1338,926],'to':[1338,572]}),
            lambda r:r[1].update({'to':[1338,1045]}),
            lambda r:r[1].update({'from':[1338.0,926]}),
            lambda r:r[1].update(bounds=[666,455,2010,1045]),
            lambda r:r[1].update(xmlSha256='0'*64),
            lambda r:r[1].update(durationMs=300),
            lambda r:r[1].update(actualAndroidInput=False),
            lambda r:replace_xml(r[1],self.frames['top']),
            lambda r:replace_xml(r[1],self.visible_host_frame()),
            lambda r:forged_outside(r[1]),lambda r:r.extend(copy.deepcopy(r)*2)]
        for index,change in enumerate(changes):
            rows=copy.deepcopy(original);change(rows)
            with self.subTest(mutation=index),self.assertRaises((AssertionError,ValueError)):
                workspace_v3.verify_menu_scrolls(rows,capture.PACKAGE,self.LABEL)

    def test_late_corrected_hierarchy_cannot_extend_either_original_deadline(self):
        for engine in ('glass','workspace'):
            clock=[10];adb=mock.Mock();reads=[];inputs=[]
            frames=[self.frames['bottom'],self.visible_host_frame()]
            def read(*,deadline):
                reads.append(deadline)
                if len(reads)==(1 if engine=='glass' else 2):clock[0]=30.1
                return frames.pop(0) if engine=='workspace' else self.visible_host_frame()
            with tempfile.TemporaryDirectory() as directory,mock.patch.object(capture.time,'monotonic',side_effect=lambda:clock[0]):
                with self.subTest(engine=engine),self.assertRaises((TimeoutError,AssertionError)):
                    if engine=='glass':
                        capture.menu_action(SimpleNamespace(read=read),adb,self.frames['bottom'],self.LABEL,
                            directory,'late-correction',30,inputs)
                    else:
                        workspace_v3.seek_menu_action(adb,read,capture.PACKAGE,self.LABEL,deadline=30,scrolls=inputs)
                self.assertEqual(adb.call_count,1);self.assertEqual(reads,[30]*(1 if engine=='glass' else 2))


class CurrentMoreModalTests(unittest.TestCase):
    """Current reader replay of the identical cold/after-reload C5 modal XML."""
    def setUp(self):
        raw=(ROOT/'tests/browser-address-host/c5-menu-more.xml').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '5117b7fd7f21633272bc63d1b1d9d122ed4bb3b18a5ecd67f684974e2b7288b1')
        self.raw=raw.decode('utf-8')

    def test_current_more_observes_actual_menu_without_an_offscreen_address_row(self):
        self.assertFalse(any(n.get('text')=='打开网址或搜索' for n in ET.fromstring(self.raw).iter('node')))
        result=collapse_v3.inspect_ui(self.raw,'more','Controlled environment',browser=True)
        self.assertEqual(result,dict(title='浏览器菜单',closeBounds=[858,434,1002,578],closePoint=[930,506]))
        # The actual historical reader retains its original address-row proof.
        with self.assertRaises(AssertionError) as failure:
            collapse_v3.legacy_modal(self.raw,'more','Controlled environment',browser=True)
        self.assertIn('打开网址或搜索',str(failure.exception))

    def test_current_more_rejects_missing_foreign_clipped_or_unowned_controls(self):
        for change in ('heading','close','download','duplicate-close','foreign','hidden-close','disabled',
                       'unclickable','small-close','small-download','outside-scroller','hidden-scroller',
                       'clipped-scroller','wrong-heading'):
            tree=ET.fromstring(self.raw);parents={c:p for p in tree.iter() for c in p}
            heading=next(n for n in tree.iter('node') if n.get('text')=='浏览器菜单')
            close=next(n for n in tree.iter('node') if n.get('content-desc')=='关闭浏览器菜单')
            download=next(n for n in tree.iter('node') if n.get('text')=='下载管理')
            scroll=next(n for n in tree.iter('node') if n.get('class')=='android.widget.ScrollView')
            if change in ('heading','close','download'):
                target={'heading':heading,'close':close,'download':download}[change];parents[target].remove(target)
            elif change=='duplicate-close':parents[close].append(copy.deepcopy(close))
            elif change=='foreign':download.set('package','other.application')
            elif change=='hidden-close':close.set('visible-to-user','false')
            elif change=='disabled':download.set('enabled','false')
            elif change=='unclickable':download.set('clickable','false')
            elif change=='small-close':close.set('bounds','[858,434][1002,577]')
            elif change=='small-download':download.set('bounds','[78,814][1002,957]')
            elif change=='outside-scroller':parents[download].remove(download);parents[scroll].append(download)
            elif change=='hidden-scroller':scroll.set('visible-to-user','false')
            elif change=='clipped-scroller':scroll.set('bounds','[78,578][1002,975]')
            elif change=='wrong-heading':heading.set('content-desc','另一个窗口')
            with self.subTest(change=change),self.assertRaises((AssertionError,KeyError)):
                collapse_v3.inspect_ui(xml(tree),'more','Controlled environment',browser=True)


class CompactMenuVisibilityTests(unittest.TestCase):
    """Replay the original C5 modal/closed frames through the current observer."""
    def setUp(self):
        fixture=ROOT/'tests/browser-address-host'
        self.opened=(fixture/'c5-compact-menu-open.xml').read_text()
        self.closed=(fixture/'c5-compact-menu-closed.xml').read_text()
        self.assertEqual(hashlib.sha256(self.opened.encode()).hexdigest(),
            '159ed416d90e6f623a60669fc2f3e0d61b83542afadc7e6e8f4a1295a83209fe')
        self.assertEqual(hashlib.sha256(self.closed.encode()).hexdigest(),
            '4472ac8f27c648fe65bc44983320013db9bbe799f40e4d7d9f169ceb92190abf')
        raw=(fixture/'c5-compact-menu-closed-frames.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '3913c602c2ab1547ebecccc8df6607af1eed29cc2cc65cbdc4ecefb25763eb38')
        self.receipts=json.loads(raw)['frames']

    def observe(self,raw,present,*,late=False):
        clock=[10.0];deadlines=[]
        def read(*,deadline):
            deadlines.append(deadline)
            clock[0]=deadline if late else clock[0]+.1
            return raw
        with mock.patch.object(compact_runner.time,'monotonic',side_effect=lambda:clock[0]),\
             mock.patch.object(compact_runner.time,'sleep',side_effect=lambda delay:clock.__setitem__(0,clock[0]+delay)):
            try:return compact_runner.observe_browser_menu(read,capture.PACKAGE,present)
            finally:
                self.assertTrue(deadlines)
                self.assertEqual(set(deadlines),{30})
                self.assertLessEqual(clock[0],30.100001)

    def test_original_open_and_all_ten_closed_observations_are_distinct(self):
        self.assertEqual(self.observe(self.opened,True),self.opened)
        self.assertEqual([row['index'] for row in self.receipts],list(range(217,227)))
        self.assertEqual([row['completedAtWallTimeMillis'] for row in self.receipts],
            [1794817324202,1794817326489,1794817328755,1794817330997,1794817333249,
             1794817335481,1794817337725,1794817339968,1794817342216,1794817345541])
        for receipt in self.receipts:
            with self.subTest(originalAttempt=receipt['index']):
                self.assertEqual(receipt['sha256'],hashlib.sha256(self.closed.encode()).hexdigest())
                self.assertEqual(receipt['bytes'],len(self.closed.encode()))
                self.assertEqual(self.observe(self.closed,False),self.closed)
        # Exercise the unmodified historical helper, not a textual imitation:
        # its broad label semantics still see the permanent browser button.
        source=ast.parse((ROOT/'tests/gecko/run_ui_visuals.py').read_text())
        legacy=next(n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name=='visible')
        namespace={'time':compact_runner.time,'ET':ET,'dump':lambda:self.closed}
        exec(compile(ast.Module(body=[legacy],type_ignores=[]),'actual-legacy-visible','exec'),namespace)
        clock=[10.0]
        with mock.patch.object(compact_runner.time,'monotonic',side_effect=lambda:clock[0]),\
             mock.patch.object(compact_runner.time,'sleep',side_effect=lambda delay:clock.__setitem__(0,clock[0]+delay)):
            with self.assertRaises(TimeoutError):namespace['visible']('浏览器菜单',False)

    def test_persistent_same_name_and_unsettled_modal_cannot_pass_the_wrong_direction(self):
        with self.assertRaises(TimeoutError):self.observe(self.closed,True)
        with self.assertRaises(TimeoutError):self.observe(self.opened,False)
        for change in ('heading','close','duplicate-heading','duplicate-close','foreign-heading','foreign-close',
                       'hidden-heading','hidden-close','disabled-close','unclickable-close','class-close',
                       'wrong-description','wrong-parent','small-close','outside-header','overlap'):
            tree=ET.fromstring(self.opened);parents={c:p for p in tree.iter() for c in p}
            heading=next(n for n in tree.iter('node') if n.get('text')=='浏览器菜单')
            close=next(n for n in tree.iter('node') if n.get('content-desc')=='关闭浏览器菜单')
            if change in ('heading','close'):
                target=heading if change=='heading' else close;parents[target].remove(target)
            elif change=='duplicate-heading':parents[heading].append(copy.deepcopy(heading))
            elif change=='duplicate-close':parents[close].append(copy.deepcopy(close))
            elif change=='foreign-heading':heading.set('package','other.application')
            elif change=='foreign-close':close.set('package','other.application')
            elif change=='hidden-heading':heading.set('visible-to-user','false')
            elif change=='hidden-close':close.set('visible-to-user','false')
            elif change=='disabled-close':close.set('enabled','false')
            elif change=='unclickable-close':close.set('clickable','false')
            elif change=='class-close':close.set('class','android.widget.TextView')
            elif change=='wrong-description':heading.set('content-desc','other modal')
            elif change=='wrong-parent':parents[close].remove(close);parents[parents[heading]].append(close)
            elif change=='small-close':close.set('bounds','[858,434][1002,577]')
            elif change=='outside-header':close.set('bounds','[1002,434][1146,578]')
            elif change=='overlap':heading.set('bounds','[78,434][900,578]')
            raw=xml(tree)
            for present in (True,False):
                with self.subTest(change=change,present=present),self.assertRaises(TimeoutError):
                    self.observe(raw,present)

    def test_closed_requires_the_actual_complete_native_toolbar(self):
        for change in ('missing','foreign','hidden','disabled','class','partial-modal','fake-same-name'):
            tree=ET.fromstring(self.closed);parents={c:p for p in tree.iter() for c in p}
            target=next(n for n in tree.iter('node') if n.get('content-desc','').startswith('当前网址 '))
            if change=='missing':parents[target].remove(target)
            elif change=='foreign':target.set('package','other.application')
            elif change=='hidden':target.set('visible-to-user','false')
            elif change=='disabled':target.set('enabled','false')
            elif change=='class':target.set('class','android.widget.TextView')
            else:
                source=ET.fromstring(self.opened)
                original=next(n for n in source.iter('node') if n.get('content-desc')==
                    ('关闭浏览器菜单' if change=='partial-modal' else '浏览器菜单'))
                extra=copy.deepcopy(original)
                if change=='fake-same-name':extra.set('package','other.application')
                tree.append(extra)
            with self.subTest(change=change),self.assertRaises(TimeoutError):self.observe(xml(tree),False)

    def test_late_open_or_closed_frame_cannot_extend_the_original_window(self):
        for present,raw in ((True,self.opened),(False,self.closed)):
            with self.subTest(present=present),self.assertRaises(TimeoutError):
                self.observe(raw,present,late=True)

    def test_actual_compact_menu_phase_observes_both_states_and_uses_one_back(self):
        source=ast.parse((ROOT/'tests/gecko/compact_chrome_v3.py').read_text())
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='run_case')
        start=next(i for i,n in enumerate(function.body) if isinstance(n,ast.Assign)
                   and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)
                   and n.value.func.id=='snapshot' and n.value.args[0].value=='menu')
        end=next(i for i,n in enumerate(function.body) if i>start and isinstance(n,ast.AugAssign)
                 and isinstance(n.target,ast.Name) and n.target.id=='command')
        phase=ast.Module(body=function.body[start:end],type_ignores=[])
        state={'xml':self.closed};inputs=[];deadlines=[]
        def tap(name,point,box):
            inputs.append((name,point,box))
            if name=='menu-status':state['xml']=self.opened
        def adb(*parts):
            inputs.append(parts)
            self.assertEqual(parts,('shell','input','keyevent','KEYCODE_BACK'))
            state['xml']=self.closed
        def dump(**options):
            if 'deadline' in options:deadlines.append(options['deadline'])
            return state['xml']
        control=dict(tap=[996,1752],bounds=[924,1680,1068,1824])
        status=dict(networkTap=[500,610],bounds=[78,578,1002,650],stateTap=[950,610],
                    texts=[{}, {},dict(bounds=[900,578,1002,650])])
        def snapshot(name):
            if name=='menu':return dict(browserAddressRow=dict(controls=[None]*4+[control]))
            return dict(networkMetrics=status)
        with tempfile.TemporaryDirectory() as directory:
            namespace=dict(vars(compact_runner),snapshot=snapshot,tap=tap,adb=adb,dump=dump,
                visible=mock.Mock(side_effect=AssertionError('Legacy visibility cannot qualify the current menu')),
                shots=Path(directory),stem='original-menu-replay',package=capture.PACKAGE,
                adb_bytes=lambda *parts:b'host image boundary; not Android evidence')
            with mock.patch.object(compact_runner.time,'monotonic',return_value=10):
                exec(compile(phase,'actual-compact-menu-phase','exec'),namespace)
            self.assertEqual(deadlines,[30,30])
            self.assertEqual(sum(parts==('shell','input','keyevent','KEYCODE_BACK') for parts in inputs),1)
            self.assertEqual((Path(directory)/'original-menu-replay-menu-open.xml').read_text(),self.opened)
            self.assertEqual((Path(directory)/'original-menu-replay-menu-closed.xml').read_text(),self.closed)
            namespace['visible'].assert_not_called()


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
        node(tree,'浏览器菜单',[36,72,864,216],text='浏览器菜单',kind='android.widget.TextView')
        node(tree,'关闭浏览器菜单',[864,72,1008,216])
        scroller=node(tree,'',[24,216,1008,1728],kind='android.widget.ScrollView',scrollable='true')
        if box is not None:node(scroller,'当前环境网络',box,text='当前环境网络')
        else:node(scroller,'下载管理',[36,480,972,642],text='下载管理')
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
