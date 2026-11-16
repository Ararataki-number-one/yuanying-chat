"""Exercise the actual bottom address, browser menu and retained environment capsule."""
import hashlib
import time
from compact_chrome_layout_v3 import address_dialog, verify_layout, verify_case
from workspace_navigation_contract_v3 import seek_menu_action


def run_case(adb, adb_bytes, dump, event, focus, visible, quick_sheet, shots, package, width, scale):
    component=package+'/local.pocketchat.CompactChromeIntegrationActivity'
    adb('shell','am','force-stop',package); adb('logcat','-c')
    adb('shell','wm','size',f'{width*3}x1920'); adb('shell','wm','density','480')
    adb('shell','settings','put','system','font_scale',str(scale))
    command=f'compact-v3-{width}-{scale}'
    adb('shell','am','start','-W','-n',component,'--es','compactCommand',command)
    sample=event(command,'ready'); verify_layout(sample,width,scale)
    stem=f'compact-chrome-{width}-font{scale}'
    (shots/(stem+'.xml')).write_text(dump()); (shots/(stem+'.png')).write_bytes(adb_bytes('exec-out','screencap','-p'))
    taps=[]; menu_scrolls=[]

    def snapshot(name):
        nonlocal command
        command+='-'+name
        adb('shell','am','start','-W','--activity-single-top','-n',component,'--es','compactAction','snapshot','--es','compactCommand',command)
        return event(command,'snapshot')

    def tap(name,point,box):
        adb('shell','input','tap',*map(str,point))
        taps.append(dict(control=name,point=point,bounds=box,actualAndroidTap=True))

    before=snapshot('management'); menu=before['browserAddressRow']['controls'][4]
    tap('menu-management',menu['tap'],menu['bounds'])
    action=event(command,'action'); assert action['action']=='more' and action['actions']==before['actions']+1
    management_xml,target=seek_menu_action(adb,dump,package,'管理全部环境',deadline=time.monotonic()+20,scrolls=menu_scrolls)
    (shots/(stem+'-management-menu.xml')).write_text(management_xml)
    tap('management',target['point'],target['bounds'])
    # The production startActivity call, not fixture navigation, owns this event.
    focus('local.pocketchat.WindowHomeActivity')
    adb('shell','input','keyevent','KEYCODE_BACK'); focus('local.pocketchat.CompactChromeIntegrationActivity')

    before=snapshot('address'); control=before['browserAddressRow']['controls'][2]
    tap('address',control['tap'],control['bounds']); visible('打开网址')
    deadline=time.monotonic()+20
    address_xml=dump(deadline=deadline); address_dialog(address_xml,package)
    # Preserve the first frame, then use only fresh post-IME native geometry.
    (shots/(stem+'-address-initial.xml')).write_text(address_xml)
    address_xml=dump(deadline=deadline); dialog=address_dialog(address_xml,package)
    (shots/(stem+'-address.xml')).write_text(address_xml)
    assert time.monotonic()<deadline
    cancel=dialog['controls'][0]; tap('cancel-address',cancel['point'],cancel['bounds'])
    visible('打开网址',False); after=snapshot('address-cancelled')
    assert after['actions']==before['actions'] and after['page']==0
    dialog.update(cancelled=True,actionsBefore=before['actions'],actionsAfter=after['actions'],rawXml=address_xml,
                  rawXmlSha256=hashlib.sha256(address_xml.encode()).hexdigest())

    before=snapshot('environment'); control=before['controls'][0]
    l,t,r,b=control['visible']; point=[(l+r)//2,(t+b)//2]
    adb('shell','input','swipe',*map(str,point+point),'700')
    action=event(command,'action'); assert action['action']=='environment' and action['actions']==before['actions']+1
    visible('快速切换环境'); sheet_xml=dump(); sheet=quick_sheet(sheet_xml,0,package)
    (shots/(stem+'-environment.xml')).write_text(sheet_xml)
    adb('shell','input','keyevent','KEYCODE_BACK'); visible('快速切换环境',False)
    long_press=dict(control='environment',action='environment',point=point,bounds=control['visible'],durationMs=700,
                    actionsBefore=before['actions'],actionsAfter=action['actions'])

    before=snapshot('menu'); control=before['browserAddressRow']['controls'][4]
    tap('menu-status',control['tap'],control['bounds']); visible('浏览器菜单')
    before_status=snapshot('status-before'); status=before_status['networkMetrics']
    assert status is not None
    (shots/(stem+'-status.xml')).write_text(dump()); (shots/(stem+'-status.png')).write_bytes(adb_bytes('exec-out','screencap','-p'))
    tap('network-status',status['networkTap'],status['bounds'])
    tap('network-state',status['stateTap'],status['texts'][2]['bounds'])
    after_status=snapshot('status-after')
    adb('shell','input','keyevent','KEYCODE_BACK'); visible('浏览器菜单',False)
    command+='-performance'
    adb('shell','am','start','-W','--activity-single-top','-n',component,'--es','compactAction','performance','--es','compactCommand',command)
    performance=event(command,'performance'); assert performance['status']=='passed'
    case=dict(navigationContract=3,viewport=width,fontScale=scale,image=stem+'.png',xml=stem+'.xml',
        layout=sample,readOnlyStatus=True,statusObservation=dict(before=before_status,after=after_status),
        actualAndroidTaps=taps,actualAndroidLongPress=long_press,performance=performance['performance'],
        environmentSheet=sheet,managementMenuXml=management_xml,menuScrolls=menu_scrolls,
        managementNavigation=dict(activity='local.pocketchat.WindowHomeActivity',actualMenuAction=True,resumedThenReturned=True),
        addressDialog=dialog,menuDismissedByBack=True,environmentDismissedByBack=True)
    verify_case(case,require_browser_chrome=True)
    return case
