#!/usr/bin/env python3
"""Run production model/parser policies on the JVM; never labels them Android evidence."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

ANDROID_JSON_SHA256 = 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'


def verify_client_json_run(value, source_id, source_tree, source_dirty, files, jar_sha, contract):
    """Same exact production and immutable-before proof for either JSON implementation."""
    if (value.get('status')!='passed' or type(value.get('passed')) is not int or value['passed']!=92
            or json.dumps(value.get('sourceIdentity'),sort_keys=True,allow_nan=False)!=json.dumps({'sourceCommit':source_id,'sourceTree':source_tree,'sourceDirty':source_dirty,'sourceFiles':files},sort_keys=True,allow_nan=False)
            or value.get('oldFailuresReproduced') is not True or value.get('executionInputsUnchanged') is not True
            or value.get('fullSelectedClass') is not True or value.get('beforeRef')!=contract['BEFORE']
            or value.get('beforeClientSha256')!=contract['BEFORE_CLIENT_SHA256']
            or value.get('sharedWholeJsonHelperSha256')!=files['app/src/main/java/local/pocketchat/J.java']
            or any(value.get(key) is not False for key in ('actualAndroidExecution','actualBinderExecution','actualServiceExecution'))
            or value.get('jsonJarSha256')!=jar_sha or value.get('validationErrors')!=[]
            or value.get('beforeFailuresRequired')!=sorted(contract['KNOWN_OLD_FAILURES'])
            or not isinstance(value.get('runs'),list) or len(value['runs'])!=2):
        raise ValueError('Incomplete paired network-client JSON lifecycle evidence')
    for record,name in zip(value['runs'],('before','current')):
        contract['verify_raw_run'](record);contract['verify_report'](record['report'],expect_pass=name=='current')
        if (json.dumps(json.loads(record['rawStdout']),sort_keys=True,allow_nan=False)!=json.dumps(record['report'],sort_keys=True,allow_nan=False)
                or record['name']!=name or record['sourceCommit']!=(source_id if name=='current' else value['beforeRef'])
                or record['clientSha256']!=(files['app/src/main/java/local/pocketchat/NetworkTransportClient.java'] if name=='current' else value['beforeClientSha256'])
                or (record['exitCode']!=0 if name=='current' else record['exitCode']==0)):
            raise ValueError('Paired network-client JSON execution selection differs')
    return value


def verify_stability_raw(value):
    """Keep complete before/candidate stdout bound to the embedded report."""
    for variant in ('candidate','before'):
        row=value[variant]
        stream_keys={'compileStdout','compileStderr','runtimeStdout','runtimeStderr'}
        if any(not isinstance(row.get(key),str) for key in stream_keys):
            raise ValueError('F04 stability original streams missing')
        actual=json.loads(row['runtimeStdout'])
        projected={key:item for key,item in row.items() if key not in stream_keys}
        if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(projected,sort_keys=True,allow_nan=False):
            raise ValueError('F04 stability original stdout differs')
    return value


def run_optional_android_client(root,output,java,client_host,source_id,source_tree,source_dirty,files,contract):
    """Execute the real paired JVM controls only with the pipeline's pinned jar."""
    android_jar=root/'work/gecko-integration/sharing-android-json.jar'
    android_client=dict(status='not-run',reason='Android JSON dependency is absent in this host pipeline',
        dependencyPath='work/gecko-integration/sharing-android-json.jar',actualAndroidExecution=False)
    if android_jar.exists() or android_jar.is_symlink():
        if android_jar.is_symlink() or not android_jar.is_file() or hashlib.sha256(android_jar.read_bytes()).hexdigest()!=ANDROID_JSON_SHA256:
            raise ValueError('Paired network-client Android JSON dependency differs')
        android_client_receipt=output/'network-transport-client-android-host-results.json'
        android_client_run=subprocess.run([sys.executable,str(client_host),'--java-home',str(Path(java).resolve().parent.parent),
            '--json-jar',str(android_jar),'--output',str(android_client_receipt)],cwd=root,text=True,capture_output=True)
        if android_client_run.returncode:
            raise ValueError('Actual Android-JSON network-client controls failed: '+android_client_run.stdout+android_client_run.stderr)
        android_value=json.loads(android_client_receipt.read_text())
        verify_client_json_run(android_value,source_id,source_tree,source_dirty,files,ANDROID_JSON_SHA256,contract)
        if hashlib.sha256(android_jar.read_bytes()).hexdigest()!=ANDROID_JSON_SHA256:
            raise ValueError('Android JSON dependency changed during paired execution')
        android_client=dict(status='passed',jsonRuntime='android',passed=92,actualAndroidExecution=False,
            output=android_client_run.stdout+android_client_run.stderr,evidence=android_value)
    return android_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-jar", type=Path, default=os.environ.get("PROFILE_JSON_JAR"))
    parser.add_argument("--network-reports", type=Path, help="Reuse already executed, same-source network host receipts from this pipeline")
    args = parser.parse_args()
    if args.json_jar is None or not Path(args.json_jar).is_file():
        parser.error("--json-jar must name a JSON-java jar for JVM model tests (not a production dependency)")
    json_jar = Path(args.json_jar).resolve()
    source_id = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
    source_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    input_paths = set((ROOT / "app/src/main/java").rglob("*.java"))
    input_paths.update((ROOT / "tests").rglob("*.java"))
    input_paths.update((ROOT / "tests").rglob("*.py"))
    input_paths.update((ROOT / "tests").rglob("*.cjs"))
    input_paths.update((ROOT / "tests/gecko/assets").glob("*.js"))
    input_paths.add(ROOT/'tests/fixtures/android-launcher-package-86db516.txt')
    input_paths.add(ROOT/'tests/fixtures/profile-display-workflow-additions.json')
    input_paths.add(ROOT/'tests/gecko/AndroidManifest.xml')
    input_paths.update((ROOT/'tests/gecko/res').rglob('*.xml'))
    input_paths.update(ROOT/'tools/gecko'/name for name in ('caret_ime_guard.py','caret_ime_contract.py','ui_visual_capture.py','caret_build_identity.py'))
    input_paths.add(Path(__file__).resolve())
    input_paths.add(ROOT/'tools/gecko/check_template_evidence.py')
    input_paths.add(ROOT/'tools/gecko/network_scope_artifacts.py')
    input_paths.add(ROOT/'tools/gecko/chrome_collapse_contract.py')
    input_paths.add(ROOT/'tools/gecko/local_draft_contract.py')
    draft_admission_inputs={path for path in (ROOT/'tests/local-draft-admission-host').rglob('*')
                            if path.is_file() and path.suffix in ('.py','.java','.in','.json')}
    input_paths.update(draft_admission_inputs)
    transport_client_inputs={path for path in (ROOT/'tests/network-transport-client-host').rglob('*')
                             if path.is_file() and path.suffix in ('.py','.java','.md','.in','.json')}
    input_paths.update(transport_client_inputs)
    input_paths.update(ROOT/'tools/gecko'/name for name in ('network_client_binding_contract.py','sdk_identity_contract.py'))
    resume_fixture_inputs={ROOT/'tests/profile_download_resume_fixture_test.py',ROOT/'tests/download-resume-fixture-host/CookieFixtureHost.java.in',
        ROOT/'tests/download-resume-fixture-host/fixture-preservation.json',ROOT/'tests/gecko/DownloadResumeIntegrationActivity.java',
        ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java',ROOT/'app/src/main/java/local/pocketchat/FileDownloads.java',
        ROOT/'app/src/main/java/local/pocketchat/J.java',ROOT/'app/src/main/java/local/pocketchat/DownloadRange.java',ROOT/'app/src/main/java/local/pocketchat/SealedFileIo.java',
        ROOT/'tests/download-resume-host/run.py',ROOT/'tests/sealed-file-host/android/util/AtomicFile.java',ROOT/'tests/download-recovery-host/android/os/Handler.java',
        ROOT/'tests/download-recovery-host/android/os/Looper.java',ROOT/'tests/download-recovery-host/android/net/Uri.java',
        ROOT/'tests/download-resume-host/stubs/android/util/Base64.java',ROOT/'tests/download-resume-host/stubs/android/os/SystemClock.java'}
    input_paths.update(resume_fixture_inputs)
    draft_stability_inputs={ROOT/'tests/gecko/GeckoLocalDraftIntegration.java',ROOT/'app/src/main/java/local/pocketchat/J.java',
                            ROOT/'tests/page-recovery-host/run.py',
                            *[p for p in (ROOT/'tests/local-draft-restoration-stability-host').glob('*') if p.is_file()]}
    input_paths.update(draft_stability_inputs)
    input_paths.add(ROOT/'tools/gecko/download_resume_contract.py')
    input_paths.add(ROOT/'tools/gecko/check_interaction_transfer_evidence.py')
    input_paths.add(ROOT/'tools/publish-gecko-release.py')
    input_paths.update(ROOT/'tools/gecko'/name for name in ('integration_event_contract.py','profile_invocation_contract.py','page_continuity_contract.py','network_sources_contract.py','caret_dispatch.py','installed_apk_read.py','caret_launcher_guard.py','run_caret_editing_phase.py','check_caret_compat_evidence.py'))
    input_paths.add(ROOT/'app/src/main/AndroidManifest.xml')
    proxy_script = ROOT / 'app/src/main/assets/gecko/background.js'
    proxy_test = ROOT / 'tests/browser-runtime/gecko-proxy-route.test.cjs'
    if proxy_test.is_file():
        input_paths.add(proxy_script)
    input_paths.add(ROOT / "tools/gecko/run_resource_host_checks.py")
    input_paths.update((ROOT / "app/src/main/assets/gecko").glob("*.js"))
    before_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
    java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
    if not java:
        parser.error("JDK 17+ with jdk.compiler is required")
    output = ROOT / "work/profile-host"
    classes = output / "classes"
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True, exist_ok=True)
    (output / "results.json").unlink(missing_ok=True)
    source = ROOT / "app/src/main/java/local/pocketchat"
    tests = ROOT / "tests/browser-runtime"
    groups = [
        ("Sha256Test", ["Sha256"]),
        ("NetworkHealthPolicyTest", ["NetworkHealthPolicy"]),
        ("NetworkOptimizationPolicyTest", ["NetworkOptimizationPolicy"]),
        ("RouteQualityComparisonTest", ["J", "RouteQuality", "LatencyProbePolicy", "NetworkOptimizationPolicy"]),
        ("NetworkStatusPolicyTest", ["NetworkStatusPolicy"]),
        ("NetworkPoolIdentityTest", ["NetworkPoolIdentity"]),
        ("LatencyProbePolicyTest", ["LatencyProbePolicy"]),
        ("LatencyRefreshPolicyTest", ["LatencyRefreshPolicy"]),
        ("EnvironmentSpecTest", ["J", "EnvironmentSpec", "EnvironmentSpecMigration"]),
        ("EnvironmentLifecyclePolicyTest", ["J", "EnvironmentSpec", "EnvironmentSpecMigration", "EnvironmentResetPlan", "EnvironmentBrowserData", "EnvironmentProcessPolicy"]),
    ]
    extras = [("FingerprintTemplateTest", ["J", "BrowserIdentitySpec", "AuditReport"]),("BrowserEditIntentTest",["J","BrowserEditIntent"]),("DownloadListPolicyTest",["DownloadListPolicy"]),("ChromeCollapseGestureTest",["ChromeCollapseGesture"])]
    groups += [(name, names) for name, names in extras if (tests / (name + ".java")).is_file()]
    if (tests / "ChromeCollapseDocumentReadyAdapterTest.java").is_file():
        groups.append(("ChromeCollapseDocumentReadyAdapterTest", []))
    if (tests / "ReloadDocumentReadyAdapterTest.java").is_file():
        groups.append(("ReloadDocumentReadyAdapterTest", []))
    files = {source / (name + ".java") for _, names in groups for name in names}
    files.update(tests / (name + ".java") for name, _ in groups)
    files.update((ROOT / "tests/route-quality-host/android/content").glob("*.java"))
    if (tests / "ChromeCollapseDocumentReadyAdapterTest.java").is_file():
        files.add(ROOT / "tests/gecko/ChromeCollapseDocumentReadyAdapter.java")
    if (tests / "ReloadDocumentReadyAdapterTest.java").is_file():
        files.add(ROOT / "tests/gecko/ReloadDocumentReadyAdapter.java")
    if (tests / "FingerprintTemplateTest.java").is_file():
        files.add(tests / "fingerprint-report-stubs/BrowserNetworkGuard.java")
    compiler = [java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-encoding", "UTF-8",
                "-source", "8", "-target", "8", "-classpath", str(json_jar), "-d", str(classes)]
    subprocess.run(compiler + [str(path) for path in sorted(files)], cwd=ROOT, check=True)
    results = []
    for name, _ in groups:
        command = [java, "-cp", str(classes) + os.pathsep + str(json_jar), "local.pocketchat." + name]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        results.append({"test": name, "exitCode": run.returncode, "output": run.stdout.strip()})
        print(run.stdout.strip())
        if run.returncode:
            print(run.stderr, file=sys.stderr)
            raise subprocess.CalledProcessError(run.returncode, command)
    # Reuse the latest published source/catalogue implementations instead of the old SOCKS-only parser.
    for directory in ("network-catalog-host", "network-source-host", "network-lineage-host", "sealed-file-host"):
        receipt = output / (directory + "-results.json")
        receipt.unlink(missing_ok=True)
        if args.network_reports is not None:
            previous = args.network_reports / (directory + "-results.json")
            report = json.loads(previous.read_text())
            if report.get("sourceCommit") != source_id or report.get("actualAndroidExecution") is not False or not isinstance(report.get("passed"), int) or report["passed"] < 1:
                raise ValueError("Reusable host receipt must be executed against this exact source: " + directory)
            shutil.copyfile(previous, receipt)
        else:
            command = [sys.executable, str(ROOT / "tests" / directory / "run.py"), "--output", str(receipt)]
            if directory != "sealed-file-host":
                command += ["--json-jar", str(json_jar)]
            subprocess.run(command, cwd=ROOT, check=True)
        report = json.loads(receipt.read_text())
        if report.get("actualAndroidExecution") is not False:
            raise ValueError("Host fixtures cannot claim Android execution")
        results.append({"test": directory, "report": str(receipt.relative_to(ROOT)), "passed": report.get("passed"),
                        "actualAndroidExecution": False})
        files.update((ROOT / "tests" / directory).rglob("*.java"))
    files.update(source / name for name in ("NetworkCatalog.java", "NetworkShareSnapshot.java", "NetworkShareJson.java", "NetworkSubscriptionCatalogPolicy.java",
        "NetworkSourceSelection.java", "EntrySelection.java", "NetworkDraft.java", "NetworkChanges.java",
        "NetworkOptimizationPolicy.java", "SealedFileIo.java", "ProfileCatalog.java",
        "EnvironmentSpecRepository.java", "EnvironmentSpecRuntime.java", "EnvironmentApplyCoordinator.java",
        "NativeNetwork.java", "NetworkUiProvider.java"))
    subprocess.run(["node", "tests/browser-runtime/session-cookies.test.cjs"], cwd=ROOT, check=True)
    if proxy_test.is_file():
        proxy_run = subprocess.run(['node', str(proxy_test)], cwd=ROOT, check=True,
                                   text=True, capture_output=True)
        proxy_value = json.loads(proxy_run.stdout)
        if (proxy_value.get('status') != 'passed' or proxy_value.get('sourceCommit') != source_id
                or proxy_value.get('sourceTree') != source_tree
                or proxy_value.get('actualAndroidExecution') is not False
                or proxy_value.get('actualProductionScriptExecution') is not True):
            raise ValueError('Actual production proxy script host execution is required')
        proxy_receipt = output / 'gecko-proxy-route-host-results.json'
        proxy_receipt.write_text(proxy_run.stdout)
        results.append({'test':'gecko-proxy-route-host',
                        'report':str(proxy_receipt.relative_to(ROOT)),
                        'passed':proxy_value.get('passed'),'actualAndroidExecution':False})
        files.update([proxy_script, proxy_test])
    bridges = sorted((ROOT / "tests/review-host").glob("*.cjs"))
    bridge_results=[]
    for bridge in bridges:
        run=subprocess.run(["node","--test","--test-reporter=tap",str(bridge)],cwd=ROOT,text=True,capture_output=True)
        print(run.stdout)
        if run.returncode:print(run.stderr,file=sys.stderr);raise subprocess.CalledProcessError(run.returncode,run.args)
        passed=re.search(r"^# pass (\d+)$",run.stdout,re.M);total=re.search(r"^# tests (\d+)$",run.stdout,re.M);failed=re.search(r"^# fail (\d+)$",run.stdout,re.M)
        if not passed or not total or not failed or passed.group(1)!=total.group(1) or failed.group(1)!="0":raise ValueError("Incomplete source bridge host suite: "+bridge.name)
        bridge_results.append({"test":bridge.name,"passed":int(passed.group(1)),"total":int(total.group(1)),"output":run.stdout})
        files.add(bridge)
    files.update((ROOT / "app/src/main/assets/gecko").glob("*.js"))
    bridge_inputs=set(bridges)|set((ROOT / "app/src/main/assets/gecko").glob("*.js"))
    (output / "identity-bridge-host-results.json").write_text(json.dumps({"schema":1,"status":"passed","actualAndroidExecution":False,"sourceCommit":source_id,"sourceTree":source_tree,"sourceDirty":bool(source_status.strip()),"sourceUnchangedDuringChecks":True,"results":bridge_results,"files":{str(path.relative_to(ROOT)):before_hashes[path] for path in sorted(bridge_inputs)}},indent=2)+"\n")
    intent = ROOT / "tests/environment-intent-host/run.py"
    if intent.is_file():
        intent_receipt = output / "environment-intent-host-results.json"
        subprocess.run([sys.executable, str(intent), "--json-jar", str(json_jar), "--output", str(intent_receipt)], cwd=ROOT, check=True)
        value = json.loads(intent_receipt.read_text())
        if value.get("actualAndroidExecution") is not False:
            raise ValueError("Intent host checks cannot claim Android execution")
        results.append({"test":"environment-intent-host","report":str(intent_receipt.relative_to(ROOT)),"passed":value.get("passed"),"actualAndroidExecution":False})
        files.update((ROOT / "tests/environment-intent-host").rglob("*.java"))
    controller = ROOT / "tests/review-host/run_identity_controller_host.py"
    if controller.is_file():
        controller_receipt=output / "identity-controller-host-results.json"
        subprocess.run([sys.executable,str(controller),"--json-jar",str(json_jar),"--output",str(controller_receipt)],cwd=ROOT,check=True)
        receipt=json.loads(controller_receipt.read_text());results.append({"test":"identity-controller-host","report":str(controller_receipt.relative_to(ROOT)),"passed":receipt["passed"],"actualAndroidExecution":False})
        files.update(ROOT/path for path in receipt["files"])
    deferred = ROOT / "tests/review-host/run_deferred_browser_host.py"
    if deferred.is_file():
        deferred_receipt=output / "deferred-browser-host-results.json"
        subprocess.run([sys.executable,str(deferred),"--json-jar",str(json_jar),"--output",str(deferred_receipt)],cwd=ROOT,check=True)
        receipt=json.loads(deferred_receipt.read_text());results.append({"test":"deferred-browser-host","report":str(deferred_receipt.relative_to(ROOT)),"passed":receipt["passed"],"actualAndroidExecution":False})
        files.update(ROOT/path for path in receipt["files"])
    terminal = ROOT / "tests/source-route-terminal-host/run.py"
    terminal_receipt = output / "source-route-terminal-host-results.json"
    subprocess.run([sys.executable, str(terminal), "--java-home", str(Path(shutil.which(java) or java).resolve().parent.parent),
                    "--json-jar", str(json_jar), "--output", str(terminal_receipt)], cwd=ROOT, check=True)
    terminal_value = json.loads(terminal_receipt.read_text())
    results.append({"test":"source-route-terminal", "report":str(terminal_receipt.relative_to(ROOT)),
                    "passed":terminal_value["total"], "actualAndroidExecution":False})
    files.update([terminal, ROOT / "tests/source-route-terminal-host/TerminalObserverTest.java", ROOT / "tests/gecko/SourceRouteTerminalObserver.java",
                  ROOT / "tests/gecko/NetworkSourcesRouteIntegrationActivity.java", ROOT / "tests/gecko/run_network_sources_route.py",
                  ROOT / "tests/profile_network_source_terminal_contract_test.py"])
    start_observation = ROOT / "tests/source-route-start-host/run.py"
    start_receipt = output / "source-route-start-host-results.json"
    subprocess.run([sys.executable, str(start_observation), "--java-home", str(Path(shutil.which(java) or java).resolve().parent.parent),
                    "--json-jar", str(json_jar), "--output", str(start_receipt)], cwd=ROOT, check=True)
    start_value = json.loads(start_receipt.read_text())
    results.append({"test":"source-route-start-observation", "report":str(start_receipt.relative_to(ROOT)),
                    "passed":start_value["total"], "actualAndroidExecution":False, "evidence":start_value})
    files.update([start_observation, ROOT / "tests/source-route-start-host/StartObservationTest.java",
                  ROOT / "tests/source-route-start-host/TerminalJoinTest.java", ROOT / "tests/source-route-start-host/terminal_join.py",
                  ROOT / "tests/gecko/SourceRouteStartObservation.java", ROOT / "app/src/main/java/local/pocketchat/NativeNetwork.java"])
    caret_test = ROOT / "tests/browser-runtime/caret-document-observer.test.cjs"
    if caret_test.is_file():
        caret_asset = ROOT / "tests/gecko/assets/caret-document-observer.js"
        command = ["node", "--test", "--test-reporter=tap", str(caret_test)]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if run.returncode:
            print(run.stdout, end="", flush=True)
            print(run.stderr, end="", file=sys.stderr, flush=True)
            raise subprocess.CalledProcessError(run.returncode, command, run.stdout, run.stderr)
        total = re.search(r"^# tests (\d+)$",run.stdout,re.M)
        passed = re.search(r"^# pass (\d+)$",run.stdout,re.M)
        failed = re.search(r"^# fail (\d+)$",run.stdout,re.M)
        if not total or not passed or not failed or int(total.group(1))<14 or total.group(1)!=passed.group(1) or failed.group(1)!="0":
            raise ValueError("Incomplete isolated caret observer host controls")
        inputs = [caret_test,caret_asset,ROOT / "app/src/main/assets/gecko/content.js"]
        value = dict(sourceCommit=source_id,sourceTree=source_tree,sourceDirty=bool(source_status.strip()),
            sourceUnchangedDuringChecks=True,status="passed",actualAndroidExecution=False,
            actualGeckoExecution=False,synthetic=True,passed=int(passed.group(1)),total=int(total.group(1)),
            scope="Actual production bridge and integration observer code in separate VM realms sharing explicit DOM doubles. Events are synthetic host callbacks; not Android input or Gecko isolation acceptance.",
            output=run.stdout,files={str(path.relative_to(ROOT)):before_hashes[path] for path in inputs})
        receipt=output / "caret-document-observer-host-results.json"
        receipt.write_text(json.dumps(value,indent=2)+"\n")
        results.append(dict(test="caret-document-observer-host",report=str(receipt.relative_to(ROOT)),passed=value["passed"],actualAndroidExecution=False))
        files.update(inputs)
    collapse_telemetry=ROOT/'tests/browser-runtime/chrome-collapse-telemetry.test.cjs'
    if collapse_telemetry.is_file():
        command=['node','--test','--test-reporter=tap',str(collapse_telemetry)]
        run=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        if run.returncode:raise subprocess.CalledProcessError(run.returncode,command,run.stdout,run.stderr)
        total=re.search(r'^# tests (\d+)$',run.stdout,re.M);passed=re.search(r'^# pass (\d+)$',run.stdout,re.M);failed=re.search(r'^# fail (\d+)$',run.stdout,re.M)
        if not total or not passed or not failed or int(total.group(1))<12 or total.group(1)!=passed.group(1) or failed.group(1)!='0':raise ValueError('Incomplete shared-DOM chrome telemetry host controls')
        inputs=[collapse_telemetry,ROOT/'tests/gecko/run_ui_visuals.py',ROOT/'tests/gecko/ChromeCollapseIntegration.java']
        value=dict(sourceCommit=source_id,sourceTree=source_tree,sourceDirty=bool(source_status.strip()),status='passed',actualAndroidExecution=False,actualGeckoExecution=False,synthetic=True,
            passed=int(passed.group(1)),total=int(total.group(1)),scope='Actual fixture/snapshot expressions in separate host VM globals sharing a DOM double. All callback events are explicitly synthetic and untrusted; no Android input or trusted-touch acceptance.',
            output=run.stdout,files={str(path.relative_to(ROOT)):before_hashes[path] for path in inputs})
        receipt=output/'chrome-collapse-telemetry-host-results.json';receipt.write_text(json.dumps(value,indent=2)+'\n')
        results.append(dict(test='chrome-collapse-telemetry-host',report=str(receipt.relative_to(ROOT)),passed=value['passed'],actualAndroidExecution=False));files.update(inputs)
    # Receipt coverage includes Android lifecycle/admission sources without pretending to compile them on the host JVM.
    lifecycle_sources=('EnvironmentSpec','EnvironmentResetPlan','EnvironmentBrowserData','EnvironmentProcessPolicy','EnvironmentSpecRepository','ProfileCatalog','Profiles','ProfileContext','EnvironmentResetActivity','WindowHomeActivity','MainActivity','ChatSession','ChatService','NetworkUiProvider','AppUpdateRoute','EnvironmentDeleteActivity','EnvironmentSpecRuntime')
    files.update(source/(name+'.java') for name in lifecycle_sources)
    files.update((ROOT/'app/src/main/AndroidManifest.xml',ROOT/'tests/gecko/EnvironmentManagementIntegrationActivity.java',ROOT/'tests/gecko/run_device.py'))
    files.update((ROOT/'tests/gecko/GeckoIntegrationTestActivity.java',ROOT/'tools/gecko/check_template_evidence.py'))
    files.update((ROOT/'tests/gecko/GeckoLocalDraftIntegration.java',ROOT/'tools/gecko/local_draft_contract.py'))
    files.update((ROOT/'tools/gecko/download_resume_contract.py',ROOT/'tests/gecko/DownloadResumeIntegrationActivity.java',ROOT/'tests/gecko/AndroidManifest.xml'))
    files.add(ROOT/'tools/gecko/check_interaction_transfer_evidence.py')
    files.add(ROOT/'tools/gecko/network_scope_artifacts.py')
    files.add(ROOT/'tools/publish-gecko-release.py')
    files.update(ROOT/'tools/gecko'/name for name in ('integration_event_contract.py','profile_invocation_contract.py','page_continuity_contract.py','network_sources_contract.py','caret_dispatch.py','installed_apk_read.py','caret_launcher_guard.py','run_caret_editing_phase.py','check_caret_compat_evidence.py'))
    files.add(ROOT/'tests/fixtures/android-launcher-package-86db516.txt')
    files.update((ROOT/'tests/gecko/GeckoCaretCompatibilityIntegrationActivity.java',
                  ROOT/'tests/gecko_caret_input_diagnostics_test.py'))
    files.update(ROOT/'tools/gecko'/name for name in ('caret_ime_guard.py','caret_ime_contract.py','ui_visual_capture.py','caret_build_identity.py'))
    files.update((ROOT/'tests/gecko/AndroidManifest.xml',ROOT/'tests/gecko/ControlledCaretInputMethodService.java',
                  ROOT/'tests/gecko/run_gecko_caret_compat.py',ROOT/'tests/gecko/run_ui_visuals.py',
                  ROOT/'tests/gecko_ui_visual_capture_test.py'))
    files.update((ROOT/'tests/gecko/res').rglob('*.xml'))
    pressure_receipt=output / "resource-pressure-host-results.json"
    subprocess.run([sys.executable,str(ROOT / "tools/gecko/run_resource_host_checks.py"),"--json-jar",str(json_jar),"--output",str(pressure_receipt)],cwd=ROOT,check=True)
    pressure=json.loads(pressure_receipt.read_text());results.append({"test":"resource-pressure-host","report":str(pressure_receipt.relative_to(ROOT)),"passed":pressure["passed"],"actualAndroidExecution":False})
    files.update(ROOT/path for path in pressure["files"])
    # Execute the real SAF-copy implementation against host streams/files. This
    # complements, and does not stand in for, the Android prompt/picker checks.
    upload_test=ROOT/'tests/gecko_upload_files_test.py'
    upload_run=subprocess.run([sys.executable,str(upload_test)],cwd=ROOT,text=True,capture_output=True)
    if upload_run.returncode:
        raise subprocess.CalledProcessError(upload_run.returncode,upload_run.args,upload_run.stdout,upload_run.stderr)
    upload_records=[json.loads(line) for line in upload_run.stdout.splitlines() if line.startswith('{')]
    if len(upload_records)!=1 or upload_records[0].get('status')!='passed' or upload_records[0].get('checks',0)<17 or upload_records[0].get('actualAndroidExecution') is not False:
        raise ValueError('Incomplete production upload-file host checks')
    upload_receipt=output/'gecko-upload-files-host-results.json'
    upload_receipt.write_text(json.dumps(dict(upload_records[0],sourceCommit=source_id,sourceTree=source_tree,
        sourceDirty=bool(source_status.strip()),output=upload_run.stdout),indent=2)+'\n')
    results.append(dict(test='gecko-upload-files-host',report=str(upload_receipt.relative_to(ROOT)),passed=upload_records[0]['checks'],actualAndroidExecution=False))
    files.update((upload_test,source/'GeckoUploadFiles.java'))
    draft_contract_test=ROOT/'tests/gecko_local_draft_contract_test.py'
    draft_contract_run=subprocess.run([sys.executable,str(draft_contract_test)],cwd=ROOT,text=True,capture_output=True,
        env=dict(os.environ,PROFILE_JSON_JAR=str(json_jar),PROFILE_JAVA=java))
    draft_contract_count=re.search(r'^Ran (\d+) tests? in ',draft_contract_run.stderr,re.M)
    if draft_contract_run.returncode or draft_contract_count is None or int(draft_contract_count.group(1))!=75:
        raise ValueError('Incomplete F04 counterfeit evidence controls: '+draft_contract_run.stdout+draft_contract_run.stderr)
    blank_controls=json.loads(draft_contract_run.stdout)['blankBarrierControls']
    blank_inputs={ROOT/'tests/gecko/GeckoLocalDraftBlankBarrier.java',source/'J.java',
                  *list((ROOT/'tests/local-draft-blank-host').rglob('*.java'))}
    if (blank_controls.get('status')!='passed' or blank_controls.get('checks')!=96
            or len(blank_controls.get('results',[]))!=96
            or len({row.get('name') for row in blank_controls['results']})!=96
            or not all(row.get('pass') is True for row in blank_controls['results'])
            or blank_controls.get('actualAndroidExecution') is not False
            or blank_controls.get('actualGeckoExecution') is not False
            or blank_controls.get('executionInputsUnchanged') is not True
            or blank_controls.get('jsonJarSha256')!=hashlib.sha256(json_jar.read_bytes()).hexdigest()
            or blank_controls.get('sourceFiles')!={str(path.relative_to(ROOT)):before_hashes[path] for path in blank_inputs}):
        raise ValueError('Incomplete actual F04 blank-preparation helper controls')
    results.append(dict(test='local-draft-evidence-controls',passed=int(draft_contract_count.group(1)),actualAndroidExecution=False,
        output=draft_contract_run.stdout+draft_contract_run.stderr,blankBarrierControls=blank_controls))
    files.update((draft_contract_test,ROOT/'tests/profile_lifecycle_gate_test.py',ROOT/'tools/publish-gecko-release.py',
                  ROOT/'tools/gecko/local_draft_contract.py',ROOT/'tests/gecko/GeckoLocalDraftIntegration.java'))
    files.update((ROOT/'tests/gecko/GeckoLocalDraftBlankBarrier.java',ROOT/'tests/gecko_local_draft_blank_barrier_test.py',ROOT/'tests/page-recovery-host/run.py'))
    files.update((ROOT/'tests/local-draft-blank-host').rglob('*.java'))
    resume_fixture_receipt=output/'download-resume-fixture-host-results.json'
    resume_fixture_run=subprocess.run([sys.executable,str(ROOT/'tests/profile_download_resume_fixture_test.py')],cwd=ROOT,text=True,capture_output=True,
        env=dict(os.environ,PROFILE_JSON_JAR=str(json_jar),PROFILE_JAVA=java,F06_COOKIE_HOST_REPORT=str(resume_fixture_receipt)))
    resume_fixture_count=re.search(r'^Ran (\d+) tests? in ',resume_fixture_run.stderr,re.M)
    if resume_fixture_run.returncode or resume_fixture_count is None or int(resume_fixture_count.group(1))!=4:
        raise ValueError('Incomplete F06 owned Cookie adapter controls: '+resume_fixture_run.stdout+resume_fixture_run.stderr)
    resume_fixture=json.loads(resume_fixture_receipt.read_text())
    raw_resume_fixture=json.loads(resume_fixture['runtimeStdout'])
    resume_raw_keys=('status','checkCount','checks','actualAndroidExecution','actualGeckoExecution','actualLoopbackHttp')
    if (json.dumps(raw_resume_fixture,sort_keys=True,allow_nan=False)!=json.dumps({key:resume_fixture[key] for key in resume_raw_keys},sort_keys=True,allow_nan=False)
            or resume_fixture.get('status')!='passed' or type(resume_fixture.get('checkCount')) is not int or resume_fixture['checkCount']!=57
            or len(resume_fixture.get('checks',[]))!=57 or len({row.get('name') for row in resume_fixture['checks']})!=57
            or not all(row.get('pass') is True for row in resume_fixture['checks'])
            or resume_fixture.get('actualAndroidExecution') is not False or resume_fixture.get('actualGeckoExecution') is not False
            or resume_fixture.get('actualLoopbackHttp') is not True or resume_fixture.get('inputsUnchanged') is not True
            or resume_fixture.get('sourceCommit')!=source_id or resume_fixture.get('jsonJarSha256')!=hashlib.sha256(json_jar.read_bytes()).hexdigest()
            or resume_fixture.get('sourceFiles')!={str(path.relative_to(ROOT)):before_hashes[path] for path in resume_fixture_inputs}):
        raise ValueError('Incomplete exact production F06 Cookie/download host evidence')
    results.append(dict(test='download-resume-fixture-host',passed=4,actualAndroidExecution=False,
        output=resume_fixture_run.stdout+resume_fixture_run.stderr,evidence=resume_fixture))
    files.update(resume_fixture_inputs)
    draft_stability_receipt=output/'local-draft-restoration-stability-host-results.json'
    draft_stability_run=subprocess.run([sys.executable,str(ROOT/'tests/local-draft-restoration-stability-host/run.py'),
        '--java-home',str(Path(java).resolve().parent.parent),'--json-jar',str(json_jar),
        '--output',str(draft_stability_receipt)],cwd=ROOT,text=True,capture_output=True)
    if draft_stability_run.returncode:
        raise ValueError('Complete F04 restoration stability method controls failed: '+draft_stability_run.stdout+draft_stability_run.stderr)
    stability_spec=importlib.util.spec_from_file_location('selected_f04_stability_contract',ROOT/'tests/local-draft-restoration-stability-host/run.py')
    stability_contract=importlib.util.module_from_spec(stability_spec);stability_spec.loader.exec_module(stability_contract)
    draft_stability=json.loads(draft_stability_receipt.read_text())
    selected=[dict(signature=name,sha256=hashlib.sha256(method.encode()).hexdigest()) for name,method in zip(
        stability_contract.SIGNATURES,stability_contract.select_methods((ROOT/'tests/gecko/GeckoLocalDraftIntegration.java').read_text()))]
    stability_contract.verify_report(draft_stability,source_id,
        {str(path.relative_to(ROOT)):before_hashes[path] for path in draft_stability_inputs},
        hashlib.sha256(json_jar.read_bytes()).hexdigest(),selected)
    verify_stability_raw(draft_stability)
    if draft_stability.get('sourceDirty')!=bool(source_status.strip()):
        raise ValueError('F04 stability host source cleanliness differs')
    results.append(dict(test='local-draft-restoration-stability-host',report=str(draft_stability_receipt.relative_to(ROOT)),
        passed=27,candidateControls=25,oldCounterexampleControls=2,actualAndroidExecution=False,evidence=draft_stability))
    files.update(draft_stability_inputs)
    draft_admission_receipt=output/'local-draft-admission-host-results.json'
    draft_admission_run=subprocess.run([sys.executable,str(ROOT/'tests/local-draft-admission-host/run.py'),
        '--java-home',str(Path(java).resolve().parent.parent),'--json-jar',str(json_jar),
        '--output',str(draft_admission_receipt)],cwd=ROOT,text=True,capture_output=True)
    if draft_admission_run.returncode:
        raise ValueError('Production PageMemory admission controls failed: '+draft_admission_run.stdout+draft_admission_run.stderr)
    draft_admission=json.loads(draft_admission_receipt.read_text())
    if (draft_admission.get('status')!='passed' or draft_admission.get('checkCount')!=73
            or len(draft_admission.get('checks',[]))!=73 or not all(row.get('pass') is True for row in draft_admission['checks'])
            or draft_admission.get('actualAndroidExecution') is not False
            or draft_admission.get('actualGeckoExecution') is not False
            or draft_admission.get('realChatGptPageMemoryCapture') is not False
            or draft_admission.get('sourceCommit')!=source_id
            or draft_admission.get('productionAdmissionExecuted') is not True
            or draft_admission.get('executionInputsUnchanged') is not True):
        raise ValueError('Incomplete actual PageMemory admission host controls')
    results.append(dict(test='local-draft-admission-host',report=str(draft_admission_receipt.relative_to(ROOT)),
                        passed=draft_admission['checkCount'],actualAndroidExecution=False,evidence=draft_admission))
    files.update(draft_admission_inputs)
    client_host=ROOT/'tests/network-transport-client-host/run.py'
    client_receipt=output/'network-transport-client-host-results.json'
    client_run=subprocess.run([sys.executable,str(client_host),'--java-home',str(Path(java).resolve().parent.parent),
        '--json-jar',str(json_jar),'--output',str(client_receipt)],cwd=ROOT,text=True,capture_output=True)
    if client_run.returncode:
        raise ValueError('Actual network-client lifecycle controls failed: '+client_run.stdout+client_run.stderr)
    client_report=json.loads(client_receipt.read_text());client_contract=runpy.run_path(str(client_host))
    client_sources=transport_client_inputs|{source/'NetworkTransportClient.java',source/'J.java'}
    expected_client_files={str(path.relative_to(ROOT)):before_hashes[path] for path in client_sources}
    if (client_report.get('status')!='passed' or type(client_report.get('passed')) is not int or client_report['passed']!=92
            or client_report.get('sourceIdentity')!={'sourceCommit':source_id,'sourceTree':source_tree,
                'sourceDirty':bool(source_status.strip()),'sourceFiles':expected_client_files}
            or client_report.get('oldFailuresReproduced') is not True
            or client_report.get('executionInputsUnchanged') is not True or client_report.get('fullSelectedClass') is not True
            or client_report.get('beforeRef')!='3eac2891438d37aa62f695b34a90f0aa02215ca2'
            or client_report.get('sharedWholeJsonHelperSha256')!=before_hashes[source/'J.java']
            or any(client_report.get(key) is not False for key in ('actualAndroidExecution','actualBinderExecution','actualServiceExecution'))
            or client_report.get('jsonJarSha256')!=hashlib.sha256(json_jar.read_bytes()).hexdigest()
            or not isinstance(client_report.get('runs'),list) or len(client_report['runs'])!=2):
        raise ValueError('Incomplete source-bound network-client lifecycle controls')
    for record,name in zip(client_report['runs'],('before','current')):
        client_contract['verify_raw_run'](record)
        client_contract['verify_report'](record['report'],expect_pass=name=='current')
        if (record['name']!=name or record['sourceCommit']!=(source_id if name=='current' else client_report['beforeRef'])
                or record['clientSha256']!=(before_hashes[source/'NetworkTransportClient.java'] if name=='current' else client_report['beforeClientSha256'])
                or (record['exitCode']!=0 if name=='current' else record['exitCode']==0)):
            raise ValueError('Network-client lifecycle execution selection differs')
    verify_client_json_run(client_report,source_id,source_tree,bool(source_status.strip()),expected_client_files,
        hashlib.sha256(json_jar.read_bytes()).hexdigest(),client_contract)
    android_client=run_optional_android_client(ROOT,output,java,client_host,source_id,source_tree,
        bool(source_status.strip()),expected_client_files,client_contract)
    results.append(dict(test='network-transport-client-host',report=str(client_receipt.relative_to(ROOT)),
                        passed=92,actualAndroidExecution=False,evidence=client_report,androidJson=android_client))
    files.update(transport_client_inputs)
    files.update((source/'NetworkTransportClient.java',source/'J.java'))
    framework_controls=ROOT/'tests/gecko_network_client_binding_test.py'
    framework_run=subprocess.run([sys.executable,str(framework_controls)],cwd=ROOT,text=True,capture_output=True)
    framework_count=re.search(r'^Ran (\d+) tests? in ',framework_run.stderr,re.M)
    if framework_run.returncode or framework_count is None or int(framework_count.group(1))!=41:
        raise ValueError('Incomplete framework binding evidence controls: '+framework_run.stdout+framework_run.stderr)
    results.append(dict(test='network-client-framework-evidence-controls',passed=41,actualAndroidExecution=False,
        output=framework_run.stdout+framework_run.stderr))
    files.update((framework_controls,ROOT/'tools/gecko/network_client_binding_contract.py',ROOT/'tools/gecko/sdk_identity_contract.py',
                  ROOT/'tests/profile_display_sampling_gate_test.py',ROOT/'tests/fixtures/profile-display-workflow-additions.json',
                  ROOT/'tests/gecko/NetworkClientBindingIntegrationActivity.java',ROOT/'tests/gecko/run_network_client_binding.py',ROOT/'tests/gecko/AndroidManifest.xml'))
    if (subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != source_id
            or subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) != source_status
            or any(not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest
                   for path, digest in before_hashes.items())
            or any(path not in before_hashes for path in files)):
        raise ValueError("Source changed during host checks; discard this execution")
    report = {"schema": 1, "status": "passed", "actualAndroidExecution": False,
              "scope": "JVM production environment/network models and storage/protocol fixtures only; no Gecko or Android execution",
              "sourceCommit": source_id,
              "sourceTree": source_tree,
              "sourceDirty": bool(source_status.strip()),
              "sourceUnchangedDuringChecks": True,
              "jsonJarSha256": hashlib.sha256(json_jar.read_bytes()).hexdigest(),
              "results": results,
              "files": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}}
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Host report: work/profile-host/results.json; Android, SDK build, ARM and real login remain separate.")

if __name__ == "__main__":
    main()
