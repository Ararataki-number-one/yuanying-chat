"""Counterfeit receipt controls only; these are not Android or UI acceptance."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests/gecko')]
import chrome_collapse_contract as reader
import chrome_collapse_contract_v2 as v2
import integration_event_contract as transport
import run_chrome_collapse as runner
import run_chrome_collapse_v2 as current_runner


def identity():
    return dict(schema=1, package=v2.PACKAGE, sourceCommit='a'*40, sourceTree='b'*40,
                dirtySource=False, version='1.7.0', versionCode=52,
                sdkCoordinate=transport.SDK_COORDINATE, apkSha256='c'*64, apkBytes=100,
                buildStampSha256='d'*64)


def node(parent, kind, text='', description='', rectangle=(10, 10, 100, 60), **values):
    l, t, r, b = rectangle
    attrs = dict(package=v2.PACKAGE, **{'class': 'android.widget.'+kind, 'text': text,
        'content-desc': description, 'bounds': f'[{l},{t}][{r},{b}]', 'enabled': 'true',
        'clickable': 'true' if kind in ('Button', 'EditText') else 'false', 'selected': 'false'})
    attrs.update(values)
    return ET.SubElement(parent, 'node', attrs)


def xml_for(phase):
    root = ET.Element('hierarchy', rotation='0')
    if phase in v2.ADDRESS_PHASES:
        node(root, 'TextView', '打开网址')
        node(root, 'EditText', v2.TARGET, '网址或搜索', (100, 200, 900, 350), focused='true')
        for index, label in enumerate(('取消', '主页', '前往')):
            node(root, 'Button', label, rectangle=(100+index*250, 600, 300+index*250, 730))
    elif phase in ('environmentPicker', 'more'):
        title = '快速切换环境' if phase == 'environmentPicker' else '会话选项'
        node(root, 'TextView', title, title)
        node(root, 'Button', description='关闭'+title, rectangle=(800, 100, 950, 250))
        if phase == 'environmentPicker':
            node(root, 'EditText', description='搜索要切换的环境')
            node(root, 'Button', '01  Controlled environment · 当前\n未分组',
                 '切换到 Controlled environment，未分组', selected='true')
        else: node(root, 'Button', '打开网址或搜索')
    elif phase in ('reading', 'readingBackMode'):
        node(root, 'Button', '退出阅读', '退出专注阅读，恢复应用工具栏和导航', (800, 100, 1050, 244))
    else:
        conversation = phase in v2.NORMAL_UI_PHASES
        labels = ('环境', '网络', '下载', '阅读') if conversation else ('会话', '环境', '下载', '网络', '设置')
        chosen = {'environment': '环境', 'drawer': '环境', 'network': '网络', 'downloads': '下载'}.get(phase)
        dock = node(root, 'LinearLayout')
        for index, label in enumerate(labels):
            parent = node(root, 'LinearLayout') if conversation and label == '阅读' else dock
            description = '进入专注阅读模式' if conversation and label == '阅读' else label
            node(parent, 'Button', label, description, (index*210, 1730, index*210+200, 1880),
                 selected='true' if label == chosen else 'false')
    return ET.tostring(root, encoding='unicode')


def seal(case, build):
    rows = []
    for sequence, (phase, sample) in enumerate(case['observations'].items(), 1):
        event = dict(kind='collapseSnapshot', result=sample, nativeContext='environment-1', processSlot=0)
        envelope = dict(schema=1, sourceCommit=build['sourceCommit'], buildIdentity=build,
            runNonce=case['runNonce'], fixtureAction='chromeCollapse', command=1,
            sequence=sequence, nativeContext='environment-1', processSlot=0,
            observedAtElapsedRealtime=1000+sequence, event=event)
        raw = json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))+'\n'
        receipt = {key: envelope[key] for key in ('schema', 'runNonce', 'fixtureAction', 'command', 'sequence', 'nativeContext', 'processSlot')}
        receipt.update(kind='eventReceipt', eventKind='collapseSnapshot', payloadBytes=len(raw.encode()), payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
        rows.append(dict(receipt=receipt, rawUtf8=raw))
    case['eventTransfer'] = dict(runNonce=case['runNonce'], fixtureAction='chromeCollapse', processSlot=0, events=rows)


def reseal(report):
    for case in report['cases']:
        seal(case, report['buildIdentity'])


def case_fixture(width, scale, nonce):
    document = 'f'*32
    message = dict(kind='documentReady', url='http://127.0.0.1:8765/c/reload-collapse', appearanceDocument='g'*32)
    ready = dict(rawMessage=message, normalizedMessage=dict(message, url=v2.TARGET), senderUrl=message['url'],
        actualUrl=message['url'], visibleUrl=v2.TARGET, nativeSession=111, currentSession=111,
        topLevel=True, contentScript=True, acceptedByProduction=True)
    trusted = [dict(type='touchend', trusted=True)]
    baseline = dict(navigationContract=2, navigationLayout='conversation-compact',
        expanded=True, toolbarVisibility=0, toolbarHeight=240, compactVisibility=8, compactHeight=120,
        compactName='Controlled environment', environmentName='Controlled environment', topVisibility=0, networkVisibility=0,
        webWidth=width*3, webHeight=1400, webX=0, webY=270, surface=101, sdkSession=111, attachedSession=111,
        draft='unsent controlled browser draft', cookie='session=synthetic-reload', sendCount=0,
        path='/c/reload-collapse', document=document, documents=1, loads=0, stops=0, scrollY=100,
        pending={'id': 'controlled-pending', 'confirmed': True}, pendingStored='{"id":"controlled-pending","confirmed":true}',
        page=0, keyboard=False, visibleDocument=True, loadingCoverVisibility=8,
        documentReadyEvidence=ready, activityStarts=0, menuOpens=0, windowFocus=True,
        touches=[], nativeTouches=[], toolbarBounds=[0, 30, width*3, 270],
        compactTap=[width*3//2, 90], addressTap=[width*3//2, 210], moreTap=[width*3-70, 210], drawerTap=[70, 210],
        environmentTap=[100, 1805], networkTap=[310, 1805], downloadsTap=[520, 1805], readingTap=[730, 1805],
        readingExitTap=[925, 172], readingRequested=False, readingActive=False, readingExitVisibility=8,
        navigationVisibility=0, navigationHeight=180, workspaceHeight=180,
        headerSwipeFrom=[width*3//2, 258], headerSwipeTo=[width*3//2, 31], headerButtonTouch=[180, 160, width*3-180, 260],
        addressDialog=dict(schema=1, ownerActivity=True, showing=False, dialogRef=0, editorRef=0),
        trusted=trusted, telemetryReady=True, fixtureInputTelemetry=dict(schema=1, realm='page-main-world',
            document=document, listenerTypes=['touchstart', 'touchmove', 'touchend'], events=trusted, count=1, dropped=0))
    observations = {}
    collapsed = ('ready', 'up', 'down', 'upBeforeChat', 'upBeforeNative', 'upBeforeResume', 'activityResume', 'headerUp')
    for phase in v2.PHASES:
        value = copy.deepcopy(baseline); value['command'] = phase
        if phase in collapsed:
            value.update(expanded=False, toolbarHeight=120, compactVisibility=0, topVisibility=8, webHeight=1520, webY=150)
        if phase == 'up': value['scrollY'] = 200
        if phase in ('network', 'downloads'):
            value.update(page=4 if phase == 'network' else 1, navigationLayout='workspace-five', toolbarVisibility=8)
        if v2.PHASES.index(phase) >= v2.PHASES.index('environmentReturn'): value['activityStarts'] = 1
        if phase == 'drawerReturn': value['activityStarts'] = 2
        if v2.PHASES.index(phase) >= v2.PHASES.index('more'): value['menuOpens'] = 1
        if phase in ('reading', 'readingBackMode'):
            value.update(readingActive=True, readingRequested=True, readingExitVisibility=0,
                         toolbarVisibility=8, navigationVisibility=8, webHeight=1820, workspaceHeight=0)
        if phase in ('environmentPicker', 'more'): value['windowFocus'] = False
        if phase in v2.ADDRESS_PHASES:
            value['windowFocus'] = False
            value['addressDialog'] = dict(schema=1, ownerActivity=True, showing=True, dialogRef=202, editorRef=203,
                dialogClass='android.app.AlertDialog', editorClass='android.widget.EditText', decorAttached=True,
                decorShown=True, decorFocus=True, editorShown=True, editorFocused=True, editorWindowFocus=True,
                sameWindow=True, editorDescription='网址或搜索', editorText=v2.TARGET, editorInputType=17,
                editorMaxLines=1, decorBounds=[50, 100, 1000, 800], editorBounds=[100, 200, 900, 350],
                cancelBounds=[100, 600, 300, 730], cancelText='取消', cancelShown=True, cancelEnabled=True, cancelClickable=True)
        observations[phase] = value
    for before, after in (('initialChat', 'up'), ('up', 'down'), ('compactExpand', 'horizontal')):
        s = observations[before]
        observations[after]['touches'] = [dict(action=a, pointers=1, width=s['webWidth'], height=s['webHeight'], expanded=s['expanded']) for a in (0, 2, 1)]
    observations['headerUp']['nativeTouches'] = [dict(action=a, pointers=1, height=1400, expanded=True) for a in (0, 2, 1)]
    native_ui = {}
    for phase in v2.UI_PHASES:
        raw = xml_for(phase)
        component = v2.ENVIRONMENT_ACTIVITY if phase in ('environment', 'drawer') else v2.ACTIVITY
        activity = 'topResumedActivity=ActivityRecord{abc u0 '+component+' t8}\n'
        native_ui[phase] = dict(phase=phase, runNonce=nonce, sourceCommit='a'*40, rawXml=raw,
            xmlBytes=len(raw.encode()), xmlSha256=hashlib.sha256(raw.encode()).hexdigest(), activityState=activity,
            activityBytes=len(activity.encode()), activitySha256=hashlib.sha256(activity.encode()).hexdigest())
    inputs = []
    for label, kind, previous, target in v2.INPUTS:
        row = dict(label=label, kind=kind, before=previous, actualAndroidInput=True)
        if kind == 'tap':
            if target == 'cancel': row.update(point=[200, 665], bounds=[100, 600, 300, 730])
            elif target == 'closePicker': row.update(point=[875, 175], bounds=[800, 100, 950, 250])
            else: row['point'] = observations[previous][target]
        elif kind == 'swipe':
            s = observations[previous]; x=s['webWidth']//2; top=s['webY']+s['webHeight']//4; bottom=s['webY']+s['webHeight']*2//3
            start, end = ([x, bottom], [x, top]) if target == 'up' else ([x, top], [x, bottom])
            if target == 'horizontal': start, end = [s['webWidth']//4, (top+bottom)//2], [s['webWidth']*3//4, (top+bottom)//2]
            if target == 'short': start, end = [x, bottom], [x, bottom-12]
            if target == 'header': start, end = s['headerSwipeFrom'], s['headerSwipeTo']
            row.update({'from': start, 'to': end, 'durationMs': 320})
        elif kind == 'longPress': row.update(point=observations[previous][target], durationMs=700)
        elif kind == 'back': row['key'] = 'KEYCODE_BACK'
        else: row.update(component=v2.ACTIVITY, originalBudgetMs=20000)
        inputs.append(row)
    readiness = dict(status='passed', sourceCommit='a'*40, preEmitOnly=True, releaseAcceptance=False,
        applicationAcceptance=False, originalActionBudgetMs=90000, preparationBudgetMs=20000)
    case = dict(navigationContract=2, viewport=width, fontScale=scale, androidUser=0, runNonce=nonce,
        sourceCommit='a'*40, actualAndroidExecution=True, actualGeckoExecution=True, actualAndroidTouchExecution=True,
        checks=[{'name': name, 'pass': True} for name in v2.NAMES], legacyBehaviorMap=[list(r) for r in v2.LEGACY_BEHAVIOR_MAP],
        observations=observations, nativeUi=native_ui, actualAndroidInputs=inputs,
        firstTapReadiness=dict(readiness, tapInvocations=1), headerReadiness=dict(readiness, gestureInvocations=1),
        fixtureRequests=[dict(kind='http', path='/c/reload-collapse', documentMarker=document)])
    seal(case, identity())
    return case


def positive():
    return dict(navigationContract=2, status='passed', sourceCommit='a'*40,
        actualAndroidExecution=True, actualGeckoExecution=True, actualAndroidTouchExecution=True,
        buildIdentity=identity(), cases=[case_fixture(w, f, str(i)*32) for i, (w, f) in enumerate(((360, 1), (412, 1), (360, 2)), 1)])


def legacy():
    report = positive(); report.pop('navigationContract')
    phase_order = ('ready', 'initialChat', 'up', 'down', 'compactExpand', 'horizontal', 'short', 'upBeforeChat',
                   'selectedChat', 'upBeforeNative', 'settings', 'nativeReturn', 'upBeforeResume', 'activityResume', 'resumeChat', 'headerUp')
    for case in report['cases']:
        case.pop('navigationContract'); values = case['observations']
        values['settings'] = dict(values['network'], command='settings', page=3)
        case['observations'] = {phase: values[phase] for phase in phase_order}
        case['checks'] = [{'name': name, 'pass': True} for name in sorted(reader.NAMES)]
        case['actualAndroidInputs'] = [{'kind': 'swipe' if i < 8 else 'tap', 'actualAndroidInput': True} for i in range(14)]
        seal(case, report['buildIdentity'])
    return report


class ChromeCollapseV2Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The counterfeit legacy owner has no Git commit. Cache only that exact
        # immutable read's real success/failure across the mutation matrix; all
        # SDK validators still execute, and no source/report bytes are invented.
        cls.environment = patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '1'})
        cls.environment.start()
        original = subprocess.check_output; cache = {}
        expected = ['git', 'show', 'a'*40+':third-party/sdk/geckoview-157.0.1-editable-selection.json']
        def read(command, **kwargs):
            if command != expected: return original(command, **kwargs)
            if not cache:
                try: cache['value'] = original(command, **kwargs)
                except subprocess.CalledProcessError as error: cache['error'] = error
            if 'error' in cache:
                error = cache['error']
                raise subprocess.CalledProcessError(error.returncode, error.cmd, output=error.output, stderr=error.stderr)
            return cache['value']
        cls.git_read = patch.object(subprocess, 'check_output', side_effect=read)
        cls.git_read.start()

    @classmethod
    def tearDownClass(cls):
        cls.git_read.stop(); cls.environment.stop()

    def setUp(self): self.report = positive()

    def verify(self, report=None): return reader.verify_auto_collapse(self.report if report is None else report, 'a'*40, 'c'*64)

    def rejected(self, change, *, rescope=False):
        value = copy.deepcopy(self.report); change(value)
        if rescope: reseal(value)
        with self.assertRaises((AssertionError, ValueError, KeyError, TypeError)):
            self.verify(value)

    def test_complete_host_only_fixture_and_exact_retained_coverage(self):
        result = self.verify()
        self.assertEqual(result['checks'], 66); self.assertEqual(result['retainedLegacyProtections'], 14)
        self.assertEqual(result['phasesPerCase'], 34); self.assertEqual(result['actualInputsPerCase'], 35)
        self.assertEqual(len(v2.LEGACY_BEHAVIOR_MAP), 14)
        self.assertEqual(sum(r[1] == 'swipe' for r in v2.INPUTS), 8)
        self.assertEqual(sum(r[1] == 'tap' for r in v2.INPUTS), 19)

    def test_legacy_report_and_explicit_one_keep_the_original_reader(self):
        value = legacy(); self.assertEqual(self.verify(value)['cases'], 3)
        value['navigationContract'] = 1; self.assertEqual(self.verify(value)['cases'], 3)

    def test_versions_do_not_default_or_coerce_to_two(self):
        for version in (True, False, None, '2', 0, 3, 2.0):
            with self.subTest(version=version): self.rejected(lambda r: r.update(navigationContract=version))
        self.rejected(lambda r: r.pop('navigationContract'))
        self.rejected(lambda r: r['cases'][0].pop('navigationContract'))

    def test_no_phase_can_be_removed_duplicated_or_reordered(self):
        for phase in v2.PHASES:
            with self.subTest(phase=phase):
                self.rejected(lambda r, p=phase: r['cases'][0]['observations'].pop(p), rescope=True)
        self.rejected(lambda r: r['cases'][0]['eventTransfer']['events'].append(r['cases'][0]['eventTransfer']['events'][-1]))
        self.rejected(lambda r: r['cases'][0]['eventTransfer']['events'].reverse())

    def test_each_required_real_input_and_exact_kind_order_are_enforced(self):
        for index in range(35):
            with self.subTest(index=index): self.rejected(lambda r, i=index: r['cases'][0]['actualAndroidInputs'].pop(i))
        self.rejected(lambda r: r['cases'][0]['actualAndroidInputs'][0].update(actualAndroidInput=False))
        self.rejected(lambda r: r['cases'][0]['actualAndroidInputs'][0].update(point=[0, 0]))
        self.rejected(lambda r: r['cases'][0]['actualAndroidInputs'][13].update(key='KEYCODE_HOME'))
        self.rejected(lambda r: r['cases'][0]['actualAndroidInputs'][29].update(durationMs=1))

    def test_native_page_reading_and_navigation_identity_are_enforced(self):
        for phase, field, value in (('network', 'page', 3), ('downloads', 'page', 4), ('reading', 'readingActive', False),
                                    ('reading', 'toolbarVisibility', 0), ('readingBack', 'readingActive', True),
                                    ('readingExit', 'webHeight', 1820), ('environmentReturn', 'activityStarts', 0),
                                    ('drawerReturn', 'activityStarts', 1), ('more', 'menuOpens', 0)):
            with self.subTest(phase=phase, field=field):
                self.rejected(lambda r, p=phase, k=field, v=value: r['cases'][0]['observations'][p].update({k:v}), rescope=True)

    def test_page_xml_alone_cannot_impersonate_a_live_owned_dialog(self):
        fields = dict(showing=False, ownerActivity=False, dialogRef=0, editorRef=0, sameWindow=False,
                      editorFocused=False, editorWindowFocus=False, decorFocus=False, cancelClickable=False,
                      editorInputType=1, editorText='https://outside.test', cancelBounds=[1, 2, 3, 4])
        for key, value in fields.items():
            with self.subTest(field=key):
                self.rejected(lambda r, k=key, v=value: r['cases'][0]['observations']['initialAddress']['addressDialog'].update({k:v}), rescope=True)
        self.rejected(lambda r: r['cases'][0]['observations']['initialAddress'].update(windowFocus=True), rescope=True)

    def test_changed_xml_hash_source_foreign_controls_and_wrong_activity_reject(self):
        for phase in v2.UI_PHASES:
            with self.subTest(phase=phase): self.rejected(lambda r, p=phase: r['cases'][0]['nativeUi'].pop(p))
        self.rejected(lambda r: r['cases'][0]['nativeUi']['network'].update(xmlSha256='0'*64))
        self.rejected(lambda r: r['cases'][0]['nativeUi']['drawer'].update(sourceCommit='f'*40))
        for change in ('foreign', 'wrong-title', 'wrong-native-page', 'historical-activity'):
            value=copy.deepcopy(self.report); item=value['cases'][0]['nativeUi']['initialAddress' if change != 'wrong-native-page' else 'network']
            if change == 'foreign': item['rawXml']=item['rawXml'].replace(v2.PACKAGE, 'foreign.test')
            if change == 'wrong-title': item['rawXml']=item['rawXml'].replace('打开网址', '伪造网页文字')
            if change == 'wrong-native-page': item['rawXml']=item['rawXml'].replace('selected="true"', 'selected="false"')
            if change == 'historical-activity': item['activityState']='mLastPausedActivity=ActivityRecord{abc u0 '+v2.ACTIVITY+' t8}\n'
            for raw,size,digest in (('rawXml','xmlBytes','xmlSha256'),('activityState','activityBytes','activitySha256')):
                item[size]=len(item[raw].encode());item[digest]=hashlib.sha256(item[raw].encode()).hexdigest()
            with self.subTest(change=change),self.assertRaises((AssertionError,ValueError)): self.verify(value)

    def test_all_original_document_state_stays_bound_even_after_menu_or_activity(self):
        for phase in ('initialChat', 'up', 'network', 'reading', 'more', 'drawerReturn'):
            for field in v2.STABLE:
                with self.subTest(phase=phase, field=field):
                    self.rejected(lambda r, p=phase, k=field: r['cases'][0]['observations'][p].update({k:None}), rescope=True)

    def test_original_gesture_and_header_guards_still_reject(self):
        changes = [lambda o:o['up']['touches'].pop(), lambda o:o['up']['touches'][1].update(height=1),
                   lambda o:o['up'].update(scrollY=0), lambda o:o['down'].update(expanded=True),
                   lambda o:o['short'].update(expanded=False), lambda o:o['horizontal'].update(expanded=False),
                   lambda o:o['activityResume'].update(expanded=True), lambda o:o['headerUp']['nativeTouches'][1].update(expanded=False),
                   lambda o:o['headerUp'].update(menuOpens=1), lambda o:o['headerUp'].update(activityStarts=1),
                   lambda o:o['resumeChat'].update(headerButtonTouch=[1, 2, 3, 4])]
        for index, change in enumerate(changes):
            with self.subTest(index=index): self.rejected(lambda r, c=change:c(r['cases'][0]['observations']), rescope=True)

    def test_nonce_digest_source_apk_and_snapshot_mismatch_reject(self):
        self.rejected(lambda r:r['cases'][0]['eventTransfer']['events'][0]['receipt'].update(payloadSha256='0'*64))
        self.rejected(lambda r:r['cases'][0].update(runNonce='f'*32))
        self.rejected(lambda r:r['cases'][0]['observations']['ready'].update(draft='altered'))
        self.rejected(lambda r:r['buildIdentity'].update(apkSha256='0'*64))
        self.rejected(lambda r:r['cases'][0]['fixtureRequests'].append(r['cases'][0]['fixtureRequests'][0]))
        self.rejected(lambda r:r['cases'][0]['firstTapReadiness'].update(tapInvocations=2))
        self.rejected(lambda r:r['cases'][0]['headerReadiness'].update(preparationBudgetMs=30000))

    def test_dispatcher_requires_explicit_version_and_keeps_v1_callable(self):
        args = (None, None, None, None, None, None)
        with self.assertRaises(TypeError): runner.run_versioned(*args)
        for version in (None, True, '2', 2.0, 0, 3):
            with self.assertRaises(ValueError): runner.run_versioned(*args, navigation_contract=version)
        with patch.object(runner, 'run', return_value='legacy') as old:
            self.assertEqual(runner.run_versioned(*args, navigation_contract=1), 'legacy'); old.assert_called_once_with(*args)
        fake=types.ModuleType('run_chrome_collapse_v2'); fake.run_v2=lambda *a:('v2', a)
        with patch.dict(sys.modules, {'run_chrome_collapse_v2': fake}), patch.object(runner, 'run', side_effect=AssertionError('legacy dispatch')):
            self.assertEqual(runner.run_versioned(*args, navigation_contract=2), ('v2', args))

    def test_cancel_uses_only_the_fresh_post_snapshot_geometry_with_one_original_budget(self):
        sample = self.report['cases'][0]['observations']['initialAddress']
        fresh = v2.inspect_ui(xml_for('initialAddress'), 'initialAddress', sample['environmentName'])
        stale = copy.deepcopy(fresh)
        stale['controls'][0].update(bounds=[100, 1100, 300, 1230], point=[200, 1165])
        order, emissions, deadlines = [], [], []
        def observe(phase, **kwargs):
            order.append('fresh' if 'address_sample' in kwargs else 'initial')
            self.assertEqual(phase, 'initialAddress'); deadlines.append(kwargs['deadline'])
            if 'address_sample' in kwargs:
                self.assertIs(kwargs['address_sample'], sample)
                return fresh
            return stale
        def snapshot(phase):
            order.append('snapshot'); self.assertEqual(phase, 'initialAddress')
            return sample
        def tap(*args, **kwargs):
            order.append('tap'); emissions.append((args, kwargs))
        with patch.object(current_runner.time, 'monotonic', side_effect=(10, 17)):
            current_runner.cancel_address_once(observe=observe, snapshot=snapshot, tap=tap,
                                               opened='initialAddress', returned='initialChat')
        self.assertEqual(order, ['initial', 'snapshot', 'fresh', 'tap'])
        self.assertEqual(deadlines, [30, 30])
        self.assertEqual(emissions, [(('initialAddress', 'initialChat', 'cancel'),
                                     dict(point=[200, 665], bounds=[100, 600, 300, 730]))])

    def test_cancel_refuses_stale_xml_expired_budget_and_non_owned_native_dialog_before_input(self):
        original = self.report['cases'][0]['observations']['initialAddress']
        fresh = v2.inspect_ui(xml_for('initialAddress'), 'initialAddress', original['environmentName'])
        for mutation in ('stale-geometry', 'expired-budget', 'owner', 'hidden', 'editor-focus', 'window-token', 'text', 'disabled'):
            sample = copy.deepcopy(original); parsed = copy.deepcopy(fresh); emissions = []
            if mutation == 'stale-geometry': parsed['controls'][0].update(bounds=[100, 1100, 300, 1230], point=[200, 1165])
            fields = {'owner': ('ownerActivity', False), 'hidden': ('showing', False),
                      'editor-focus': ('editorFocused', False), 'window-token': ('sameWindow', False),
                      'text': ('editorText', 'y'), 'disabled': ('cancelEnabled', False)}
            if mutation in fields:
                field, value = fields[mutation]; sample['addressDialog'][field] = value
            calls = []
            def observe(phase, **kwargs):
                calls.append(kwargs['deadline'])
                return parsed
            with self.subTest(mutation=mutation), patch.object(current_runner.time, 'monotonic', side_effect=(10, 31)), self.assertRaises((AssertionError, TimeoutError)):
                current_runner.cancel_address_once(observe=observe, snapshot=lambda phase: sample,
                    tap=lambda *a, **k: emissions.append((a, k)), opened='initialAddress', returned='initialChat')
            self.assertEqual(emissions, []); self.assertEqual(calls, [30, 30])

    def test_workload_runs_shared_reader_before_cancel_and_always_keeps_partial_originals(self):
        source = (ROOT/'tests/gecko/run_chrome_collapse_v2.py').read_text()
        tree = ast.parse(source)
        functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        address = ast.unparse(functions['address'])
        self.assertEqual(address.count('cancel_address_once('), 1)
        self.assertNotIn("dialog['controls']", address)
        observation = ast.unparse(functions['ui'])
        self.assertIn('if deadline is None:', observation)
        self.assertIn('address_cancel(address_sample, parsed)', observation)
        self.assertIn('xml = capture.read(deadline=deadline)', observation)
        self.assertIn("attempt.update(status='not-ready', error=repr(error))", observation)
        self.assertIn("raw_file('chrome-v2-'", observation)
        guarded = [n for n in ast.walk(functions['run_v2']) if isinstance(n, ast.Try)
                   and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == 'partial'
                           for statement in n.finalbody for child in ast.walk(statement))]
        self.assertEqual(len(guarded), 1)
        actual = ast.unparse(guarded[0])
        self.assertLess(actual.index("event('ready')"), actual.index("address('ready'"))
        self.assertIn('events=transfer.records', ast.unparse(functions['partial']))
        self.assertIn('releaseAcceptance=False', ast.unparse(functions['partial']))
        self.assertIn('actualAndroidInputs=inputs', ast.unparse(functions['partial']))

    def failed_driver(self, early=False):
        """Actual Python flow, declared fake device edges; never Android evidence."""
        case=self.report['cases'][0];build=self.report['buildIdentity'];nonce=case['runNonce']
        rows=case['eventTransfer']['events'][:2]
        payloads={transport.event_uri(row['receipt']):row['rawUtf8'].encode() for row in rows}
        original_output=subprocess.check_output;commands=[];published=1
        stale=xml_for('initialAddress').replace('[100,600][300,730]','[100,1100][300,1230]')
        state='topResumedActivity=ActivityRecord{abc u0 '+v2.ACTIVITY+' t8}\n'
        class Capture:
            def __init__(self,**kwargs):
                self.diagnostics=kwargs['diagnostics'];self.nonce='f'*32;self.count=0
                if not early:self.save()
            def save(self):
                self.diagnostics.write_text(json.dumps(dict(sourceCommit=build['sourceCommit'],runNonce=self.nonce,attemptCount=self.count))+'\n')
            def read(self,deadline):
                self.count+=1
                self.save()
                if self.count==1:return stale
                raise TimeoutError('controlled fresh native observation failure')
        def output(command,**kwargs):
            if command==['git','rev-parse','HEAD^{tree}']:return build['sourceTree']+'\n'
            if command==['host-only-adb','-s','host-only-serial','shell','dumpsys','activity','activities']:return state.encode()
            return original_output(command,**kwargs)
        def adb(*parts):
            nonlocal published
            commands.append(parts)
            if parts[:3]==('exec-out','content','read'):return json.dumps(build)
            if parts==('shell','am','get-current-user'):return '0\n'
            if parts[:3]==('shell','am','broadcast'):
                self.assertEqual(parts[-1],'initialAddress');published=2
            if parts[:2]==('logcat','-d'):return '\n'.join(json.dumps(row['receipt']) for row in rows[:published])
            return ''
        first=types.ModuleType('chrome_first_tap_readiness')
        def first_tap(**kwargs):
            if early:raise TimeoutError('controlled first tap readiness failure')
            return dict(point=case['observations']['ready']['compactTap'],hostOnly=True)
        first.first_tap_once=first_tap
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with patch.object(current_runner,'expected_build',return_value=build),\
                 patch.object(current_runner,'verify_installed',side_effect=lambda actual,expected:self.assertEqual(actual,expected)),\
                 patch.object(current_runner,'resume_transport',return_value=['host-only-adb','-s','host-only-serial']),\
                 patch.object(current_runner,'UiVisualCapture',Capture),\
                 patch.object(current_runner.uuid,'uuid4',return_value=types.SimpleNamespace(hex=nonce)),\
                 patch.object(subprocess,'check_output',side_effect=output),patch.dict(sys.modules,{'chrome_first_tap_readiness':first}),\
                 self.assertRaisesRegex(TimeoutError,'controlled first tap readiness failure' if early else 'controlled fresh native observation failure'):
                current_runner.run_v2(adb,lambda *parts:payloads[parts[-1]],build['sourceCommit'],[],out,lambda component:None)
            partial=json.loads((out/('chrome-v2-'+nonce+'-partial.json')).read_bytes())
            self.assertFalse(partial['caseCompleted']);self.assertFalse(partial['releaseAcceptance'])
            self.assertEqual(partial['eventTransfer']['events'],rows[:1] if early else rows)
            self.assertEqual(list(partial['observations']),['ready'] if early else ['ready','initialAddress'])
            self.assertEqual([row['label'] for row in partial['actualAndroidInputs']],[] if early else ['initialAddress'])
            self.assertFalse(any(parts[:3]==('shell','input','tap') for parts in commands))
            if early:
                self.assertIsNone(partial['captureFile']);self.assertEqual(partial['captureStatus'],'not-started')
                self.assertEqual(partial['captureAttemptCount'],0);self.assertIsNone(partial['firstTapReadiness'])
                self.assertIn('FileNotFoundError',partial['captureError']);self.assertEqual(partial['uiAttempts'],[])
                self.assertEqual(list(out.glob('chrome-v2-ui-capture-*')),[])
                import run_chrome_collapse_diagnostic as diagnostic
                destination=out/'diagnostic';destination.mkdir()
                copied=diagnostic.collect_v2_diagnostics(out,destination,build['sourceCommit'],build)
                self.assertEqual(len(copied),1)
                self.assertEqual((destination/copied[0]['name']).read_bytes(),(out/copied[0]['name']).read_bytes())
            else:
                self.assertEqual(partial['firstTapReadiness']['point'],case['observations']['ready']['compactTap'])
                self.assertEqual(partial['captureStatus'],'available');self.assertEqual(partial['captureAttemptCount'],2)
                self.assertEqual((out/partial['uiAttempts'][0]['xml']['name']).read_bytes(),stale.encode())
            self.assertEqual(len(partial['rawFiles']),0 if early else 2)
            for record in partial['rawFiles']:
                raw=(out/record['name']).read_bytes()
                self.assertEqual((record['bytes'],record['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()))
            self.assertIn('controlled first tap readiness failure' if early else 'controlled fresh native observation failure',partial['error'])

    def test_actual_runner_failure_keeps_owned_event_bytes_and_emitted_input_prefix_without_cancel(self):
        self.failed_driver()

    def test_actual_runner_failure_before_capture_keeps_original_ready_event_without_inventing_capture_file(self):
        self.failed_driver(early=True)


if __name__ == '__main__': unittest.main()
