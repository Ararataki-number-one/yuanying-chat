"""Exact presentation ports of the immutable inactive-route predicate.

Captured Android XML is consumed unchanged. The existing 2.0.46 label port is
preserved. Current cards additionally use two exact source-selector changes
for their named edit action and drawable-backed status, retaining every route,
count, bounds and read-only check. The original tool remains unchanged.
"""
import hashlib
from pathlib import Path
import re

ORIGINAL_PATH = Path(__file__).resolve().parents[2] / 'tools/gecko/network_ui_route_contract.py'
ORIGINAL_SHA256 = 'f7a1e1d8b136022604778f7664f6e9df374b64253c0b4045ea9a395c8f2e06b0'
ORIGINAL_CONTEXT = "                for label in ('● 未运行', '当前没有运行线路'):\n".encode()
CURRENT_CONTEXT = "                for label in ('● 未连接', '当前没有运行线路'):\n".encode()


def port_original_source(raw):
    """Reject any whole-source drift before making one exact label change."""
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Inactive-route original module identity differs')
    if raw.count(ORIGINAL_CONTEXT) != 1 or CURRENT_CONTEXT in raw:
        raise ValueError('Inactive-route exact original label context differs')
    current = raw.replace(ORIGINAL_CONTEXT, CURRENT_CONTEXT, 1)
    if current.count(CURRENT_CONTEXT) != 1 or current.replace(CURRENT_CONTEXT, ORIGINAL_CONTEXT, 1) != raw:
        raise ValueError('Inactive-route complete label inverse differs')
    return current


_namespace = {'__name__': 'network_ui_route_contract46_exact_label_port'}
exec(compile(port_original_source(ORIGINAL_PATH.read_bytes()),
             str(ORIGINAL_PATH) + ' [2.0.46 exact inactive-label port]', 'exec'), _namespace)
_legacy_inactive_route = _namespace['visible_inactive_route']


CARD_CONTEXT = (
    "            if any(node.attrib.get('text') == '编辑网络' and\n"
    "                   node.attrib.get('class') == 'android.widget.Button'\n"
    "                   for node in card.iter('node')):\n"
).encode()
PRESENTED_CARD_CONTEXT = "            if _actual_presented_card(card, environment):\n".encode()
LABEL_CONTEXT = "                    matches = [node for node in values if node.attrib['text'] == label]\n".encode()
PRESENTED_LABEL_CONTEXT = "                    matches = [node for node in values if _actual_presented_label(node, label)]\n".encode()


def port_current_presentation(raw):
    """Port two selectors; retain every assertion in the fixed original body.

    This changes how actual nodes are identified. It does not normalize, add,
    move or rewrite any captured XML node or any evidence field.
    """
    expected = port_original_source(ORIGINAL_PATH.read_bytes())
    if type(raw) is not bytes or raw != expected:
        raise ValueError('Inactive presentation requires the complete original label port')
    start = raw.index(b'def visible_inactive_route(')
    end = raw.index(b'\ndef reveal_modal_action(', start)
    body = raw[start:end]
    if body.count(CARD_CONTEXT) != 1 or body.count(LABEL_CONTEXT) != 1:
        raise ValueError('Inactive presentation exact selector contexts differ')
    changed = body.replace(CARD_CONTEXT, PRESENTED_CARD_CONTEXT, 1).replace(LABEL_CONTEXT, PRESENTED_LABEL_CONTEXT, 1)
    restored = changed.replace(PRESENTED_CARD_CONTEXT, CARD_CONTEXT, 1).replace(PRESENTED_LABEL_CONTEXT, LABEL_CONTEXT, 1)
    if restored != body:
        raise ValueError('Inactive presentation complete selector inverse differs')
    return raw[:start] + changed + raw[end:]


_presentation_code = compile(port_current_presentation(port_original_source(ORIGINAL_PATH.read_bytes())),
                             str(ORIGINAL_PATH) + ' [actual semantic presentation selectors]', 'exec')


def _visible_bounds(node):
    values = list(map(int, re.findall(r'-?\d+', node.get('bounds', ''))))
    if (len(values) != 4 or values[0] < 0 or values[1] < 0
            or values[2] <= values[0] or values[3] <= values[1]
            or node.get('visible-to-user') == 'false'):
        return None
    return values


def _inside(node, owner):
    value, card = _visible_bounds(node), _visible_bounds(owner)
    return (value is not None and card is not None
            and card[0] <= value[0] < value[2] <= card[2]
            and card[1] <= value[1] < value[3] <= card[3])


def visible_inactive_route(tree, environment):
    """Use the real named edit action and readable drawable-backed status.

    The legacy presentation keeps its complete original predicate. For the
    current presentation, both selector callbacks point at existing, unique
    nodes in the same actual card; the unchanged original predicate still
    checks absence of running stages/summary and unique visible readonly labels.
    """
    editors = [node for node in tree.iter('node')
               if node.get('content-desc') == '编辑网络 · ' + environment]
    if not editors:
        return _legacy_inactive_route(tree, environment)
    if len(editors) != 1:
        return False
    editor = editors[0]
    if (editor.get('class') != 'android.widget.Button' or editor.get('text') != '编辑'
            or editor.get('enabled') != 'true' or editor.get('clickable') != 'true'):
        return False
    cards = [node for node in tree.iter('node')
             if node.get('class') == 'android.widget.LinearLayout'
             and node.get('content-desc', '').startswith(environment + '，')
             and node.get('content-desc', '').endswith('，查看窗口详情')]
    if len(cards) != 1:
        return False
    card = cards[0]
    if (card.get('enabled') != 'true' or card.get('clickable') != 'true'
            or editor not in list(card.iter('node')) or not _inside(editor, card)):
        return False
    titles = [node for node in tree.iter('node') if node.get('text') == environment]
    if len(titles) != 1 or titles[0] not in list(card.iter('node')) or not _inside(titles[0], card):
        return False
    statuses = [node for node in card.iter('node') if node.get('text') == '未连接']
    described = [node for node in card.iter('node') if node.get('content-desc', '').startswith('网络状态：')]
    if len(statuses) != 1 or len(described) != 1 or statuses[0] is not described[0]:
        return False
    status = statuses[0]
    if (status.get('class') != 'android.widget.TextView' or status.get('content-desc') != '网络状态：未连接'
            or status.get('enabled') != 'true' or not _inside(status, card)):
        return False
    namespace = {
        '__name__': 'network_ui_route_actual_presentation',
        '_actual_presented_card': lambda actual, name: actual is card and name == environment,
        '_actual_presented_label': lambda actual, label:
            (actual is status or actual.get('text') == label) if label == '● 未连接'
            else actual.get('text') == label,
    }
    exec(_presentation_code, namespace)
    return namespace['visible_inactive_route'](tree, environment)
