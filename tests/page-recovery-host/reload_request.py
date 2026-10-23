#!/usr/bin/env python3
"""Run the production reload callbacks and synchronous website-job archival on host."""
import argparse, hashlib, json, os, pathlib, subprocess, tempfile
from run import member, ROOT

def run(json_jar):
    source=ROOT/'app/src/main/java/local/pocketchat'
    selections={
      'CHAT':('ChatSession.java',['static final class ReloadTarget','ReloadTarget reloadTarget(','boolean archiveWebsiteNavigation(','void completeReply(','void abandonWait(','boolean currentReplyActive(']),
      'MAIN':('MainActivity.java',['boolean reloadMatches(','void requestReload(','void confirmReload(','void confirmIndependentReload(']),
      'OBSERVER':('WebReplyObserver.java',['static boolean same(','static boolean webJob(','boolean archiveNavigation(','void receive(JSONObject event,Object port)','static boolean stable(','static boolean bindingRoute(','void finishStopped(']),
      'POLICY':('BrowserRuntimePolicy.java',['static boolean sameDocument(','static boolean leftConversation(','static boolean official(','static String conversationId(']),
      'REPLY_POLICY':('BrowserSettingsPolicy.java',['static boolean currentReply(']),
      'MEMORY':('PageMemory.java',['static boolean completeDraft(','static boolean hasDraft('])}
    if 'ReloadTarget reloadTargetAfterInspection(' in (source/'ChatSession.java').read_text():
        selections['CHAT'][1].append('ReloadTarget reloadTargetAfterInspection(')
    fixture=pathlib.Path(__file__).with_name('ReloadRequestHost.java');text=fixture.read_text();methods=[]
    paths={fixture,pathlib.Path(__file__).resolve(),pathlib.Path(__file__).with_name('run.py')}|{source/name for name,_ in selections.values()}
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    for marker,(name,needles) in selections.items():
        original=(source/name).read_text();text=text.replace('/* '+marker+' */','\n'.join(member(original,n) for n in needles));methods.extend(name+':'+n for n in needles)
    # The independent-loss positive action is not exercised in this host workload.
    text=text.replace('/* CHAT */','')
    text=text.replace('class ChatSession {','class ChatSession { void reloadConfirmed(ReloadTarget t,JSONObject p,boolean i){throw new AssertionError("Unexpected independent reload");}')
    text=text.replace('import java.util.*;','import java.util.*;import java.net.URI;import android.net.Uri;')
    with tempfile.TemporaryDirectory(prefix='reload-request-host-') as root:
        root=pathlib.Path(root);java=root/'local/pocketchat/ReloadRequestHost.java';java.parent.mkdir(parents=True);java.write_text(text)
        uri=root/'android/net/Uri.java';uri.parent.mkdir(parents=True);uri.write_text('package android.net; public class Uri {java.net.URI value; public static Uri parse(String x){Uri u=new Uri();u.value=java.net.URI.create(x);return u;} public String getPath(){return value.getPath();}public String getEncodedPath(){return value.getRawPath();}}')
        subprocess.run(['javac','-encoding','UTF-8','-cp',str(json_jar.resolve()),'-d',str(root),str(java),str(uri)],check=True)
        result=subprocess.run(['java','-cp',str(root)+os.pathsep+str(json_jar.resolve()),'local.pocketchat.ReloadRequestHost'],text=True,capture_output=True)
        if not result.stdout:raise RuntimeError(result.stderr)
        report=json.loads(result.stdout)
    report.update(actualAndroidExecution=False,scope='Exact production requestReload, identity guards and archiveNavigation; controlled host callbacks/preferences/widgets, no real Android touch or storage claim',productionMembers=methods,sourceFiles=hashes,jsonJarSha256=hashlib.sha256(json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--json-jar',type=pathlib.Path,required=True);a=p.parse_args();report=run(a.json_jar);print(json.dumps(report,ensure_ascii=False));raise SystemExit(0 if report['status']=='passed' and report['executionInputsUnchanged'] else 1)
