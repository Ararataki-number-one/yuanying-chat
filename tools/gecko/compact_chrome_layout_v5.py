"""Version 5 header: compact network strip with expanded, disjoint touch regions.

This reads the new native geometry and its original input receipts. Historical
v4 results remain with the v4 reader; no old action is relabelled as a new one.
"""
import hashlib
import re
import xml.etree.ElementTree as ET

if __package__:
    from .browser_header_contract_v5 import verify_header, network_extension
    from .compact_chrome_layout_v2 import address_dialog, inside, rect
    from .workspace_navigation_contract_v4 import bounds, menu_action, navigation, verify_menu_scrolls
else:
    from browser_header_contract_v5 import verify_header, network_extension
    from compact_chrome_layout_v2 import address_dialog, inside, rect
    from workspace_navigation_contract_v4 import bounds, menu_action, navigation, verify_menu_scrolls


def network_dialog_visible(xml, package):
    """Read NetworkMetricsUi's native AlertDialog, not a custom browser sheet."""
    tree=ET.fromstring(xml); nodes=list(tree.iter('node'))
    parents={child:parent for parent in tree.iter() for child in parent}
    ids=('alertTitle','parentPanel','topPanel','customPanel','buttonPanel','button1','button2','button3')
    markers=[n for n in nodes if n.get('resource-id') in ('android:id/'+v for v in ids)
             or n.get('text')=='网络情况' or n.get('content-desc')=='网络情况']
    if not markers:
        navigation(xml,package,conversation=True)
        return False

    def unique(identifier):
        found=[n for n in nodes if n.get('resource-id')=='android:id/'+identifier]
        assert len(found)==1, 'The native network dialog must own one '+identifier
        return found[0]

    def contained(node, ancestor, *, enabled=True):
        current=node
        while True:
            assert current.get('package')==package and current.get('visible-to-user')!='false'
            assert current.get('enabled') in ('true','false')
            if enabled or current is not node:
                assert current.get('enabled')=='true'
            l,t,r,b=bounds(current)
            if current is ancestor:
                return
            parent=parents.get(current); assert parent is not None and parent.tag=='node'
            pl,pt,pr,pb=bounds(parent)
            assert pl<=l<r<=pr and pt<=t<b<=pb, 'Native dialog controls must remain in their actual window'
            current=parent

    panel=unique('parentPanel'); top=unique('topPanel'); body=unique('customPanel'); buttons=unique('buttonPanel')
    window=panel
    while parents.get(window) is not None and parents[window].tag=='node':
        window=parents[window]
    assert parents.get(window) is tree and tree.tag=='hierarchy'
    contained(panel,window)
    assert panel.get('class')==top.get('class')=='android.widget.LinearLayout'
    assert body.get('class')=='android.widget.FrameLayout'
    assert buttons.get('class') in ('android.widget.ScrollView','android.widget.LinearLayout')
    for part in (top,body,buttons):
        assert parents.get(part) is panel
        contained(part,panel)
    assert bounds(top)[3]<=bounds(body)[1]<bounds(body)[3]<=bounds(buttons)[1]
    title=unique('alertTitle')
    headings=[n for n in nodes if n.get('text')=='网络情况' or n.get('content-desc')=='网络情况']
    assert len(headings)==1 and headings[0] is title
    assert title.get('class')=='android.widget.TextView' and title.get('text')=='网络情况'
    # Android's alertTitle has no redundant content-description in the original
    # device XML. Its text, resource id, role and native window establish identity.
    contained(title,top)
    details=[n for n in nodes if n.get('content-desc')=='当前环境网络详情']
    assert len(details)==1 and details[0].get('class')=='android.widget.ScrollView'
    contained(details[0],body)
    # Native footer contains only the exit action. Optional network actions live
    # in the real scrollable body and may be outside its first visible viewport.
    assert not any(n.get('resource-id') in ('android:id/button1','android:id/button3') for n in nodes)
    close=unique('button2')
    assert close.get('class')=='android.widget.Button' and close.get('text')=='关闭'
    assert close.get('clickable')=='true'
    contained(close,buttons)
    footer_controls=[n for n in buttons.iter('node') if n.get('class')=='android.widget.Button']
    assert footer_controls==[close], 'The native footer must expose only its close action'
    l,t,r,b=bounds(close)
    assert min(r-l,b-t)>=144, 'The native close control retains its 48 dp target'
    for description,labels in (('测一下网络延迟',('测一下延迟','正在测量…')),
                               ('查看当前网络连接详情',('连接详情',))):
        visible=[n for n in nodes if n.get('content-desc')==description or n.get('text') in labels]
        assert len(visible)<=1
        if visible:
            control=visible[0]
            assert control.get('class')=='android.widget.Button' and control.get('text') in labels
            assert control.get('content-desc')==description and control.get('clickable')=='true'
            contained(control,details[0],enabled=description=='查看当前网络连接详情')
    return True


