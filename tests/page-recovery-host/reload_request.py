#!/usr/bin/env python3
"""Run current browser reload/draft guards and retirement of legacy observations."""
import argparse, hashlib, json, os, pathlib, subprocess, tempfile
from run import member, ROOT

def run(json_jar, java_home=None):
    source=ROOT/'app/src/main/java/local/pocketchat'
    selections={
      'CHAT':('ChatSession.java',['static final class ReloadTarget','ReloadTarget reloadTarget(','ReloadTarget reloadTargetAfterInspection(','void reloadConfirmed(','boolean currentReplyActive(','private long invalidateBrowserPageWork(','long beginNavigation(']),
      'MAIN':('MainActivity.java',['static boolean chatUrl(','boolean reloadMatches(','void requestReload(','void confirmReload(','void confirmIndependentReload(','void reloadCurrent(','void verifyReloadDraft(']),
      'OBSERVER':('WebReplyObserver.java',['static boolean same(','static boolean webJob(','void restorePending(','void receive(JSONObject event, Object port)']),
      'POLICY':('BrowserRuntimePolicy.java',['static boolean sameDocument(','static boolean official(']),
      'REPLY_POLICY':('BrowserSettingsPolicy.java',['static boolean currentReply(']),
      'MEMORY':('PageMemory.java',['static boolean completeDraft(','static boolean hasDraft(']),
      'PROFILE':('ProfileUi.java',['static boolean working('])}
    fixture=pathlib.Path(__file__).with_name('ReloadRequestHost.java');text=fixture.read_text();methods=[]
    paths={fixture,pathlib.Path(__file__).resolve(),pathlib.Path(__file__).with_name('run.py')}|{source/name for name,_ in selections.values()}
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    for marker,(name,needles) in selections.items():
        original=(source/name).read_text();text=text.replace('/* '+marker+' */','\n'.join(member(original,n) for n in needles));methods.extend(name+':'+n for n in needles)
    binary=lambda name:str(java_home/'bin'/name) if java_home else name
    with tempfile.TemporaryDirectory(prefix='reload-request-host-') as root:
        root=pathlib.Path(root);java=root/'local/pocketchat/ReloadRequestHost.java';java.parent.mkdir(parents=True);java.write_text(text)
        uri=root/'android/net/Uri.java';uri.parent.mkdir(parents=True);uri.write_text('package android.net; public class Uri {java.net.URI value; public static Uri parse(String x){Uri u=new Uri();u.value=java.net.URI.create(x);return u;} public String getPath(){return value.getPath();}public String getEncodedPath(){return value.getRawPath();}public String getHost(){return value.getHost();}public String getScheme(){return value.getScheme();}public String getUserInfo(){return value.getUserInfo();}public int getPort(){return value.getPort();}}')
        built=subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(json_jar.resolve()),'-d',str(root),str(java),str(uri)],text=True,capture_output=True)
        if built.returncode:raise RuntimeError(built.stderr)
        result=subprocess.run([binary('java'),'-cp',str(root)+os.pathsep+str(json_jar.resolve()),'local.pocketchat.ReloadRequestHost'],text=True,capture_output=True)
        if result.returncode or not result.stdout:raise RuntimeError(result.stderr)
        report=json.loads(result.stdout)
    report.update(actualAndroidExecution=False,scope='Exact current requestReload, ReloadTarget, draft save/recheck, reloadConfirmed and legacy restorePending methods. Controlled browser navigation, callback scheduler, preferences, archive writes and widgets; no Android/Gecko, live website or durable-storage claim. Old sending/result observation is retired, not emulated.',productionMembers=methods,sourceFiles=hashes,jsonJarSha256=hashlib.sha256(json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--java-home',type=pathlib.Path);a=p.parse_args();report=run(a.json_jar,a.java_home);print(json.dumps(report,ensure_ascii=False));raise SystemExit(0 if report['status']=='passed' and report['executionInputsUnchanged'] else 1)
