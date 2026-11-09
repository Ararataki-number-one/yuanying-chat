"""Native selector controls; synthetic XML here is not Android acceptance.

The unchanged c244 device flow supplies every actual tap, lifecycle assertion,
capture, timeout and cohort. Only two obsolete presentation selectors change.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/gecko/run_environment_dashboard.py'
BASE_COMMIT = 'c244835a4c1e3629909b2b1ce132ca5987a97d9a'
BASE_SHA256 = '99b0298e0dc5f45c744d8086d0f9fe51b1c4d0fa63cd08f50037a2196cd05064'
SPEC = importlib.util.spec_from_file_location('environment_dashboard_presentation', RUNNER)
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

# These are the complete six device-flow line changes. Everything else in the
# original runner is compared byte-for-byte with its actual committed source.
DELTAS = (
    ("            xml=wait(lambda x:'打开环境 日常会话' in x,'environment list button')\n",
     "            xml=wait(lambda x:environment_action_description(x,'日常会话') is not None,'environment list button')\n"),
    ("            click(xml,description='打开环境 日常会话');xml=wait(dashboard,'warm list opens dashboard');snapshot('warm-list',xml)\n",
     "            click(xml,description=environment_action_description(xml,'日常会话'));xml=wait(dashboard,'warm list opens dashboard');snapshot('warm-list',xml)\n"),
    ("            xml=wait(lambda x:'打开环境 日常会话' in x,'list for second environment')\n",
     "            xml=wait(lambda x:environment_action_description(x,'日常会话') is not None,'list for second environment')\n"),
    ("                if '打开环境 资料整理' in xml:break\n",
     "                if environment_action_description(xml,'资料整理') is not None:break\n"),
    ("            click(xml,description='打开环境 资料整理');xml=wait(lambda x:dashboard(x) and '资料整理' in x,'separate process second environment');snapshot('second-environment',xml,profileProcess='profile1',slot=1)\n",
     "            click(xml,description=environment_action_description(xml,'资料整理'));xml=wait(lambda x:dashboard(x) and '资料整理' in x,'separate process second environment');snapshot('second-environment',xml,profileProcess='profile1',slot=1)\n"),
    ("            xml=wait(lambda x:'启动与界面' in x and '会话' in x,'settings workspace')\n",
     "            xml=wait(settings_workspace,'settings workspace')\n"),
)


def original_flow(raw):
    if type(raw) is not bytes:
        raise ValueError('Complete dashboard source bytes required')
    start = raw.index(b'def environment_action_description(')
    end = raw.index(b'def run(', start)
    raw = raw[:start] + raw[end:]
    for previous, current in reversed(DELTAS):
        old, new = previous.encode(), current.encode()
        if raw.count(new) != 1:
            raise ValueError('Every dashboard selector change must occur exactly once')
        raw = raw.replace(new, old, 1)
    if len(raw) != 12001 or hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('The complete original dashboard device flow changed')
    return raw


def node(parent, kind, text='', description='', bounds='[60,361][1020,674]', **attributes):
    values = {'class': kind, 'package': RUN.PACKAGE, 'text': text,
              'content-desc': description, 'enabled': 'true', 'clickable': 'false',
              'bounds': bounds}
    values.update(attributes)
    return ET.SubElement(parent, 'node', values)


def environment_tree(name='日常会话', metadata='已收藏，01 · 工作 · 默认 · 电脑版，手机网络 · 连接需处理，需处理'):
    root = ET.Element('hierarchy')
    card = node(root, 'android.widget.LinearLayout', description='打开环境：'+name+'，'+metadata,
                clickable='true')
    node(card, 'android.widget.TextView', name, bounds='[264,404][828,474]')
    node(card, 'android.widget.TextView', '01 · 工作 · 默认 · 电脑版', bounds='[264,474][828,539]')
    return root, card


def settings_tree():
    root = ET.Element('hierarchy')
    node(root, 'android.widget.TextView', '设置', '应用设置')
    node(root, 'android.widget.TextView', '启动与外观')
    node(root, 'android.widget.Button', '会话', '会话', clickable='true')
    return root


def xml(tree):
    return ET.tostring(tree, encoding='unicode')


class DashboardPresentation(unittest.TestCase):
    def test_every_original_device_action_assertion_timeout_and_cohort_is_retained(self):
        previous = subprocess.check_output(
            ['git', 'show', BASE_COMMIT+':tests/gecko/run_environment_dashboard.py'], cwd=ROOT)
        self.assertEqual((len(previous), hashlib.sha256(previous).hexdigest()), (12001, BASE_SHA256))
        self.assertEqual(original_flow(RUNNER.read_bytes()), previous)

    def test_original_flow_changes_missing_or_duplicate_selector_ports_reject(self):
        current = RUNNER.read_bytes()
        for old, new in DELTAS:
            for candidate in (current.replace(new.encode(), b'', 1),
                              current.replace(new.encode(), new.encode()*2, 1)):
                with self.assertRaises(ValueError):
                    original_flow(candidate)
        for old, new in (
                (b'for _ in range(8):', b'for _ in range(7):'),
                (b'until=time.monotonic()+7', b'until=time.monotonic()+6'),
                (b'actualAndroidTaps=len(taps)-entry_taps', b'actualAndroidTaps=7'),
                (b"slot=1)", b"slot=0)"),
                (b"        assert dashboard(xml),('dashboard absent',name)\n",
                 b"        assert True,('dashboard absent',name)\n")):
            self.assertEqual(current.count(old), 1)
            with self.assertRaises(ValueError):
                original_flow(current.replace(old, new, 1))

    def test_current_named_card_and_variable_metadata_select_actual_description(self):
        for name in ('日常会话', '资料整理'):
            for metadata in ('已收藏，01 · 工作 · 默认 · 电脑版，手机网络 · 连接需处理，需处理',
                             '02 · 学习，手机网络 · 未连接，未连接'):
                tree, card = environment_tree(name, metadata)
                before = xml(tree)
                self.assertEqual(RUN.environment_action_description(before, name), card.get('content-desc'))
                self.assertEqual(xml(tree), before)

    def test_absent_other_similar_old_and_selection_cards_do_not_open_an_environment(self):
        tree, card = environment_tree()
        self.assertIsNone(RUN.environment_action_description(xml(tree), '资料整理'))
        self.assertIsNone(RUN.environment_action_description('<hierarchy />', '日常会话'))
        for description in ('打开环境 日常会话', '打开环境：日常会话备份，01',
                            '选择环境：日常会话，01', '打开环境：日常会话'):
            card.set('content-desc', description)
            self.assertIsNone(RUN.environment_action_description(xml(tree), '日常会话'))

    def test_ambiguous_disabled_invisible_or_non_native_cards_reject(self):
        tree, card = environment_tree()
        tree.append(copy.deepcopy(card))
        with self.assertRaises(AssertionError):
            RUN.environment_action_description(xml(tree), '日常会话')
        for attribute, value in (('class', 'android.widget.Button'), ('enabled', 'false'),
                                 ('clickable', 'false'), ('visible-to-user', 'false'),
                                 ('bounds', ''), ('bounds', '[60,361][60,674]'),
                                 ('bounds', '[-1,361][1020,674]')):
            tree, card = environment_tree()
            card.set(attribute, value)
            with self.subTest(attribute=attribute, value=value), self.assertRaises(AssertionError):
                RUN.environment_action_description(xml(tree), '日常会话')
        tree, card = environment_tree()
        card.set('package', 'another.package')
        self.assertIsNone(RUN.environment_action_description(xml(tree), '日常会话'))

    def test_title_must_belong_to_the_named_visible_card(self):
        for mutation in ('missing', 'duplicate', 'other-card', 'wrong-class', 'disabled',
                         'hidden', 'outside', 'empty'):
            tree, card = environment_tree()
            title = card[0]
            if mutation == 'missing':card.remove(title)
            elif mutation == 'duplicate':card.append(copy.deepcopy(title))
            elif mutation == 'other-card':card.remove(title);tree.append(title)
            elif mutation == 'wrong-class':title.set('class', 'android.widget.Button')
            elif mutation == 'disabled':title.set('enabled', 'false')
            elif mutation == 'hidden':title.set('visible-to-user', 'false')
            elif mutation == 'outside':title.set('bounds', '[264,675][828,745]')
            elif mutation == 'empty':title.set('bounds', '[264,404][264,474]')
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                RUN.environment_action_description(xml(tree), '日常会话')

    def test_settings_requires_real_identity_current_section_and_native_chat_action(self):
        tree = settings_tree()
        self.assertTrue(RUN.settings_workspace(xml(tree)))
        for index in range(3):
            altered = copy.deepcopy(tree)
            altered.remove(altered[index])
            self.assertFalse(RUN.settings_workspace(xml(altered)))
        tree[1].set('text', '启动与界面')
        self.assertFalse(RUN.settings_workspace(xml(tree)))
        for index, attribute, value in ((0, 'class', 'android.widget.Button'),
                                         (1, 'class', 'android.widget.Button'),
                                         (2, 'class', 'android.widget.TextView'),
                                         (2, 'enabled', 'false'), (2, 'clickable', 'false')):
            tree = settings_tree();tree[index].set(attribute, value)
            with self.subTest(index=index, attribute=attribute), self.assertRaises(AssertionError):
                RUN.settings_workspace(xml(tree))
        tree = settings_tree();tree.append(copy.deepcopy(tree[0]))
        with self.assertRaises(AssertionError):
            RUN.settings_workspace(xml(tree))


if __name__ == '__main__':
    unittest.main(verbosity=2)
