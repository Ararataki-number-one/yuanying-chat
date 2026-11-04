#!/usr/bin/env python3
"""Run every new browser host suite and the carried conversation regressions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['java-home','json-jar','android-json-jar','android-jar','webkit-jar','jsdom-module']:p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'work/browser-host-controls');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    java=['--java-home',str(a.java_home.resolve())];desktop=a.json_jar.resolve();android_json=a.android_json_jar.resolve();cases=[]
    def add(name,script,arguments=(),report=None):cases.append((name,[sys.executable,script,*map(str,arguments)],report))
    add('address','tests/browser-address-host/run.py',java+['--output',out/'address.json'],out/'address.json')
    add('permissions','tests/browser-permissions-host/run.py',java+['--output',out/'permissions.json'],out/'permissions.json')
    add('transfer','tests/browser-files-host/transfer.py',java+['--output',out/'transfer.json'],out/'transfer.json')
    add('route','tests/chromium-route-host/run.py',java+['--output',out/'route.json'],out/'route.json')
    add('runtime','tests/chromium-route-host/runtime.py',java+['--android-jar',a.android_jar.resolve(),'--webkit-jar',a.webkit_jar.resolve(),'--json-jar',desktop,'--output',out/'runtime.json'],out/'runtime.json')
    for label,jar in [('desktop',desktop),('android-json',android_json)]:
        target=out/('lease-boundaries-'+label+'.json');add('lease-boundaries-'+label,'tests/chromium-route-host/lease_boundaries.py',java+['--json-jar',jar,'--output',target],target)
        for name,script in [('preferences','tests/browser-preferences-host/run.py'),('library','tests/browser-library-host/run.py'),('transcript-store','tests/transcript-store-performance-host/run.py'),('chat-progress','tests/chat-progress-performance-host/run.py')]:
            target=out/(name+'-'+label+'.json');add(name+'-'+label,script,java+['--json-jar',jar,'--output',target],target)
        target=out/('chooser-'+label);add('chooser-'+label,'tests/browser-files-host/chooser.py',java+['--json-jar',jar,'--output',target],target/'results.json')
        target=out/('network-fence-'+label);add('network-fence-'+label,'tests/network-fence-completion-host/run.py',java+['--json-jar',jar,'--output',target],target/'results.json')
        target=out/('ui-download-observer-'+label+'.json');add('ui-download-observer-'+label,'tests/gecko-ui-download-observer-host/run.py',java+['--json-jar',jar,'--output',target],target)
        target=out/('event-journal-'+label+'.json');add('event-journal-'+label,'tests/gecko-event-journal-host/run.py',java+['--json-jar',jar,'--output',target],target)
        for ref in ['1e3086a',None]:
            name='chat-chrome-'+label+('-before' if ref else '-current');target=out/(name+'.json');arguments=java+['--json-jar',jar,'--output',target]+(['--before-ref',ref] if ref else []);add(name,'tests/chat-chrome-performance-host/run.py',arguments,target)
    add('shell','tests/ux-shell-host/run.py',java+['--output',out/'shell'])
    for name,script in [('focus','tests/ux-shell-host/focus_run.py'),('frame-binding','tests/ux-shell-host/frame_binding_run.py'),('loading','tests/loading-performance-host/run.py')]:
        target=out/(name+'.json');add(name,script,java+['--output',target],target)
    for name,script in [('browser-controls','tests/browser-controls-performance-host/run.py'),('transcript-order','tests/browser-transcript-order-host/run.py')]:
        target=out/(name+'.json');add(name,script,['--jsdom-module',a.jsdom_module.resolve(),'--output',target],target)
    add('browser-targeting','tests/browser_targeting_test.py')
    add('chrome-diagnostic-controls','tests/gecko_chrome_diagnostic_test.py')
    add('network-callback-cohort','tests/network_settings_callback_contract_test.py')
    add('network-completion-proof','tests/network_fence_completion_contract_test.py')
    add('network-callback-source-history','tests/profile_network_settings_callback_source_compatibility_test.py')
    add('evidence-gate','tests/browser_evidence_test.py')
    add('publisher-gate','tests/browser_publish_gate_test.py')
    add('baseline-bundle','tests/browser_baseline_bundle_test.py')
    add('workflow-gate','tests/browser_acceptance_workflow_test.py')
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','app/src/main/java','tests','tools/browser','.github/workflows/browser-2_1-acceptance.yml'],cwd=ROOT,text=True).splitlines()
    files=[ROOT/name for name in sorted(set(names)) if (ROOT/name).is_file()]
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    environment=dict(os.environ,JSDOM_MODULE=str(a.jsdom_module.resolve()),JAVA_HOME=str(a.java_home.resolve()));environment['PATH']=str(a.java_home.resolve()/'bin')+os.pathsep+environment['PATH']
    results=[]
    for name,command,report in cases:
        print(json.dumps(dict(suite=name,status='running')),flush=True)
        ran=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True,timeout=300)
        log=out/(name+'.log');log.write_text(ran.stdout+ran.stderr)
        row=dict(suite=name,status='passed' if ran.returncode==0 else 'failed',command=command,exitCode=ran.returncode,log=str(log),logSha256=hashlib.sha256(log.read_bytes()).hexdigest())
        if ran.returncode:row['failureReason']='Child process exited with code '+str(ran.returncode)
        if report and report.is_file():
            value=json.loads(report.read_text());row.update(report=str(report),reportSha256=hashlib.sha256(report.read_bytes()).hexdigest())
            if value.get('status','passed')!='passed' or value.get('executionInputsUnchanged',True) is not True or value.get('sourceUnchangedDuringChecks',True) is not True:row.update(status='failed',failureReason='Report failed or execution inputs changed')
        elif report:row.update(status='failed',failureReason='Required report was not produced: '+str(report))
        results.append(row);print(json.dumps(dict(suite=name,status=row['status'])),flush=True)
        if row['status']!='passed':
            # These fixed suites consume synthetic fixtures, never signing keys.
            # Keep their full local log and expose a bounded tail in Actions logs
            # so a failed artifact transport cannot hide the actual assertion.
            print(json.dumps(dict(suite=name,failureReason=row.get('failureReason'),logTailLimitCharacters=20000)),flush=True)
            print((ran.stdout+ran.stderr)[-20000:],flush=True)
            break
    stable=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in files)
    passed=stable and len(results)==len(cases) and all(r['status']=='passed' for r in results)
    report=dict(status='passed' if passed else 'failed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),executionInputsUnchanged=stable,sourceFiles=hashes,suites=results,requiredSuites=len(cases),completedSuites=len(results),dependencies={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in [desktop,android_json,a.android_jar,a.webkit_jar]},actualAndroidExecution=False,actualAndroidWebViewExecution=False,scope='Production Java/JavaScript host behavior and actual-API compilation with declared adapters. New browser policies/files/route/permissions and prior shell/loading/progress/chrome/control-cache/transcript regressions; no device or frame-rate claim.')
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],completed=len(results),required=len(cases),executionInputsUnchanged=stable)))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
