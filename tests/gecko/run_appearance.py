#!/usr/bin/env python3
"""Actual Android taps and system night-mode events. Never uses a real account."""
import argparse,hashlib,json,pathlib,re,subprocess,time,uuid,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',default='emulator-5554');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';out.mkdir(parents=True,exist_ok=True)
pkg='local.pocketchat.test';token=uuid.uuid4().hex;checks=[];taps=[]
def adb(*args,binary=False):return subprocess.check_output([a.adb,'-s',a.serial,*args],text=not binary,timeout=40)
def wait(fn,pred,seconds=40):
 end=time.monotonic()+seconds;last=None
 while time.monotonic()<end:
  try:
   last=fn()
   if pred(last):return last
  except (subprocess.CalledProcessError,json.JSONDecodeError,ET.ParseError):pass
  time.sleep(.4)
 raise AssertionError('Expected appearance state not reached: '+str(last))
def report():return json.loads(adb('exec-out','content','read','--uri','content://'+pkg+'.evidence/appearance'))
def check(name,value):
 checks.append({'name':name,'pass':bool(value)})
 if not value:raise AssertionError(name)
def tree():
 adb('shell','uiautomator','dump','/sdcard/pocket-appearance.xml');return ET.fromstring(adb('exec-out','cat','/sdcard/pocket-appearance.xml'))
def tap(label):
 rows=lambda t:[n for n in t.iter('node') if n.get('text')==label]
 n=rows(wait(tree,lambda t:bool(rows(t))))[0];x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')));assert x2>x1 and y2>y1
 adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));taps.append(label)
def signed(n):return n-(1<<32) if n>=1<<31 else n
def snapshot(name):
 (out/('appearance-'+name+'.png')).write_bytes(adb('exec-out','screencap','-p',binary=True))
 (out/('appearance-'+name+'.xml')).write_text(ET.tostring(tree(),encoding='unicode'))
def start():adb('shell','am','start','-W','-n',pkg+'/local.pocketchat.AppearanceIntegrationActivity','--es','runToken',token)
def theme(dark,mode):return wait(report,lambda r:r.get('runToken')==token and r.get('dark')==dark and r.get('mode')==mode)
try:
 adb('shell','am','force-stop',pkg);adb('shell','pm','clear',pkg);adb('shell','cmd','uimode','night','no');start()
 initial=theme(False,'system');identity=initial['buildIdentity'];instance=initial['instance']
 check('Missing preference defaults to follow system',initial['mode']=='system' and not initial['systemDark'])
 source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();check('Actual installed source matches tested commit',identity['sourceCommit']==source)
 apk=root/'app/build/outputs/apk/integration/app-x86_64-integration.apk';check('Actual installed APK identity matches built APK',identity['apkSha256']==hashlib.sha256(apk.read_bytes()).hexdigest())
 tap('检查弹窗');wait(report,lambda r:r.get('modalVisible'));snapshot('light')
 adb('shell','cmd','uimode','night','yes');night=theme(True,'system')
 check('System event changes appearance without recreating activity',night['instance']==instance and night['configurations']>0)
 check('Native text and background use night palette',night['textColor']==signed(0xffe3e7ef) and night['backgroundColor']==signed(0xff15181e))
 check('Already open central modal becomes dark',night['modalVisible'] and night['modalColor']==signed(0xff20242c))
 check('Night status bar uses light icons',night['systemUi']&8192==0 and night['systemUi']&16==0)
 check('Draft and selection survive system theme event',night['draft']==initial['draft'] and night['selectionStart']==initial['selectionStart'] and night['selectionEnd']==initial['selectionEnd'])
 check('Primary button text stays white',night['primaryText']==-1);snapshot('dark');tap('关闭')
 tap('打开外观设置');tap('始终白天');manual=theme(False,'light');check('Manual light overrides dark system',manual['systemDark'] and manual['textColor']==signed(0xff172033))
 adb('shell','cmd','uimode','night','no');theme(False,'light');adb('shell','cmd','uimode','night','yes');theme(False,'light')
 check('Manual mode ignores later system toggles',report()['instance']==instance and not report()['dark'])
 tap('始终黑夜');theme(True,'dark');tap('完成');adb('shell','am','force-stop',pkg);start();persisted=theme(True,'dark')
 check('Manual choice survives process restart',persisted['instance']!=instance)
 tap('打开外观设置');tap('跟随系统');theme(True,'system');tap('完成');adb('shell','cmd','uimode','night','no');day=theme(False,'system')
 check('Returning to automatic follows subsequent system changes',day['textColor']==signed(0xff172033) and not day['systemDark'])
 result={'status':'passed','actualAndroidExecution':True,'actualAndroidTaps':len(taps),'systemModeEvents':True,'buildIdentity':identity,'checks':checks,'checkCount':len(checks),'taps':taps}
 (out/'appearance-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
except Exception as e:
 (out/'appearance-failure.json').write_text(json.dumps({'status':'failed','checks':checks,'taps':taps,'error':str(e)},indent=2)+'\n');raise
finally:adb('shell','cmd','uimode','night','no')
