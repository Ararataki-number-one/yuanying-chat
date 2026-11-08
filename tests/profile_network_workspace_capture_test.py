"""Network screenshot route/fixture rejection tests; no Android execution claim."""
import copy
import importlib
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
capture = importlib.import_module('capture_network_workspace')
glass = importlib.import_module('capture_glass_navigation')


def hierarchy(tab='环境网络'):
    root = ET.Element('hierarchy')
    def node(label, box, *, button=False, selected=False, **extra):
        fields = {'package': capture.PACKAGE, 'text': label, 'content-desc': label,
            'class': 'android.widget.Button' if button else 'android.widget.TextView',
            'bounds': '[{},{}][{},{}]'.format(*box), 'visible-to-user': 'true',
            'clickable': str(button).lower(), 'enabled': 'true', 'selected': str(selected).lower()}
        fields.update(extra)
        return ET.SubElement(root, 'node', fields)
    boxes = ((51,2358,277,2562),(277,2358,504,2562),(504,2358,731,2562),
             (731,2358,958,2562),(958,2358,1185,2562))
    for label, box in zip(capture.LABELS, boxes):
        node(label, box, button=True, selected=label == '网络')
    for index, label in enumerate(capture.TABS):
        node(label, (60+index*370,270,400+index*370,414), button=True, selected=label == tab)
    node(capture.SUMMARIES[tab], (60,180,1100,250))
    node('', (60,450,1176,2330), **{'class':'android.widget.ScrollView'})
    if tab == '环境网络':
        node('未配置', (950,500,1120,565), **{'content-desc':'网络状态：未配置'})
    return root


def xml(root):
    return ET.tostring(root, encoding='unicode')


def last_card_hierarchy(*, notice='above', card_top=1950, action='配置'):
    root = hierarchy()
    def node(parent, text, box, *, description='', kind='android.widget.TextView', clickable=False):
        return ET.SubElement(parent, 'node', {'package':capture.PACKAGE, 'class':kind, 'text':text,
            'content-desc':description, 'bounds':'[{},{}][{},{}]'.format(*box),
            'visible-to-user':'true', 'enabled':'true', 'clickable':str(clickable).lower()})
    nav = node(root, '', (36,2331,1200,2568), kind='android.widget.LinearLayout')
    for child in list(root)[:5]:
        root.remove(child); nav.append(child)
    scroll = next(n for n in root if n.get('class') == 'android.widget.ScrollView')
    scroll.set('bounds', '[0,650][1236,2604]'); scroll.set('scrollable', 'true')
    card = node(scroll, '', (60,card_top,1176,card_top+320), kind='android.widget.LinearLayout',
        description=capture.LAST_ENVIRONMENT+'，未配置，查看窗口详情')
    node(card, capture.LAST_ENVIRONMENT, (108,card_top+20,936,card_top+90))
    node(card, '未配置', (960,card_top+20,1140,card_top+90), description='网络状态：未配置')
    node(card, '选择连接方式', (108,card_top+110,816,card_top+180))
    node(card, action, (840,card_top+120,996,card_top+264), description='编辑网络 · '+capture.LAST_ENVIRONMENT,
         kind='android.widget.Button', clickable=True)
    node(card, '', (996,card_top+120,1140,card_top+264), description=capture.LAST_ENVIRONMENT+'的更多网络操作',
         kind='android.widget.Button', clickable=True)
    if notice:
        box = (60,450,1176,630) if notice == 'above' else (0,2120,1236,2301)
        feedback = node(root, '', box, description='网络连接提示', kind='android.widget.LinearLayout')
        node(feedback, '手机 VPN 未连接，已暂停网页联网', (box[0]+12,box[1]+12,box[2]-160,box[3]-12))
    return root


