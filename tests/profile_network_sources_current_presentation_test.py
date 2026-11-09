"""Real failed-cohort UI selectors; the original route assertions stay intact."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/network-sources-ui214-drawable-inactive.xml'
SPEC = importlib.util.spec_from_file_location('actual_network_inactive_presentation',
    ROOT / 'tests/gecko/network_inactive_label46.py')
PRESENTATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRESENTATION)


def card(tree, name='UI Window'):
    return next(node for node in tree.iter('node')
                if node.get('content-desc', '').startswith(name + '，'))


def editor(tree):
    return next(node for node in tree.iter('node')
                if node.get('content-desc') == '编辑网络 · UI Window')


def status(tree):
    return next(node for node in card(tree).iter('node') if node.get('text') == '未连接')


def remove(tree, node):
    next(parent for parent in tree.iter() if node in list(parent)).remove(node)


class CurrentNetworkPresentation(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.tree = ET.fromstring(self.raw)

    def accepted(self, tree):
        return PRESENTATION.visible_inactive_route(tree, 'UI Window')

    def test_original_failed_hierarchy_is_verified_and_read_without_rewriting(self):
        proof = json.loads(FIXTURE.with_suffix('.provenance.json').read_text())
        self.assertEqual((proof['runId'], proof['runAttempt'], proof['jobId'], proof['artifactId']),
                         ('42602397050', '1', 129124178920, 13668228869))
        self.assertEqual(proof['sourceCommit'], 'c244835a4c1e3629909b2b1ce132ca5987a97d9a')
        self.assertTrue(proof['failedCohort'])
        self.assertFalse(proof['releaseAcceptance'])
        self.assertEqual(proof['touchUiChecksCompleted'], 0)
        self.assertEqual(len(self.raw), 18600)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
                         '5f4e6939394798d27dcf5dc64394c88f47333244e31dbca8b2389805227f3bf8')
        self.assertEqual(len(self.raw), proof['bytes'])
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), proof['sha256'])
        self.assertEqual(hashlib.sha1(b'blob ' + str(len(self.raw)).encode() + b'\0' + self.raw).hexdigest(), proof['gitBlob'])
        self.assertEqual(editor(self.tree).get('text'), '编辑')
        self.assertEqual(status(self.tree).get('content-desc'), '网络状态：未连接')
        before = ET.tostring(self.tree)
        self.assertFalse(PRESENTATION._legacy_inactive_route(self.tree, 'UI Window'))
        self.assertTrue(self.accepted(self.tree))
        self.assertEqual(ET.tostring(self.tree), before)
        self.assertEqual(FIXTURE.read_bytes(), self.raw)

    def test_exact_selector_inverse_preserves_complete_original_assertion_source(self):
        original = PRESENTATION.ORIGINAL_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), PRESENTATION.ORIGINAL_SHA256)
        before = PRESENTATION.port_original_source(original)
        current = PRESENTATION.port_current_presentation(before)
        self.assertEqual(current.count(PRESENTATION.PRESENTED_CARD_CONTEXT), 1)
        self.assertEqual(current.count(PRESENTATION.PRESENTED_LABEL_CONTEXT), 1)
        restored = current.replace(PRESENTATION.PRESENTED_CARD_CONTEXT, PRESENTATION.CARD_CONTEXT, 1)
        restored = restored.replace(PRESENTATION.PRESENTED_LABEL_CONTEXT, PRESENTATION.LABEL_CONTEXT, 1)
        self.assertEqual(restored, before)
        self.assertEqual(restored.replace(PRESENTATION.CURRENT_CONTEXT, PRESENTATION.ORIGINAL_CONTEXT, 1), original)
        for changed in (before + b'\n', before.replace(PRESENTATION.CARD_CONTEXT, b'', 1),
                        before.replace(PRESENTATION.LABEL_CONTEXT, b'', 1), current, bytearray(before)):
            with self.subTest(kind=type(changed).__name__), self.assertRaises(ValueError):
                PRESENTATION.port_current_presentation(changed)

    def test_named_editor_is_unique_enabled_clickable_visible_and_in_its_actual_card(self):
        for key, value in [('content-desc', '编辑网络 · Other window'), ('content-desc', ''),
                           ('text', '删除'), ('class', 'android.widget.TextView'),
                           ('enabled', 'false'), ('clickable', 'false'),
                           ('bounds', '[0,0][0,0]'), ('bounds', '[0,0][20,20]'),
                           ('visible-to-user', 'false')]:
            tree = copy.deepcopy(self.tree); editor(tree).set(key, value)
            with self.subTest(attribute=key, value=value):
                self.assertFalse(self.accepted(tree))
        tree = copy.deepcopy(self.tree); card(tree).append(copy.deepcopy(editor(tree)))
        self.assertFalse(self.accepted(tree))
        tree = copy.deepcopy(self.tree); node = editor(tree); remove(tree, node); card(tree, '默认环境').append(node)
        self.assertFalse(self.accepted(tree))

    def test_owner_and_title_cannot_be_borrowed_from_another_environment(self):
        for mutation in ('missing-description', 'wrong-environment', 'duplicate-card', 'duplicate-title', 'hidden-card'):
            tree = copy.deepcopy(self.tree); owner = card(tree)
            if mutation == 'missing-description': owner.set('content-desc', '')
            elif mutation == 'wrong-environment': owner.set('content-desc', 'Other window，未连接，查看窗口详情')
            elif mutation == 'duplicate-card': tree.append(copy.deepcopy(owner))
            elif mutation == 'duplicate-title': owner.append(copy.deepcopy(next(n for n in owner.iter('node') if n.get('text') == 'UI Window')))
            else: owner.set('bounds', '[0,0][0,0]')
            with self.subTest(mutation=mutation):
                self.assertFalse(self.accepted(tree))
        self.assertFalse(PRESENTATION.visible_inactive_route(self.tree, 'Other window'))

    def test_actual_drawable_status_keeps_identity_count_visibility_and_readonly_checks(self):
        for key, value in [('text', '已连接'), ('text', '连接中'), ('content-desc', ''),
                           ('content-desc', '网络状态：已连接'), ('class', 'android.widget.Button'),
                           ('enabled', 'false'), ('clickable', 'true'), ('bounds', '[0,0][0,0]'),
                           ('bounds', '[0,0][20,20]'), ('visible-to-user', 'false')]:
            tree = copy.deepcopy(self.tree); status(tree).set(key, value)
            with self.subTest(attribute=key, value=value):
                self.assertFalse(self.accepted(tree))
        for mutation in ('missing', 'duplicate', 'other-card', 'duplicate-legacy-label'):
            tree = copy.deepcopy(self.tree); node = status(tree); owner = card(tree)
            if mutation == 'missing': remove(tree, node)
            elif mutation == 'duplicate': owner.append(copy.deepcopy(node))
            elif mutation == 'other-card': remove(tree, node); card(tree, '默认环境').append(node)
            else:
                duplicate = copy.deepcopy(node); duplicate.set('text', '● 未连接'); duplicate.set('content-desc', '')
                owner.append(duplicate)
            with self.subTest(mutation=mutation):
                self.assertFalse(self.accepted(tree))

    def test_original_absent_route_and_no_fabricated_running_stage_assertions_still_run(self):
        for mutation in ('missing', 'duplicate', 'other-card', 'hidden', 'clickable'):
            tree = copy.deepcopy(self.tree); owner = card(tree)
            node = next(n for n in owner.iter('node') if n.get('text') == '当前没有运行线路')
            if mutation == 'missing': remove(tree, node)
            elif mutation == 'duplicate': owner.append(copy.deepcopy(node))
            elif mutation == 'other-card': remove(tree, node); card(tree, '默认环境').append(node)
            elif mutation == 'hidden': node.set('bounds', '[0,0][0,0]')
            else: node.set('clickable', 'true')
            with self.subTest(mutation=mutation):
                self.assertFalse(self.accepted(tree))
        for label in ('入口', '固定出口', '目的地', '运行线路 · 自动优选'):
            tree = copy.deepcopy(self.tree)
            card(tree).append(ET.Element('node', {'text': label, 'class': 'android.widget.TextView',
                                                 'clickable': 'false', 'bounds': '[36,377][200,398]'}))
            with self.subTest(forbidden=label):
                self.assertFalse(self.accepted(tree))


if __name__ == '__main__':
    unittest.main(verbosity=2)
