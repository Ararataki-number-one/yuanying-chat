"""Current navigation replay with independent Android density and owned XML.

All UI, transport, DEX and clock observations here are declared host models.
Git source bytes, the real driver ZIP/readback verifier, production navigation
producer and publication-facing reader execute without replacing their result.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests/gecko')]
import workspace_navigation_contract_v3 as current
import ui_hierarchy_driver as driver
from profile_chrome_native_short_target_test import controlled_evidence, output
from profile_navigation_v3_test import browser_xml

PACKAGE = 'local.pocketchat.test'


def create_source_repository(path):
    path = Path(path); path.mkdir(parents=True, exist_ok=True)
    for name in (driver.JAVA_SOURCE, driver.PYTHON_SOURCE):
        target = path/name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    def git(*parts):
        return subprocess.check_output(['git', *parts], cwd=path, stderr=subprocess.PIPE).decode().strip()
    git('init', '-q'); git('add', '.')
    git('-c', 'user.name=Navigation Host', '-c', 'user.email=navigation@invalid.example',
        'commit', '-q', '-m', 'Actual observer sources for controlled navigation boundary')
    return git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')


def scale_xml(raw, dpi):
    tree = ET.fromstring(raw)
    for node in tree.iter('node'):
        l, t, r, b = current.bounds(node)
        l, t, r, b = [int(value*dpi/480+.5) for value in (l, t, r, b)]
        node.set('bounds', f'[{l},{t}][{r},{b}]')
    return ET.tostring(tree, encoding='unicode')


def node(parent, kind, box, *, text='', description='', **extra):
    return ET.SubElement(parent, 'node', {'package':PACKAGE, 'class':'android.widget.'+kind,
        'text':text, 'content-desc':description, 'clickable':'true', 'enabled':'true',
        'selected':'false', 'bounds':f'[{box[0]},{box[1]}][{box[2]},{box[3]}]', **extra})


def menu_xml(dpi=420, *, partial=False, above=False):
    tree = ET.Element('hierarchy')
    panel = node(tree, 'LinearLayout', (0,0,1080,1920))
    node(panel, 'TextView', (100,200,900,350), text='浏览器菜单', description='浏览器菜单')
    node(panel, 'Button', (900,206,1044,350), description='关闭浏览器菜单')
    scroll = node(panel, 'ScrollView', (100,400,980,1600), scrollable='true')
    box = (100,400,980,450) if above else (100,1550,980,1600) if partial else (100,600,980,744)
    node(scroll, 'Button', box, text='管理全部环境')
    return scale_xml(ET.tostring(tree, encoding='unicode'), dpi)


def workspace_xml(dpi=420):
    tree = ET.Element('hierarchy'); host = node(tree, 'FrameLayout', (0,0,1080,1920))
    row = node(host, 'LinearLayout', (0,1700,1080,1880))
    for index, label in enumerate(('浏览器', '环境', '下载', '网络', '设置')):
        node(row, 'Button', (index*216,1700,(index+1)*216,1880), text=label, description=label,
             selected='true' if label == '环境' else 'false')
    return scale_xml(ET.tostring(tree, encoding='unicode'), dpi)


class ControlledCapture:
    def __init__(self, evidence, frames):
        self.clock = 100.0
        self.frames = list(frames)
        self.deadlines, self.calls, self.saved = [], [], []
        self.late_read = False; self.late_save = False
        self.observer = driver.HierarchyDriver(evidence, Path('/unused-host-only-receipt.json'))
        self.report = dict(schema=1, sourceCommit=evidence['sourceCommit'], serial=evidence['serial'],
            runNonce='6'*32, scope='Declared controlled host transport; no Android execution.',
            acquisitionDriver=copy.deepcopy(evidence), attempts=[], attemptCount=0, droppedAttempts=0)

    def now(self):
        self.clock += .001
        return self.clock

    def now_ns(self):
        return int(self.now()*1e9)

    def read(self, deadline=None):
        self.deadlines.append(deadline)
        if self.late_read:
            self.clock = deadline+.001
        index = self.report['attemptCount']+1
        xml = self.frames.pop(0)
        raw = xml.encode('utf-8')
        remote = '/sdcard/pocketchat-ui-visual-'+self.report['runNonce']+'-'+str(index)+'.xml'
        start = self.now_ns()
        budget = deadline-start/1e9
        commands = []
        for parts, stdout in ((self.observer.dump_parts(remote, max(.001,budget)), ('UI hierchary dumped to: '+remote+'\n').encode()),
                              (['shell','cat',remote], raw)):
            cs = self.now_ns(); self.clock += .005; ce = self.now_ns()
            commands.append(dict(parts=parts, startedAtMonotonicNanos=cs, completedAtMonotonicNanos=ce,
                startedAtWallTimeMillis=cs//1_000_000, completedAtWallTimeMillis=ce//1_000_000,
                timeoutSeconds=max(.001,deadline-cs/1e9), exitCode=0, stdout=output(stdout), stderr=output(b'')))
        end = self.now_ns()
        self.report['attempts'].append(dict(index=index, remotePath=remote, status='captured', commands=commands,
            startedAtMonotonicNanos=start, completedAtMonotonicNanos=end, existingSceneDeadline=deadline,
            xmlBytes=len(raw), xmlSha256=hashlib.sha256(raw).hexdigest()))
        self.report['attemptCount'] = index
        return xml

    def adb(self, *parts):
        self.calls.append(parts); self.clock += .01
        if parts == ('shell','wm','density'):
            return self.density_raw
        assert parts[:3] in (('shell','input','tap'), ('shell','input','swipe'))
        return ''

    def save(self, name, raw):
        self.saved.append((name,raw))
        if self.late_save:
            self.clock += 21


def controlled_roundtrip(repository, source, tree, dpi=420, *, return_capture=False, menu_sequence=None):
    """Reusable real-parser positive for consumers; everything device-side is synthetic."""
    repository = Path(repository)
    cached = repository/'controlled-native-evidence.json'
    if cached.exists():
        evidence = json.loads(cached.read_text())
    else:
        evidence = controlled_evidence(repository, source, tree)
        cached.write_text(json.dumps(evidence))
    initial = scale_xml(browser_xml(), dpi)
    capture = ControlledCapture(evidence, [initial, *(menu_sequence or [menu_xml(dpi)]), workspace_xml(dpi), initial])
    capture.density_raw = f'Physical density: 160\nOverride density: {dpi}\n'
    with mock.patch.object(current.time, 'monotonic', side_effect=capture.now), \
            mock.patch.object(current.time, 'monotonic_ns', side_effect=capture.now_ns):
        first = capture.read(deadline=capture.now()+30)
        result = current.exercise_workspace_roundtrip(capture.adb, first, capture.save, PACKAGE,
                                                     browser=True, capture=capture)
    return (result,capture) if return_capture else result


class IndependentDensityTests(unittest.TestCase):
    def test_complete_physical_and_override_readbacks_keep_exact_bytes(self):
        for raw, dpi in (('Physical density: 420\n',420),
                         ('Physical density: 160\nOverride density: 420\n',420),
                         ('Physical density: 480\r\nOverride density: 320\r\n',320)):
            value = current.display_density_evidence(raw)
            self.assertEqual(value['rawStdout'],raw)
            self.assertEqual(current.display_density(value),dpi/160)
            self.assertEqual(current.minimum_touch_pixels(value),int(48*dpi/160+.5))

    def test_unknown_duplicate_truncated_reordered_or_self_reported_density_rejects(self):
        for raw in ('420','Override density: 420\n','Physical density: 0\n',
                    'Physical density: 160\nOverride density: 420\nOverride density: 480\n',
                    'Physical density: 160\nPhysical density: 420\n',
                    'Physical density: 160\nerror\n', 'Physical density: 160\nOverride density: '):
            with self.subTest(raw=raw),self.assertRaises(AssertionError):current.display_density_evidence(raw)
        value = current.display_density_evidence('Physical density: 160\nOverride density: 420\n')
        for key,bad in (('schema',True),('stdoutBytes',True),('effectiveDpi',480),('stdoutSha256','0'*64),
                        ('command',['shell','getprop','page.devicePixelRatio'])):
            changed=copy.deepcopy(value);changed[key]=bad
            with self.subTest(key=key),self.assertRaises(AssertionError):current.display_density(changed)

    def test_actual_navigation_never_infers_density_from_the_target(self):
        raw = scale_xml(browser_xml(),420)
        with self.assertRaises(AssertionError):current.navigation(raw,PACKAGE,conversation=True,browser=True)
        value = current.display_density_evidence('Physical density: 420\n')
        actual=current.navigation(raw,PACKAGE,conversation=True,browser=True,density_evidence=value)
        self.assertEqual(actual['density'],2.625)
        tree=ET.fromstring(raw)
        for element in tree.iter('node'):
            if element.get('content-desc') in ('后退','打开当前环境主页','刷新网页','浏览器菜单'):
                l,t,r,b=current.bounds(element);element.set('bounds',f'[{l},{t}][{r-1},{b-1}]')
        with self.assertRaises(AssertionError):
            current.navigation(ET.tostring(tree,encoding='unicode'),PACKAGE,conversation=True,browser=True,density_evidence=value)
        self.assertEqual(current.navigation(browser_xml(),PACKAGE,conversation=True,browser=True)['density'],3)

    def test_menu_seek_and_replay_share_independent_48dp_with_original_direction(self):
        evidence=current.display_density_evidence('Physical density: 420\n')
        for above in (False,True):
            frames=[menu_xml(partial=True,above=above),menu_xml()];scrolls=[];calls=[]
            with mock.patch.object(current.time,'monotonic',return_value=100):
                raw,target=current.seek_menu_action(lambda *args:calls.append(args),
                    lambda **args:frames.pop(0),PACKAGE,'管理全部环境',deadline=120,scrolls=scrolls,density_evidence=evidence)
            self.assertEqual(len(calls),1);self.assertEqual(len(scrolls),1)
            self.assertEqual(target['bounds'][3]-target['bounds'][1],126)
            self.assertTrue(current.verify_menu_scrolls(scrolls,PACKAGE,'管理全部环境',density_evidence=evidence))
            self.assertEqual(scrolls[0]['from'][1]<scrolls[0]['to'][1],above)
            changed=copy.deepcopy(scrolls);changed[0]['from'],changed[0]['to']=changed[0]['to'],changed[0]['from']
            with self.assertRaises(AssertionError):current.verify_menu_scrolls(changed,PACKAGE,'管理全部环境',density_evidence=evidence)


class RoundtripEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='navigation-density-source-')
        cls.repository=Path(cls.temporary.name)
        cls.source,cls.tree=create_source_repository(cls.repository)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def fixture(self, **options):return controlled_roundtrip(self.repository,self.source,self.tree,**options)

    def verify(self,value):return current.verify_workspace_roundtrip(value,PACKAGE,source=self.source,root=self.repository)

    def test_actual_producer_preserves_three_inputs_and_native_20s_deadlines(self):
        for dpi in (420,480):
            value,capture=self.fixture(dpi=dpi,return_capture=True)
            summary=self.verify(value)
            self.assertEqual(summary['minimumActionTouchPx'],int(48*dpi/160+.5))
            self.assertEqual(summary['densityDpi'],dpi)
            self.assertEqual(summary['runId'],value['hierarchyCapture']['acquisitionDriver']['runId'])
            self.assertEqual([call[:3] for call in capture.calls],[('shell','wm','density')]+[('shell','input','tap')]*3)
            self.assertEqual([name for name,_ in capture.saved],['production-navigation-menu.xml','production-navigation-environments.xml','production-navigation-chat.xml'])
            for index,row in enumerate(value['hierarchyCapture']['attempts']):
                self.assertLessEqual(row['existingSceneDeadline']-row['startedAtMonotonicNanos']/1e9,30 if index==0 else 20)

    def test_reader_rejects_density_xml_driver_path_targets_and_deadline_forgery(self):
        good=self.fixture()
        mutations=(lambda r:r['densityEvidence'].update(effectiveDpi=480),
            lambda r:r['nativeUi']['chat'].update(rawXml=r['nativeUi']['chat']['rawXml']+' '),
            lambda r:r['hierarchyCapture']['acquisitionDriver']['installedJar'].update(sha256='f'*64),
            lambda r:r['hierarchyCapture']['attempts'][1]['commands'][0]['parts'].__setitem__(0,'other-shell'),
            lambda r:r['inputs'][0].update(point=[0,0]),
            lambda r:r['inputs'][1].update(captureIndex=1),
            lambda r:r['hierarchyCapture']['attempts'][1].update(existingSceneDeadline=125),
            lambda r:r['hierarchyCapture']['attempts'][2].update(existingSceneDeadline=125),
            lambda r:r['hierarchyCapture']['attempts'][3].update(existingSceneDeadline=125),
            lambda r:r['hierarchyCapture']['attempts'][1].update(completedAtMonotonicNanos=130_000_000_000))
        for change in mutations:
            value=copy.deepcopy(good);change(value)
            with self.subTest(change=change),self.assertRaises((AssertionError,ValueError,KeyError)):
                self.verify(value)

    def test_rehashed_menu_target_and_tap_cannot_escape_its_real_native_scroller(self):
        value=self.fixture();observation=value['nativeUi']['menu']
        tree=ET.fromstring(observation['rawXml'])
        target=next(n for n in tree.iter('node') if n.get('text')=='管理全部环境')
        target.set('bounds','[88,200][858,326]')
        raw=ET.tostring(tree,encoding='unicode').encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
        observation.update(rawXml=raw.decode(),xmlBytes=len(raw),xmlSha256=digest)
        capture=value['hierarchyCapture']['attempts'][observation['captureIndex']-1]
        capture.update(xmlBytes=len(raw),xmlSha256=digest)
        capture['commands'][1]['stdout']=output(raw)
        value['inputs'][1].update(bounds=[88,200,858,326],point=[473,263])
        with self.assertRaisesRegex(AssertionError,'clipped by its native menu'):self.verify(value)

    def test_recorded_menu_scroll_uses_same_density_and_never_gets_initial_30s_budget(self):
        value,capture=self.fixture(return_capture=True,menu_sequence=[menu_xml(partial=True),menu_xml()])
        self.verify(value)
        self.assertEqual(len(value['menuScrolls']),1)
        self.assertEqual(sum(call[:3]==('shell','input','swipe') for call in capture.calls),1)
        late=copy.deepcopy(value)
        row=late['hierarchyCapture']['attempts'][1]
        row['existingSceneDeadline']=row['startedAtMonotonicNanos']/1e9+30
        with self.assertRaises(AssertionError):self.verify(late)

    def test_late_observation_or_save_never_produces_next_input(self):
        for late_read,late_save in ((True,False),(False,True)):
            value,first=self.fixture(return_capture=True)
            evidence=value['hierarchyCapture']['acquisitionDriver']
            initial=value['nativeUi']['initial']['rawXml']
            capture=ControlledCapture(evidence,[initial,menu_xml(),workspace_xml(),initial])
            capture.density_raw='Physical density: 160\nOverride density: 420\n'
            with mock.patch.object(current.time,'monotonic',side_effect=capture.now), \
                    mock.patch.object(current.time,'monotonic_ns',side_effect=capture.now_ns):
                raw=capture.read(deadline=capture.now()+30)
                capture.late_read=late_read;capture.late_save=late_save
                with self.assertRaises((AssertionError,TimeoutError)):
                    current.exercise_workspace_roundtrip(capture.adb,raw,capture.save,PACKAGE,browser=True,capture=capture)
            self.assertEqual([call[:3] for call in capture.calls],[('shell','wm','density'),('shell','input','tap')])

    def current_file_runner(self, *, legacy_input=False):
        tree=ast.parse((ROOT/'tests/gecko/run_device.py').read_text())
        def owner(nodes):
            for parent in ast.walk(tree):
                body=getattr(parent,'body',None)
                if isinstance(body,list) and any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='navigation_capture' for t in n.targets) for n in body):return body
            raise AssertionError('Actual file runner has no source-bound navigation capture')
        body=owner(tree)
        start=next(i for i,n in enumerate(body) if isinstance(n,ast.ImportFrom) and n.module=='ui_visual_capture')
        end=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Constant) and t.slice.value=='productionNavigation' for t in n.targets))
        actual=compile(ast.fix_missing_locations(ast.Module(body=body[start:end+1],type_ignores=[])),'actual-file-navigation-entry','exec')
        value=self.fixture();evidence=value['hierarchyCapture']['acquisitionDriver']
        # Keep the v3 roundtrip fixtures above intact. Current device-runner AST
        # receives separately constructed v4 XML, never relabelled old evidence.
        from profile_navigation_v4_test import browser_xml as browser_v4_xml
        import workspace_navigation_contract_v4 as latest
        initial=value['nativeUi']['initial']['rawXml'] if legacy_input else scale_xml(browser_v4_xml(),420)
        capture=ControlledCapture(evidence,[initial,menu_xml(),workspace_xml(),initial]);capture.density_raw='Physical density: 420\n'
        events=[]
        def factory(**options):
            events.append(('prepare',options));return capture
        def adb(*parts):
            if parts in [('logcat','-c'),('shell','pidof',PACKAGE)] or parts[:2]==('shell','am'):
                events.append(('original',parts));return '123\n'
            return capture.adb(*parts)
        import ui_visual_capture
        with tempfile.TemporaryDirectory() as out, mock.patch.object(ui_visual_capture.UiVisualCapture,'for_device',side_effect=factory), \
                mock.patch.object(current.time,'monotonic',side_effect=capture.now), \
                mock.patch.object(current.time,'monotonic_ns',side_effect=capture.now_ns), \
                mock.patch.object(current.time,'sleep',side_effect=lambda seconds:setattr(capture,'clock',capture.clock+seconds)):
            namespace=dict(args=types.SimpleNamespace(adb='host-adb',serial=evidence['serial']),source=self.source,
                OUT=Path(out),adb=adb,package=PACKAGE,time=current.time,report={})
            if legacy_input:
                with self.assertRaisesRegex(AssertionError,'Missing or ambiguous native browser control.*windows'):
                    exec(actual,namespace)
                self.assertNotIn('productionNavigation',namespace['report'])
                self.assertEqual(capture.calls,[('shell','wm','density')])
            else:
                exec(actual,namespace)
                record=namespace['report']['productionNavigation']
                self.assertEqual(record['navigationContract'],4)
                summary=latest.verify_workspace_roundtrip(record,PACKAGE,source=self.source,root=self.repository)
                self.assertEqual(summary['minimumActionTouchPx'],126)
                self.assertEqual(summary['densityDpi'],420)
                self.assertEqual([call[:3] for call in capture.calls],[('shell','wm','density')]+[('shell','input','tap')]*3)
                for index,row in enumerate(record['hierarchyCapture']['attempts']):
                    self.assertLessEqual(row['existingSceneDeadline']-row['startedAtMonotonicNanos']/1e9,30 if index==0 else 20)
        self.assertEqual(events[0][0],'prepare')
        self.assertEqual(events[0][1]['source'],self.source)
        self.assertEqual(events[0][1]['serial'],evidence['serial'])
        self.assertEqual(events[0][1]['diagnostics'].name,'production-navigation-capture.json')
        self.assertEqual(len(capture.deadlines),1 if legacy_input else 4)

    def test_real_file_runner_prepares_owned_capture_before_current_scene(self):
        self.current_file_runner()

    def test_current_file_runner_rejects_old_v3_controls_before_any_native_tap(self):
        self.current_file_runner(legacy_input=True)


if __name__ == '__main__':unittest.main()