class NetworkHierarchyTests(unittest.TestCase):
    def observe(self, root, tab='环境网络'):
        return capture.network_observation(xml(root), tab, glass.workspace_navigation_geometry)

    def test_all_three_loaded_tabs_require_the_real_network_navigation(self):
        for tab in capture.TABS:
            with self.subTest(tab=tab):
                value = self.observe(hierarchy(tab), tab)
                self.assertEqual(value['selectedTab'], tab)
                self.assertEqual(value['summary'], capture.SUMMARIES[tab])
                self.assertTrue(value['geometry']['valid'])

    def test_missing_duplicate_hidden_disabled_foreign_and_wrongly_selected_tabs_fail(self):
        for change in ('missing', 'duplicate', 'hidden', 'disabled', 'foreign', 'selection', 'bounds'):
            with self.subTest(change=change):
                root = hierarchy()
                node = root[5]
                if change == 'missing': root.remove(node)
                elif change == 'duplicate': root.append(copy.deepcopy(node))
                else:
                    key, value = {'hidden':('visible-to-user','false'), 'disabled':('enabled','false'),
                        'foreign':('package','unrelated.app'), 'selection':('selected','false'),
                        'bounds':('bounds','[60,2700][400,2800]')}[change]
                    node.set(key, value)
                self.assertIsNone(self.observe(root))

    def test_wrong_workspace_route_or_two_selected_tabs_fail(self):
        root = hierarchy()
        root[3].set('selected', 'false');root[1].set('selected', 'true')
        self.assertIsNone(self.observe(root))
        root = hierarchy();root[6].set('selected', 'true')
        self.assertIsNone(self.observe(root))

    def test_old_eight_record_capture_or_unloaded_content_cannot_pass(self):
        for change in ('eight', 'connected-count', 'missing-scroll', 'loading'):
            with self.subTest(change=change):
                root = hierarchy()
                if change == 'missing-scroll': root.remove(root[9])
                elif change == 'loading':
                    node = copy.deepcopy(root[8]);node.set('text', '正在读取窗口网络…');root.append(node)
                else:
                    value = '8 个环境 · 0 个已连接' if change == 'eight' else '5 个环境 · 1 个已连接'
                    root[8].set('text', value);root[8].set('content-desc', value)
                self.assertIsNone(self.observe(root))

    def test_a_connected_badge_cannot_hide_behind_zero_count_text(self):
        root = hierarchy();root[-1].set('content-desc', '网络状态：已连接')
        self.assertIsNone(self.observe(root))
        root = hierarchy();root.remove(root[-1])
        self.assertIsNone(self.observe(root))


class NetworkLastCardTests(unittest.TestCase):
    def layout(self, root):
        return capture.last_card_layout(xml(root), glass.workspace_navigation_geometry)

    def test_inline_notice_does_not_shrink_the_bottom_safe_viewport(self):
        value = self.layout(last_card_hierarchy())
        self.assertEqual(value['feedback']['placement'], 'above-scroll')
        self.assertEqual(value['safeViewportBounds'], [24,674,1212,2307])
        self.assertTrue(value['fullyVisible'])
        self.assertIsNone(capture.scroll_plan(value))
        self.assertEqual(value['lastCard']['actions']['edit'][0]['text'], '配置')

    def test_bottom_notice_restricts_the_real_viewport_and_needs_a_bounded_upward_swipe(self):
        value = self.layout(last_card_hierarchy(notice='bottom'))
        self.assertFalse(value['fullyVisible'])
        self.assertEqual(value['feedback']['placement'], 'overlaps-scroll-bottom')
        self.assertEqual(value['safeViewportBounds'][3], 2096)
        plan = capture.scroll_plan(value)
        self.assertGreater(plan['start'][1], plan['end'][1])
        for x, y in (plan['start'], plan['end']):
            self.assertTrue(value['safeViewportBounds'][0] < x < value['safeViewportBounds'][2])
            self.assertTrue(value['safeViewportBounds'][1] < y < value['safeViewportBounds'][3])
        self.assertEqual(plan['durationMillis'], 420)

    def test_actual_row_coordinates_move_before_last_card_is_declared_visible(self):
        before = self.layout(last_card_hierarchy(notice='bottom'))
        after = self.layout(last_card_hierarchy(notice='bottom', card_top=1700))
        self.assertTrue(capture.rows_moved_up(before, after))
        self.assertTrue(after['fullyVisible'])
        clock_only = copy.deepcopy(before)
        clock_only['feedback']['texts'] = ['状态文字发生变化']
        self.assertFalse(capture.rows_moved_up(before, clock_only))

    def test_missing_details_or_clipped_action_cannot_pass_as_full_visibility(self):
        for broken in ('detail', 'action', 'small-target'):
            with self.subTest(broken=broken):
                root = last_card_hierarchy()
                card = next(n for n in root.iter('node') if n.get('content-desc','').startswith(capture.LAST_ENVIRONMENT+'，'))
                if broken == 'detail': card.remove(next(n for n in card if n.get('text') == '选择连接方式'))
                elif broken == 'action': card.remove(next(n for n in card if n.get('content-desc','').startswith('编辑网络 ·')))
                else: next(n for n in card if n.get('content-desc','').startswith('编辑网络 ·')).set('bounds','[840,2070][996,2200]')
                value = self.layout(root)
                self.assertFalse(value['fullyVisible'])
                with self.assertRaises(ValueError): capture.scroll_plan(value)

    def test_unscrollable_obscured_card_is_rejected_without_fake_movement(self):
        root = last_card_hierarchy(notice='bottom')
        next(n for n in root.iter('node') if n.get('class') == 'android.widget.ScrollView').set('scrollable','false')
        with self.assertRaises(ValueError): capture.scroll_plan(self.layout(root))


