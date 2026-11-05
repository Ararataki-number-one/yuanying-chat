#!/usr/bin/env python3
"""Run the production controller with host doubles; preserve exact source-bound receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--json-jar',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if not args.json_jar.is_file():parser.error('JSON-java jar not found')
    json_digest=hashlib.sha256(args.json_jar.read_bytes()).hexdigest()
    java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:parser.error('JDK with jdk.compiler required')
    output=ROOT/'work/identity-controller-host/classes';output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'app/src/main/java/local/pocketchat'
    sources=[source/(name+'.java') for name in ['J','EnvironmentSpec','BrowserIdentitySpec','NetworkHealthPolicy','IdentityTemplateController','FingerprintTemplateUi']]+sorted((ROOT/'tests/review-host/identity-controller').rglob('*.java'))
    inputs=sources+[Path(__file__).resolve()];before={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip();status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    # Preserve the original fixture bytes. Recording children is solely a UI
    # boundary adapter so the actual new template action can be clicked below.
    layout=ROOT/'tests/review-host/identity-controller/android/widget/LinearLayout.java'
    original_layout=layout.read_text();old='public void addView(android.view.View view){}'
    if original_layout.count(old)!=1:raise ValueError('Exact unique LinearLayout child-recording boundary required')
    adapted_layout=original_layout.replace(old,'public final java.util.List<android.view.View> children=new java.util.ArrayList<>(); public void addView(android.view.View view){children.add(view);}',1)
    with tempfile.TemporaryDirectory(prefix='identity-controller-entry-') as temporary:
        adapted=Path(temporary)/'android/widget/LinearLayout.java';adapted.parent.mkdir(parents=True);adapted.write_text(adapted_layout)
        compiled_sources=[path for path in sources if path!=layout]+[adapted]
        subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-source','8','-target','8','-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(output),*map(str,compiled_sources)],cwd=ROOT,check=True)
    run=subprocess.run([java,'-cp',str(output)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.IdentityControllerHostTest'],cwd=ROOT,text=True,capture_output=True)
    if run.returncode:print(run.stdout);print(run.stderr);raise subprocess.CalledProcessError(run.returncode,run.args)
    report=json.loads(run.stdout.strip())
    if report.get('status')!='passed' or report.get('actualAndroidExecution') is not False or report.get('passed')!=report.get('total') or len(report.get('checks',[]))!=report.get('passed') or any(check.get('pass') is not True for check in report['checks']):raise ValueError('Incomplete controller host result')
    boundary_run=subprocess.run([java,'-cp',str(output)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.GeckoTimeZoneEntryBoundaryHost'],cwd=ROOT,text=True,capture_output=True)
    if boundary_run.returncode:raise RuntimeError('Timezone UI-entry boundary failed:\n'+boundary_run.stdout+'\n'+boundary_run.stderr)
    boundary=json.loads(boundary_run.stdout.strip())
    if boundary.get('schema')!=1 or boundary.get('status')!='passed' or boundary.get('passed')!=13 or boundary.get('total')!=13 or len(boundary.get('checks',[]))!=13 or any(value.get('pass') is not True for value in boundary['checks']) or boundary.get('defaultSystemOnly') is not True or any(boundary.get(key) is not False for key in ['nativeSettingReadback','customSupported','actualAndroidExecution','actualGeckoExecution']):raise ValueError('Incomplete or overclaimed timezone UI-entry boundary')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=commit or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)!=status or any(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest for path,digest in before.items()) or hashlib.sha256(args.json_jar.read_bytes()).hexdigest()!=json_digest:raise ValueError('Controller host sources changed during execution')
    report.update(sourceCommit=commit,sourceTree=tree,sourceDirty=bool(status.strip()),sourceUnchangedDuringChecks=True,files=before,jsonJarSha256=json_digest,timezoneEntryBoundary=boundary,temporaryBoundaryAdapters={str(layout.relative_to(ROOT)):{'originalSha256':hashlib.sha256(original_layout.encode()).hexdigest(),'compiledSha256':hashlib.sha256(adapted_layout.encode()).hexdigest(),'scope':'Exact single addView child recording only; original fixture and all original test assertions unchanged'}})
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ['status','passed','total','actualAndroidExecution','sourceCommit','scope']},ensure_ascii=False))

if __name__=='__main__':main()