def text_metrics(value, lines):
    assert value['fontHeight'] <= value['contentHeight']+1
    assert type(value['lineCount']) is int and 1 <= value['lineCount'] <= lines
    assert value['maxLines'] == lines
    assert 0 < value['layoutHeight'] <= value['contentHeight']+1
    assert value['textSizePx'] > 0 and abs(value['textSizePx']-value['expectedTextSizePx']) < .01


def verify_browser_address_row(row, density):
    left, top, right, bottom = rect(row['bounds'])
    assert row['shown'] is row['parentIsConversationBar'] is True
    assert type(row['stacked']) is bool
    padding = row['padding']
    assert padding == [round(n*density) for n in (4,6,4,8)]
    controls = row['controls']
    assert [v['name'] for v in controls] == ['home','windows','address','tools','menu']
    boxes = []
    for index, value in enumerate(controls):
        l,t,r,b = rect(value['bounds'])
        assert value['shown'] is value['clickable'] is True
        assert value['enabled'] is True
        assert left <= l < r <= right and top <= t < b <= bottom
        assert r-l >= 47.9*density and b-t >= 47.9*density
        inside(value['tap'], value['bounds'])
        assert value['tap'] == [(l+r)//2,(t+b)//2]
        boxes.append((l,t,r,b))
    assert controls[0]['description'] == '打开当前环境主页'
    assert controls[1]['description'] == '网页窗口'
    assert re.fullmatch(r'当前网址 .+，点击输入网址或搜索', controls[2]['description'])
    assert controls[3]['description'] == '网页工具'
    assert controls[4]['description'] == '浏览器菜单'
    back,home,address,reload,menu = boxes
    actions = [back,home,reload,menu]
    assert all(abs((r-l)/density-48) < .34 and abs((b-t)/density-48) < .34 for l,t,r,b in actions)
    assert all(a[2] <= b[0] for a,b in zip(actions,actions[1:]))
    assert all(a[1] == back[1] and a[3] == back[3] for a in actions)
    assert back[0] == left+padding[0] and menu[2] == right-padding[2]
    text_metrics(controls[2]['text'],1)
    if row['stacked']:
        assert (right-left)/density < 280.34
        assert address[0] == back[0] and address[2] == menu[2] and address[1] == top+padding[1]
        assert abs((back[1]-address[3])/density-4) < .34
        assert bottom == back[3]+padding[3]
    else:
        assert back[2] == home[0] and reload[2] == menu[0]
        assert abs((address[0]-home[2])/density-4) < .34
        assert abs((reload[0]-address[2])/density-4) < .34
        assert address[2]-address[0] >= 71.9*density
        assert abs(address[1]+address[3]-back[1]-back[3]) <= 1
        assert min(address[1],back[1]) == top+padding[1]
        assert bottom == max(address[3],back[3])+padding[3]
    return True


def verify_layout(layout, width, scale):
    verify_header(layout)
    assert type(layout.get('navigationContract')) is int and layout['navigationContract'] == 4
    assert layout['browserChrome'] is True
    assert layout['geckoOnly'] and layout['pageMode'] and layout['noNativeChat'] and layout['systemWebViews'] == 0
    assert abs(layout['viewportDp']-width) < .01 and abs(layout['fontScale']-scale) < .01
    assert layout['syntheticPresentation'] is True and layout['actualLatencyMeasurement'] is False
    assert layout['latency'] == layout['expectedLatency'] == '42 ms（02:00）'
    assert layout['networkInHeader'] is True and layout['topChildren'] == 1
    tl,tt,tr,tb = rect(layout['toolbar']); density=(tr-tl)/width
    assert abs(density-3) < .01
    top = rect(layout['topBounds'])
    assert top[1] == tt and top[3] < tb
    assert abs(layout['topHeightDp']-(top[3]-top[1])/density) < .34
    verify_status(layout)
    network = rect(layout['networkMetrics']['bounds'])
    assert top[3] <= network[1] < network[3] <= tb
    row=layout['browserAddressRow']; verify_browser_address_row(row,density)
    assert row['stacked'] is False, 'Normal and enlarged-font browser must use one bottom row'
    wl,wt,wr,wb = rect(layout['windowBounds'])
    web=rect(layout['webBounds'])
    assert tb <= web[1] < web[3] <= row['bounds'][1] < row['bounds'][3] <= wb
    assert wl <= row['bounds'][0] < row['bounds'][2] <= wr
    controls=layout['controls']; assert [c['name'] for c in controls] == ['environment']
    capsule=rect(controls[0]['visible']); control=controls[0]
    l,t,r,b=rect(control['touch'])
    assert control['widthDp'] >= 47.9 and control['heightDp'] >= 47.9
    assert tl <= l < r <= tr and tt <= t < b <= tb
    assert l <= capsule[0] < capsule[2] <= r and t <= capsule[1] < capsule[3] <= b
    inside(control['tap'],control['touch'])
    capsule_height=(capsule[3]-capsule[1])/density
    assert 35.9 <= capsule_height <= max(36,32*scale+8)+.34
    assert 0 <= (capsule[1]-top[1])/density <= 4.34
    assert 47.9 <= layout['topHeightDp'] <= max(48,capsule_height+4)+.67
    text_metrics(layout['capsuleText'],1)
    if scale == 2: assert layout['capsuleText']['ellipsized']
    return True


def verify_status(layout):
    verify_header(layout)
    assert layout['networkInHeader'] is True and layout['networkShown'] is True
    status=layout['networkMetrics']; box=rect(status['bounds']); density=3
    assert status['clickable'] is status['focusable'] is True
    assert status['background'] == 'android.graphics.drawable.RippleDrawable'
    assert status['description'].startswith('当前环境网络：')
    texts=status['texts']; assert len(texts) == 3
    for value,lines in zip(texts,(2,2,1)):
        text_metrics(value,lines)
        assert value['contentHeight'] <= value['layoutHeight']+1
        assert value['layoutHeight']/density <= value['expectedTextSizePx']/density*1.8*value['lineCount']+6
        if value['text'] in ('42 ms（02:00）','已连接'):
            assert value['ellipsized'] is False and value['inkWidth'] <= value['contentWidth']+1
    dot=status['dot']
    assert abs(dot['textSizeDp']-9) < .01 and dot['inkWidth'] <= dot['contentWidth']+1
    assert dot['fontHeight'] <= dot['contentHeight']+1
    address_height=max(texts[0]['bounds'][3]-texts[0]['bounds'][1],dot['height'])
    metrics_height=max(v['bounds'][3]-v['bounds'][1] for v in texts[1:])
    assert 27.9*density <= box[3]-box[1] <= max(48*density,address_height+metrics_height+4*density+2)
    inside(status['networkTap'],status['bounds']); inside(status['stateTap'],texts[2]['bounds'])


def verify_case(case, *, require_browser_chrome=True):
    assert require_browser_chrome is True
    assert type(case.get('headerContract')) is int and case['headerContract'] == 5
    assert type(case.get('navigationContract')) is int and case['navigationContract'] == 4
    assert (case['viewport'],case['fontScale']) in ((360,1),(412,1),(360,2))
    verify_layout(case['layout'],case['viewport'],case['fontScale'])
    assert case['layout']['networkShown'] is True and case['layout']['networkMetrics'] is not None
    taps=case['actualAndroidTaps']
    assert [v['control'] for v in taps] == ['menu-management','management','address','cancel-address','environment','windows','tools','network-status','network-state','network-extension']
    for value in taps:
        assert value['actualAndroidTap'] is True; inside(value['point'],value['bounds'])
    for tap_index,control_index in ((0,4),(2,2),(5,1),(6,3)):
        control=case['layout']['browserAddressRow']['controls'][control_index]
        assert taps[tap_index]['point'] == control['tap'] and taps[tap_index]['bounds'] == control['bounds']
    verify_menu_scrolls(case['menuScrolls'],'local.pocketchat.test','管理全部环境')
    raw=case['managementMenuXml']; target=menu_action(raw,'local.pocketchat.test','管理全部环境')
    assert taps[1]['point'] == target['point'] and taps[1]['bounds'] == target['bounds']
    assert case['managementNavigation'] == dict(activity='local.pocketchat.WindowHomeActivity',actualMenuAction=True,resumedThenReturned=True)
    dialog=case['addressDialog']; observed=address_dialog(dialog['rawXml'],'local.pocketchat.test')
    assert dialog['rawXmlSha256'] == hashlib.sha256(dialog['rawXml'].encode()).hexdigest()
    assert dialog['controls'] == observed['controls'] and dialog['cancelled'] is True
    assert dialog['actionsBefore'] == dialog['actionsAfter']
    assert taps[3]['point'] == observed['controls'][0]['point'] and taps[3]['bounds'] == observed['controls'][0]['bounds']
    environment=case['environmentSelection']
    assert environment['action'] == 'environment' and environment['actionsAfter'] == environment['actionsBefore']+1
    assert environment['addressDialogOpened'] is False and environment['inputKind'] == 'tap'
    assert taps[4]['bounds'] == case['layout']['controls'][0]['touch']
    inside(taps[4]['point'], taps[4]['bounds'])
    sheet=case['environmentSheet']
    assert sheet['title'] == '快速切换环境' and sheet['currentSlot'] == 0
    assert sheet['searchDescription'] == '搜索要切换的环境' and sheet['closeDescription'] == '关闭快速切换环境'
    for key,title in (('windowSheet','网页窗口'),('toolsSheet','网页工具')):
        raw=case[key]['rawXml']; nodes=list(ET.fromstring(raw).iter('node'))
        assert case[key]['rawXmlSha256'] == hashlib.sha256(raw.encode()).hexdigest()
        assert len([n for n in nodes if n.get('package') == 'local.pocketchat.test' and n.get('class') == 'android.widget.TextView' and n.get('text') == n.get('content-desc') == title]) == 1
        closes=[n for n in nodes if n.get('package') == 'local.pocketchat.test' and n.get('class') == 'android.widget.Button' and n.get('content-desc') == '关闭'+title]
        assert len(closes)==1 and closes[0].get('enabled')==closes[0].get('clickable')=='true'
        match=re.fullmatch(r'\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]',closes[0].get('bounds',''))
        assert match is not None
        l,t,r,b=map(int,match.groups());assert min(r-l,b-t)>=144
        assert not any(n.get('text') == '打开网址' for n in nodes)
        assert case[key]['dismissedByBack'] is True
    nodes=list(ET.fromstring(case['toolsSheet']['rawXml']).iter('node'))
    for labels in (('后退',),('前进',),('刷新网页','停止加载'),('复制当前网址',),('进入专注阅读',)):
        matches=[n for n in nodes if n.get('package') == 'local.pocketchat.test' and n.get('class') == 'android.widget.Button' and n.get('text') in labels]
        assert len(matches) == 1 and matches[0].get('clickable') == 'true'
        assert matches[0].get('visible-to-user')!='false'
    windows=list(ET.fromstring(case['windowSheet']['rawXml']).iter('node'))
    assert not any(n.get('text')=='快速切换环境' for n in windows)
    before,after=case['statusObservation']['before'],case['statusObservation']['after']
    verify_status(before); verify_status(after)
    assert before['actions'] == after['actions'] and before['page'] == after['page'] == 0
    assert before['networkMetrics'] == after['networkMetrics']
    status=before['networkMetrics']
    assert taps[7]['point'] == status['networkTap'] and taps[7]['bounds'] == status['bounds']
    assert taps[8]['point'] == status['stateTap'] and taps[8]['bounds'] == status['texts'][2]['bounds']
    extension=network_extension(before)
    assert taps[9]['point'] == extension['point'] and taps[9]['bounds'] == extension['bounds']
    assert case['networkDetailsFromHeader'] is case['environmentDismissedByBack'] is True
    details=case['networkDetails']; assert len(details)==3
    for value in details:
        raw=value['rawXml']; assert value['rawXmlSha256'] == hashlib.sha256(raw.encode()).hexdigest()
        assert network_dialog_visible(raw,'local.pocketchat.test') is True
        assert value['dismissedByBack'] is True
    return True
