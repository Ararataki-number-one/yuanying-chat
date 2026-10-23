#!/usr/bin/env python3
"""Run native sharing checks and exercise the shipped import/export dialogs via Android taps."""
import argparse,hashlib,json,pathlib,re,shlex,subprocess,time,uuid,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',default='emulator-5554');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';out.mkdir(parents=True,exist_ok=True)
pkg='local.pocketchat.test';token=uuid.uuid4().hex;checks=[]
def adb(*args,binary=False):return subprocess.check_output([a.adb,'-s',a.serial,*args],text=not binary,timeout=40)
def wait(fn,pred,seconds=90):
 end=time.monotonic()+seconds;last=None
 while time.monotonic()<end:
  try:
   last=fn()
   if pred(last):return last
  except (subprocess.CalledProcessError,ET.ParseError,json.JSONDecodeError):pass
  time.sleep(.5)
 raise AssertionError('Expected state not reached: '+str(last))
def xml():
 adb('shell','uiautomator','dump','/sdcard/pocket-sharing.xml');raw=adb('exec-out','cat','/sdcard/pocket-sharing.xml');(out/'network-source-sharing-ui.xml').write_text(raw);return ET.fromstring(raw)
def nodes(tree,text):return [n for n in tree.iter('node') if n.get('text')==text]
def tap(text):
 tree=wait(xml,lambda t:bool(nodes(t,text)),30);n=nodes(tree,text)[0];x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')));assert x2>x1 and y2>y1;adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));checks.append(text)
def report():return json.loads(adb('exec-out','content','read','--uri','content://'+pkg+'.evidence/network-source-sharing'))
try:
 adb('shell','am','force-stop',pkg)
 adb('shell','am','start','-W','-n',pkg+'/local.pocketchat.NetworkSharingIntegrationActivity','--es','runToken',token)
 r=wait(report,lambda r:r.get('runToken')==token,180);assert r['status']=='passed',r
 assert r['actualAndroidExecution'] and r['actualNativeExecution'] and len(r['checks'])>=30 and all(x['pass'] for x in r['checks'])
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert r['buildIdentity']['sourceCommit']==source
 installed=hashlib.sha256((root/'app/build/outputs/apk/integration/app-x86_64-integration.apk').read_bytes()).hexdigest();assert r['buildIdentity']['apkSha256']==installed
 tap('仅分享入口');wait(xml,lambda t:bool(nodes(t,'分享入口')),20);tap('复制配置')
 tap('测试订阅整条线路');wait(xml,lambda t:bool(nodes(t,'分享整条线路')),30)
 tap('仅分享出口');wait(xml,lambda t:bool(nodes(t,'分享出口')),20);tap('复制配置')
 for trigger,title in [('测试入口分享','分享入口'),('测试出口分享','分享出口'),('测试固定出口分享','分享出口')]:
  tap(trigger);wait(xml,lambda t:bool(nodes(t,title)),30);tap('复制配置')
 tap('检查分享未改动线路')
 r=wait(report,lambda value:value.get('sharePreparationPreservesActiveSnapshot') is True or value.get('status')=='failed',20)
 assert r['status']=='passed' and r['sharePreparationPreservesActiveSnapshot'] and all(x['pass'] for x in r['checks']),r
 # Open a real provider file through the production Activity; preview must be explicit.
 adb('shell','am','start','-W','-n',pkg+'/local.pocketchat.NetworkImportActivity','-a','android.intent.action.VIEW','-d',r['shareUri'],'-t','application/vnd.pocketchat.network')
 wait(xml,lambda t:bool(nodes(t,'导入预览')),30);tap('导入并选择环境');wait(xml,lambda t:bool(nodes(t,'选择应用环境')),90)
 # Repeated file import must offer the actual existing environment and a separate apply step.
 tap('Sharing Window');wait(xml,lambda t:bool(nodes(t,'保存并应用')),30)
 tree=xml();text=' '.join(n.get('text','') for n in tree.iter('node'));assert 'Portable VLESS' in text and 'Sharing Exit' in text,text
 tap('取消')
 (out/'network-source-sharing-screen.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
 r['uiChecks']=checks;r['actualAndroidTaps']=len(checks);r['cancelledBeforeRouteApplication']=True
 (out/'network-source-sharing-results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':'passed','nativeChecks':len(r['checks']),'actualAndroidTaps':len(checks)}))
except Exception:
 (out/'network-source-sharing-failure-log.txt').write_text(adb('logcat','-d'))
 raise
