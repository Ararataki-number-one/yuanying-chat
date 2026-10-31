"""Bounded trusted-gesture traversal of the production update ScrollView.

This driver inspects real UIAutomator snapshots; it does not infer off-screen
controls from source or native reports. It returns a fresh visible installer
button snapshot after inspecting all original update settings.
"""
import hashlib
import re
import xml.etree.ElementTree as ET

LABELS = ('应用更新', '当前安装版本', '安装更新', '删除安装包', '自动检查更新', 'Wi-Fi 下自动下载新版')
MAX_SWIPES = 6


def _bounds(node):
    match = re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', node.get('bounds', ''))
    if not match:
        raise AssertionError('Missing or invalid actual Android bounds')
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        raise AssertionError('Empty actual Android bounds')
    return left, top, right, bottom


def _snapshot(xml, package):
    root = ET.fromstring(xml)
    nodes = list(root.iter('node'))
    titles = [n for n in nodes if n.get('package') == package and n.get('text') == LABELS[0]
              and n.get('class') == 'android.widget.TextView']
    scrolls = [n for n in nodes if n.get('package') == package
               and n.get('class') == 'android.widget.ScrollView']
    if len(titles) != 1 or len(scrolls) != 1:
        raise AssertionError('Expected the actual production update page and one ScrollView')
    _bounds(titles[0])
    scroll = scrolls[0]
    viewport = _bounds(scroll)
    seen = {LABELS[0]}
    for node in scroll.iter('node'):
        if node.get('package') != package or node.get('enabled') != 'true':
            continue
        text = node.get('text', '')
        label = next((label for label in LABELS[1:] if text == label or
                      label == '当前安装版本' and text.startswith(label + ' ')), None)
        if label is None:
            continue
        bounds = _bounds(node)
        cx, cy = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
        if not (viewport[0] <= cx < viewport[2] and viewport[1] <= cy < viewport[3]):
            continue
        if label in ('安装更新', '删除安装包'):
            if node.get('class') != 'android.widget.Button' or node.get('clickable') != 'true':
                raise AssertionError('Expected enabled actual Android update button: ' + label)
        elif label in LABELS[-2:]:
            if node.get('class') != 'android.widget.Switch':
                raise AssertionError('Expected actual Android update switch: ' + label)
        elif node.get('class') != 'android.widget.TextView':
            raise AssertionError('Expected actual installed-version text')
        seen.add(label)
    return viewport, seen


def scan_update_controls(adb, initial_xml, save, package):
    """Inspect every required label, then restore a visible installer button.

    At most six downward and six upward 400 ms Android swipes are admitted.
    No timeout, label, installer assertion or old acceptance result is waived.
    """
    xml = initial_xml
    observed = set()
    snapshots, gestures = [], []

    def inspect(stage):
        viewport, visible = _snapshot(xml, package)
        observed.update(visible)
        name = 'update-ui-scroll-%02d-%s.xml' % (len(snapshots), stage)
        save(name, xml)
        snapshots.append(dict(file=name, sha256=hashlib.sha256(xml.encode('utf-8')).hexdigest(),
                              visibleLabels=[label for label in LABELS if label in visible]))
        return viewport, visible

    def swipe(viewport, direction):
        nonlocal xml
        left, top, right, bottom = viewport
        x = (left + right) // 2
        margin = max(1, (bottom - top) // 5)
        y1, y2 = bottom - margin, top + margin
        if direction == 'up':
            y1, y2 = y2, y1
        adb('shell', 'input', 'swipe', str(x), str(y1), str(x), str(y2), '400')
        gestures.append(dict(direction=direction, x=x, fromY=y1, toY=y2, duration=400))
        adb('shell', 'uiautomator', 'dump', '/sdcard/update-ui-scroll.xml')
        xml = adb('shell', 'cat', '/sdcard/update-ui-scroll.xml')

    viewport, visible = inspect('initial')
    for unused in range(MAX_SWIPES):
        if observed == set(LABELS):
            break
        swipe(viewport, 'down')
        viewport, visible = inspect('settings')
    missing = [label for label in LABELS if label not in observed]
    if missing:
        raise AssertionError(('Update controls absent after bounded actual scrolling', missing, snapshots))
    for unused in range(MAX_SWIPES):
        if '安装更新' in visible:
            break
        swipe(viewport, 'up')
        viewport, visible = inspect('installer')
    if '安装更新' not in visible:
        raise AssertionError('Actual installer button is not visible after bounded return scrolling')
    # The retained installer driver selects the first global matching text.
    # Refuse duplicates so it can only select the visible enabled button above.
    installers = [node for node in ET.fromstring(xml).iter('node') if node.get('text') == '安装更新']
    if len(installers) != 1:
        raise AssertionError('Expected one unique actual installer target in the returned snapshot')
    return xml, dict(labelsSeen=[label for label in LABELS if label in observed],
                     snapshots=snapshots, gestures=gestures, maxSwipesPerDirection=MAX_SWIPES,
                     scope='Real UIAutomator snapshots and trusted Android swipes on the update page; no APK installed by this traversal.')
