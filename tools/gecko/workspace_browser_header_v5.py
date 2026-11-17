"""Current compact header XML cross-checked against its live native delegate.

The bottom browser toolbar remains navigation contract 4. Historical v4 header
XML keeps its original 48 dp visible-row requirement in its original reader.
"""
import json
import re
import xml.etree.ElementTree as ET
try:
    from .workspace_navigation_contract_v4 import navigation, bounds
    from .browser_header_contract_v5 import verify_header
except ImportError:
    from workspace_navigation_contract_v4 import navigation, bounds
    from browser_header_contract_v5 import verify_header


def native_observation(raw, nonce, source):
    def pairs(values):
        result = {}
        for key, value in values:
            assert key not in result, 'Duplicate header field'
            result[key] = value
        return result
    assert type(raw) is str and 0 < len(raw.encode('utf-8')) <= 3500
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite native header')))
    assert value['schema'] == 1 and value['headerContract'] == 5 and value['status'] == 'observed'
    assert value['scene'] == 'chat' and value['nonce'] == nonce and re.fullmatch('[0-9a-f]{32}', nonce)
    assert value['sourceCommit'] == source and re.fullmatch('[0-9a-f]{40}', source)
    assert value['actualAndroidLayout'] is value['windowFocused'] is True and value['layoutRequested'] is False
    assert value['engine'] in ('gecko', 'chromium')
    assert value['activityClass'] in ('local.pocketchat.MainActivity', 'local.pocketchat.BrowserActivity')
    assert type(value['activityIdentity']) is type(value['delegateIdentity']) is int
    assert value['activityIdentity'] != 0 and value['delegateIdentity'] != 0
    assert 0 < value['startedUptimeMs'] <= value['observedUptimeMs']
    assert value['density'] == value['layout']['density']
    verify_header(value['layout'])
    return value


def conversation_header(xml, package, width, height, scale, environment, *, browser=False, native):
    result = navigation(xml, package, conversation=True, browser=browser)
    verify_header(native['layout'])
    assert native['fontScale'] == scale and abs(native['density']-3) < .01
    nodes = list(ET.fromstring(xml).iter('node'))
    capsules = [n for n in nodes if n.get('package') == package and n.get('content-desc', '').startswith('当前环境：')]
    assert len(capsules) == 1
    capsule = capsules[0]
    assert capsule.get('content-desc') == f'当前环境：{environment}，点按切换环境'
    assert capsule.get('class') == 'android.widget.Button'
    assert capsule.get('clickable') == 'true' and capsule.get('long-clickable') == 'false'
    status = [n for n in nodes if n.get('package') == package and n.get('content-desc', '').startswith('当前环境网络：')]
    assert len(status) == 1 and status[0].get('clickable') == status[0].get('enabled') == 'true'
    assert status[0].get('class') == 'android.widget.Button' and status[0].get('visible-to-user') != 'false'
    status_bounds = bounds(status[0])
    assert min(status_bounds[2]-status_bounds[0],status_bounds[3]-status_bounds[1]) >= 28*3
    assert status_bounds == native['layout']['networkMetrics']['bounds']
    assert not any(n.get('package') == package and n.get('content-desc') in ('管理环境', '更多') for n in nodes)
    l, t, r, b = bounds(capsule)
    assert [l,t,r,b] == native['capsuleAccessibilityBounds']
    assert 0 <= l < r <= width*3 and 0 <= t < b < result['toolbarBounds'][1] < height*3
    assert b-t >= 36*3 and abs(result['density']-3) < .01
    tree = ET.fromstring(xml); parents = {child: parent for parent in tree.iter() for child in parent}
    actual = next(n for n in tree.iter('node') if n.get('package') == package and n.get('content-desc') == capsule.get('content-desc'))
    host = parents[actual]; hl,ht,hr,hb = bounds(host)
    assert host.get('class') == 'android.widget.FrameLayout' and min(hr-hl,hb-ht) >= 48*3
    assert hl <= l < r <= hr and ht <= t < b <= hb <= status_bounds[1]
    assert status_bounds[1] < status_bounds[3] <= result['toolbarBounds'][1]
    for control in result['controls']:
        cl, ct, cr, cb = control['bounds']
        assert 0 <= cl < cr <= width*3 and b < ct < cb <= height*3
        assert cr-cl >= 48*3 and cb-ct >= 48*3
    result.update(environment=environment, capsuleBounds=[l,t,r,b],
                  environmentTapOnlyDescribed=True, networkStatusInHeader=True, networkBounds=status_bounds, capsuleHostBounds=[hl,ht,hr,hb])
    result['headerContract'] = 5
    return result



def verify_capture(record, source):
    assert record['headerContract'] == 5 and record['scene'] == 'chat'
    native = native_observation(record['browserHeaderRaw'], record['browserHeaderNonce'], source)
    width, height = map(int, record['logicalViewport'].split('x'))
    assert record['actualPixels'] == [width*3, height*3] and record['densityDpi'] == 480
    assert native['windowBounds'] == [0,0,width*3,height*3]
    left, top, right, bottom = native['layout']['toolbar']
    assert 0 <= left < right <= width*3 and 0 <= top < bottom <= height*3
    # System side insets reduce the measured header width in landscape.
    assert 0 < native['layout']['viewportDp'] <= width
    assert native['fontScale'] == record['fontScale']
    return conversation_header(record['browserHeaderRawXml'], 'local.pocketchat.test', width, height,
                               record['fontScale'], '日常会话', browser=True, native=native)
