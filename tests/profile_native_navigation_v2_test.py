"""Explicit v1/v2 native-navigation host controls; never Android acceptance."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import native_navigation_v2 as nav

# Exact v1 method ASTs read from public06a802, not a moving HEAD or a rebuilt APK.
V1_DASHBOARD_AST = '1b7b22e2d498d4c69233103757f1dc85f4201f897d134151b7a2937daee72c23'
V1_DEVICE_MAIN_AST = '8c200a4617c93203ee2cbd8092a49f67f1a4c3d9f92756cdb6a6b505afd5143b'
V1_CHAT_AST = '212fe678be25a00c1cfc5586d213110b6f9ab87a7ad78d8a7b695c93486bcb37'
AST_SHA = lambda value: hashlib.sha256(ast.dump(value,include_attributes=False).encode()).hexdigest()


class NativeNavigationV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = ROOT / 'tests/fixtures/native-navigation-v2'
        cls.provenance = json.loads((cls.fixtures / 'provenance.json').read_text())
        cls.ui = (cls.fixtures / 'canonical06-ui-chat.xml').read_text()

    def altered(self, change):
        root = ET.fromstring(self.ui)
        change(root)
        return ET.tostring(root, encoding='unicode')

    def button(self, tree, label):
        return next(n for n in tree.iter('node') if n.get('class') == 'android.widget.Button' and n.get('text') == label)

    def test_actual_two_failed_old_oracle_hierarchies_have_valid_current_navigation(self):
        for row in self.provenance['files']:
            with self.subTest(file=row['file']):
                raw = (self.fixtures / row['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
                value = nav.validate_chat(raw.decode(), row['width'], row['height'], row['density'])
                self.assertEqual(value['navigation']['labels'], ['环境', '网络', '下载', '阅读'])
                self.assertEqual(value['navigation']['centerOffsetPx'], 0)
                self.assertNotIn('>会话<', raw.decode())

    def test_apk_role_selects_before_v1_and_current_v2_without_appversion_guessing(self):
        self.assertEqual(nav.protocol_for_variant('before'), 1)
        self.assertEqual(nav.protocol_for_variant('current'), 2)
        for value in ('2.1.4', 'baseline', None, True):
            with self.assertRaises(ValueError):nav.protocol_for_variant(value)

    def test_full_labels_reading_button_touch_targets_and_center_are_independent_requirements(self):
        changes = [lambda r:self.button(r, '环境').set('text', '环'),
                   lambda r:self.button(r, '阅读').set('visible-to-user', 'false'),
                   lambda r:self.button(r, '下载').set('bounds', '[623,1602][789,1702]'),
                   lambda r:self.button(r, '阅读').set('bounds', '[700,1596][916,1812]')]
        def offset(root):
            for label in ('环境', '网络', '下载'):
                node=self.button(root,label);box=[int(x) for x in __import__('re').findall(r'\d+',node.get('bounds'))]
                box[0]+=3;box[2]+=3;node.set('bounds','[%d,%d][%d,%d]'%tuple(box))
        changes.append(offset)
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):nav.validate_chat(self.altered(change),1080,1920,480)

    def test_duplicate_foreign_or_retired_footer_controls_do_not_pass_v2(self):
        def duplicate(root):root.append(copy.deepcopy(self.button(root,'环境')))
        def foreign(root):self.button(root,'网络').set('package','foreign.app')
        def retired(root):
            node=copy.deepcopy(self.button(root,'环境'));node.set('text','设置');root.append(node)
        for change in (duplicate,foreign,retired):
            with self.assertRaises(ValueError):nav.validate_navigation(self.altered(change),1080,1920,480)

    def test_old_header_or_clickable_network_cannot_substitute_current_header(self):
        def old(root):
            n=next(n for n in root.iter('node') if n.get('content-desc','').startswith('当前环境：'))
            n.set('content-desc','当前环境：日常会话，点击展开环境工具栏')
        def network(root):
            next(n for n in root.iter('node') if n.get('content-desc','').startswith('当前环境网络：')).set('clickable','true')
        self.assertFalse(nav.chat_ready(self.altered(old),1080,1920,480))
        self.assertFalse(nav.chat_ready(self.altered(network),1080,1920,480))

    def test_real_environment_button_is_revealed_by_scroll_without_substituting_card_tap(self):
        blank='<hierarchy><node package="local.pocketchat.test" class="android.widget.ScrollView" scrollable="true" bounds="[0,100][1080,1800]"/></hierarchy>'
        target='<hierarchy><node package="local.pocketchat.test" class="android.widget.Button" text="打开环境" content-desc="打开环境 日常会话" enabled="true" clickable="true" bounds="[50,600][500,744]"/></hierarchy>'
        state={'scrolled':False};commands=[]
        def adb(*args):
            commands.append(args)
            self.assertEqual(args[:3],('shell','input','swipe'));state['scrolled']=True
        def dump(deadline):return target if state['scrolled'] else blank
        result=nav.reveal_environment_entry(adb,dump,'日常会话',1080,1920,480)
        self.assertEqual(result,target);self.assertEqual(len(commands),1)
        self.assertIsNone(nav.environment_open_button(target,'资料整理',1080,1920,480))

    def font_rows(self):
        identity=dict(sourceCommit='1'*40,sourceTree='2'*40,apkSha256='3'*64)
        rows=[]
        checks=('layoutFits','glyphFits','wholeLabel','widthFits','viewVisible','horizontalLineFits','horizontalGlyphFits','verticalUnscrolled','selectionMatches')
        for selected in range(-1,4):
            for index,label in enumerate(nav.LABELS):
                rows.append(dict(schema=1,kind='label',nonce='a'*32,actualAndroidLayout=True,**identity,fontScale=2,density=3,
                    selectedIndex=selected,measurement=dict(buttonIndex=index,label=label,valid=True,width=180,height=204,
                    selected=selected==index,checks=dict.fromkeys(checks,True))))
        rows.append(dict(schema=1,kind='summary',nonce='a'*32,actualAndroidLayout=True,**identity,fontScale=2,density=3,status='verified',observationCount=20))
        return identity,rows

    def test_synthetic_font_transport_requires_all20_current_nonce_source_and_real_label_checks(self):
        identity,rows=self.font_rows()
        raw='\n'.join(json.dumps(r) for r in rows)
        self.assertEqual(nav.validate_native_font_records(raw,'a'*32,identity,2,480)['observationCount'],20)
        for mutate in (lambda r:r.pop(),lambda r:r.append(copy.deepcopy(r[0])),
                       lambda r:r[0].update(nonce='b'*32),lambda r:r[0].update(sourceCommit='f'*40),
                       lambda r:r[0]['measurement']['checks'].update(glyphFits=False),
                       lambda r:r[0]['measurement'].update(label='环'),lambda r:r[0].update(fontScale=1.3),
                       lambda r:r[0].update(selectedIndex=True)):
            bad=copy.deepcopy(rows);mutate(bad)
            with self.assertRaises(ValueError):nav.validate_native_font_records('\n'.join(json.dumps(r) for r in bad),'a'*32,identity,2,480)

    def test_native_font_controller_requests_one_current_source_nonce_and_retains_raw_output(self):
        identity,rows=self.font_rows();calls=[]
        raw='\n'.join(json.dumps(r) for r in rows)+'\n'
        def adb(deadline,*parts):
            self.assertEqual(deadline,125);calls.append(parts)
            return raw if parts[0]=='logcat' else ''
        with tempfile.TemporaryDirectory() as directory,patch.object(nav.time,'monotonic',return_value=100),\
                patch.object(nav.uuid,'uuid4',return_value=SimpleNamespace(hex='a'*32)):
            value=nav.capture_native_fonts(adb,identity=identity,font_scale=2,density=480,out=directory,stem='current')
            self.assertEqual(value['observationCount'],20)
            self.assertEqual((Path(directory)/value['file']).read_text(),raw)
            self.assertEqual(calls[0][:6],('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.UiVisualIntegrationActivity'))
            self.assertIn('--activity-clear-top',calls[0]);self.assertIn('navigation-typography',calls[0])
            self.assertFalse(any('input' in call or 'clear' in call for call in calls))

    def test_before_apk_retains_complete_original_chat_oracle_and_never_uses_v2_font_fixture(self):
        path='tests/gecko/run_ui_visuals.py'
        new=ast.parse((ROOT/path).read_text())
        get=lambda tree:next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='capture')
        new_chat=next(n for n in get(new).body if isinstance(n,ast.If) and ast.unparse(n.test)=="scene == 'chat'")
        branch=new_chat.body[0];self.assertEqual(ast.unparse(branch.test),'navigation_protocol == 1')
        self.assertEqual(AST_SHA(ast.Module(body=branch.body,type_ignores=[])),V1_CHAT_AST)
        font=next(n for n in get(new).body if isinstance(n,ast.If) and any(isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id=='capture_native_fonts' for c in ast.walk(n)))
        self.assertEqual(ast.unparse(font.test),"scene == 'chat' and navigation_protocol == 2")

    def test_current_settings_route_executes_native_search_and_book_without_legacy_tab_assumptions(self):
        tree=ast.parse((ROOT/'tools/gecko/native_navigation_v2.py').read_text())
        method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_dashboard_v2')
        loop=next(n for n in method.body if isinstance(n,ast.Try)).body[0]
        start=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='command_deadline' for t in n.targets))
        end=next(i for i,n in enumerate(loop.body[start:],start) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='snapshot')
        program=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(loop.body[start:end+1]),type_ignores=[])),'actual-current-settings-route','exec')
        def xml(*texts,search=None):
            root=ET.fromstring(self.ui)
            for text in texts:ET.SubElement(root,'node',{'text':text})
            if search is not None:ET.SubElement(root,'node',{'class':'android.widget.EditText','text':search,'content-desc':'搜索应用操作'})
            return ET.tostring(root,encoding='unicode')
        state={'xml':(self.fixtures/'canonical-a9-manager-top.xml').read_text()};commands=[];snapshots=[]
        def wait(predicate,label,**options):
            self.assertEqual(options.get('deadline',135),135)
            self.assertTrue(predicate(state['xml']),label)
            return state['xml']
        def click(value,label=None,description=None):
            if description=='搜索操作':state['xml']=xml(search='')
            elif label=='阅读':state['xml']=self.ui
            else:raise AssertionError((label,description))
        def adb(*parts):
            commands.append(parts)
            if parts==('shell','input','text','setting'):state['xml']=xml('1 项操作','应用设置',search='setting')
            elif parts==('shell','input','keyevent','66'):state['xml']=xml('启动与界面','阅读')
            else:raise AssertionError(parts)
        env=dict(time=SimpleNamespace(monotonic=lambda:100),wait=wait,click=click,adb=adb,
                 tree=lambda value:list(ET.fromstring(value).iter('node')),validate_navigation=nav.validate_navigation,
                 chat_ready=nav.chat_ready,dashboard=lambda value:False,width=360,height=640,
                 reveal_manager_command_entry=nav.reveal_manager_command_entry,
                 dump=lambda *,deadline:state['xml'],
                 snapshot=lambda name,value,**metadata:snapshots.append((name,nav.validate_chat(value,1080,1920,480),metadata)))
        with patch.object(nav.time,'monotonic',return_value=100):
            exec(program,env)
        self.assertEqual(commands,[('shell','input','text','setting'),('shell','input','keyevent','66')])
        self.assertEqual(snapshots[0][0],'workspace-chat')
        self.assertFalse(snapshots[0][2]['dashboard_required'])

    def test_current_settings_route_missing_actual_reveal_dependency_cannot_emit_input(self):
        tree=ast.parse((ROOT/'tools/gecko/native_navigation_v2.py').read_text())
        method=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_dashboard_v2')
        loop=next(node for node in method.body if isinstance(node,ast.Try)).body[0]
        start=next(index for index,node in enumerate(loop.body) if isinstance(node,ast.Assign)
                   and any(isinstance(target,ast.Name) and target.id=='command_deadline' for target in node.targets))
        program=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(loop.body[start:start+3]),type_ignores=[])),
                        'actual-current-settings-route-without-reveal','exec')
        emitted=[]
        environment=dict(time=SimpleNamespace(monotonic=lambda:100),width=360,height=640,
                         adb=lambda *parts:emitted.append(('adb',parts)),
                         dump=lambda **options:self.ui,
                         click=lambda *parts,**options:emitted.append(('click',parts,options)))
        with self.assertRaisesRegex(NameError,'reveal_manager_command_entry'):
            exec(program,environment)
        self.assertEqual(emitted,[])

    def test_full_original_dashboard_run_and_all_its_case_identifiers_are_retained(self):
        path='tests/gecko/run_environment_dashboard.py'
        new=ast.parse((ROOT/path).read_text())
        get=lambda tree:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        self.assertEqual(AST_SHA(get(new)),V1_DASHBOARD_AST)
        text=(ROOT/'tools/gecko/native_navigation_v2.py').read_text()
        for scenario in ('home-return','warm-list','second-environment','workspace-chat',
                         'persists-beyond-five-seconds','warm-list-second-process-and-settings-chat-entry'):
            self.assertIn(scenario,text)

    def test_device_runner_changes_only_explicit_nav_dispatch_and_keeps_original_v1_assertion(self):
        path='tests/gecko/run_device.py';new=ast.parse((ROOT/path).read_text())
        new_main=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        class Restore(ast.NodeTransformer):
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Call) and any(isinstance(a,ast.Constant) and a.value=='--native-navigation-version' for a in node.value.args):return None
                return self.generic_visit(node)
            def visit_If(self,node):
                if isinstance(node.test,ast.Compare) and ast.unparse(node.test)=='args.native_navigation_version == 1':return node.body
                return self.generic_visit(node)
        restored=Restore().visit(new_main)
        self.assertEqual(AST_SHA(restored),V1_DEVICE_MAIN_AST)


if __name__=='__main__':unittest.main()
