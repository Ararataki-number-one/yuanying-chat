"""Current download icon plus the unchanged native four-character label gate."""
import json
import re
import xml.etree.ElementTree as ET

PACKAGE = 'local.pocketchat.test'


def nodes(xml):
    assert isinstance(xml, str) and 0 < len(xml.encode('utf-8')) <= 1000000
    tree = ET.fromstring(xml)
    assert tree.tag == 'hierarchy'
    return list(tree.iter('node'))


def bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib['bounds'])
    assert match, 'Invalid native bounds'
    value = list(map(int, match.groups()))
    assert value[0] < value[2] and value[1] < value[3], 'Empty native bounds'
    return value


def control(xml, record, *, description=None, text=None):
    candidates = [node for node in nodes(xml) if node.attrib.get('class') == 'android.widget.Button'
                  and (description is None or node.attrib.get('content-desc') == description)
                  and (text is None or node.attrib.get('text') == text)]
    assert len(candidates) == 1, ('Missing or duplicate download control', description, text)
    node = candidates[0]
    assert node.attrib.get('package') == PACKAGE and all(node.attrib.get(key) == 'true' for key in ('clickable', 'enabled'))
    left, top, right, bottom = bounds(node)
    density = record['densityDpi'] / 160
    assert right - left >= 48 * density and bottom - top >= 48 * density, 'Download touch target below 48 dp'
    assert 0 <= left < right <= record['actualPixels'][0] and 0 <= top < bottom <= record['actualPixels'][1]
    return node


def folder_dialog(xml, record):
    owned = [node for node in nodes(xml) if node.attrib.get('package') == PACKAGE]
    assert len([node for node in owned if node.attrib.get('text') == '保存位置']) == 1
    assert len([node for node in owned if node.attrib.get('text', '').startswith('默认位置：Download/元婴期院士/窗口_编号/')]) == 1
    control(xml, record, text='知道了')


def verify_download_workspace(record, source=None):
    try:
        from .ui_visual_contract import verify_download_location
    except ImportError:
        from ui_visual_contract import verify_download_location
    verify_download_location(record, source)
    assert type(record['downloadWorkspaceContract']) is int and record['downloadWorkspaceContract'] == 2
    value = record['downloadWorkspace']
    assert value['schema'] == 2 and type(value['schema']) is int
    assert value['status'] == 'passed' and value['actualAndroidExecution'] is True
    assert record['scene'] == 'downloads' and (source is None or value['sourceCommit'] == source)
    assert re.fullmatch('[0-9a-f]{40}', value['sourceCommit'])
    invocation = value['invocationNonce']
    assert re.fullmatch('[0-9a-f]{32}', invocation) and invocation != record['downloadLocationNonce']
    icon = control(value['headerXml'], record, description='保存位置', text='')
    assert not any(node.attrib.get('text') == '保存位置' for node in nodes(value['headerXml'])), 'Initial tools must remain collapsed'
    folder_dialog(value['dialogXml'], record)
    control(value['returnedXml'], record, description='保存位置', text='')
    tools = control(value['beforeToolsXml'], record, description='展开下载工具', text='')
    label = control(value['toolsXml'], record, text='保存位置')
    assert not any(node.attrib.get('content-desc') == '展开下载工具' for node in nodes(value['toolsXml']))
    events = value['events']
    assert isinstance(events, list) and 3 <= len(events) <= 19
    assert all(type(event['sequence']) is int for event in events)
    assert [event['sequence'] for event in events] == list(range(1, len(events) + 1))
    assert all(type(event['atMs']) is int and event['atMs'] > 0 for event in events)
    assert [event['atMs'] for event in events] == sorted(event['atMs'] for event in events)
    taps = [event for event in events if event['kind'] == 'tap']
    assert len(taps) == 2 and [event['target'] for event in taps] == ['保存位置', '展开下载工具']
    for event, node in zip(taps, (icon, tools)):
        rectangle = bounds(node)
        assert all(type(event[key]) is list and all(type(n) is int for n in event[key]) for key in ('bounds', 'point'))
        assert event['bounds'] == rectangle
        assert event['point'] == [(rectangle[0] + rectangle[2]) // 2, (rectangle[1] + rectangle[3]) // 2]
    assert events[0] == taps[0] and events[1]['kind'] == 'back' and events[1]['keyCode'] == 4
    assert sum(event['kind'] == 'back' for event in events) == 1
    swipes = [event for event in events if event['kind'] == 'swipe']
    assert len(swipes) <= 16 and all(event['kind'] in ('tap', 'back', 'swipe') for event in events)
    tools_index = events.index(taps[1])
    for group, stage in ((events[2:tools_index], 'reveal-tools'), (events[tools_index + 1:], 'reveal-label')):
        assert len(group) <= 8 and all(event['kind'] == 'swipe' and event['stage'] == stage for event in group)
    assert all(event['stage'] in ('reveal-tools', 'reveal-label') and event['durationMs'] == 350 for event in swipes)
    for event in swipes:
        assert len(event['from']) == len(event['to']) == 2
        assert all(type(n) is int for n in event['from'] + event['to'])
        assert event['from'][0] == event['to'][0]
        assert (event['from'][1] < event['to'][1]) if event['stage'] == 'reveal-tools' else (event['from'][1] > event['to'][1])
        assert all(0 <= point[0] < record['actualPixels'][0] and 0 <= point[1] < record['actualPixels'][1] for point in (event['from'], event['to']))
    assert all(type(value[key]) is int for key in ('actualAndroidTaps', 'actualAndroidBack', 'actualAndroidSwipes'))
    assert value['actualAndroidTaps'] == 2 and value['actualAndroidBack'] == 1 and value['actualAndroidSwipes'] == len(swipes)
    native = json.loads(record['downloadLocationRaw'])
    assert native['sourceCommit'] == value['sourceCommit'] and native['invocationNonce'] == invocation
    assert all(type(native[key]) is int and native[key] != 0 for key in ('activityIdentity', 'rootIdentity', 'buttonIdentity'))
    expected = [native['left'], native['top'], native['left'] + native['width'], native['top'] + native['height']]
    assert bounds(label) == expected == bounds(control(value['measuredXml'], record, text='保存位置')), 'Native label and actual expanded UI geometry differ'
    for key in ('dialogImage', 'toolsImage', 'dialogXmlFile', 'toolsXmlFile'):
        assert isinstance(value[key], str) and re.fullmatch(r'[A-Za-z0-9_.-]+\.(png|xml)', value[key])
    return value
