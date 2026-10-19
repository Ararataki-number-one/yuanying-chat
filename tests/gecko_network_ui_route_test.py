"""Negative controls for route assertions; no Android execution or app acceptance."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('network_ui_route',ROOT/'tools/gecko/network_ui_route_contract.py')
ROUTE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ROUTE)


def text(value, **extra):
    return ET.Element('node',dict(text=value,**{'class':'android.widget.TextView','clickable':'false','bounds':'[10,10][100,50]'},**extra))


def card(name='UI Window', entrance='Entry A', exit='ManualSource'):
    root=ET.Element('node');heading=ET.SubElement(root,'node');heading.append(text(name))
    stages=ET.SubElement(root,'node')
    for key,value in [('入口',entrance),('固定出口',exit),('目的地','ChatGPT')]:
        row=ET.SubElement(stages,'node');row.append(text(key));row.append(text(value))
    button=text('编辑网络');button.set('class','android.widget.Button');button.set('clickable','true');root.append(button)
    return root


class NetworkRouteUiTest(unittest.TestCase):
    def check_route(self,*cards):
        tree=ET.Element('hierarchy');tree.extend(cards)
        return ROUTE.visible_route(tree,'UI Window','Entry A','ManualSource')

    def test_named_card_has_all_three_readonly_stages(self):self.assertTrue(self.check_route(card()))
    def test_entrance_and_exit_cannot_be_swapped(self):self.assertFalse(self.check_route(card(entrance='ManualSource',exit='Entry A')))
    def test_another_environment_cannot_supply_the_missing_route(self):self.assertFalse(self.check_route(card(entrance='Wrong'),card(name='Other window')))
    def test_missing_destination_is_rejected(self):
        value=card();stages=value[1];stages.remove(stages[-1]);self.assertFalse(self.check_route(value))
    def test_hidden_stage_value_is_rejected(self):
        value=card();value[1][0][1].set('bounds','[0,0][0,0]');self.assertFalse(self.check_route(value))
    def test_clickable_route_value_is_rejected(self):
        value=card();value[1][1][1].set('clickable','true');self.assertFalse(self.check_route(value))
    def test_old_combined_line_cannot_replace_the_new_stage_checks(self):
        value=card();value.remove(value[1]);value.insert(1,text('Entry A → ManualSource'));self.assertFalse(self.check_route(value))


if __name__=='__main__':unittest.main()
