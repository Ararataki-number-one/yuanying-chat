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
    assert top[1]==tt and top[3]==network[1] and network[3]==tb
    assert abs(layout['toolbarHeightDp']-(layout['topHeightDp']+layout['networkHeightDp']))<.34
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


def verify_case(case):
    assert type(case.get('navigationContract')) is int and case['navigationContract']==2
    assert (case['viewport'],case['fontScale']) in ((360,1),(412,1),(360,2))
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
