#!/usr/bin/env python3
"""Current default-IP timezone core, strict schema and route/native gate controls."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
EXTRACTOR=ROOT/'tests/gecko-timezone-flow-host/run.py'
spec=importlib.util.spec_from_file_location('ip_timezone_actual_members',EXTRACTOR)
extractor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def change(text,before,after,label):
    if text.count(before)!=1:raise ValueError('Unique current semantic hunk required: '+label)
    return text.replace(before,after,1)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    def tool(name):
        found=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
        if not found:p.error('Provide JDK17 --java-home')
        return found
    sources=[PROD/n for n in ['GeckoTimeZoneSpec.java','GeckoTimeZoneStore.java','GeckoTimeZonePolicy.java','GeckoIpTimeZonePolicy.java','GeckoTimeZoneController.java','EnvironmentSpec.java','NetworkShareJson.java','J.java']]
    adapters=ROOT/'tests/gecko-timezone-host/GeckoTimeZoneHost.java';ui=PROD/'GeckoTimeZoneUi.java'
    methods={key:extractor.block(ui.read_text(),key) for key in ['static int selectionFor(', 'static GeckoTimeZoneSpec selected(', 'static String summary(']}
    inputs=sources+[adapters,ui,HERE/'IpTimeZoneHost.java',HERE/'README.md',Path(__file__).resolve(),EXTRACTOR]
    hashes={str(path.relative_to(ROOT)):sha(path) for path in inputs};jar=sha(a.json_jar)
    texts={path.name:path.read_text() for path in sources};a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='gecko-ip-timezone-') as temporary:
        temp=Path(temporary)
        def execute(current,label):
            out=artifacts/label;out.mkdir(exist_ok=True);generated=[]
            for name,value in current.items():
                path=out/name;path.write_text(value);generated.append(path)
            wrapper=out/'GeckoTimeZoneUi.java';wrapper.write_text('package local.pocketchat;import org.json.*;final class GeckoTimeZoneUi {\n'+'\n'.join(methods.values())+'\n}\n')
            context=out/'android/content/Context.java';context.parent.mkdir(parents=True,exist_ok=True);context.write_text('package android.content;public abstract class Context {public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();}\n')
            command=[tool('javac'),'--release','17','-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(temp/label/'classes'),*map(str,generated),str(wrapper),str(context),str(adapters),str(HERE/'IpTimeZoneHost.java')]
            compiled=subprocess.run(command,text=True,capture_output=True,timeout=60)
            (out/'compile.command.json').write_text(json.dumps(command)+'\n');(out/'compile.stdout.log').write_text(compiled.stdout);(out/'compile.stderr.log').write_text(compiled.stderr)
            if compiled.returncode:raise RuntimeError(label+' compilation failed:\n'+compiled.stderr)
            command=[tool('java'),'-cp',str(temp/label/'classes')+os.pathsep+str(a.json_jar.resolve()),'local.pocketchat.IpTimeZoneHost',str(temp/label/'state')]
            ran=subprocess.run(command,text=True,capture_output=True,timeout=60)
            (out/'run.command.json').write_text(json.dumps(command)+'\n');(out/'run.stdout.log').write_text(ran.stdout);(out/'run.stderr.log').write_text(ran.stderr)
            return ran
        current=execute(texts,'current')
        if current.returncode:raise RuntimeError(current.stdout+'\n'+current.stderr)
        result=json.loads(current.stdout)
        mutants=[
            ('geo-route-envelope','GeckoIpTimeZonePolicy.java','!routeStamp.equals(envelope.opt("routeStamp"))||','','Foreign/malformed envelope rejected: routeStamp'),
            ('current-route-binding','GeckoTimeZoneController.java','op.routeStamp.equals(op.access.ipRouteStamp())','true','Route change immediately invalidates an old match even before a lifecycle notification'),
            ('effective-native-zone','GeckoTimeZoneController.java','op.access.apply(op.effective.zoneId,','op.access.apply(op.desired.spec.zoneId,','Native apply receives resolved IANA rather than empty desired IP zone'),
            ('rfp-priority','GeckoTimeZoneController.java','if(session.privacy.level()>=2){op.rfpManaged=true;','if(false){op.rfpManaged=true;','Automatic IP under RFP resets native override without querying or weakening protection'),
        ]
        for label,name,before,after,assertion in mutants:
            altered=dict(texts);altered[name]=change(texts[name],before,after,label);failed=execute(altered,'mutant-'+label)
            if failed.returncode!=1 or 'java.lang.AssertionError: '+assertion not in failed.stderr:raise AssertionError('Mutant must compile and fail its exact assertion: '+label+'\n'+failed.stdout+failed.stderr)
            controls.append(dict(name=label,compiled=True,runtimeExitCode=failed.returncode,assertion=assertion,mutantSourceSha256=hashlib.sha256(altered[name].encode()).hexdigest()));result['checks'].append('Compiled current semantic mutant rejected: '+label)
        result['passed']+=len(controls);result['total']+=len(controls)
    stable=all(sha(path)==hashes[str(path.relative_to(ROOT))] for path in inputs) and sha(a.json_jar)==jar
    result.update(schema=1,status='passed' if stable else 'source-changed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,jsonJarSha256=jar,executionInputsUnchanged=stable,compiledSemanticMutants=controls,uiMethodSha256={key:hashlib.sha256(value.encode()).hexdigest() for key,value in methods.items()},actualAndroidExecution=False,actualGeckoNativeExecution=False,actualPublicGeoServiceExecution=False,actualDateIntlExecution=False,actualWorkerExecution=False,actualSqliteExecution=False,actualAesKeystoreExecution=False,scope='Complete current IP schema/parser, timezone Spec/Store/Policy/Controller and exact UI selection/summary declarations. Existing explicit Context/catalog/plain atomic-vault adapters; actual filesystem/FileLock and strict JSON. Queued handler/writer/native/geo callbacks are declared host boundaries and cannot prove same browser exit, first-inline clock or Worker effects; those require independent real Android production gate. New default is tested from a truly missing sidecar; legacy schema1/manual migration is separate. Four compiled actual semantic mutants test route correlation, current route binding, effective native IANA and RFP priority; no original deadline is extended.')
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({key:result[key] for key in ['schema','status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
    if not stable:raise SystemExit(1)
if __name__=='__main__':main()
