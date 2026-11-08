"""Selector/geometry checks only; these models are not Android execution evidence."""
import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
SPEC=importlib.util.spec_from_file_location('glass_capture',ROOT/'tools/gecko/capture_glass_navigation.py')
CAPTURE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CAPTURE)


def hierarchy(labels,boxes,selected=None):
    root=ET.Element('hierarchy')
    for label,box in zip(labels,boxes):
        ET.SubElement(root,'node',{'package':'local.pocketchat.test','text':label,
            'content-desc':label,'class':'android.widget.Button','clickable':'true','enabled':'true',
            'selected':str(label==selected).lower(),'visible-to-user':'true',
            'bounds':'[{},{}][{},{}]'.format(*box)})
    return root


def xml(root):return ET.tostring(root,encoding='unicode')


class NavigationCaptureModesTest(unittest.TestCase):
    compact=((291,2358,509,2562),(509,2358,727,2562),(727,2358,945,2562),(984,2352,1200,2568))
    workspace=((51,2358,277,2562),(277,2358,504,2562),(504,2358,731,2562),(731,2358,958,2562),(958,2358,1185,2562))

    def test_chat_retains_centered_three_and_separate_reading(self):
        value=xml(hierarchy(CAPTURE.LABELS,self.compact))
        self.assertIsNotNone(CAPTURE.navigation(value))
        self.assertIsNone(CAPTURE.workspace_navigation_geometry(value))
        geometry=CAPTURE.observed_navigation_geometry(value)
        self.assertEqual(geometry['layout'],'conversation-split')
        self.assertEqual(geometry['horizontalCenterOffsetPx'],0)
        self.assertFalse(CAPTURE.selected_navigation(value,'网络'))

    def test_all_five_selected_destinations_use_workspace_geometry(self):
        for selected in CAPTURE.WORKSPACE_LABELS:
            with self.subTest(selected=selected):
                value=xml(hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,selected))
                self.assertIsNone(CAPTURE.navigation(value))
                self.assertTrue(CAPTURE.selected_navigation(value,selected))
                geometry=CAPTURE.observed_navigation_geometry(value)
                self.assertEqual(geometry['layout'],'workspace-five')
                self.assertEqual(geometry['leftToRightLabels'],list(CAPTURE.WORKSPACE_LABELS))
                self.assertEqual(geometry['horizontalCenterOffsetPx'],0)

    def test_old_selected_compact_bar_cannot_pass_as_native_workspace(self):
        for selected in ('环境','网络','下载'):
            value=xml(hierarchy(CAPTURE.LABELS,self.compact,selected))
            self.assertFalse(CAPTURE.selected_navigation(value,selected))

    def test_missing_duplicate_hidden_and_disabled_destinations_fail_closed(self):
        for broken in ('missing','duplicate','hidden','disabled'):
            with self.subTest(broken=broken):
                root=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
                node=root[0]
                if broken=='missing':root.remove(node)
                elif broken=='duplicate':ET.SubElement(root,'node',dict(node.attrib))
                elif broken=='hidden':node.set('visible-to-user','false')
                else:node.set('enabled','false')
                self.assertFalse(CAPTURE.selected_navigation(xml(root),'环境'))

    def test_wrong_order_misalignment_and_small_targets_fail_closed(self):
        variants=[]
        order=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        order[0].set('text','环境');order[1].set('text','会话');variants.append(order)
        off_center=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        off_center[0].set('bounds','[61,2358][277,2562]');variants.append(off_center)
        unequal=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        unequal[0].set('bounds','[51,2358][267,2562]');variants.append(unequal)
        too_short=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'环境')
        too_short[0].set('bounds','[51,2358][277,2501]');variants.append(too_short)
        for root in variants:self.assertFalse(CAPTURE.selected_navigation(xml(root),'环境'))

    def test_hidden_chat_bar_does_not_confuse_visible_workspace(self):
        root=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'下载')
        for node in hierarchy(CAPTURE.LABELS,self.compact):
            node.set('visible-to-user','false');root.append(node)
        self.assertTrue(CAPTURE.selected_navigation(xml(root),'下载'))

    def test_two_visible_bars_are_ambiguous(self):
        root=hierarchy(CAPTURE.WORKSPACE_LABELS,self.workspace,'网络')
        root.extend(hierarchy(CAPTURE.LABELS,self.compact))
        self.assertIsNone(CAPTURE.observed_navigation_geometry(xml(root)))
        self.assertFalse(CAPTURE.selected_navigation(xml(root),'网络'))


if __name__=='__main__':unittest.main()
