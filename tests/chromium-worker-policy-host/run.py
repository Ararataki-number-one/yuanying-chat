#!/usr/bin/env python3
"""Run exact ChromiumRuntime Worker admission methods with declared JVM edges.

Native ServiceWorkerController/Looper/route evidence are controlled edges, not
Android execution. The immutable identity and route policy are full production
classes. Mutants must fail the same semantic assertions as the real methods.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
PARSER=ROOT/'tests/gecko-navigation-host/run.py'
MEMBERS=('static final class WorkerPolicy {','boolean allowed(){','void block(String reason){',
         'long beginWorkerPolicy(){','boolean confirmWorkerPolicy(',
         'boolean workerRequestsAllowed(){','boolean updateWorkerNetwork(){',
         'JSONObject workerPolicyReceipt(){','void onMain(Runnable task){')
MUTANTS=(
 ('missing-restrict-admission','&&!requested.restrict',''),
 ('stale-token-admission','||token!=workerPolicyGeneration',''),
 ('foreign-environment-admission','||(identity!=null&&!identity.equals(expected))',''),
 ('missing-native-readback','workerNativeMatches=actual==blocked','workerNativeMatches=true'),
 ('early-unconfirmed-network','boolean blocked=!workerRequestsAllowed()','boolean blocked=false'),
 ('duplicate-confirmation-overwrite','if(before!=null&&(before.token!=token||before.revision!=revision||!before.identity.equals(expected)||before.restrict!=restrict))return false;',''),
)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def extract(source):
    spec=importlib.util.spec_from_file_location('worker_source_parser',PARSER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=[]
    for needle in MEMBERS:
        matches=[i for i in range(len(source)) if source.startswith(needle,i) and not source[source.rfind('\n',0,i)+1:i].strip()]
        if len(matches)!=1:raise ValueError('Production declaration must be unique: '+needle)
        result.append(module.member_at(source,matches[0]))
    return '\n'.join(result)

def integration_contract(source):
    required=(
      'active!=null&&active.workerRequestsAllowed()&&publicWeb(request.getUrl())',
      'requested!=null&&!requested.identity.equals(expected)',
      'workers!=null&&!workers.identity.equals(selected.identity)',
      'getAllowContentAccess()||workers.getServiceWorkerWebSettings().getAllowFileAccess()||!updateWorkerNetwork()',
      'if(!updateWorkerNetwork())throw new IllegalStateException',
    )
    for value in required:
        if source.count(value)!=1:raise ValueError('Missing or duplicate live native integration: '+value)
    if 'setBlockNetworkLoads(false)' in source:raise ValueError('Unconditional native Worker network reopening')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',required=True,type=Path)
    parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    paths=[PROD/'ChromiumRuntime.java',PROD/'ChromiumRoutePolicy.java',PROD/'EnvironmentSpec.java',PROD/'J.java',HERE/'Harness.java.in',Path(__file__).resolve(),PARSER,PROD/'ChromiumFingerprintUi.java']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in paths}
    source=paths[0].read_text();integration_contract(source);members=extract(source)
    spec=importlib.util.spec_from_file_location('worker_ui_source_parser',PARSER);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    ui=paths[-1].read_text();ui_members='\n'.join(module.member_at(ui,ui.index(needle)) for needle in ('static String workerSummary(', 'private static JSONObject fields('))
    template=(HERE/'Harness.java.in').read_text();results=[]
    with tempfile.TemporaryDirectory(prefix='chromium-worker-policy-') as temporary:
        base=Path(temporary)
        for name,needle,replacement in [('production',None,None),*MUTANTS]:
            selected=members
            if needle is not None:
                if selected.count(needle)!=1:raise ValueError('Mutation target is not unique: '+name)
                selected=selected.replace(needle,replacement,1)
            java=base/name/'WorkerPolicyHost.java';java.parent.mkdir();java.write_text(template.replace('__ACTUAL_PRODUCTION_MEMBERS__',selected).replace('__ACTUAL_UI_MEMBERS__',ui_members))
            classes=java.parent/'classes';cp=str(args.json_jar.resolve())
            compiled=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-source','17','-target','17','-cp',cp,'-d',str(classes),str(java),*map(str,paths[1:4])],capture_output=True,text=True,timeout=30)
            if compiled.returncode:raise RuntimeError(name+' compilation failed: '+compiled.stderr)
            executed=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(classes)+':'+cp,'local.pocketchat.WorkerPolicyHost'],capture_output=True,text=True,timeout=30)
            if name=='production':
                if executed.returncode:raise RuntimeError(executed.stdout+executed.stderr)
                report=json.loads(executed.stdout)
            else:
                if executed.returncode==0 or 'AssertionError:' not in executed.stderr:raise ValueError('Worker protection mutant was not rejected by behavior: '+name)
                results.append(dict(name=name,rejected=True,assertion=executed.stderr.split('AssertionError:',1)[1].splitlines()[0].strip()))
    report.update(mutants=results,sourceFiles=hashes,actualProductionMembers=len(MEMBERS),actualProductionMethods=len(MEMBERS)-1,actualUiMethods=2,
        executionInputsUnchanged=all(digest(ROOT/name)==sha for name,sha in hashes.items()),
        jsonJarSha256=digest(args.json_jar),actualAndroidExecution=False,actualWebViewExecution=False,
        scope='Exact nine ChromiumRuntime production members and two ChromiumFingerprintUi receipt-summary methods, full immutable EnvironmentSpec/route-policy/J classes; explicit native ServiceWorker settings, Looper, handler, route evidence and listener JVM edges. Exercises initial/pending/confirmed/restricted/route-loss/owner-replacement/stale-revision admission and native readback faults; UI never substitutes desired values for actual confirmation. No Android ServiceWorker execution or browser fingerprint protection claim.')
    if not report['executionInputsUnchanged']:raise ValueError('Sources changed during execution')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('status','passed','total','actualProductionMembers','actualProductionMethods','executionInputsUnchanged')}))

if __name__=='__main__':main()
