#!/usr/bin/env python3
"""Run the source-bound production Chromium browser on a real Android emulator."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from profile_invocation_contract import expected_build,verify_installed

NATIVE_TARGET_FIELDS=('screenX','screenY','width','height','visibleLeft','visibleTop','visibleRight','visibleBottom')
DOM_TARGET_FIELDS=('x','y','left','top','right','bottom','viewportWidth','viewportHeight','scrollX','scrollY','devicePixelRatio','visualScale','visualWidth','visualHeight','visualOffsetLeft','visualOffsetTop')


def target_number(value,name,integer=False):
    if type(value) not in (int,float) or integer and type(value) is not int or abs(value)>10000000 or not math.isfinite(value):
        raise AssertionError('Invalid trusted target '+name)
    return value


def validate_tap_target(current):
    """Accept only a current, hit-tested point inside the real visible WebView."""
    stage=current.get('stage');expected='upload' if stage in ('file-picker-1','file-picker-2') else 'download' if stage=='download-click' else None
    target=current.get('tapTarget')
    if expected is None or type(target) is not dict:raise AssertionError('Unexpected trusted target stage')
    if target.get('id')!=expected or target.get('ready') is not True or type(target.get('stableSamples')) is not int or target['stableSamples']!=2 or target.get('visualStateComplete') is not True:raise AssertionError('Trusted target has no stable visual proof')
    native=target.get('nativeFrame');dom=target.get('dom')
    if type(native) is not dict or type(dom) is not dict:raise AssertionError('Trusted target geometry is missing')
    for key in NATIVE_TARGET_FIELDS:target_number(native.get(key),key,True)
    for key in DOM_TARGET_FIELDS:target_number(dom.get(key),key)
    scale=target_number(native.get('nativeScale'),'nativeScale')
    if any(native.get(key) is not True for key in ('shown','windowFocus','foreground')) or native.get('layoutRequested') is not False:raise AssertionError('Trusted target native layout is not ready')
    if dom.get('id')!=expected or dom.get('hitTarget') is not True or not str(dom.get('url','')).startswith('http://browser-fixture.example/'):raise AssertionError('Trusted target DOM hit is not the fixture element')
    width,height=dom['viewportWidth'],dom['viewportHeight'];x,y=dom['x'],dom['y']
    if not (width>0 and height>0 and native['width']>0 and native['height']>0 and dom['right']>dom['left'] and dom['bottom']>dom['top'] and 0<x<width and 0<y<height and dom['left']<x<dom['right'] and dom['top']<y<dom['bottom'] and abs(x-(dom['left']+dom['right'])/2)<.01 and abs(y-(dom['top']+dom['bottom'])/2)<.01):raise AssertionError('Trusted target center is outside the DOM viewport')
    visual_width,visual_height=dom['visualWidth'],dom['visualHeight'];left,top=dom['visualOffsetLeft'],dom['visualOffsetTop']
    if not (scale>0 and visual_width>0 and visual_height>0 and left>=0 and top>=0 and left+visual_width<=width+1 and top+visual_height<=height+1 and left<x<left+visual_width and top<y<top+visual_height):raise AssertionError('Trusted target center is outside the actual visual viewport')
    if abs(visual_width*scale-native['width'])>1 or abs(visual_height*scale-native['height'])>1:raise AssertionError('Trusted target native scale and visual viewport differ')
    point_x=target_number(target.get('x'),'screen x',True);point_y=target_number(target.get('y'),'screen y',True)
    if not (native['screenX']<=native['visibleLeft']<native['visibleRight']<=native['screenX']+native['width'] and native['screenY']<=native['visibleTop']<native['visibleBottom']<=native['screenY']+native['height'] and native['visibleLeft']<=point_x<native['visibleRight'] and native['visibleTop']<=point_y<native['visibleBottom']):raise AssertionError('Trusted target is outside the visible native WebView')
    if point_x!=native['screenX']+math.floor((x-left)*scale+.5) or point_y!=native['screenY']+math.floor((y-top)*scale+.5):raise AssertionError('Trusted target screen transform differs')
    return point_x,point_y


def brief(value,limit=512):
    return str(value).encode('utf-8','replace')[:limit].decode('utf-8','ignore')


def target_summary(value):
    if type(value) is not dict:return None
    result={key:value[key] for key in ('ready','stableSamples','visualStateComplete','x','y') if type(value.get(key)) in (bool,int,float) and (type(value[key]) is bool or abs(value[key])<=10000000 and math.isfinite(value[key]))}
    if type(value.get('id')) is str:result['id']=brief(value['id'],80)
    for section,keys in [('nativeFrame',NATIVE_TARGET_FIELDS+('nativeScale','viewFocus','shown','windowFocus','foreground','layoutRequested')),('dom',DOM_TARGET_FIELDS+('documentFocus','hitTarget'))]:
        source=value.get(section)
        if type(source) is dict:result[section]={key:source[key] for key in keys if type(source.get(key)) in (bool,int,float) and (type(source[key]) is bool or abs(source[key])<=10000000 and math.isfinite(source[key]))}
    if type(value.get('dom')) is dict:
        for key in ('id','hitId','hitTag'):
            if type(value['dom'].get(key)) is str:result.setdefault('dom',{})[key]=brief(value['dom'][key],80)
    return result


def input_summary(value):
    """Bounded controlled-input metadata, without document text or event payloads."""
    if type(value) is not dict:return None
    result={key:value[key] for key in ('matching','ordinal','completed','ready','afterTask','afterFrame','rejected') if type(value.get(key)) in (bool,int) and abs(value[key])<=10000000}
    events=value.get('events')
    if type(events) is list:
        result['events']=[]
        for row in events[-12:]:
            if type(row) is not dict:continue
            event={key:brief(row[key],60) for key in ('type',) if type(row.get(key)) is str}
            event.update({key:row[key] for key in ('trusted','ordinal','x','y','focused') if type(row.get(key)) in (bool,int,float) and (type(row[key]) is bool or abs(row[key])<=10000000 and math.isfinite(row[key]))})
            result['events'].append(event)
    return result


def diagnostic_failure(current,error,last_resumed,actions):
    """Bounded synthetic diagnostics; excludes page content, cookies and extras."""
    value=current if type(current) is dict else {};summary={}
    for key in ('status','stage','runNonce','sourceCommit','failure'):
        if type(value.get(key)) is str:summary[key]=brief(value[key],512 if key=='failure' else 100)
    for key in ('taskId','passed','total','foreground','pendingChooser','routeAllowed'):
        if type(value.get(key)) in (bool,int) and abs(value[key])<=10000000:summary[key]=value[key]
    summary['tapTarget']=target_summary(value.get('tapTarget'))
    summary['pickerBarrier']=input_summary(value.get('pickerBarrier'))
    native=value.get('nativeInputEvents')
    if type(native) is list:
        summary['nativeInputEvents']=[]
        for row in native[-12:]:
            if type(row) is not dict:continue
            event={'stage':brief(row['stage'],60)} if type(row.get('stage')) is str else {}
            event.update({key:row[key] for key in ('action','x','y','handled') if type(row.get(key)) in (bool,int,float) and (type(row[key]) is bool or abs(row[key])<=10000000 and math.isfinite(row[key]))})
            summary['nativeInputEvents'].append(event)
    checks=value.get('checks',[])
    if type(checks) is list:summary['checks']=[{'name':brief(row.get('name',''),220),'pass':row.get('pass') is True} for row in checks[-6:] if type(row) is dict]
    resumed=[brief(line,320) for line in last_resumed[-8:]] if type(last_resumed) is list else []
    trusted=[]
    for row in actions[-8:] if type(actions) is list else []:
        if type(row) is not dict:continue
        selected={key:brief(row[key],100) for key in ('kind','stage') if type(row.get(key)) is str}
        selected.update({key:row[key] for key in ('x','y','value','browserTaskId','enhancedTaskId','actualDocumentsUiObserved','actualEnhancedActivityResumed') if type(row.get(key)) in (bool,int) and abs(row[key])<=10000000})
        trusted.append(selected)
    packet=dict(event='browser-acceptance-failure',error=brief(error),lastValidatedReport=summary,lastResumedComponents=resumed,trustedAndroidActions=trusted)
    if len(json.dumps(packet,ensure_ascii=False,separators=(',',':')).encode('utf-8'))>16000:
        packet.update(lastResumedComponents=[],trustedAndroidActions=[],diagnosticTrimmed=True);summary.pop('checks',None)
    return packet


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb',default='adb')
    parser.add_argument('--serial',default='emulator-5554')
    parser.add_argument('--output',type=Path,default=ROOT/'work/browser-acceptance')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.serial!='emulator-5554':parser.error('Only the controlled emulator target is allowed')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('A clean checked-out source tree is required before Android acceptance')
    def adb(*parts,check=True,timeout=30):
        return subprocess.run([args.adb,'-s',args.serial,*parts],check=check,capture_output=True,timeout=timeout)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    settings=(ROOT/'app/build.gradle').read_text()
    apk=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk'
    identity=expected_build(apk,source,tree,re.search(r"versionName '([^']+)'",settings).group(1),int(re.search(r'versionCode (\d+)',settings).group(1)))
    paths=[Path(__file__).resolve(),ROOT/'tests/gecko/BrowserIntegrationActivity.java',ROOT/'tests/gecko/BrowserEvidenceProvider.java',ROOT/'tests/gecko/AndroidManifest.xml',ROOT/'.github/workflows/browser-2_1-acceptance.yml']
    paths+=list((ROOT/'app/src/main/java/local/pocketchat').glob('*.java'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    nonce=uuid.uuid4().hex;actions=[];handled=set();result=None;error=None;browser_task=None;original_settings={};last_validated_report=None;last_resumed=[]
    report=dict(status='running',sourceCommit=source,sourceTree=tree,runNonce=nonce,expectedBuildIdentity=identity,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualDesktopChromiumExecution=False,actualPublicWebsiteExecution=False,actualDevicePerformanceMeasurement=False)
    try:
        if adb('shell','getprop','ro.kernel.qemu').stdout.decode().strip()!='1':raise ValueError('A real controlled Android emulator is required')
        installed=json.loads(adb('exec-out','content','read','--uri','content://local.pocketchat.test.evidence/build-identity').stdout)
        verify_installed(installed,identity)
        adb('shell','am','force-stop','local.pocketchat.test')
        for key in ['font_scale','accelerometer_rotation','user_rotation']:original_settings[key]=adb('shell','settings','get','system',key).stdout.decode().strip()
        for key,value in [('font_scale','2.0'),('accelerometer_rotation','0'),('user_rotation','0')]:adb('shell','settings','put','system',key,value)
        adb('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.BrowserIntegrationActivity','--es','runNonce',nonce,'--es','sourceCommit',source)
        until=time.monotonic()+360
        while time.monotonic()<until:
            raw=adb('exec-out','content','read','--uri','content://local.pocketchat.test.browser-evidence/result',check=False)
            try:current=json.loads(raw.stdout)
            except (ValueError,UnicodeDecodeError):time.sleep(.25);continue
            if current.get('runNonce')!=nonce:time.sleep(.25);continue
            verify_installed(current['buildIdentity'],identity)
            if current.get('sourceCommit')!=source:raise ValueError('Browser report source differs')
            last_validated_report=current
            stage=current.get('stage','')
            if stage.startswith('file-picker-') and stage not in handled:
                x,y=validate_tap_target(current)
                adb('shell','input','tap',str(x),str(y));actions.append(dict(kind='tap',stage=stage,x=x,y=y,targetProof=current['tapTarget']))
                chooser_until=time.monotonic()+20;chooser=False
                while time.monotonic()<chooser_until:
                    top=adb('shell','dumpsys','activity','activities').stdout.decode(errors='replace')
                    active=[line for line in top.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
                    last_resumed=active
                    if any('documentsui' in line.lower() for line in active):chooser=True;break
                    time.sleep(.2)
                if not chooser:raise AssertionError('The trusted tap did not open Android DocumentsUI: '+stage)
                adb('shell','input','keyevent','KEYCODE_BACK');actions.append(dict(kind='back',stage=stage,actualDocumentsUiObserved=True));handled.add(stage)
            elif stage=='download-click' and stage not in handled:
                x,y=validate_tap_target(current);adb('shell','input','tap',str(x),str(y));actions.append(dict(kind='tap',stage=stage,x=x,y=y,targetProof=current['tapTarget']));handled.add(stage)
            elif stage in ('rotate-landscape','rotate-portrait') and stage not in handled:
                rotation='1' if stage=='rotate-landscape' else '0';adb('shell','settings','put','system','user_rotation',rotation);actions.append(dict(kind='rotation',stage=stage,value=int(rotation)));handled.add(stage)
            elif stage=='switch-to-gecko' and 'engine-roundtrip' not in handled:
                browser_task=current.get('taskId');switch_until=time.monotonic()+45;enhanced=False;enhanced_task=None
                while time.monotonic()<switch_until:
                    top=adb('shell','dumpsys','activity','activities').stdout.decode(errors='replace')
                    active=[line for line in top.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
                    last_resumed=active
                    match=next((re.search(r'\bt(\d+)\b',line) for line in active if '/local.pocketchat.MainActivity' in line),None)
                    if match:enhanced=True;enhanced_task=int(match.group(1));break
                    time.sleep(.2)
                if not enhanced:raise AssertionError('The real enhanced MainActivity did not resume')
                if type(browser_task) is not int or enhanced_task==browser_task:raise AssertionError('The browser and enhanced activity must occupy separate actual tasks')
                adb('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.BrowserIntegrationActivity','--es','runNonce',nonce,'--es','sourceCommit',source)
                actions.append(dict(kind='engine-roundtrip',actualEnhancedActivityResumed=True,browserTaskId=browser_task,enhancedTaskId=enhanced_task));handled.add('engine-roundtrip')
            if current.get('status') in ('passed','failed'):
                result=current;break
            time.sleep(.15)
        if result is None:raise TimeoutError('Source-bound browser integration did not complete')
        if result['status']!='passed':raise AssertionError(result.get('failure') or 'Browser integration failed')
        if result.get('actualAndroidWebViewExecution') is not True or not result.get('provider',{}).get('version'):raise AssertionError('Actual Android WebView provider evidence is missing')
        if set(handled)!={'file-picker-1','file-picker-2','download-click','rotate-landscape','rotate-portrait','engine-roundtrip'}:raise AssertionError('Required trusted actions did not all occur')
        if result.get('taskId')!=browser_task:raise AssertionError('The existing browser task was not preserved')
        if not result['checks'] or not all(c['pass'] is True for c in result['checks']):raise AssertionError('Browser checks did not all pass')
        if result['proxy']['upstreamConnections']!=0 or result['proxy']['forwardingImplemented'] is not False:raise AssertionError('The synthetic proxy must never forward public traffic')
        report.update(status='passed',actualAndroidExecution=True,actualAndroidWebViewExecution=True)
    except Exception as failure:
        error=failure;report.update(status='failed',error=type(failure).__name__+': '+str(failure))
        # The stage snapshot precedes its single tap. Read only current,
        # source-bound diagnostics after a failure; this never retries a tap.
        try:
            latest=json.loads(adb('exec-out','content','read','--uri','content://local.pocketchat.test.browser-evidence/result',check=False,timeout=10).stdout)
            if latest.get('runNonce')==nonce and latest.get('sourceCommit')==source:
                verify_installed(latest['buildIdentity'],identity)
                last_validated_report=latest
        except Exception:pass
        try:
            top=adb('shell','dumpsys','activity','activities',check=False,timeout=10).stdout.decode(errors='replace')
            last_resumed=[line for line in top.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
        except Exception:pass
        diagnostic=diagnostic_failure(last_validated_report,report['error'],last_resumed,actions);report['failureDiagnostic']=diagnostic
        print('BROWSER_ACCEPTANCE_FAILURE '+json.dumps(diagnostic,ensure_ascii=False,separators=(',',':')),flush=True)
    finally:
        unchanged=all(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p.relative_to(ROOT))] for p in paths)
        report.update(sourceFiles=hashes,executionInputsUnchanged=unchanged,result=result,lastValidatedReport=last_validated_report,trustedAndroidActions=actions,actualAndroidTaps=sum(a['kind']=='tap' for a in actions),scope='Real Android emulator and production browser classes with controlled proxy-origin HTML, real Android DocumentsUI cancellation and native file publication. Installed integration APK/source/SDK identity is checked. No desktop-as-WebView, public website, physical phone or frame-time acceptance.')
        if not unchanged:report.update(status='failed',error='Execution source changed');error=error or ValueError('Execution source changed')
        try:(args.output/'webview-provider.txt').write_bytes(adb('shell','dumpsys','webviewupdate',check=False).stdout)
        except Exception:pass
        try:(args.output/'screen.png').write_bytes(adb('exec-out','screencap','-p',check=False).stdout)
        except Exception:pass
        for key,value in original_settings.items():
            try:adb('shell','settings','delete','system',key) if value=='null' else adb('shell','settings','put','system',key,value)
            except Exception:pass
        (args.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(status=report['status'],actualAndroidExecution=report['actualAndroidExecution'],actualAndroidWebViewExecution=report['actualAndroidWebViewExecution'],actualAndroidTaps=report['actualAndroidTaps'],output=str(args.output/'results.json'))))
    if error:raise error


if __name__=='__main__':main()
