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
    p.add_argument('--gecko-sdk-jar',type=Path,help='Optional exact real derived SDK classes for local API verification')
    p.add_argument('--gecko-sdk-receipt',type=Path,help='Actual build receipt for the supplied real SDK input')
    p.add_argument('--output',type=Path,default=ROOT/'work/browser-host-controls');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if a.gecko_sdk_jar and not a.gecko_sdk_receipt:p.error('--gecko-sdk-jar requires its actual --gecko-sdk-receipt')
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
    add('chrome-firsttap-controls','tests/profile_chrome_first_tap_readiness_test.py')
    add('network-callback-cohort','tests/network_settings_callback_contract_test.py')
    add('network-completion-proof','tests/network_fence_completion_contract_test.py')
    add('network-callback-source-history','tests/profile_network_settings_callback_source_compatibility_test.py')
    add('evidence-gate','tests/browser_evidence_test.py')
    add('publisher-gate','tests/browser_publish_gate_test.py')
    add('baseline-bundle','tests/browser_baseline_bundle_test.py')
    add('workflow-gate','tests/browser_acceptance_workflow_test.py')
    for label,jar in [('desktop',desktop),('android-json',android_json)]:
        for name,script in [('chromium-fingerprint-store','tests/chromium-fingerprint-store-host/run.py'),('gecko-navigation','tests/gecko-navigation-host/run.py')]:
            target=out/(name+'-'+label+'.json');add(name+'-'+label,script,java+['--json-jar',jar,'--output',target],target)
        target=out/('gecko-route-hold-'+label+'.json');add('gecko-route-hold-'+label,'tests/gecko-navigation-host/route_hold.py',java+['--json-jar',jar,'--output',target],target)
        target=out/('chromium-fingerprint-'+label+'.json');add('chromium-fingerprint-'+label,'tests/chromium-fingerprint-host/run.py',java+['--json-jar',jar,'--webkit-jar',a.webkit_jar.resolve(),'--output',target],target)
        target=out/('generic-download-source-'+label+'.json');add('generic-download-source-'+label,'tests/generic-download-source-host/run.py',java+['--json-jar',jar,'--output',target],target)
        for name,script in [('gecko-session-navigation','tests/gecko-navigation-host/session_navigation.py'),('gecko-client-ready','tests/gecko-navigation-host/client_ready.py')]:
            target=out/(name+'-'+label+'.json');add(name+'-'+label,script,java+['--json-jar',jar,'--output',target],target)
        target=out/('chromium-fingerprint-activity-'+label+'.json');add('chromium-fingerprint-activity-'+label,'tests/chromium-fingerprint-activity-host/run.py',java+['--json-jar',jar,'--output',target],target)
        for name,script in [('chromium-worker-policy','tests/chromium-worker-policy-host/run.py'),('gecko-request-headers','tests/gecko-request-headers-host/run.py'),('gecko-timezone','tests/gecko-timezone-host/run.py'),('gecko-timezone-report','tests/gecko-timezone-host/report.py'),('gecko-timezone-flow','tests/gecko-timezone-flow-host/run.py'),('gecko-timezone-stale','tests/gecko-timezone-stale-host/run.py'),('gecko-timezone-routing','tests/gecko-timezone-routing-host/run.py'),('gecko-timezone-delete','tests/gecko-timezone-delete-host/run.py'),('gecko-timezone-http-wait','tests/gecko-timezone-http-host/run.py'),('gecko-addon-lifecycle','tests/gecko-addon-lifecycle-host/run.py'),('request-identity-timezone','tests/request-identity-timezone-host/run.py'),('environment-audit-pending','tests/environment-audit-pending-host/run.py'),('gecko-ip-timezone','tests/gecko-ip-timezone-host/run.py'),('gecko-ip-transport','tests/gecko-ip-transport-host/run.py'),('ip-timezone-fixture-setup','tests/ip-timezone-fixture-setup-host/run.py'),('gecko-popup-navigation','tests/gecko-popup-navigation-host/run.py')]:
            target=out/(name+'-'+label+'.json');add(name+'-'+label,script,java+['--json-jar',jar,'--output',target],target)
        target=out/('runtime-origin-adapter-'+label+'.json');add('runtime-origin-adapter-'+label,'tests/runtime-origin-adapter-host/run.py',java+['--json-jar',jar,'--android-jar',a.android_jar.resolve(),'--jsdom-module',a.jsdom_module.resolve(),'--output',target],target)
    cases.append(('gecko-site-boundary',['node','--test','tests/browser-runtime/gecko-site-boundary.test.cjs'],None))
    cases.append(('chromium-fingerprint-script',['node','--test','tests/chromium-fingerprint-script.test.cjs'],None))
    cases.append(('gecko-worker-request-headers',['node','--test','tests/request-identity/worker_request_headers_test.cjs'],None))
    cases.append(('gecko-native-timezone-bridge',['node','--test','tests/request-identity/native_timezone_bridge_test.cjs'],None))
    cases.append(('gecko-ip-timezone-bootstrap',['node','--test','tests/request-identity/ip_timezone_bootstrap_test.cjs'],None))
    cases.append(('gecko-timezone-native-signal',['node','--test','tests/gecko-timezone-host/signal.test.cjs'],None))
    target=out/'native-protection-independent-boundaries.json';cases.append(('native-protection-independent-boundaries',['node','tests/browser-runtime/native-protection-independent-boundaries.test.cjs','--receipt',str(target)],target))
    cases.append(('session-cookies-coalescing',['node','tests/browser-runtime/session-cookies-coalescing.test.cjs'],None))
    target=out/'session-cookies-independent-boundaries.json';cases.append(('session-cookies-independent-boundaries',['node','tests/browser-runtime/session-cookies-independent-boundaries.test.cjs','--receipt',str(target)],target))
    add('gecko-native-timezone-api','tests/gecko/native_timezone_api_contract.py')
    add('gecko-native-timezone-session-api','tests/gecko/native_timezone_session_api_contract.py')
    target=out/'gecko-app-session-api.json';sdk_arguments=(['--sdk-jar',a.gecko_sdk_jar.resolve()] if a.gecko_sdk_jar else [])+(['--sdk-receipt',a.gecko_sdk_receipt.resolve()] if a.gecko_sdk_receipt else []);add('gecko-app-session-api','tests/gecko/app_session_identity_api_contract.py',java+['--android-jar',a.android_jar.resolve(),'--output',target]+sdk_arguments,target)
    add('connection-timezone-prerequisite','tests/profile_connection_timezone_prerequisite_test.py')
    add('connection-route-timezone-prerequisite','tests/connection_route_timezone_prerequisite_test.py')
    add('fingerprint-publisher-gate','tests/browser_fingerprint_publish_gate_test.py')
    add('fingerprint-evidence-gate','tests/browser_fingerprint_evidence_test.py')
    add('fingerprint-fixture-controls','tests/browser_fingerprint_fixture_test.py')
    add('fingerprint-server-controls','tests/browser_fingerprint_server_test.py')
    add('worker-policy-evidence-gate','tests/browser_worker_policy_evidence_test.py')
    add('worker-policy-server-controls','tests/browser_worker_policy_server_test.py')
    add('worker-policy-runner-controls','tests/browser_worker_policy_runner_test.py')
    add('environment-policy-publication-gate','tests/browser_environment_publish_gate_test.py')
    add('gecko-environment-policy-evidence-gate','tests/gecko_environment_policy_evidence_test.py')
    add('gecko-environment-policy-runner-controls','tests/gecko_environment_policy_runner_test.py')
    cases.append(('gecko-environment-policy-page-controls',['node','tests/gecko_environment_policy_page_test.cjs'],None))
    add('dual-browser-source-history','tests/profile_dual_browser_source_compatibility_test.py')
    add('worker-timezone-source-history','tests/profile_worker_timezone_source_compatibility_test.py')
    add('worker-timezone-host-source-history','tests/profile_worker_timezone_host_source_compatibility_test.py')
    add('phase1-context-fix-source-history','tests/profile_phase1_context_fix_source_compatibility_test.py')
    add('public-source-history','tests/browser_public_history_test.py')
    add('page-bridge-guard-adapters','tests/profile_page_bridge_guard_adapters_test.py')
    add('page-bridge-budget-source-history','tests/profile_page_bridge_budget_source_compatibility_test.py')
    add('ip-timezone-source-history','tests/profile_ip_timezone_source_compatibility_test.py')
    add('ip-timezone-publication','tests/browser_ip_timezone_publication_test.py')
    add('ip-timezone-publisher-gate','tests/browser_ip_timezone_publish_gate_test.py')
    add('ip-timezone-server-controls','tests/browser_ip_timezone_server_test.py')
    add('ip-timezone-evidence-gate','tests/gecko_ip_timezone_evidence_test.py')
    add('ip-timezone-runner-controls','tests/gecko_ip_timezone_runner_test.py')
    for label,jar in [('desktop',desktop),('android-json',android_json)]:
        for name,script in [('gecko-ip-window-barrier','tests/gecko-ip-window-barrier-host/run.py'),('ip-timezone-fixture-process','tests/ip-timezone-fixture-process-host/run.py')]:
            target=out/(name+'-'+label+'.json');add(name+'-'+label,script,java+['--json-jar',jar,'--output',target],target)
    target=out/'gecko-ip-rfp-standard.json';add('gecko-ip-rfp-standard','tests/gecko_ip_timezone_rfp_standard_test.py',java+['--output',target],target)
    add('pure212-ci-source-history','tests/profile_pure212_ci_source_compatibility_test.py')
    for label,jar in [('desktop',desktop),('android-json',android_json)]:
        target=out/('ip-timezone-fixture-ui-hotpath-'+label+'.json');add('ip-timezone-fixture-ui-hotpath-'+label,'tests/ip-timezone-fixture-ui-hotpath-host/run.py',java+['--json-jar',jar,'--output',target],target)
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','app/src/main/java','app/src/main/assets','tests','tools/browser','tools/gecko','.github/workflows/browser-2_1-acceptance.yml'],cwd=ROOT,text=True).splitlines()
    files=[ROOT/name for name in sorted(set(names)) if (ROOT/name).is_file()]
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    environment=dict(os.environ,JSDOM_MODULE=str(a.jsdom_module.resolve()),JAVA_HOME=str(a.java_home.resolve()),PROFILE_JAVA=str(a.java_home.resolve()/'bin/java'),PROFILE_JSON_JAR=str(a.json_jar.resolve()),PROFILE_ANDROID_JSON_JAR=str(a.android_json_jar.resolve()));environment['PATH']=str(a.java_home.resolve()/'bin')+os.pathsep+environment['PATH']
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
    report=dict(status='passed' if passed else 'failed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),executionInputsUnchanged=stable,sourceFiles=hashes,suites=results,requiredSuites=len(cases),completedSuites=len(results),dependencies={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in [desktop,android_json,a.android_jar,a.webkit_jar]},actualAndroidExecution=False,actualAndroidWebViewExecution=False,scope='Production Java/JavaScript host behavior and actual-API compilation with declared adapters. Includes Chromium policy storage/setting adapters/script controls, Gecko website/ChatGPT boundaries and route leases, browser files/permissions and carried shell/loading/progress/chrome/control-cache/transcript regressions. No device execution, full fingerprint protection, site compatibility or frame-rate claim.')
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],completed=len(results),required=len(cases),executionInputsUnchanged=stable)))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
