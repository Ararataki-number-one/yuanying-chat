"""Explicit current card-v2 inactive predicate; never accepts the old grammar.

The unchanged original Activity still requires a saved-only, unconnected
WindowNetworkState and null source/identity/freshness-bound running config.
This read-only adapter recognizes its current native card presentation only.
"""
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
CONTRACT_VERSION = 2
SOURCE_IDENTITIES = {
    'app/src/main/java/local/pocketchat/NetworkWorkspaceUi.java':
        (71307, '19ed9529d3e4c5b52ee8969b64ee057848b559ee4d4bf92faf97c7bab9fa4ea1'),
    'tests/gecko/NetworkSourcesUiIntegrationActivity.java':
        (19946, 'aa36b402d7d0979e51a5482a706f9583a55a197848f8fc08472cb195c4f06449'),
}


def verify_source_contract(root=ROOT):
    for name, (size, digest) in SOURCE_IDENTITIES.items():
        raw = (Path(root) / name).read_bytes()
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Unknown network card-v2 production/fixture source: ' + name)


def _bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    if match is None:
        return None
    left, top, right, bottom = map(int, match.groups())
    return (left, top, right, bottom) if left < right and top < bottom else None


def _visible(node, parents):
    rect = _bounds(node)
    if rect is None or node.get('visible-to-user') == 'false':
        return False
    parent = parents.get(node)
    while parent is not None:
        if parent.get('visible-to-user') == 'false':
            return False
        if 'bounds' in parent.attrib:
            area = _bounds(parent)
            if area is None or not (area[0] <= rect[0] < rect[2] <= area[2]
                                    and area[1] <= rect[1] < rect[3] <= area[3]):
                return False
        parent = parents.get(parent)
    return True


def visible_inactive_route(tree, environment):
    verify_source_contract()  # Current raw sources only; no history projection.
    if type(environment) is not str or not environment:
        return False
    parents = {child: parent for parent in tree.iter() for child in parent}
    named = [n for n in tree.iter('node') if n.get('text') == environment
             and n.get('package') == PACKAGE and n.get('class') == 'android.widget.TextView']
    if len(named) != 1 or not _visible(named[0], parents):
        return False
    cards = [n for n in tree.iter('node') if n.get('package') == PACKAGE
             and n.get('class') == 'android.widget.LinearLayout'
             and n.get('content-desc', '').startswith(environment + '，未连接，')
             and n.get('content-desc', '').endswith('，当前没有运行线路，查看窗口详情')]
    if len(cards) != 1:
        return False
    card = cards[0]
    if named[0] not in set(card.iter()) or card.get('clickable') != 'true' or not _visible(card, parents):
        return False
    description = card.get('content-desc', '')
    if any(value in description for value in ('，入口：', '，固定出口：', '，目的地：', '，等待应用：', '运行线路 ·')):
        return False
    edits = [n for n in card.iter('node') if n.get('class') == 'android.widget.Button'
             and (n.get('text') == '编辑' or n.get('content-desc', '').startswith('编辑网络 · '))]
    if len(edits) != 1:
        return False
    edit = edits[0]
    if (edit.get('text') != '编辑' or edit.get('content-desc') != '编辑网络 · ' + environment
            or edit.get('package') != PACKAGE or edit.get('clickable') != 'true'
            or edit.get('enabled') != 'true' or not _visible(edit, parents)):
        return False
    values = [node for node in card.iter('node') if node.get('text')]
    labels = [node.get('text') for node in values]
    if any(label in labels for label in ('入口', '固定出口', '目的地')):
        return False
    if any(label.startswith(('运行线路 ·', '等待应用')) for label in labels):
        return False
    for label, description in (('未连接', '网络状态：未连接'), ('当前没有运行线路', '')):
        matches = [n for n in values if n.get('text') == label]
        if len(matches) != 1:
            return False
        value = matches[0]
        if (value.get('class') != 'android.widget.TextView' or value.get('package') != PACKAGE
                or value.get('content-desc', '') != description
                or value.get('clickable') != 'false' or not _visible(value, parents)):
            return False
    return True
