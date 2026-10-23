"""Negative controls for route assertions; no Android execution or app acceptance."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock

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


class SystemClipboardWindowTest(unittest.TestCase):
    app = '  Window #1 Window{abc u0 local.pocketchat.test/local.pocketchat.NetworkSourcesUiIntegrationActivity}:\n'
    overlay = '  Window #0 Window{def u0 ClipboardOverlay}:\n'

    def test_overlay_blocks_the_next_single_app_touch(self):
        self.assertTrue(ROUTE.clipboard_overlay_present(self.overlay+self.app,'local.pocketchat.test'))

    def test_absent_overlay_allows_the_next_touch(self):
        self.assertFalse(ROUTE.clipboard_overlay_present(self.app,'local.pocketchat.test'))

    def test_old_focus_reference_is_not_a_live_overlay_window(self):
        self.assertFalse(ROUTE.clipboard_overlay_present(self.app+'  mLastFocus=Window{def u0 ClipboardOverlay}\n','local.pocketchat.test'))

    def test_missing_app_window_is_rejected(self):
        with self.assertRaises(AssertionError):ROUTE.clipboard_overlay_present(self.overlay,'local.pocketchat.test')

    def test_unsupported_or_empty_dump_cannot_mean_unobstructed(self):
        for raw in ('', 'permission denied', 'mCurrentFocus=Window{abc u0 local.pocketchat.test/Fixture}'):
            with self.assertRaises(AssertionError):ROUTE.clipboard_overlay_present(raw,'local.pocketchat.test')


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


class InactiveNetworkRouteUiTest(unittest.TestCase):
    def card(self, name='UI Window'):
        value = card(name=name)
        value.remove(value[1])
        value.insert(1, text('● 未运行'))
        value.insert(2, text('当前没有运行线路'))
        return value

    def visible(self, *cards):
        tree = ET.Element('hierarchy'); tree.extend(cards)
        return ROUTE.visible_inactive_route(tree, 'UI Window')

    def test_saved_configuration_is_explicitly_inactive(self):
        self.assertTrue(self.visible(self.card()))

    def test_synthetic_running_route_is_rejected(self):
        value = self.card(); value.append(card()[1])
        self.assertFalse(self.visible(value))
        value = self.card(); value.append(text('运行线路 · 自动优选'))
        self.assertFalse(self.visible(value))

    def test_each_state_is_required_in_the_named_card(self):
        for index in (1, 2):
            value = self.card(); value.remove(value[index])
            self.assertFalse(self.visible(value, self.card('Other window')))

    def test_hidden_or_interactive_state_is_rejected(self):
        for field, data in (('bounds', '[0,0][0,0]'), ('clickable', 'true')):
            value = self.card(); value[2].set(field, data)
            self.assertFalse(self.visible(value))


class ModalActionScrollTest(unittest.TestCase):
    def tree(self, visible=False, title='入口订阅详情', scrollable=True):
        tree=ET.Element('hierarchy');heading=text('详情');heading.set('content-desc',title);tree.append(heading)
        body=ET.SubElement(tree,'node',{'class':'android.widget.ScrollView','package':'local.pocketchat.test',
                                      'scrollable':str(scrollable).lower(),'bounds':'[100,200][900,1600]'})
        if visible:
            action=text('删除订阅');action.set('class','android.widget.Button');action.set('package','local.pocketchat.test');action.set('enabled','true');action.set('clickable','true');action.set('bounds','[120,1400][880,1530]');body.append(action)
        return tree

    def reveal(self, read, swipe, **kwargs):
        return ROUTE.reveal_modal_action(read,swipe,'入口订阅详情','删除订阅','local.pocketchat.test',**kwargs)

    def test_visible_action_does_not_scroll_or_invoke_it(self):
        value=self.tree(True);swipe=Mock();self.assertIs(self.reveal(lambda:value,swipe),value);swipe.assert_not_called()

    def test_hidden_action_uses_one_actual_scroll_inside_the_modal(self):
        hidden,visible=self.tree(),self.tree(True);read=Mock(side_effect=[hidden,visible]);swipe=Mock();record=Mock()
        self.assertIs(self.reveal(read,swipe,record=record),visible)
        swipe.assert_called_once_with(500,1320,500,480);record.assert_called_once()

    def test_another_modal_is_rejected_without_a_gesture(self):
        swipe=Mock()
        with self.assertRaises(AssertionError):self.reveal(lambda:self.tree(title='其他弹窗'),swipe)
        swipe.assert_not_called()

    def test_absent_scroll_body_cannot_fall_back_to_screen_swipes(self):
        swipe=Mock()
        with self.assertRaises(AssertionError):self.reveal(lambda:self.tree(scrollable=False),swipe)
        swipe.assert_not_called()

    def test_scroll_budget_is_finite_and_missing_action_stays_failed(self):
        swipe=Mock()
        with self.assertRaises(AssertionError):self.reveal(lambda:self.tree(),swipe,max_scrolls=2)
        self.assertEqual(swipe.call_count,2)

    def test_nonclickable_label_cannot_replace_an_actual_action(self):
        value=self.tree(True);value[-1][0].set('clickable','false');swipe=Mock()
        with self.assertRaises(AssertionError):self.reveal(lambda:value,swipe)
        swipe.assert_not_called()

    def test_disabled_action_is_not_accepted_or_force_clicked(self):
        value=self.tree(True);value[-1][0].set('enabled','false');swipe=Mock()
        with self.assertRaises(AssertionError):self.reveal(lambda:value,swipe)
        swipe.assert_not_called()


if __name__=='__main__':unittest.main()
