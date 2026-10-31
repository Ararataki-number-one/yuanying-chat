"""Exact inactive-label port controls; the S6 XML is a failed-cohort observation.

These offline checks do not replace fresh Android subscription UI acceptance.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SHIM_PATH = ROOT / 'tests/gecko/network_inactive_label46.py'
ACTUAL_XML = ROOT / 'tests/fixtures/network-sources-ui46-actual-inactive.xml'
RUNNER = ROOT / 'tests/gecko/run_network_sources_ui.py'
OLD_IMPORT = b'from network_ui_route_contract import visible_inactive_route, reveal_modal_action, clipboard_overlay_present\n'
NEW_IMPORT = b'from network_ui_route_contract import reveal_modal_action, clipboard_overlay_present\nfrom network_inactive_label46 import visible_inactive_route\n'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


SHIM = module('sources_ui46_exact_label_port', SHIM_PATH)
ORIGINAL = module('sources_ui46_original_immutable', SHIM.ORIGINAL_PATH)


def card(tree, environment='UI Window'):
    parents = {child: parent for parent in tree.iter() for child in parent}
    title = next(node for node in tree.iter('node') if node.get('text') == environment)
    value = parents[title]
    while not any(node.get('text') == '编辑网络' and node.get('class') == 'android.widget.Button'
                  for node in value.iter('node')):
        value = parents[value]
    return value


def text_node(value):
    return ET.Element('node', {'text': value, 'class': 'android.widget.TextView',
                              'clickable': 'false', 'bounds': '[10,10][100,50]'})


class NetworkSourcesInactiveLabel46(unittest.TestCase):
    def setUp(self):
        self.raw = ACTUAL_XML.read_bytes()
        self.tree = ET.fromstring(self.raw)

    def test_complete_original_module_and_runner_inverse_are_exact(self):
        original = SHIM.ORIGINAL_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), SHIM.ORIGINAL_SHA256)
        current = SHIM.port_original_source(original)
        self.assertEqual(current.count(SHIM.CURRENT_CONTEXT), 1)
        self.assertEqual(current.replace(SHIM.CURRENT_CONTEXT, SHIM.ORIGINAL_CONTEXT, 1), original)
        self.assertEqual(len(original), 6181)
        runner = RUNNER.read_bytes()
        self.assertEqual(runner.count(NEW_IMPORT), 1)
        self.assertEqual(hashlib.sha256(runner.replace(NEW_IMPORT, OLD_IMPORT, 1)).hexdigest(),
                         '11668477263a1427bc7affe3311c252dbe1ac0c70a89ab1d9e2f4b48dd63b9cf')

    def test_exact_failed_cohort_xml_passes_new_label_without_mutation(self):
        self.assertEqual(len(self.raw), 16105)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
                         '5e2f431f22f2cad2fdb6e6b469f3312a67ee9040d20d1374b4422ad7d1573cf6')
        provenance = json.loads(ACTUAL_XML.with_suffix('.provenance.json').read_text())
        self.assertEqual(provenance['sourceCommit'], 'affff9dbf5138527ec0c512522313d4b797b1bb1')
        self.assertEqual((provenance['run'], provenance['job']), (41180501269, 124479407569))
        self.assertEqual(provenance['artifactCommit'], '71901f39fe501beca97ceaa96122988e12d4413e')
        self.assertEqual(provenance['artifactTree'], '0ec4f0359bba6ba341e68c158f89d3fafc4d818c')
        self.assertEqual(provenance['artifactPath'], 'network-source-ui-latest.xml')
        self.assertEqual(provenance['bytes'], len(self.raw))
        self.assertEqual(provenance['sha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(provenance['gitBlob'], hashlib.sha1(b'blob ' + str(len(self.raw)).encode() + b'\0' + self.raw).hexdigest())
        before = ET.tostring(self.tree)
        self.assertFalse(ORIGINAL.visible_inactive_route(self.tree, 'UI Window'))
        self.assertTrue(SHIM.visible_inactive_route(self.tree, 'UI Window'))
        self.assertEqual(ET.tostring(self.tree), before)
        self.assertEqual(ACTUAL_XML.read_bytes(), self.raw)
        self.assertEqual([n.get('text') for n in card(self.tree).iter('node') if n.get('text')],
                         ['UI Window', '● 未连接', '地区未标注 · IP 未核验 · 延迟未测',
                          '当前没有运行线路', '编辑网络', '测速'])

    def test_source_drift_missing_duplicate_relocated_and_unknown_inputs_fail(self):
        original = SHIM.ORIGINAL_PATH.read_bytes()
        context = SHIM.ORIGINAL_CONTEXT
        variants = [original + b'\n', original.replace(context, b'', 1),
                    original.replace(context, context + context, 1),
                    original.replace(context, b'', 1) + context,
                    original.replace(context, SHIM.CURRENT_CONTEXT, 1),
                    original.replace(b"value.attrib.get('clickable') != 'false'", b'False', 1),
                    b'unknown source', bytearray(original)]
        for raw in variants:
            with self.subTest(identity=hashlib.sha256(raw).hexdigest()), self.assertRaises(ValueError):
                SHIM.port_original_source(raw)

    def test_required_exact_statuses_stay_same_card_readonly_visible_and_unique(self):
        for label in ('● 未连接', '当前没有运行线路'):
            for mutation in ('missing', 'duplicate', 'other-card', 'hidden', 'clickable'):
                tree = copy.deepcopy(self.tree)
                owner = card(tree)
                node = next(n for n in owner.iter('node') if n.get('text') == label)
                parent = next(n for n in owner.iter() if node in list(n))
                if mutation == 'missing': parent.remove(node)
                elif mutation == 'duplicate': parent.append(copy.deepcopy(node))
                elif mutation == 'other-card': parent.remove(node); card(tree, '默认环境').append(node)
                elif mutation == 'hidden': node.set('bounds', '[0,0][0,0]')
                elif mutation == 'clickable': node.set('clickable', 'true')
                with self.subTest(label=label, mutation=mutation):
                    self.assertFalse(SHIM.visible_inactive_route(tree, 'UI Window'))

    def test_running_stages_summaries_wrong_environment_and_wrong_status_stay_rejected(self):
        for label in ('入口', '固定出口', '目的地', '运行线路 · 自动优选'):
            tree = copy.deepcopy(self.tree); card(tree).append(text_node(label))
            with self.subTest(forbidden=label):
                self.assertFalse(SHIM.visible_inactive_route(tree, 'UI Window'))
        for label in ('● 未运行', '● 已连接', '● 连接中', ''):
            tree = copy.deepcopy(self.tree)
            next(n for n in card(tree).iter('node') if n.get('text') == '● 未连接').set('text', label)
            with self.subTest(wrongStatus=label):
                self.assertFalse(SHIM.visible_inactive_route(tree, 'UI Window'))
        self.assertFalse(SHIM.visible_inactive_route(self.tree, 'Other window'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