class NetworkFixtureAndCompletionTests(unittest.TestCase):
    def report(self):
        identity = dict(sourceCommit='a'*40, sourceTree='b'*40, apkSha256='c'*64)
        return dict(buildIdentity=identity, runNonce='d'*32, environmentWorkspacePreview=dict(
            identity, status='captured', runNonce='d'*32, seededEnvironmentCount=5,
            restoredDefaultFont=True, restoredHierarchy={'file':'environment-restored.xml'},
            restoredActivity={'file':'environment-restored-activity.txt'}))

    def test_reuses_the_completed_same_invocation_without_reset(self):
        value = capture.inherited_fixture(self.report())
        self.assertEqual(value['seededEnvironmentCount'], 5)
        self.assertFalse(value['resetPerformed'])

    def test_failed_foreign_or_incomplete_prior_fixture_is_rejected(self):
        cases = [('status','failed'),('seededEnvironmentCount',8),('restoredDefaultFont',False),
            ('runNonce','e'*32),('sourceCommit','f'*40),('sourceTree','f'*40),('apkSha256','f'*64),
            ('restoredHierarchy',{}),('restoredActivity',{})]
        for key, value in cases:
            with self.subTest(field=key), self.assertRaises(ValueError):
                report = self.report();report['environmentWorkspacePreview'][key] = value
                capture.inherited_fixture(report)

    def result(self):
        return dict(errors=[], restoredDefaultFont=True, returnedToNetwork=True,
            lastCardPreview=dict(status='captured', fullyVisible=True, feedbackDismissalsDuringScroll=0,
                inputCount=1, scrollRequired=True, observedRowsMovedUp=True),
            scenes=[dict(name=name, selectedTab=tab, fontScale=scale)
                    for name, (tab, scale) in capture.SCENES.items()])

    def test_only_all_required_distinct_scenes_with_restored_font_complete(self):
        self.assertTrue(capture.complete(self.result()))
        for change in ('missing', 'duplicate', 'wrong-font', 'wrong-tab', 'error', 'font', 'route'):
            with self.subTest(change=change):
                result = self.result()
                if change == 'missing': result['scenes'].pop()
                elif change == 'duplicate': result['scenes'][-1] = result['scenes'][0]
                elif change == 'wrong-font': result['scenes'][-1]['fontScale'] = 1.0
                elif change == 'wrong-tab': result['scenes'][0]['selectedTab'] = '入口'
                elif change == 'error': result['errors'].append({'phase':'capture'})
                elif change == 'font': result['restoredDefaultFont'] = False
                else: result['returnedToNetwork'] = False
                self.assertFalse(capture.complete(result))

    def test_final_card_scene_requires_actual_visibility_without_extra_notice_dismissal(self):
        for key, value in (('fullyVisible',False),('feedbackDismissalsDuringScroll',1),('inputCount',4),
                           ('observedRowsMovedUp',False),('status','failed')):
            with self.subTest(field=key):
                result = self.result(); result['lastCardPreview'][key] = value
                self.assertFalse(capture.complete(result))
        result = self.result()
        result['lastCardPreview'].update(inputCount=0, scrollRequired=False, observedRowsMovedUp=False,
            skipReason='The actual final card already fits')
        self.assertTrue(capture.complete(result))


if __name__ == '__main__':
    unittest.main()
