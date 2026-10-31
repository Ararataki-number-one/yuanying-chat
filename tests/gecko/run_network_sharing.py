#!/usr/bin/env python3
"""Run native sharing checks and exercise the shipped import/export dialogs via Android taps."""
import argparse,hashlib,json,pathlib,re,shlex,subprocess,sys,time,uuid,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',default='emulator-5554');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';out.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(root/'tools'))
from gecko.network_sources_contract import verify_network_sharing
pkg='local.pocketchat.test';token=uuid.uuid4().hex;checks=[];experience_checks=[];tap_journal=[]
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
def tap(text,*,additional=False):
 tree=wait(xml,lambda t:bool(nodes(t,text)),30);n=nodes(tree,text)[0];x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')));assert x2>x1 and y2>y1
 command=['shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)];adb(*command)
 (experience_checks if additional else checks).append(text)
 tap_journal.append(dict(text=text,category='experience46' if additional else 'original-contract',bounds=[x1,y1,x2,y2],adbArguments=command))
def prepare(scope='整条线路'):
 tap(scope,additional=True);tap('准备分享',additional=True)
 wait(xml,lambda t:bool(nodes(t,'分享'+scope)),40)
def verify_tap_accounting(report):
 # The immutable contract still verifies its original18 actual actions. New46
 # choices remain actual taps too: retain them separately and in full order.
 assert checks==[row['text']for row in tap_journal if row['category']=='original-contract']
 assert experience_checks==[row['text']for row in tap_journal if row['category']=='experience46']
 assert experience_checks==['整条线路','准备分享']*3+['仅分享出口']
 assert len(tap_journal)==len(checks)+len(experience_checks)
 for row in tap_journal:
  x1,y1,x2,y2=row['bounds'];assert x2>x1 and y2>y1
  assert row['category']in ('original-contract','experience46')
  assert row['adbArguments']==['shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)]
 assert report['uiChecks']==checks and report['actualAndroidTaps']==len(checks)
 assert report['experienceUiChecks']==experience_checks and report['experienceActualAndroidTaps']==len(experience_checks)
 assert report['actualAndroidTapJournal']==tap_journal and report['totalActualAndroidTaps']==len(tap_journal)
def report():
 raw=adb('exec-out','content','read','--uri','content://'+pkg+'.evidence/network-source-sharing')
 (out/'network-source-sharing-native-raw.json').write_text(raw)
 return json.loads(raw)
try:
 adb('shell','am','force-stop',pkg)
 adb('shell','am','start','-W','-n',pkg+'/local.pocketchat.NetworkSharingIntegrationActivity','--es','runToken',token)
 r=wait(report,lambda r:r.get('runToken')==token,300);assert r['status']=='passed',r
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert r['buildIdentity']['sourceCommit']==source
 installed=hashlib.sha256((root/'app/build/outputs/apk/integration/app-x86_64-integration.apk').read_bytes()).hexdigest();assert r['buildIdentity']['apkSha256']==installed
 verify_network_sharing(r,source,installed,run_token=token)
 prepare();tap('仅分享入口');wait(xml,lambda t:bool(nodes(t,'分享入口')),20);tap('复制配置')
 tap('测试订阅整条线路');prepare()
 tap('仅分享出口');wait(xml,lambda t:bool(nodes(t,'分享出口')),20);tap('复制配置')
 for trigger,title in [('测试入口分享','分享入口'),('测试出口分享','分享出口'),('测试固定出口分享','分享出口')]:
  tap(trigger);wait(xml,lambda t:bool(nodes(t,title)),30);tap('复制配置')
 tap('检查分享未改动线路')
 r=wait(report,lambda value:value.get('sharePreparationPreservesActiveSnapshot') is True or value.get('status')=='failed',20)
 assert r['status']=='passed' and r['sharePreparationPreservesActiveSnapshot'] and all(x['pass'] for x in r['checks']),r
 tap('测试入口失败后仅分享出口');prepare();partial=wait(xml,lambda t:bool(nodes(t,'分享整条线路')),40)
 partial_text=' '.join(n.get('text','') for n in partial.iter('node'));assert '入口' in partial_text and '整条线路暂未生成' in partial_text and '出口配置已准备好' in partial_text,partial_text
 assert not nodes(partial,'复制配置') and not nodes(partial,'分享文件'),partial_text
 assert nodes(partial,'重试入口'),partial_text
 assert not nodes(partial,'仅分享入口')
 tap('仅分享出口',additional=True);wait(xml,lambda t:bool(nodes(t,'分享出口')),20);tap('复制配置');tap('恢复分享测试线路')
 r=wait(report,lambda value:value.get('partialSharePreservesActiveSnapshot') is True or value.get('status')=='failed',20)
 assert r['status']=='passed' and r['partialSharePreservesActiveSnapshot'],r
 # Open a real provider file through the production Activity; preview must be explicit.
 adb('shell','am','start','-W','-n',pkg+'/local.pocketchat.NetworkImportActivity','-a','android.intent.action.VIEW','-d',r['shareUri'],'-t','application/vnd.pocketchat.network')
 wait(xml,lambda t:bool(nodes(t,'导入预览')),30);tap('导入并选择环境');wait(xml,lambda t:bool(nodes(t,'选择应用环境')),90)
 # Repeated file import must offer the actual existing environment and a separate apply step.
 tap('Sharing Window');wait(xml,lambda t:bool(nodes(t,'保存并应用')),30)
 tree=xml();text=' '.join(n.get('text','') for n in tree.iter('node'));assert 'Portable VLESS' in text and 'Sharing Exit' in text,text
 tap('取消')
 (out/'network-source-sharing-screen.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
 r['uiChecks']=checks;r['actualAndroidTaps']=len(checks);r['uiChecksScope']='original-contract-required-actual-Android-taps';r['experienceUiChecks']=experience_checks;r['experienceActualAndroidTaps']=len(experience_checks);r['actualAndroidTapJournal']=tap_journal;r['totalActualAndroidTaps']=len(tap_journal);r['cancelledBeforeRouteApplication']=True
 verify_tap_accounting(r)
 verify_network_sharing(r,source,installed,complete=True,run_token=token)
 (out/'network-source-sharing-results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':'passed','nativeChecks':len(r['checks']),'actualAndroidTaps':len(checks),'experienceActualAndroidTaps':len(experience_checks),'totalActualAndroidTaps':len(tap_journal)}))
except Exception:
 (out/'network-source-sharing-failure-log.txt').write_text(adb('logcat','-d'))
 raise
