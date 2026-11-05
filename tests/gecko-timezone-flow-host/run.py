#!/usr/bin/env python3
"""Actual timezone controller and actual UI application methods, explicit host boundaries."""
import argparse, hashlib, json, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def block(source, marker):
    """Take a unique declaration verbatim, balancing Java code, strings and comments."""
    if source.count(marker)!=1: raise ValueError('Unique current declaration required: '+marker)
    start=source.index(marker); brace=source.index('{', start); depth=0; state='code'; i=brace
    while i<len(source):
        c=source[i]; n=source[i:i+2]
        if state in ('string','char'):
            if c=='\\': i+=2; continue
            if c==('"' if state=='string' else "'"): state='code'
        elif state=='line':
            if c=='\n': state='code'
        elif state=='comment':
            if n=='*/': state='code'; i+=2; continue
        elif n=='//': state='line'; i+=2; continue
        elif n=='/*': state='comment'; i+=2; continue
        elif c=='"': state='string'
        elif c=="'": state='char'
        elif c=='{': depth+=1
        elif c=='}':
            depth-=1
            if depth==0: return source[start:i+1]
        i+=1
    raise ValueError('Incomplete Java declaration '+marker)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'work/gecko-timezone-flow-host/results.json');a=p.parse_args()
    def tool(name):
        result=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
        if not result:p.error('Provide JDK17 --java-home')
        return result
    names=['GeckoTimeZoneController.java','GeckoTimeZoneSpec.java','GeckoTimeZoneStore.java','GeckoTimeZonePolicy.java','GeckoIpTimeZonePolicy.java','EnvironmentSpec.java','NetworkShareJson.java','J.java','BrowserSettingsPolicy.java']
    sources=[PROD/name for name in names]
    ui=PROD/'GeckoTimeZoneUi.java'
    markers=['static String summary(', 'static String busy(', 'static final class Fence {', 'private static boolean activity(', 'static void applySafely(', 'private static void confirm(', 'private static void commit(']
    methods={marker:block(ui.read_text(),marker) for marker in markers}
    audit=PROD/'EnvironmentAudit.java'
    audit_methods={marker:block(audit.read_text(),marker) for marker in ['static String hash(', 'String policyStamp(', 'boolean observationCurrent(']}
    inputs=sources+[ui,audit,HERE/'TimezoneFlowHost.java',ROOT/'tests/gecko-timezone-host/GeckoTimeZoneHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):sha(path) for path in inputs}
    with tempfile.TemporaryDirectory(prefix='timezone-flow-') as temp:
        folder=Path(temp);classes=folder/'classes';context=folder/'android/content/Context.java';context.parent.mkdir(parents=True)
        context.write_text('package android.content; public abstract class Context {public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();}\n')
        extracted=folder/'GeckoTimeZoneUi.java'
        extracted.write_text('package local.pocketchat;\nimport java.util.function.*;import org.json.*;\nfinal class GeckoTimeZoneUi {\n'+'\n'.join(methods.values())+'\n}\n')
        audit_extracted=folder/'EnvironmentAudit.java'
        audit_extracted.write_text('package local.pocketchat;\nimport java.util.*;import org.json.*;\nfinal class EnvironmentAudit {static final String OBSERVATION_EXECUTION_ID=UUID.randomUUID().toString(); final ChatSession session;int retired;EnvironmentAudit(ChatSession s){session=s;}void retirePageCheck(){retired++;}void nativeDocumentProofChanged(Object nativeSession,String epoch){retirePageCheck();}\n'+'\n'.join(audit_methods.values())+'\n}\n')
        compile=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar.resolve()),'-d',str(classes),*map(str,sources),str(HERE/'TimezoneFlowHost.java'),str(ROOT/'tests/gecko-timezone-host/GeckoTimeZoneHost.java'),str(context),str(extracted),str(audit_extracted)],capture_output=True,text=True)
        if compile.returncode:raise RuntimeError(compile.stderr)
        run=subprocess.run([tool('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.TimezoneFlowHost',str(folder/'state')],capture_output=True,text=True,timeout=60)
        if run.returncode:raise RuntimeError(run.stdout+'\n'+run.stderr)
        result=json.loads(run.stdout)
        controller=PROD/'GeckoTimeZoneController.java';current=controller.read_text()
        mutations=[
            ('reuse-old-completed-context','prepare(nativeSession,sessionId,epoch,access,gate,true);','prepare(nativeSession,sessionId,epoch,access,gate,false);','New document synchronously revokes old confirmation despite identical SDK session and open epoch'),
            ('accept-stale-open-epoch','!old.epoch.equals(epoch)','false','Stale document-validation authority cannot revoke current confirmation: old-open-epoch'),
        ]
        rejected=[]
        for label,before,after,assertion in mutations:
            if current.count(before)!=1:raise RuntimeError('Exact unique current semantic mutation required: '+label)
            mutant=folder/label/'GeckoTimeZoneController.java';mutant.parent.mkdir();mutant.write_text(current.replace(before,after,1));mutant_classes=mutant.parent/'classes'
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar.resolve()),'-d',str(mutant_classes),*map(str,[path for path in sources if path!=controller]),str(mutant),str(HERE/'TimezoneFlowHost.java'),str(ROOT/'tests/gecko-timezone-host/GeckoTimeZoneHost.java'),str(context),str(extracted),str(audit_extracted)],capture_output=True,text=True)
            if compiled.returncode:raise RuntimeError(label+' failed compilation instead of exercising current semantics:\n'+compiled.stderr)
            failed=subprocess.run([tool('java'),'-cp',str(mutant_classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.TimezoneFlowHost',str(mutant.parent/'state')],capture_output=True,text=True,timeout=60)
            if failed.returncode!=1 or 'java.lang.AssertionError: '+assertion not in failed.stderr:raise RuntimeError(label+' did not fail its actual control-flow assertion:\n'+failed.stdout+'\n'+failed.stderr)
            rejected.append(dict(name=label,compiled=True,runtimeExitCode=failed.returncode,assertion=assertion,executedControllerSha256=sha(mutant)))
            result['checks'].append('Compiled current-controller semantic mutant rejected: '+label)
        result['passed']+=len(rejected);result['total']+=len(rejected)
    stable=all(sha(path)==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report=dict(schema=1,status='passed' if stable else 'source-changed',passed=result['passed'],total=result['total'],checks=result['checks'],compiledSemanticMutants=rejected,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,methodSha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in methods.items()},auditMethodSha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in audit_methods.items()},executionInputsUnchanged=stable,jsonJarSha256=sha(a.json_jar),actualIpLookupExecution=False,manualSelectionBoundary='Retained cases explicitly save manual system/IANA with actual store CAS. Separate controls retain the real missing-store IP default and deny it at this manual-only native boundary; no successful IP matching is simulated.',actualAndroidExecution=False,actualGeckoNativeSettingExecution=False,actualSqliteExecution=False,actualAesKeystoreExecution=False,nativeProofNotificationBoundary='These legacy completed-observation cases have no pending ordinary audit; the notification collaborator only forwards the original counted retirement. Exact pending owner discrimination executes in the dedicated current-method host.',scope='Complete actual current Controller/Spec/Store/Policy/EnvironmentSpec/strict NetworkShareJson/J and BrowserSettingsPolicy. UI summary/busy/Fence/activity/applySafely/confirm/commit and EnvironmentAudit hash/policyStamp/observationCurrent declarations copied verbatim from current source and hash-bound. Real filesystem/FileLock and explicit catalog/atomic-vault adapters reused from core host. Same-SDK-session document/COOP context changes execute fresh read/apply/publication and exact callback fences; two production semantic mutants must compile then fail these actual assertions. Native apply callbacks are synthetic; zero-setter idempotence requires the independent native API suite. Manual executor/handler/delayed clock, Activity/WebView, draft and Modal boundaries are explicit; no native/Date/Worker support is inferred.')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['schema','status','passed','total','executionInputsUnchanged','actualAndroidExecution','actualGeckoNativeSettingExecution']}))
    if not stable:raise SystemExit(1)

if __name__=='__main__':main()
