"""Settings capture observation/scroll rejection tests; no Android execution claim."""
import copy
import importlib
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
capture = importlib.import_module('capture_settings_workspace')
glass = importlib.import_module('capture_glass_navigation')


def node(parent, text, box, *, kind='android.widget.TextView', description='', clickable=False, selected=False):
    return ET.SubElement(parent, 'node', {'package': capture.PACKAGE, 'text': text, 'content-desc': description,
        'class': kind, 'bounds': '[{},{}][{},{}]'.format(*box), 'visible-to-user': 'true',
        'clickable': str(clickable).lower(), 'enabled': 'true', 'selected': str(selected).lower()})


def hierarchy(*, offset=0, last=False, notice=False):
    root = ET.Element('hierarchy')
    node(root, '设置', (66,102,930,222), description=capture.TITLE)
    node(root, capture.SUMMARY, (66,231,1000,285))
    node(root, '', (1032,111,1182,261), kind='android.widget.Button', description=capture.SEARCH, clickable=True)
    scroll = node(root, '', (0,400,1236,2604), kind='android.widget.ScrollView')
    scroll.set('scrollable', 'true')
    if notice:
        feedback = node(root, '', (24,310,1212,390), kind='android.widget.LinearLayout')
        node(feedback, '尚未连接', (48,315,950,375))
        node(feedback, '×', (1020,310,1180,390), kind='android.widget.Button', description='关闭提示', clickable=True)
    titles = capture.ENTRY_TITLES[-4:] if last else capture.ENTRY_TITLES[:5]
    start = 1100 if last else 470
    for index, title in enumerate(titles):
        top = start + index*250 + offset
        row = node(scroll, '', (60,top,1176,top+220), kind='android.widget.LinearLayout', clickable=True)
        labels = node(row, '', (264,top+30,1050,top+190), kind='android.widget.LinearLayout')
        node(labels, title, (264,top+30,1050,top+110))
        node(labels, '查看支持的功能' if title == capture.ENTRY_TITLES[-1] else '当前实际摘要',
             (264,top+120,1050,top+180))
    nav = node(root, '', (36,2331,1200,2568), kind='android.widget.LinearLayout')
    boxes = ((51,2358,277,2562),(277,2358,504,2562),(504,2358,731,2562),
             (731,2358,958,2562),(958,2358,1185,2562))
    for label, box in zip(capture.LABELS, boxes):
        node(nav, label, box, kind='android.widget.Button', description=label, clickable=True, selected=label == '设置')
    return root


def observe(root):
    return capture.settings_observation(ET.tostring(root, encoding='unicode'), glass.workspace_navigation_geometry)


def successful_result():
    return dict(errors=[], restoredDefaultFont=True, returnedToEnvironment=True,
        embeddedMainActivityObservation=dict(activity=dict(actualProductionActivity=capture.MAIN_ACTIVITY),
            settingsObservation=dict(selectedNavigation='设置')),
        scenes=[dict(name=name, fontScale=scale, activity=dict(actualProductionActivity=capture.ACTIVITY))
                for name, scale in capture.SCENES.items()],
        largeFontFullyVisibleEntries=list(capture.ENTRY_TITLES),
        bottomScrollPreview=dict(status='captured', fullyVisible=True, observedRowsMovedUp=True,
            additionalSwipeStationary=True, inputCount=3, feedbackDismissalsDuringScroll=0))


