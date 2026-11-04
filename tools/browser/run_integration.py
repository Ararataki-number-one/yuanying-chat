#!/usr/bin/env python3
"""Run the source-bound production Chromium browser on a real Android emulator."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from profile_invocation_contract import expected_build,verify_installed


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
    nonce=uuid.uuid4().hex;actions=[];handled=set();result=None;error=None;browser_task=None;original_settings={}
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
            stage=current.get('stage','')
            if stage.startswith('file-picker-') and stage not in handled:
                target=current['tapTarget'];x,y=int(target['x']),int(target['y'])
                adb('shell','input','tap',str(x),str(y));actions.append(dict(kind='tap',stage=stage,x=x,y=y))
                chooser_until=time.monotonic()+20;chooser=False
                while time.monotonic()<chooser_until:
                    top=adb('shell','dumpsys','activity','activities').stdout.decode(errors='replace')
                    active=[line for line in top.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
                    if any('documentsui' in line.lower() for line in active):chooser=True;break
                    time.sleep(.2)
                if not chooser:raise AssertionError('The trusted tap did not open Android DocumentsUI: '+stage)
                adb('shell','input','keyevent','KEYCODE_BACK');actions.append(dict(kind='back',stage=stage,actualDocumentsUiObserved=True));handled.add(stage)
            elif stage=='download-click' and stage not in handled:
                target=current['tapTarget'];x,y=int(target['x']),int(target['y']);adb('shell','input','tap',str(x),str(y));actions.append(dict(kind='tap',stage=stage,x=x,y=y));handled.add(stage)
            elif stage in ('rotate-landscape','rotate-portrait') and stage not in handled:
                rotation='1' if stage=='rotate-landscape' else '0';adb('shell','settings','put','system','user_rotation',rotation);actions.append(dict(kind='rotation',stage=stage,value=int(rotation)));handled.add(stage)
            elif stage=='switch-to-gecko' and 'engine-roundtrip' not in handled:
                browser_task=current.get('taskId');switch_until=time.monotonic()+45;enhanced=False;enhanced_task=None
                while time.monotonic()<switch_until:
                    top=adb('shell','dumpsys','activity','activities').stdout.decode(errors='replace')
                    active=[line for line in top.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
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
    finally:
        unchanged=all(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p.relative_to(ROOT))] for p in paths)
        report.update(sourceFiles=hashes,executionInputsUnchanged=unchanged,result=result,trustedAndroidActions=actions,actualAndroidTaps=sum(a['kind']=='tap' for a in actions),scope='Real Android emulator and production browser classes with controlled proxy-origin HTML, real Android DocumentsUI cancellation and native file publication. Installed integration APK/source/SDK identity is checked. No desktop-as-WebView, public website, physical phone or frame-time acceptance.')
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
