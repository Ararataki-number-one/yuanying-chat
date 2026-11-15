"""Strict native geometry and input receipts for the redesigned chrome controls."""
import re
import xml.etree.ElementTree as ET


def rect(value):
    assert type(value) is list and len(value) == 4 and all(type(n) is int for n in value)
    left,top,right,bottom=value
    assert 0 <= left < right and 0 <= top < bottom
    return left,top,right,bottom


def inside(point, rectangle):
    left,top,right,bottom=rect(rectangle)
    assert type(point) is list and len(point)==2 and all(type(n) is int for n in point)
    assert left <= point[0] < right and top <= point[1] < bottom


def address_dialog(xml, package):
    nodes=list(ET.fromstring(xml).iter('node'))
    assert type(package) is str and package.endswith('.test')
    def owned(kind, label, field='text'):
        found=[n for n in nodes if n.attrib.get('package')==package
               and n.attrib.get('class')=='android.widget.'+kind and n.attrib.get(field)==label]
        assert len(found)==1, ('Missing or ambiguous address dialog control',label)
        return found[0]
    owned('TextView','打开网址')
    inputs=[n for n in nodes if n.attrib.get('package')==package and n.attrib.get('class')=='android.widget.EditText']
    assert len(inputs)==1 and inputs[0].attrib.get('enabled')=='true'
    assert inputs[0].attrib.get('content-desc')=='网址或搜索'
    actions=[]
    for label in ('取消','主页','前往'):
        node=owned('Button',label)
        assert node.attrib.get('enabled')==node.attrib.get('clickable')=='true'
        match=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.attrib.get('bounds',''))
        assert match is not None
        rectangle=list(map(int,match.groups()));left,top,right,bottom=rect(rectangle)
        actions.append(dict(label=label,bounds=rectangle,point=[(left+right)//2,(top+bottom)//2]))
    return dict(title='打开网址',editableFields=1,controls=actions)


def verify_browser_address_row(row, density):
    """Measure the real address and four action controls between native rows."""
    left, top, right, bottom = rect(row['bounds'])
    padding = row['padding']
    assert type(padding) is list and len(padding) == 4
    assert all(type(value) is int and value >= 0 for value in padding)
    assert type(row['stacked']) is bool
    controls = row['controls']
    assert [item['name'] for item in controls] == ['back', 'forward', 'address', 'reload', 'home']
    boxes = []
    for item in controls:
        box = rect(item['bounds']); l, t, r, b = box
        assert item['shown'] is True and item['clickable'] is True
        assert left <= l < r <= right and top <= t < b <= bottom
        assert r-l >= 47.9*density and b-t >= 47.9*density
        inside(item['tap'], item['bounds'])
        boxes.append(box)
    back, forward, address, reload, home = boxes
    actions = [back, forward, reload, home]
    assert all(abs((r-l)/density-48) < .34 and abs((b-t)/density-48) < .34 for l,t,r,b in actions)
    assert all(a[2] <= b[0] for a,b in zip(actions, actions[1:]))
    assert all(a[1] == back[1] and a[3] == back[3] for a in actions)
    assert back[0] == left+padding[0] and home[2] == right-padding[2]
    assert forward[0] == back[2] and reload[2] == home[0]
    assert address[2]-address[0] >= 159.9*density
    assert controls[2]['lineCount'] == 1
    assert controls[2]['fontHeight'] <= controls[2]['contentHeight']+1
    if row['stacked']:
        assert address[0] == back[0] and address[2] == home[2]
        assert address[1] == top+padding[1]
        assert abs((back[1]-address[3])/density-4) < .34
        assert bottom == back[3]+padding[3]
    else:
        assert forward[2] == address[0] and address[2] == reload[0]
        assert abs((address[1]+address[3])-(back[1]+back[3])) <= 1
        assert min(address[1],back[1]) == top+padding[1]
        assert bottom == max(address[3],back[3])+padding[3]
    return bottom-top


def verify_layout(layout, width, scale):
    assert type(layout.get('navigationContract')) is int and layout['navigationContract']==2
    assert layout['geckoOnly'] and layout['pageMode'] and layout['noNativeChat'] and layout['systemWebViews']==0
    assert abs(layout['viewportDp']-width)<.01 and abs(layout['fontScale']-scale)<.01
    assert layout['syntheticPresentation'] is True and layout['actualLatencyMeasurement'] is False
    assert layout['latency']==layout['expectedLatency']=='42 ms（02:00）'
    assert not layout['networkClickable'] and not layout['networkFocusable']
    assert layout['networkBackground']=='none' and '点击' not in layout['networkDescription']
    tl,tt,tr,tb=rect(layout['toolbar']);density=(tr-tl)/width
    assert abs(density-3)<.01
    top=rect(layout['topBounds']);network=rect(layout['networkBounds'])
    browser_height = 0
    if layout.get('browserChrome') is True:
        row = layout['browserAddressRow']
        browser_height = verify_browser_address_row(row, density)
        assert tl <= row['bounds'][0] < row['bounds'][2] <= tr, 'Browser address row lies outside the toolbar'
        assert top[3] == row['bounds'][1] and row['bounds'][3] == network[1]
    else:
        assert 'browserAddressRow' not in layout
        assert top[3] == network[1]
    assert top[1] == tt and network[3] == tb
    assert abs(layout['toolbarHeightDp']-(layout['topHeightDp']+browser_height/density+layout['networkHeightDp']))<.34
    assert layout['networkHeightDp']>=20
    controls=layout['controls']
    assert [c['name'] for c in controls]==['drawer','environment','more']
    capsule=rect(controls[1]['visible']);capsule_height=(capsule[3]-capsule[1])/density
    assert 51.9 <= capsule_height <= max(52,32*scale+12)+.34
    assert abs(layout['topHeightDp']-(capsule_height+4))<.67
    for control in controls:
        left,t,right,b=rect(control['touch']);vl,vt,vr,vb=rect(control['visible'])
        assert control['widthDp']>=47.9 and control['heightDp']>=47.9
        assert tl<=left<right<=tr and tt<=t<b<=tb
        assert left<=vl<vr<=right and t<=vt<vb<=b
        inside(control['tap'],control['touch'])
        assert b<=layout['networkTap'][1], 'Header touch region covers read-only network center'
    assert all(a['touch'][2]<=b['touch'][0] for a,b in zip(controls,controls[1:]))
    dot=layout['decorativeDot']
    assert abs(dot['textSizeDp']-9)<.01 and dot['inkWidth']<=dot['contentWidth']+1
    assert dot['fontHeight']<=dot['contentHeight']+1
    texts=layout['texts'];assert len(texts)==4
    for index,text in enumerate(texts):
        assert text['fontHeight']<=text['contentHeight']+1
        assert text['text'] not in ('简洁','原网页')
        assert type(text['lineCount']) is int and 1<=text['lineCount']<=(1,2,2,1)[index]
        assert text['maxLines']==(1,2,2,1)[index]
        assert text['layoutHeight']>0 and text['layoutHeight']<=text['contentHeight']+1
        assert text['textSizePx']>0 and abs(text['textSizePx']-text['expectedTextSizePx'])<.01
        if index:
            # Native fallback layout, at most two lines and the fixed two-dp
            # role spacing. Extra blank vertical space cannot pass this bound.
            assert text['contentHeight']<=text['layoutHeight']+1
            assert text['layoutHeight']/density <= text['expectedTextSizePx']/density*1.8*text['lineCount']+6
        if text['text'] in ('42 ms（02:00）','已连接'):
            assert not text['ellipsized'] and text['inkWidth']<=text['contentWidth']+1
    if scale==2:assert texts[0]['ellipsized']
    address_height=max(texts[1]['bounds'][3]-texts[1]['bounds'][1],dot['height'])
    metrics_height=max(t['bounds'][3]-t['bounds'][1] for t in texts[2:])
    assert network[3]-network[1] <= address_height+metrics_height+4*density+2
    inside(layout['networkTap'],layout['networkBounds'])
    inside(layout['stateTap'],texts[3]['bounds'])
    return True


def verify_case(case, *, require_browser_chrome):
    # Missing current evidence must never silently select a historical layout.
    assert type(require_browser_chrome) is bool
    assert type(case.get('navigationContract')) is int and case['navigationContract']==2
    assert (case['viewport'],case['fontScale']) in ((360,1),(412,1),(360,2))
    if require_browser_chrome:
        assert case['layout'].get('browserChrome') is True, 'Current browser address controls must be measured'
    verify_layout(case['layout'],case['viewport'],case['fontScale'])
    assert case['readOnlyStatus'] is True
    status=case['statusObservation']
    assert all(type(status[key]) is int for key in ('beforeActions','afterActions','afterPage'))
    assert status['beforeActions']==status['afterActions']==0 and status['afterPage']==0
    assert status['points']==[case['layout']['networkTap'],case['layout']['stateTap']]
    taps=case['actualAndroidTaps']
    assert [t['control'] for t in taps]==['drawer','address','cancel-address','more']
    for tap in taps:
        assert tap['actualAndroidTap'] is True
        inside(tap['point'],tap['bounds'])
    assert [t['action'] for t in taps]==['activity:local.pocketchat.WindowHomeActivity','address-dialog','cancel-address-dialog','more']
    # Input receipts must use the measured native controls, not a rectangle
    # supplied by the receipt itself. This fixture changes no header geometry.
    for tap_index,control_index in ((0,0),(1,1),(3,2)):
        target=case['layout']['controls'][control_index]
        assert taps[tap_index]['bounds']==target['touch'] and taps[tap_index]['point']==target['tap']
    assert case['managementNavigation']==dict(activity='local.pocketchat.WindowHomeActivity',actualDrawerTap=True,resumedThenReturned=True)
    dialog=case['addressDialog']
    assert dialog['title']=='打开网址' and dialog['editableFields']==1 and dialog['cancelled'] is True
    assert [c['label'] for c in dialog['controls']]==['取消','主页','前往']
    assert all(type(dialog[key]) is int and dialog[key]>=0 for key in ('actionsBefore','actionsAfter'))
    assert dialog['actionsBefore']==dialog['actionsAfter']
    cancel=dialog['controls'][0]
    assert taps[2]['point']==cancel['point'] and taps[2]['bounds']==cancel['bounds']
    long_press=case['actualAndroidLongPress']
    assert all(type(long_press[key]) is int and long_press[key]>=0 for key in ('actionsBefore','actionsAfter'))
    assert long_press['control']=='environment' and long_press['action']=='environment'
    assert type(long_press['durationMs']) is int and long_press['durationMs']==700
    assert long_press['actionsAfter']==long_press['actionsBefore']+1
    assert long_press['bounds']==case['layout']['controls'][1]['visible']
    inside(long_press['point'],long_press['bounds'])
    sheet=case['environmentSheet']
    assert sheet['title']=='快速切换环境' and sheet['currentSlot']==0
    assert sheet['searchDescription']=='搜索要切换的环境' and sheet['closeDescription']=='关闭快速切换环境'
    assert case['menuDismissedByBack'] is True and case['environmentDismissedByBack'] is True
    return True
