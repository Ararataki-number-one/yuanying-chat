"""Current raw card grammar versus original failed Android cohort evidence.

These controls qualify only the read-only UI predicate, never source-library
activation, the complete86 Android checks, network or a future CI run.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/network-sources-card-v2-06-actual.xml'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


V2 = module('current_network_card_v2', ROOT / 'tests/gecko/network_inactive_card_v2.py')
V1 = module('original_network_card_v1', ROOT / 'tests/gecko/network_inactive_label46.py')
HISTORY = module('current_network_runner_comparison', ROOT / 'tests/gecko/network_sources_ui_history.py')


def card(tree, name='UI Window'):
    return next(n for n in tree.iter('node') if n.get('content-desc', '').startswith(name + '，')
                and n.get('content-desc', '').endswith('，查看窗口详情'))


def parent(tree, node):
    return next(p for p in tree.iter() if node in list(p))


class NetworkSourcesCardV2Test(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.tree = ET.fromstring(self.raw)

    def test_original06_raw_xml_and_state_are_inactive_failed_cohort_not_activation(self):
        self.assertEqual(len(self.raw), 17946)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), 'bac01eebfe041fd1c07053d0e4b7d6685e5ed2348dfeb6fea73d4e2082dde3e0')
        proof = json.loads((FIXTURE.parent / 'network-sources-card-v2-06.provenance.json').read_text())
        self.assertEqual((proof['sourceCommit'], proof['run'], proof['runAttempt'], proof['job']),
                         ('06a802663075664b75aa9d19184d9c02b6bab7c9', 42492356825, 1, 128777268095))
        self.assertEqual(proof['cohortStatus'], 'failed-before-touch-scenarios')
        self.assertFalse(proof['actualRouteApplication'])
        for name, identity in proof['files'].items():
            raw = (FIXTURE.parent / name).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (identity['bytes'], identity['sha256']))
        state = json.loads((FIXTURE.parent / 'network-sources-card-v2-06-state.json').read_text())
        self.assertTrue(state['ready'])
        self.assertEqual((state['stage'], state['checkCount']), ('window-tab', 8))
        self.assertEqual(state['checks'][7], {'name': 'Saved source settings alone do not create a running route summary', 'pass': True})
        original = ET.tostring(self.tree)
        self.assertFalse(V1.visible_inactive_route(self.tree, 'UI Window'))
        self.assertTrue(V2.visible_inactive_route(self.tree, 'UI Window'))
        self.assertEqual(ET.tostring(self.tree), original)
        self.assertEqual(FIXTURE.read_bytes(), self.raw)

    def test_v1_and_v2_are_explicit_mutually_exclusive_not_a_label_union(self):
        old = ET.fromstring((ROOT / 'tests/fixtures/network-sources-ui46-actual-inactive.xml').read_bytes())
        self.assertTrue(V1.visible_inactive_route(old, 'UI Window'))
        self.assertFalse(V2.visible_inactive_route(old, 'UI Window'))
        self.assertFalse(V2.visible_inactive_route(self.tree, '默认环境'))
        self.assertFalse(V2.visible_inactive_route(self.tree, 'missing'))
        for old_status in ('● 未连接', '● 未运行', '已连接', '等待应用', '未配置'):
            tree = copy.deepcopy(self.tree)
            node = next(n for n in card(tree).iter('node') if n.get('text') == '未连接')
            node.set('text', old_status)
            node.set('content-desc', '网络状态：' + old_status)
            with self.subTest(status=old_status):
                self.assertFalse(V2.visible_inactive_route(tree, 'UI Window'))

    def test_each_exact_status_is_unique_readonly_visible_and_same_card(self):
        for text in ('未连接', '当前没有运行线路'):
            for mutation in ('missing', 'duplicate', 'other-card', 'zero-bounds', 'clipped', 'hidden-parent', 'clickable', 'foreign-package', 'wrong-desc'):
                tree = copy.deepcopy(self.tree)
                owner = card(tree)
                node = next(n for n in owner.iter('node') if n.get('text') == text)
                p = parent(tree, node)
                if mutation == 'missing': p.remove(node)
                elif mutation == 'duplicate': p.append(copy.deepcopy(node))
                elif mutation == 'other-card': p.remove(node); card(tree, '默认环境').append(node)
                elif mutation == 'zero-bounds': node.set('bounds', '[0,0][0,0]')
                elif mutation == 'clipped': node.set('bounds', '[0,0][320,640]')
                elif mutation == 'hidden-parent': p.set('visible-to-user', 'false')
                elif mutation == 'clickable': node.set('clickable', 'true')
                elif mutation == 'foreign-package': node.set('package', 'another.app')
                elif mutation == 'wrong-desc': node.set('content-desc', 'unbound')
                with self.subTest(text=text, mutation=mutation):
                    self.assertFalse(V2.visible_inactive_route(tree, 'UI Window'))

    def test_edit_identity_card_identity_and_foreground_visibility_cannot_mix(self):
        for mutation in ('missing', 'duplicate', 'other-card', 'old-label', 'wrong-desc', 'wrong-class', 'disabled', 'clipped', 'wrong-card', 'duplicate-title'):
            tree = copy.deepcopy(self.tree)
            owner = card(tree)
            edit = next(n for n in owner.iter('node') if n.get('text') == '编辑')
            p = parent(tree, edit)
            if mutation == 'missing': p.remove(edit)
            elif mutation == 'duplicate': p.append(copy.deepcopy(edit))
            elif mutation == 'other-card': p.remove(edit); card(tree, '默认环境').append(edit)
            elif mutation == 'old-label': edit.set('text', '编辑网络')
            elif mutation == 'wrong-desc': edit.set('content-desc', '编辑网络 · 默认环境')
            elif mutation == 'wrong-class': edit.set('class', 'android.widget.TextView')
            elif mutation == 'disabled': edit.set('enabled', 'false')
            elif mutation == 'clipped': edit.set('bounds', '[0,0][320,640]')
            elif mutation == 'wrong-card': owner.set('content-desc', owner.get('content-desc').replace('UI Window', 'Other'))
            elif mutation == 'duplicate-title': owner.append(copy.deepcopy(next(n for n in owner.iter('node') if n.get('text') == 'UI Window')))
            with self.subTest(mutation=mutation):
                self.assertFalse(V2.visible_inactive_route(tree, 'UI Window'))

    def test_no_synthetic_running_route_or_pending_claim_is_accepted(self):
        for label in ('入口', '固定出口', '目的地', '运行线路 · 自动优选', '等待应用 · 保存的候选'):
            tree = copy.deepcopy(self.tree)
            node = copy.deepcopy(next(n for n in card(tree).iter('node') if n.get('text') == '当前没有运行线路'))
            node.set('text', label)
            card(tree).append(node)
            with self.subTest(label=label):
                self.assertFalse(V2.visible_inactive_route(tree, 'UI Window'))
        tree = copy.deepcopy(self.tree)
        owner = card(tree)
        owner.set('content-desc', owner.get('content-desc').replace('，查看窗口详情', '，入口：假的入口，查看窗口详情'))
        self.assertFalse(V2.visible_inactive_route(tree, 'UI Window'))

    def test_source_selection_is_whole_raw_and_unknown_or_weakened_source_rejects(self):
        V2.verify_source_contract()
        with tempfile.TemporaryDirectory(prefix='network-card-v2-source-') as temp:
            root = Path(temp)
            for name in V2.SOURCE_IDENTITIES:
                p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes((ROOT / name).read_bytes())
            V2.verify_source_contract(root)
            for name in V2.SOURCE_IDENTITIES:
                p = root / name; before = p.read_bytes()
                for changed in (before + b'\n', before[:-1], b'unknown'):
                    p.write_bytes(changed)
                    with self.subTest(source=name), self.assertRaises(ValueError):
                        V2.verify_source_contract(root)
                p.write_bytes(before)

    def test_only_one_import_changes_and_whole_runner_inverse_retains_every_budget(self):
        raw = (ROOT / 'tests/gecko/run_network_sources_ui.py').read_bytes()
        before = HISTORY.historical_runner_input(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), HISTORY.AFTER_SHA256)
        self.assertEqual(hashlib.sha256(before).hexdigest(), HISTORY.BEFORE_SHA256)
        self.assertEqual(before.replace(HISTORY.BEFORE_IMPORT, HISTORY.AFTER_IMPORT, 1), raw)
        self.assertEqual(len(raw), len(before))
        self.assertIn(b'from network_inactive_card_v2 import visible_inactive_route\n', raw)
        self.assertNotIn(b'network_sources_ui_history', raw)
        self.assertIn(b'no running core', raw)
        for variant in (raw + b'\n', raw.replace(HISTORY.AFTER_IMPORT, b''),
                        raw.replace(HISTORY.AFTER_IMPORT, HISTORY.AFTER_IMPORT * 2),
                        raw.replace(b'seconds=20)', b'seconds=21)', 1), bytearray(raw)):
            with self.subTest(kind=type(variant).__name__), self.assertRaises(ValueError):
                HISTORY.historical_runner_input(variant)
        self.assertEqual(HISTORY.historical_runner_input(before), before)


if __name__ == '__main__':
    unittest.main()
