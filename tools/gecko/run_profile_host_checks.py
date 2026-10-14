#!/usr/bin/env python3
"""Run production model/parser policies on the JVM; never labels them Android evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

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
    input_paths.add(Path(__file__).resolve())
    input_paths.add(ROOT/'tools/gecko/check_template_evidence.py')
    input_paths.update(ROOT/'tools/gecko'/name for name in ('integration_event_contract.py','profile_invocation_contract.py'))
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
        ("NetworkHealthPolicyTest", ["NetworkHealthPolicy"]),
        ("NetworkStatusPolicyTest", ["NetworkStatusPolicy"]),
        ("NetworkPoolIdentityTest", ["NetworkPoolIdentity"]),
        ("LatencyProbePolicyTest", ["LatencyProbePolicy"]),
        ("EnvironmentSpecTest", ["J", "EnvironmentSpec", "EnvironmentSpecMigration"]),
        ("EnvironmentLifecyclePolicyTest", ["J", "EnvironmentSpec", "EnvironmentSpecMigration", "EnvironmentResetPlan", "EnvironmentBrowserData", "EnvironmentProcessPolicy"]),
    ]
    extras = [("FingerprintTemplateTest", ["J", "BrowserIdentitySpec", "AuditReport"]),("BrowserEditIntentTest",["J","BrowserEditIntent"])]
    groups += [(name, names) for name, names in extras if (tests / (name + ".java")).is_file()]
    files = {source / (name + ".java") for _, names in groups for name in names}
    files.update(tests / (name + ".java") for name, _ in groups)
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
    files.update(source / name for name in ("NetworkCatalog.java", "NetworkSubscriptionCatalogPolicy.java",
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
    caret_test = ROOT / "tests/browser-runtime/caret-document-observer.test.cjs"
    if caret_test.is_file():
        caret_asset = ROOT / "tests/gecko/assets/caret-document-observer.js"
        command = ["node", "--test", "--test-reporter=tap", str(caret_test)]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if run.returncode:
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
    # Receipt coverage includes Android lifecycle/admission sources without pretending to compile them on the host JVM.
    lifecycle_sources=('EnvironmentSpec','EnvironmentResetPlan','EnvironmentBrowserData','EnvironmentProcessPolicy','EnvironmentSpecRepository','ProfileCatalog','Profiles','ProfileContext','EnvironmentResetActivity','WindowHomeActivity','MainActivity','ChatSession','ChatService','NetworkUiProvider','AppUpdateRoute','EnvironmentDeleteActivity','EnvironmentSpecRuntime')
    files.update(source/(name+'.java') for name in lifecycle_sources)
    files.update((ROOT/'app/src/main/AndroidManifest.xml',ROOT/'tests/gecko/EnvironmentManagementIntegrationActivity.java',ROOT/'tests/gecko/run_device.py'))
    files.update((ROOT/'tests/gecko/GeckoIntegrationTestActivity.java',ROOT/'tools/gecko/check_template_evidence.py'))
    files.update(ROOT/'tools/gecko'/name for name in ('integration_event_contract.py','profile_invocation_contract.py'))
    pressure_receipt=output / "resource-pressure-host-results.json"
    subprocess.run([sys.executable,str(ROOT / "tools/gecko/run_resource_host_checks.py"),"--json-jar",str(json_jar),"--output",str(pressure_receipt)],cwd=ROOT,check=True)
    pressure=json.loads(pressure_receipt.read_text());results.append({"test":"resource-pressure-host","report":str(pressure_receipt.relative_to(ROOT)),"passed":pressure["passed"],"actualAndroidExecution":False})
    files.update(ROOT/path for path in pressure["files"])
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
