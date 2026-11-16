"""Exercise the actual bottom address, browser menu and retained environment capsule."""
import hashlib
import time
import xml.etree.ElementTree as ET
from compact_chrome_layout_v3 import address_dialog, verify_layout, verify_case
from workspace_navigation_contract_v3 import bounds, navigation, seek_menu_action


def browser_menu_visible(xml, package):
    """Distinguish the modal from the persistent button bearing the same name."""
    tree=ET.fromstring(xml); nodes=list(tree.iter('node'))
    parents={child:parent for parent in tree.iter() for child in parent}
    headings=[n for n in nodes if n.get('class')=='android.widget.TextView'
              and (n.get('text')=='浏览器菜单' or n.get('content-desc')=='浏览器菜单')]
    closes=[n for n in nodes if n.get('content-desc')=='关闭浏览器菜单'
            or n.get('text')=='关闭浏览器菜单']
    if not headings and not closes:
        navigation(xml,package,conversation=True)
        return False
    assert len(headings)==len(closes)==1, 'The actual menu heading and close control must agree'
    heading,close=headings[0],closes[0]
    assert heading.get('text')==heading.get('content-desc')=='浏览器菜单'
    assert close.get('class')=='android.widget.Button' and close.get('clickable')=='true'
    assert close.get('content-desc')=='关闭浏览器菜单'
    for control in (heading,close):
        assert control.get('package')==package and control.get('enabled')=='true'
        assert control.get('visible-to-user')!='false'
    header=parents[heading]
    assert parents[close] is header
    panel=parents[header]
    for container in (header,panel):
        assert container.get('package')==package and container.get('class')=='android.widget.LinearLayout'
        assert container.get('visible-to-user')!='false'
    hl,ht,hr,hb=bounds(header); pl,pt,pr,pb=bounds(panel)
    assert pl<=hl<hr<=pr and pt<=ht<hb<=pb
    for control in (heading,close):
        l,t,r,b=bounds(control)
        assert hl<=l<r<=hr and ht<=t<b<=hb
    l,t,r,b=bounds(close)
    assert min(r-l,b-t)>=144, 'The actual menu close control retains its 48 dp target'
    assert bounds(heading)[2]<=l, 'Menu heading and close control must not overlap'
    return True


def observe_browser_menu(dump, package, present):
    """Observe one real transition within the original 20-second window."""
    assert type(present) is bool
    deadline=time.monotonic()+20
    xml=''; problem=None
    while time.monotonic()<deadline:
        xml=dump(deadline=deadline)
        if time.monotonic()>=deadline:
            break
        try:
            found=browser_menu_visible(xml,package)
        except (AssertionError,KeyError,ET.ParseError) as error:
            problem=str(error)
        else:
            if found is present:
                return xml
        remaining=deadline-time.monotonic()
        if remaining<=0:
            break
        time.sleep(min(.2,remaining))
    raise TimeoutError(('Current browser menu visibility did not settle',present,problem,xml[-3000:]))


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
    tap('menu-status',control['tap'],control['bounds'])
    menu_xml=observe_browser_menu(dump,package,True)
    (shots/(stem+'-menu-open.xml')).write_text(menu_xml)
    before_status=snapshot('status-before'); status=before_status['networkMetrics']
    assert status is not None
    (shots/(stem+'-status.xml')).write_text(dump()); (shots/(stem+'-status.png')).write_bytes(adb_bytes('exec-out','screencap','-p'))
    tap('network-status',status['networkTap'],status['bounds'])
    tap('network-state',status['stateTap'],status['texts'][2]['bounds'])
    after_status=snapshot('status-after')
    adb('shell','input','keyevent','KEYCODE_BACK')
    menu_xml=observe_browser_menu(dump,package,False)
    (shots/(stem+'-menu-closed.xml')).write_text(menu_xml)
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
