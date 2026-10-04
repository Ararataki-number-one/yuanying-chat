#!/usr/bin/env python3
"""Actual Android screenshots of production UI; never touches the formal app."""
import argparse,json,pathlib,re,struct,subprocess,time,xml.etree.ElementTree as ET

root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';shots=out/'ui-visuals';shots.mkdir(exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',required=True);args=p.parse_args()
package='local.pocketchat.test';scenes=['chat','environments','network','proxy','entries','browser'];records=[]
def adb(*values):return subprocess.check_output([args.adb,'-s',args.serial,*values],timeout=90).decode(errors='replace')
def dump():
    adb('shell','uiautomator','dump','/sdcard/ui-visual.xml')
    return adb('shell','cat','/sdcard/ui-visual.xml')
def click(xml,label):
    node=next(n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text')==label)
    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']));adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
def capture(variant,width,height,scale,scene):
    adb('shell','am','force-stop',package);adb('logcat','-c')
    if 'com.google.android.apps.nexuslauncher' in adb('shell','pm','list','packages','com.google.android.apps.nexuslauncher'):adb('shell','am','force-stop','com.google.android.apps.nexuslauncher')
    adb('shell','wm','size',f'{width*3}x{height*3}');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
    adb('shell','am','start','-W','-n',package+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction',scene)
    required={'chat':'原网页','environments':'环境管理','network':'窗口网络','proxy':'代理地址','entries':'选择入口','browser':'基本信息'}[scene]
    deadline=time.monotonic()+35
    while True:
        xml=dump()
        runtime=adb('logcat','-d','-s','AndroidRuntime:E','*:S')
        if 'FATAL EXCEPTION' in runtime:raise AssertionError((variant,scene,'Android UI crashed',runtime[-5000:]))
        if required in xml:break
        if time.monotonic()>deadline:raise AssertionError((variant,scene,'screen did not appear',xml[-2000:]))
        time.sleep(.5)
    if scene=='browser':click(xml,'浏览器');time.sleep(2.5);xml=dump();assert '网页显示方式' in xml
    if scene=='chat':time.sleep(2.5);xml=dump();assert all(label in xml for label in ['会话','环境','下载','网络','设置','原网页'])
    assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')
    stem=f'{variant}-{width}x{height}-font{scale:g}-{scene}'
    (shots/(stem+'.xml')).write_text(xml)
    raw=subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30)
    pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(variant,scene,'Unexpected actual viewport',pixels)
    density=int(re.findall(r'density: (\d+)',adb('shell','wm','density'))[-1]);assert density==480,density
    (shots/(stem+'.png')).write_bytes(raw)
    records.append({'variant':variant,'logicalViewport':f'{width}x{height}','actualPixels':list(pixels),'densityDpi':density,'fontScale':scale,'scene':scene,'image':stem+'.png','xml':stem+'.xml'})
try:
    for variant in ['baseline','current']:
        adb('shell','am','force-stop',package)
        adb('install','-r',str(out/('ui-'+variant+'.apk')))
        adb('shell','pm','clear',package)
        if int(adb('shell','getprop','ro.build.version.sdk').strip())>=33:adb('shell','pm','grant',package,'android.permission.POST_NOTIFICATIONS')
        for width,height in [(360,640),(412,640)]:
            for scene in scenes:capture(variant,width,height,1,scene)
        for scene in ['proxy','entries','browser']:capture(variant,360,640,2,scene)
    report={'status':'passed','actualAndroidExecution':True,'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'screenshots':records,'scope':'Production native UI and original widgets with local synthetic records; webpage, login and network core not replaced.'}
except Exception as error:
    (out/'ui-visual-log.txt').write_text(adb('logcat','-d'))
    (out/'ui-visual-failure.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
    (out/'ui-visual-failure.xml').write_text(dump())
    report={'status':'failed','error':repr(error),'screenshots':records};raise
finally:
    (out/'ui-visual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    adb('shell','settings','put','system','font_scale','1');adb('shell','wm','size','reset');adb('shell','wm','density','reset')
