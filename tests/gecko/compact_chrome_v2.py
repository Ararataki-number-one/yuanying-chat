"""Execute current header taps and long-press on the real Android chrome."""
from compact_chrome_layout_v2 import address_dialog, verify_layout, verify_case


def run_case(adb, adb_bytes, dump, event, focus, visible, quick_sheet, shots, package, width, scale):
    component=package+'/local.pocketchat.CompactChromeIntegrationActivity'
    adb('shell','am','force-stop',package);adb('logcat','-c')
    adb('shell','wm','size',f'{width*3}x1920');adb('shell','wm','density','480')
    adb('shell','settings','put','system','font_scale',str(scale))
    command=f'compact-v2-{width}-{scale}'
    adb('shell','am','start','-W','-n',component,'--es','compactCommand',command)
    sample=event(command,'ready')
    verify_layout(sample,width,scale)
    stem=f'compact-chrome-{width}-font{scale}'
    (shots/(stem+'.xml')).write_text(dump())
    (shots/(stem+'.png')).write_bytes(adb_bytes('exec-out','screencap','-p'))

    def snapshot(name):
        nonlocal command
        command+='-'+name
        adb('shell','am','start','-W','--activity-single-top','-n',component,
            '--es','compactAction','snapshot','--es','compactCommand',command)
        return event(command,'snapshot')

    taps=[]
    def tap(control, point, rectangle, action):
        adb('shell','input','tap',*map(str,point))
        taps.append(dict(control=control,point=point,bounds=rectangle,action=action,actualAndroidTap=True))

    for point in (sample['networkTap'],sample['stateTap']):
        adb('shell','input','tap',*map(str,point))
    status=snapshot('status')
    assert sample['actions']==status['actions']==0 and status['page']==0
    before=snapshot('drawer');control=before['controls'][0]
    tap('drawer',control['tap'],control['touch'],'activity:local.pocketchat.WindowHomeActivity')
    action=event(command,'action')
    assert action['action']=='activity:local.pocketchat.WindowHomeActivity' and action['actions']==before['actions']+1 and action['page']==0
    focus('local.pocketchat.WindowHomeActivity')
    adb('shell','input','keyevent','KEYCODE_BACK');focus('local.pocketchat.CompactChromeIntegrationActivity')
    management=dict(activity='local.pocketchat.WindowHomeActivity',actualDrawerTap=True,resumedThenReturned=True)

    before=snapshot('address');control=before['controls'][1]
    tap('address',control['tap'],control['touch'],'address-dialog')
    visible('打开网址')
    address_xml=dump();dialog=address_dialog(address_xml,package)
    (shots/(stem+'-address.xml')).write_text(address_xml)
    cancel=dialog['controls'][0]
    tap('cancel-address',cancel['point'],cancel['bounds'],'cancel-address-dialog')
    visible('打开网址',False)
    after=snapshot('address-cancelled')
    assert after['actions']==before['actions'] and after['page']==0
    dialog.update(cancelled=True,actionsBefore=before['actions'],actionsAfter=after['actions'])

    before=snapshot('environment');control=before['controls'][1]
    left,top,right,bottom=control['visible'];point=[(left+right)//2,(top+bottom)//2]
    adb('shell','input','swipe',str(point[0]),str(point[1]),str(point[0]),str(point[1]),'700')
    action=event(command,'action')
    assert action['action']=='environment' and action['actions']==before['actions']+1 and action['page']==0
    visible('快速切换环境');sheet_xml=dump();sheet=quick_sheet(sheet_xml,0,package)
    (shots/(stem+'-environment.xml')).write_text(sheet_xml)
    adb('shell','input','keyevent','KEYCODE_BACK');visible('快速切换环境',False)
    long_press=dict(control='environment',action='environment',point=point,bounds=control['visible'],
                    durationMs=700,actionsBefore=before['actions'],actionsAfter=action['actions'])

    before=snapshot('more');control=before['controls'][2]
    tap('more',control['tap'],control['touch'],'more')
    action=event(command,'action')
    assert action['action']=='more' and action['actions']==before['actions']+1 and action['page']==0
    visible('浏览器菜单');adb('shell','input','keyevent','KEYCODE_BACK');visible('浏览器菜单',False)
    command+='-performance'
    adb('shell','am','start','-W','--activity-single-top','-n',component,
        '--es','compactAction','performance','--es','compactCommand',command)
    performance=event(command,'performance');assert performance['status']=='passed'
    case=dict(navigationContract=2,viewport=width,fontScale=scale,image=stem+'.png',xml=stem+'.xml',
        readOnlyStatus=True,statusObservation=dict(beforeActions=sample['actions'],afterActions=status['actions'],
            afterPage=status['page'],points=[sample['networkTap'],sample['stateTap']]),
        actualAndroidTaps=taps,actualAndroidLongPress=long_press,layout=sample,
        performance=performance['performance'],environmentSheet=sheet,managementNavigation=management,
        addressDialog=dialog,menuDismissedByBack=True,environmentDismissedByBack=True)
    verify_case(case)
    return case
