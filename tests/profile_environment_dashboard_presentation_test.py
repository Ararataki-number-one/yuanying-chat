"""Native selectors and exact interaction ports; synthetic XML is not Android acceptance.

The original dashboard cohorts, captures, lifecycle observations and timeouts
remain. Browser entry is now direct, and dashboard checks explicitly choose
environment details. The inverse pins every deliberate port and rejects any
unrelated change to the accepted runner.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
import dashboard_browser_entry_compatibility as browser_ports
from historical_source_inputs import browser_v2_bytes


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
RUNNER = ROOT / 'tests/gecko/run_environment_dashboard.py'
BASE_COMMIT = 'c244835a4c1e3629909b2b1ce132ca5987a97d9a'
BASE_SHA256 = '99b0298e0dc5f45c744d8086d0f9fe51b1c4d0fa63cd08f50037a2196cd05064'
SPEC = importlib.util.spec_from_file_location('environment_dashboard_presentation', RUNNER)
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

# These are the complete six device-flow line changes. Everything else in the
# original runner is compared byte-for-byte with its actual committed source.
DELTAS = (
    ("            xml=wait(lambda x:'打开环境 日常会话' in x,'environment list button')\n",
     "            xml=wait(lambda x:environment_action_description(x,'日常会话') is not None,'environment list button')\n"),
    ("            click(xml,description='打开环境 日常会话');xml=wait(dashboard,'warm list opens dashboard');snapshot('warm-list',xml)\n",
     "            click(xml,description=environment_action_description(xml,'日常会话'));xml=wait(dashboard,'warm list opens dashboard');snapshot('warm-list',xml)\n"),
    ("            xml=wait(lambda x:'打开环境 日常会话' in x,'list for second environment')\n",
     "            xml=wait(lambda x:environment_action_description(x,'日常会话') is not None,'list for second environment')\n"),
    ("                if '打开环境 资料整理' in xml:break\n",
     "                if environment_action_description(xml,'资料整理') is not None:break\n"),
    ("            click(xml,description='打开环境 资料整理');xml=wait(lambda x:dashboard(x) and '资料整理' in x,'separate process second environment');snapshot('second-environment',xml,profileProcess='profile1',slot=1)\n",
     "            click(xml,description=environment_action_description(xml,'资料整理'));xml=wait(lambda x:dashboard(x) and '资料整理' in x,'separate process second environment');snapshot('second-environment',xml,profileProcess='profile1',slot=1)\n"),
    ("            xml=wait(lambda x:'启动与界面' in x and '会话' in x,'settings workspace')\n",
     "            xml=wait(settings_workspace,'settings workspace')\n"),
)


# Current settings entry alone waits for the native window input transaction.
# Reverse only these three exact changes before the retained v2 source proof.
WINDOW_INPUT_PORTS = (
    ('    def wait(predicate,label,timeout=35):\n',
     '    def wait(predicate,label,timeout=35,*,sync_window=False):\n'),
    ('            xml=dump(deadline=deadline)\n',
     '            xml=dump(deadline=deadline,sync_window=True) if sync_window else dump(deadline=deadline)\n'),
    ("            xml=wait(settings_workspace,'settings workspace')\n",
     "            xml=wait(settings_workspace,'settings workspace',sync_window=True)\n"),
)


def original_selector_flow(raw):
    if type(raw) is not bytes:
        raise ValueError('Complete dashboard source bytes required')
    start = raw.index(b'def environment_action_description(')
    end = raw.index(b'def run(', start)
    raw = raw[:start] + raw[end:]
    for previous, current in reversed(DELTAS):
        old, new = previous.encode(), current.encode()
        if raw.count(new) != 1:
            raise ValueError('Every dashboard selector change must occur exactly once')
        raw = raw.replace(new, old, 1)
    if len(raw) != 12001 or hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('The complete original dashboard device flow changed')
    return raw


def original_flow(raw):
    return original_selector_flow(browser_ports.historical_dashboard_source(raw))


def node(parent, kind, text='', description='', bounds='[60,361][1020,674]', **attributes):
    values = {'class': kind, 'package': RUN.PACKAGE, 'text': text,
              'content-desc': description, 'enabled': 'true', 'clickable': 'false',
              'bounds': bounds}
    values.update(attributes)
    return ET.SubElement(parent, 'node', values)


def environment_tree(name='日常会话', metadata='已收藏，01 · 工作 · 默认 · 电脑版，手机网络 · 连接需处理，需处理'):
    root = ET.Element('hierarchy')
    card = node(root, 'android.widget.LinearLayout', description='打开浏览器：'+name+'，'+metadata,
                clickable='true')
    node(card, 'android.widget.TextView', name, bounds='[264,404][828,474]')
    node(card, 'android.widget.TextView', '01 · 工作 · 默认 · 电脑版', bounds='[264,474][828,539]')
    return root, card


def settings_tree():
    root = ET.Element('hierarchy')
    node(root, 'android.widget.TextView', '设置', '应用设置')
    node(root, 'android.widget.TextView', '启动与外观')
    node(root, 'android.widget.Button', '浏览器', '浏览器', clickable='true')
    return root


def xml(tree):
    return ET.tostring(tree, encoding='unicode')


class DashboardPresentation(unittest.TestCase):
    def test_original_workload_outside_explicit_browser_entry_ports_is_retained(self):
        previous = subprocess.check_output(
            ['git', 'show', BASE_COMMIT+':tests/gecko/run_environment_dashboard.py'], cwd=ROOT)
        self.assertEqual((len(previous), hashlib.sha256(previous).hexdigest()), (12001, BASE_SHA256))
        # This retained inverse describes the actual released v2 navigation.
        # Current v3 behavior and every other runner byte are checked below.
        self.assertEqual(original_flow(browser_v2_bytes('tests/gecko/run_environment_dashboard.py')), previous)

    def test_original_flow_changes_missing_or_duplicate_selector_ports_reject(self):
        current = browser_v2_bytes('tests/gecko/run_environment_dashboard.py')
        for old, new, count in browser_ports.HUNKS:
            for candidate in (current.replace(new.encode(), b'', 1),
                              current.replace(new.encode(), new.encode()*2, 1)):
                with self.assertRaises(ValueError):
                    original_flow(candidate)
        prior = browser_ports.historical_dashboard_source(current)
        for old, new in DELTAS:
            for candidate in (prior.replace(new.encode(), b'', 1),
                              prior.replace(new.encode(), new.encode()*2, 1)):
                with self.assertRaises(ValueError):
                    original_selector_flow(candidate)
        for old, new in (
                (b'for _ in range(8):', b'for _ in range(7):'),
                (b'until=time.monotonic()+7', b'until=time.monotonic()+6'),
                (b'actualAndroidTaps=len(taps)-entry_taps', b'actualAndroidTaps=7'),
                (b"slot=1)", b"slot=0)"),
                (b"        assert dashboard(xml),('dashboard absent',name)\n",
                 b"        assert True,('dashboard absent',name)\n")):
            self.assertEqual(current.count(old), 1)
            with self.assertRaises(ValueError):
                original_flow(current.replace(old, new, 1))

    def test_current_named_card_and_variable_metadata_select_actual_description(self):
        for name in ('日常会话', '资料整理'):
            for metadata in ('已收藏，01 · 工作 · 默认 · 电脑版，手机网络 · 连接需处理，需处理',
                             '02 · 学习，手机网络 · 未连接，未连接'):
                tree, card = environment_tree(name, metadata)
                before = xml(tree)
                self.assertEqual(RUN.environment_action_description(before, name), card.get('content-desc'))
                self.assertEqual(xml(tree), before)

    def test_absent_other_similar_old_and_selection_cards_do_not_open_an_environment(self):
        tree, card = environment_tree()
        self.assertIsNone(RUN.environment_action_description(xml(tree), '资料整理'))
        self.assertIsNone(RUN.environment_action_description('<hierarchy />', '日常会话'))
        for description in ('打开环境 日常会话', '打开浏览器：日常会话备份，01',
                            '选择环境：日常会话，01', '打开浏览器：日常会话'):
            card.set('content-desc', description)
            self.assertIsNone(RUN.environment_action_description(xml(tree), '日常会话'))

    def test_ambiguous_disabled_invisible_or_non_native_cards_reject(self):
        tree, card = environment_tree()
        tree.append(copy.deepcopy(card))
        with self.assertRaises(AssertionError):
            RUN.environment_action_description(xml(tree), '日常会话')
        for attribute, value in (('class', 'android.widget.Button'), ('enabled', 'false'),
                                 ('clickable', 'false'), ('visible-to-user', 'false'),
                                 ('bounds', ''), ('bounds', '[60,361][60,674]'),
                                 ('bounds', '[-1,361][1020,674]')):
            tree, card = environment_tree()
            card.set(attribute, value)
            with self.subTest(attribute=attribute, value=value), self.assertRaises(AssertionError):
                RUN.environment_action_description(xml(tree), '日常会话')
        tree, card = environment_tree()
        card.set('package', 'another.package')
        self.assertIsNone(RUN.environment_action_description(xml(tree), '日常会话'))

    def test_title_must_belong_to_the_named_visible_card(self):
        for mutation in ('missing', 'duplicate', 'other-card', 'wrong-class', 'disabled',
                         'hidden', 'outside', 'empty'):
            tree, card = environment_tree()
            title = card[0]
            if mutation == 'missing':card.remove(title)
            elif mutation == 'duplicate':card.append(copy.deepcopy(title))
            elif mutation == 'other-card':card.remove(title);tree.append(title)
            elif mutation == 'wrong-class':title.set('class', 'android.widget.Button')
            elif mutation == 'disabled':title.set('enabled', 'false')
            elif mutation == 'hidden':title.set('visible-to-user', 'false')
            elif mutation == 'outside':title.set('bounds', '[264,675][828,745]')
            elif mutation == 'empty':title.set('bounds', '[264,404][264,474]')
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                RUN.environment_action_description(xml(tree), '日常会话')

    def test_settings_requires_real_identity_current_section_and_native_chat_action(self):
        tree = settings_tree()
        self.assertTrue(RUN.settings_workspace(xml(tree)))
        for index in range(3):
            altered = copy.deepcopy(tree)
            altered.remove(altered[index])
            self.assertFalse(RUN.settings_workspace(xml(altered)))
        tree[1].set('text', '启动与界面')
        self.assertFalse(RUN.settings_workspace(xml(tree)))
        for index, attribute, value in ((0, 'class', 'android.widget.Button'),
                                         (1, 'class', 'android.widget.Button'),
                                         (2, 'class', 'android.widget.TextView'),
                                         (2, 'enabled', 'false'), (2, 'clickable', 'false')):
            tree = settings_tree();tree[index].set(attribute, value)
            with self.subTest(index=index, attribute=attribute), self.assertRaises(AssertionError):
                RUN.settings_workspace(xml(tree))
        tree = settings_tree();tree.append(copy.deepcopy(tree[0]))
        with self.assertRaises(AssertionError):
            RUN.settings_workspace(xml(tree))


class CurrentBrowserEntryObservation(unittest.TestCase):
    RAW = ROOT/'tests/browser-address-host/c5-launcher-browser.xml'

    @staticmethod
    def functions(source):
        module=ast.parse(source)
        run=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        return {n.name:n for n in run.body if isinstance(n,ast.FunctionDef)}

    def reader(self,source=None,**boundaries):
        functions=self.functions(source or RUNNER.read_text())
        namespace=dict(vars(RUN),**boundaries)
        selected=[copy.deepcopy(functions[name]) for name in ('tree','dashboard','browser','wait')]
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(RUNNER)+':actual-entry-observer','exec'),namespace)
        return namespace

    def test_current_selector_accepts_the_original_c5_browser_and_old_selector_reproduces_failure(self):
        raw=self.RAW.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'e574e7e3731d5d5f1b21195ac4e6691550bd636ef8cc9bd5cb0d9f517bdb340f')
        current=self.reader()['browser']
        previous=self.reader(browser_v2_bytes('tests/gecko/run_environment_dashboard.py').decode())['browser']
        self.assertTrue(current(raw.decode()))
        self.assertFalse(previous(raw.decode()))

    def require_original_flow(self, current):
        previous=browser_v2_bytes('tests/gecko/run_environment_dashboard.py').decode()
        restored=current
        for old_port,new_port in reversed(WINDOW_INPUT_PORTS):
            self.assertEqual(restored.count(new_port),1)
            restored=restored.replace(new_port,old_port,1)
        old=ast.get_source_segment(previous,self.functions(previous)['browser'])
        new=ast.get_source_segment(restored,self.functions(restored)['browser'])
        self.assertNotEqual(new,old)
        self.assertEqual(current.count(new),1)
        self.assertEqual(current.count('UiVisualCapture.for_device('),1)
        self.assertNotIn('UiVisualCapture(',current)
        restored=restored.replace(new,old,1).replace('UiVisualCapture.for_device(','UiVisualCapture(',1)
        self.assertEqual(restored,previous)
        self.assertNotIn('historical_source_inputs',current)
        self.assertNotIn('dashboard_browser_entry_compatibility',current)

    def test_all_other_device_flow_bytes_and_original_budgets_remain_exact(self):
        self.require_original_flow(RUNNER.read_text())

    def test_native_observer_does_not_allow_changed_workload_source_or_budgets(self):
        current=RUNNER.read_text()
        for before,after in (
                ('UiVisualCapture.for_device(', 'UiVisualCapture('),
                ('UiVisualCapture.for_device(', 'UiVisualCapture.unverified('),
                ('serial=args.serial,source=source,', 'serial=args.serial,source="wrong-source",'),
                ('def wait(predicate,label,timeout=35,*,sync_window=False):',
                 'def wait(predicate,label,timeout=36,*,sync_window=False):'),
                ('until=time.monotonic()+7', 'until=time.monotonic()+6')):
            altered=current.replace(before,after,1)
            self.assertNotEqual(altered,current)
            with self.subTest(change=after),self.assertRaises(AssertionError):
                self.require_original_flow(altered)

    def test_window_synchronization_is_exactly_one_opt_in_without_other_flow_changes(self):
        current=RUNNER.read_text()
        for old,new in WINDOW_INPUT_PORTS:
            for replacement in (old,new*2):
                with self.subTest(port=new,replacement=replacement),self.assertRaises(AssertionError):
                    self.require_original_flow(current.replace(new,replacement,1))
        for before,after in (
                ('*,sync_window=False', '*,sync_window=True'),
                ('if sync_window else dump(deadline=deadline)', 'if True else dump(deadline=deadline)'),
                ("wait(browser,'workspace opens browser directly')",
                 "wait(browser,'workspace opens browser directly',sync_window=True)"),
                ("click(xml,'浏览器');wait(browser,", "click(xml,'浏览器');click(xml,'浏览器');wait(browser,"),
                ('time.sleep(.2)', 'time.sleep(.5)')):
            self.assertEqual(current.count(before),1)
            with self.subTest(change=after),self.assertRaises(AssertionError):
                self.require_original_flow(current.replace(before,after,1))

    def test_missing_foreign_clipped_hidden_disabled_and_duplicate_native_controls_never_qualify(self):
        reader=self.reader()['browser']
        labels=('后退','打开当前环境主页','当前网址','刷新网页','浏览器菜单','当前环境：')
        for label in labels:
            for change in ('missing','foreign','wrong-class','hidden','clipped','duplicate'):
                tree=ET.fromstring(self.RAW.read_text());parents={c:p for p in tree.iter() for c in p}
                target=next(n for n in tree.iter('node') if n.get('content-desc','').startswith(label))
                if change=='missing':parents[target].remove(target)
                elif change=='foreign':target.set('package','foreign.package')
                elif change=='wrong-class':target.set('class','android.widget.TextView')
                elif change=='hidden':target.set('visible-to-user','false')
                elif change=='clipped':target.set('bounds','[10,10][11,11]')
                else:parents[target].append(copy.deepcopy(target))
                with self.subTest(label=label,change=change):self.assertFalse(reader(xml(tree)))
        for label in labels[1:]:
            tree=ET.fromstring(self.RAW.read_text())
            target=next(n for n in tree.iter('node') if n.get('content-desc','').startswith(label))
            target.set('enabled','false')
            with self.subTest(label=label,change='disabled'):self.assertFalse(reader(xml(tree)))

    def test_old_reading_label_alone_and_wrong_environment_capsule_do_not_qualify(self):
        reader=self.reader()['browser']
        original=ET.fromstring(self.RAW.read_text())
        capsule=next(n for n in original.iter('node') if n.get('content-desc','').startswith('当前环境：'))
        decoy=ET.Element('hierarchy');decoy.append(copy.deepcopy(capsule))
        node(decoy,'android.widget.Button',description='进入专注阅读模式',clickable='true')
        self.assertFalse(reader(xml(decoy)))
        for attribute,value in (('text','另一个环境'),('long-clickable','false'),('clickable','false')):
            tree=copy.deepcopy(original)
            changed=next(n for n in tree.iter('node') if n.get('content-desc','').startswith('当前环境：'))
            changed.set(attribute,value)
            with self.subTest(attribute=attribute):self.assertFalse(reader(xml(tree)))
        node(original,'android.widget.TextView',description='环境仪表盘')
        with self.assertRaisesRegex(AssertionError,'unexpectedly opened environment details'):reader(xml(original))

    def test_actual_startup_wait_accepts_only_before_its_original_deadline(self):
        raw=self.RAW.read_text()
        for duration in (0,35,36):
            class Clock:
                now=0
                def monotonic(self):return self.now
                def sleep(self,seconds):self.now+=seconds
            clock=Clock();calls=[]
            def dump(*,deadline):
                calls.append(deadline);clock.now+=duration;return raw
            namespace=self.reader(time=clock,dump=dump,adb=lambda *parts:'')
            if duration==0:self.assertEqual(namespace['wait'](namespace['browser'],'actual launcher browser'),raw)
            else:
                with self.assertRaisesRegex(AssertionError,'wait budget expired'):
                    namespace['wait'](namespace['browser'],'actual launcher browser')
            self.assertEqual(calls,[35])


class SettingsWindowReadiness(unittest.TestCase):
    """Actual runner statements at controlled I/O boundaries, not a device rerun."""
    RAW = ROOT/'tests/browser-address-host/c13-settings-before-window-transition.xml'
    OBSERVATION = ROOT/'tests/browser-address-host/c13-settings-dashboard-failure.json'

    def setUp(self):
        self.raw=self.RAW.read_text()
        self.observation=json.loads(self.OBSERVATION.read_text())

    def flow(self,*,barrier_seconds=0,barrier_error=None,settings_xml=None,logcat_delay=0):
        class Clock:
            now=0
            def monotonic(self):return self.now
            def sleep(self,seconds):self.now+=seconds
        clock=Clock();reads=[];inputs=[];taps=[];state={'page':'settings','synchronized':False}
        browser_xml=CurrentBrowserEntryObservation.RAW.read_text()
        def dump(**kwargs):
            reads.append(dict(kwargs))
            if kwargs.get('sync_window') is True:
                clock.now+=barrier_seconds
                if barrier_error is not None:raise barrier_error
                state['synchronized']=True
            if state['page']=='browser':return browser_xml
            return self.raw if settings_xml is None else settings_xml
        def adb(*parts):
            if parts[:1]==('logcat',):
                clock.now+=logcat_delay;return ''
            self.assertEqual(parts[:3],('shell','input','tap'))
            inputs.append(dict(parts=parts,at=clock.now,synchronized=state['synchronized']))
            # Controlled native boundary: a usable window accepts the one tap.
            # This model does not claim how Android delivered the original tap.
            if state['synchronized']:state['page']='browser'
            return ''
        source=RUNNER.read_text();module=ast.parse(source)
        run=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        functions={n.name:n for n in run.body if isinstance(n,ast.FunctionDef)}
        selected=[copy.deepcopy(functions[name]) for name in ('tree','dashboard','browser','wait','click')]
        namespace=dict(vars(RUN),time=clock,dump=dump,adb=adb,taps=taps)
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(RUNNER)+':actual-settings-functions','exec'),namespace)
        guarded=next(n for n in run.body if isinstance(n,ast.Try))
        cohort=next(n for n in guarded.body if isinstance(n,ast.For))
        matches=[i for i,n in enumerate(cohort.body) if isinstance(n,ast.Assign)
                 and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)
                 and n.value.func.id=='wait' and n.value.args
                 and isinstance(n.value.args[0],ast.Name) and n.value.args[0].id=='settings_workspace']
        self.assertEqual(len(matches),1)
        statements=copy.deepcopy(cohort.body[matches[0]:matches[0]+3])
        self.assertEqual([n.value.func.id for n in statements],['wait','click','wait'])
        self.assertEqual(statements[1].value.args[1].value,'浏览器')
        code=compile(ast.Module(body=statements,type_ignores=[]),str(RUNNER)+':actual-settings-navigation','exec')
        return dict(execute=lambda:exec(code,namespace),namespace=namespace,clock=clock,reads=reads,inputs=inputs,taps=taps)

    def test_original_failure_is_preserved_and_its_real_xml_already_satisfied_identity(self):
        raw=self.RAW.read_bytes();record=self.observation
        self.assertEqual(hashlib.sha256(self.OBSERVATION.read_bytes()).hexdigest(),
                         '1e5f5722117ae39e00a0fef6329dd7e9197f8534aa92bb8a5d1a9d7069e30070')
        self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),
                         (24849,'f8da53f6401933f85f64d9af41fe1ab05391d319c75c5d818705efc38a7920a6'))
        self.assertEqual(record['status'],'failed')
        self.assertEqual(record['sourceCommit'],'d067ff6c83b0f8807c22b4fbb13d131a6fcf3488')
        self.assertTrue(RUN.settings_workspace(self.raw))
        self.assertEqual(record['actualAndroidTaps'][-1],dict(label='浏览器',description=None,x=148,y=1704))

    def test_actual_settings_flow_syncs_then_emits_the_one_original_tap(self):
        model=self.flow(barrier_seconds=.4);model['execute']()
        self.assertEqual(model['reads'],[{'deadline':35,'sync_window':True},{'deadline':35.4}])
        self.assertEqual(model['inputs'],[dict(parts=('shell','input','tap','148','1704'),at=.4,synchronized=True)])
        self.assertEqual(model['taps'],[self.observation['actualAndroidTaps'][-1]])

    def test_default_read_path_does_not_enable_window_synchronization(self):
        model=self.flow();reader=model['namespace']
        self.assertEqual(reader['wait'](RUN.settings_workspace,'controlled default observer'),self.raw)
        self.assertEqual(model['reads'],[{'deadline':35}])
        self.assertEqual(model['inputs'],[])

    def test_expired_or_failed_sync_never_reaches_the_original_tap(self):
        for duration,error in ((35,None),(36,None),(0,TimeoutError('native window sync deadline')),
                               (0,RuntimeError('unknown native synchronization error'))):
            model=self.flow(barrier_seconds=duration,barrier_error=error)
            expected=type(error) if error is not None else AssertionError
            with self.subTest(duration=duration,error=error),self.assertRaises(expected):model['execute']()
            self.assertEqual(model['reads'],[{'deadline':35,'sync_window':True}])
            self.assertEqual(model['inputs'],[]);self.assertEqual(model['taps'],[])

    def test_sync_preserves_the_original_identity_and_same_deadline_during_polling(self):
        model=self.flow(barrier_seconds=.5,settings_xml='<hierarchy />')
        with self.assertRaisesRegex(AssertionError,'wait budget expired'):model['execute']()
        self.assertGreater(len(model['reads']),1)
        self.assertTrue(all(row=={'deadline':35,'sync_window':True} for row in model['reads']))
        self.assertEqual(model['inputs'],[]);self.assertEqual(model['taps'],[])

    def test_crash_check_cannot_make_a_late_synchronized_frame_actionable(self):
        model=self.flow(barrier_seconds=.4,logcat_delay=35)
        with self.assertRaisesRegex(AssertionError,'wait budget expired'):model['execute']()
        self.assertEqual(model['reads'],[{'deadline':35,'sync_window':True}])
        self.assertEqual(model['inputs'],[]);self.assertEqual(model['taps'],[])


if __name__ == '__main__':
    unittest.main(verbosity=2)