class SettingsWorkspaceObservationTests(unittest.TestCase):
    def test_actual_route_header_actionable_rows_and_inline_notice_are_measured(self):
        value = observe(hierarchy(notice=True))
        self.assertEqual(value['selectedNavigation'], '设置')
        self.assertEqual(value['fullyVisibleEntries'], list(capture.ENTRY_TITLES[:5]))
        self.assertEqual(value['feedback']['placement'], 'above-scroll')
        self.assertEqual(value['safeViewportBounds'], [24,424,1212,2307])
        self.assertEqual(value['navigationBounds'], [36,2331,1200,2568])
        self.assertFalse(value['glyphFitVerified'])
        self.assertFalse(value['lastEntryFullyVisible'])

    def test_header_search_and_five_nav_reject_missing_duplicate_foreign_hidden_and_disabled(self):
        for description in (capture.TITLE, capture.SEARCH, '设置'):
            for fault in ('missing', 'duplicate', 'foreign', 'hidden', 'disabled-or-wrong-title'):
                with self.subTest(description=description, fault=fault):
                    root = hierarchy()
                    target = next(n for n in root.iter('node') if n.get('content-desc') == description)
                    parent = next(n for n in root.iter() if target in n)
                    if fault == 'missing':
                        parent.remove(target)
                    elif fault == 'duplicate':
                        parent.append(copy.deepcopy(target))
                    elif fault == 'foreign':
                        target.set('package', 'other.package')
                    elif fault == 'hidden':
                        target.set('visible-to-user', 'false')
                    elif description == capture.TITLE:
                        target.set('text', '旧设置页')
                    else:
                        target.set('enabled', 'false')
                    self.assertIsNone(observe(root))
        root = hierarchy()
        next(n for n in root.iter('node') if n.get('content-desc') == '设置').set('selected', 'false')
        self.assertIsNone(observe(root))

    def test_rows_require_real_unique_enabled_clickable_ancestor_and_full_text(self):
        for fault in ('duplicate', 'disabled', 'not-actionable'):
            with self.subTest(fault=fault):
                root = hierarchy()
                title = next(n for n in root.iter('node') if n.get('text') == capture.ENTRY_TITLES[0])
                parent = next(n for n in root.iter() if title in n)
                row = next(n for n in root.iter() if parent in n)
                if fault == 'duplicate':
                    parent.append(copy.deepcopy(title))
                elif fault == 'disabled':
                    row.set('enabled', 'false')
                else:
                    row.set('clickable', 'false')
                self.assertIsNone(observe(root))
        root = hierarchy(last=True)
        value = observe(root)
        self.assertTrue(value['lastEntryFullyVisible'])
        title = next(n for n in root.iter('node') if n.get('text') == capture.ENTRY_TITLES[-1])
        parent = next(n for n in root.iter() if title in n)
        parent.remove(parent[-1])
        self.assertFalse(observe(root)['lastEntryFullyVisible'])

    def test_last_row_must_fit_above_nav_with_a_real_touch_target(self):
        self.assertFalse(observe(hierarchy(last=True, offset=250))['lastEntryFullyVisible'])
        root = hierarchy(last=True)
        last = next(n for n in root.iter('node') if n.get('text') == capture.ENTRY_TITLES[-1])
        parent = next(n for n in root.iter() if last in n)
        row = next(n for n in root.iter() if parent in n)
        row.set('bounds', '[60,1850][1176,1980]')
        value = observe(root)
        self.assertFalse(value['lastEntry']['minimumTouchTarget'])
        self.assertFalse(value['lastEntryFullyVisible'])
        search = next(n for n in root.iter('node') if n.get('content-desc') == capture.SEARCH)
        search.set('bounds', '[1032,111][1182,250]')
        self.assertIsNone(observe(root))

    def test_scroll_uses_observed_safe_viewport_and_requires_real_coordinate_change(self):
        before, after = observe(hierarchy(last=True)), observe(hierarchy(last=True, offset=-200))
        plan = capture.scroll_plan(before)
        self.assertGreater(plan['start'][1], plan['end'][1])
        for x, y in (plan['start'], plan['end']):
            left, top, right, bottom = before['safeViewportBounds']
            self.assertTrue(left < x < right and top < y < bottom)
        self.assertTrue(capture.rows_moved_up(before, after))
        self.assertFalse(capture.rows_stationary(before, after))
        changed_text = copy.deepcopy(before)
        changed_text['visibleRows'][0]['details'][0]['text'] = '仅文字计时变化'
        self.assertFalse(capture.rows_moved_up(before, changed_text))
        self.assertTrue(capture.rows_stationary(before, changed_text))
        before['scrollable'] = False
        with self.assertRaises(ValueError):
            capture.scroll_plan(before)

    def test_resumed_component_requires_exact_production_activity(self):
        raw = ('topResumedActivity=ActivityRecord{abc u0 ' + capture.ACTIVITY + ' t8}').encode()
        self.assertEqual(capture.activity_observation(raw, capture.ACTIVITY)['actualProductionActivity'], capture.ACTIVITY)
        for wrong in (capture.MAIN_ACTIVITY, capture.ACTIVITY + 'Preview', 'other/' + capture.ACTIVITY):
            value = raw.replace(capture.ACTIVITY.encode(), wrong.encode())
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                capture.activity_observation(value, capture.ACTIVITY)

    def test_completion_cannot_claim_no_input_visibility_as_real_scrolling(self):
        self.assertTrue(capture.complete(successful_result()))
        for key, values in {
                'inputCount': (0, 1, True, capture.MAX_SCROLLS+1),
                'observedRowsMovedUp': (False,), 'additionalSwipeStationary': (False,),
                'fullyVisible': (False,), 'feedbackDismissalsDuringScroll': (1,)}.items():
            for value in values:
                changed = successful_result(); changed['bottomScrollPreview'][key] = value
                with self.subTest(key=key, value=value):
                    self.assertFalse(capture.complete(changed))

    def test_completion_requires_every_entry_both_actual_routes_all_scales_and_restore(self):
        for title in capture.ENTRY_TITLES:
            changed = successful_result(); changed['largeFontFullyVisibleEntries'].remove(title)
            self.assertFalse(capture.complete(changed))
        variants = []
        changed = successful_result(); changed['restoredDefaultFont'] = False; variants.append(changed)
        changed = successful_result(); changed['returnedToEnvironment'] = False; variants.append(changed)
        changed = successful_result(); changed['embeddedMainActivityObservation'] = {}; variants.append(changed)
        changed = successful_result(); changed['embeddedMainActivityObservation']['settingsObservation'] = None; variants.append(changed)
        changed = successful_result(); changed['scenes'][1]['fontScale'] = 1.0; variants.append(changed)
        changed = successful_result(); changed['scenes'][0]['activity']['actualProductionActivity'] = capture.MAIN_ACTIVITY; variants.append(changed)
        changed = successful_result(); changed['scenes'].pop(); variants.append(changed)
        changed = successful_result(); changed['errors'].append({'error':'actual failure'}); variants.append(changed)
        for changed in variants:
            self.assertFalse(capture.complete(changed))

    def test_existing_fixture_owner_identity_is_required_before_settings_launch(self):
        identity = dict(sourceCommit='a'*40, sourceTree='b'*40, apkSha256='c'*64)
        report = dict(buildIdentity=identity, runNonce='d'*32,
            environmentWorkspacePreview=dict(identity, status='captured', seededEnvironmentCount=5,
                restoredDefaultFont=True, runNonce='d'*32, restoredHierarchy={'file':'owned.xml'},
                restoredActivity={'file':'owned-activity.txt'}))
        self.assertFalse(capture.inherited_fixture(report)['resetPerformed'])
        for key, value in [('sourceCommit','e'*40),('sourceTree','e'*40),('apkSha256','e'*64),
                ('runNonce','e'*32),('seededEnvironmentCount',4),('status','failed'),('restoredDefaultFont',False)]:
            changed = copy.deepcopy(report); changed['environmentWorkspacePreview'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                capture.inherited_fixture(changed)


if __name__ == '__main__':
    unittest.main()
