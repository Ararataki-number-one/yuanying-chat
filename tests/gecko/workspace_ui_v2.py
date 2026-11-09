"""Actual Android selection controls in the redesigned environment workspace."""
import xml.etree.ElementTree as ET

from workspace_navigation_contract import bounds


def button(xml, label, package):
    matches = [n for n in ET.fromstring(xml).iter('node')
               if n.attrib.get('package') == package
               and n.attrib.get('class') == 'android.widget.Button'
               and n.attrib.get('text') == label]
    assert len(matches) == 1, ('Missing or ambiguous environment action', label)
    node = matches[0]
    assert node.attrib.get('enabled') == node.attrib.get('clickable') == 'true', node.attrib
    return node, bounds(node)


def capture_selection(adb, adb_bytes, dump, xml, package, width, height, shots, stem, record):
    counts = [n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text') == '8 个环境']
    assert len(counts) == 1
    assert bounds(counts[0])[3]-bounds(counts[0])[1] <= 48*3
    taps = []
    for label in ('多选', '全选'):
        node, rectangle = button(xml, label, package)
        left, top, right, bottom = rectangle
        point = [(left+right)//2, (top+bottom)//2]
        adb('shell', 'input', 'tap', *map(str, point))
        taps.append(dict(label=label, point=point, bounds=rectangle))
        xml = dump()
    assert '已选 8 个' in xml, 'Actual select-all did not select all eight environment records'
    labels = ('取消全选', '批量分组', '收藏', '取消收藏')
    seen, swipes, frames = {}, [], []
    for attempt in range(7):
        tree = ET.fromstring(xml)
        for label in labels:
            found = [n for n in tree.iter('node') if n.attrib.get('package') == package
                     and n.attrib.get('class') == 'android.widget.Button'
                     and n.attrib.get('text') == label]
            assert len(found) <= 1, ('Ambiguous selection action', label)
            if not found:
                continue
            node = found[0]
            assert node.attrib.get('enabled') == node.attrib.get('clickable') == 'true', node.attrib
            left, top, right, bottom = bounds(node)
            if right-left >= 48*3 and bottom-top >= 48*3 and 0 <= left < right <= width*3 and 0 <= top < bottom <= height*3:
                seen[label] = dict(bounds=[left,top,right,bottom], enabled=True, clickable=True)
        name = stem + '-selection-v2-' + str(attempt)
        (shots/(name+'.xml')).write_text(xml)
        (shots/(name+'.png')).write_bytes(adb_bytes('exec-out', 'screencap', '-p'))
        frames.append(name+'.png')
        if set(seen) == set(labels):
            break
        assert attempt < 6, ('Actual horizontal swipes did not reveal every selection action', sorted(seen))
        scrollers = [n for n in tree.iter('node')
                     if n.attrib.get('package') == package
                     and n.attrib.get('class') == 'android.widget.HorizontalScrollView'
                     and n.attrib.get('scrollable') == 'true'
                     and any(c.attrib.get('text') in labels[1:] for c in n.iter('node'))]
        assert len(scrollers) == 1, 'The enlarged selection actions must have one actual horizontal scroller'
        left, top, right, bottom = bounds(scrollers[0])
        y=(top+bottom)//2
        gesture=[left+(right-left)*4//5,y,left+(right-left)//5,y]
        adb('shell','input','swipe',*map(str,gesture),'350')
        swipes.append(dict(bounds=[left,top,right,bottom], coordinates=gesture, durationMs=350))
        xml=dump()
    adb('shell', 'input', 'keyevent', '4')
    assert '批量分组' not in dump(), 'Back did not close the actual selection footer'
    record['selectionCheck'] = dict(navigationContract=2, actualAndroidTaps=taps,
        actualAndroidSwipes=swipes, actualAndroidBack=True, selectedCount=8,
        allFourFooterActionsReachable=True, actions=seen, images=frames)
