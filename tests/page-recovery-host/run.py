#!/usr/bin/env python3
"""Execute exact production methods with controlled Android adapters; no device claim."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
def member(text,needle):
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
    while i<len(text):
        c=text[i];n=text[i:i+2]
        if line:
            if c=='\n':line=False
        elif block:
            if n=='*/':block=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif n=='//':line=True;i+=1
        elif n=='/*':block=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
        i+=1
    raise ValueError('Unclosed member: '+needle)
def main():
    p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);a=p.parse_args()
    source=ROOT/'app/src/main/java/local/pocketchat'
    selections={
      'CHAT':('ChatSession.java',['void beginNavigation(','void awaitLogin(','boolean pageMayReportConnected(','void inspectPageStatus(','void sync(','void networkStatus(','void navigationTimeout(','void finishNavigation(String error,boolean retry)','void scheduleRecovery(','void runRecovery(','void acceptTranscript(','static final class ReloadTarget','ReloadTarget reloadTarget(','void reloadConfirmed(','void observeReplyProgress(','void diagnoseStalledReply(','void observeWebsiteProbe(','boolean retainExistingConnection(']),
      'PROVIDER':('NetworkUiProvider.java',['void captureTransition(']),
      'DEFERRED':('DeferredBrowserSettings.java',['static void drain(','static void release(']),
      'EDITOR':('EnvironmentEditorUi.java',['static void applySafely(MainActivity a,JSONObject value,EditText name,java.util.function.BooleanSupplier current,java.util.function.Consumer<Boolean> done)']),
      'CAPTURE':('PageMemory.java',['void remember(','void capture(']),
      'MEMORY':('PageMemory.java',['static boolean completeDraft(','static boolean hasDraft(']),
      'MAIN':('MainActivity.java',['void status(','void showStatusDetails(','boolean reloadMatches(','void confirmIndependentReload(']),
      'REPLY':('ReplyState.java',['static String describe(','static long elapsedSeconds(','static void show(','static void checkWithoutRecovery(','static void websiteConnection(']),
      'NETWORK':('NetworkStatusUi.java',['static boolean current(','static boolean connectionReady(','static String pageStatus(','static String sendStatus(']),
      'LOGIN':('LoginPagePolicy.java',['static String host(','static boolean login(']),
      'LIFECYCLE':('GeckoWebView.java',['private void contentStopped(','private boolean canRecoverAutomatically(','public void onResume(','boolean hasVisibleDocument(','private void failure('])}
    fixture=pathlib.Path(__file__).parent/'PageRecoveryHost.java'
    inputs={source/name for name,_ in selections.values()}|{source/name for name in ('WebReplyObserver.java','BrowserRuntimePolicy.java','BrowserSettingsPolicy.java','BrowserBridgeRequests.java')}|{fixture,pathlib.Path(__file__).resolve(),fixture.with_name('ReloadRequestHost.java'),fixture.with_name('reload_request.py')}
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(inputs)}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    text=fixture.read_text()
    methods=[]
    for marker,(name,needles) in selections.items():
        original=(source/name).read_text();parts=[member(original,needle) for needle in needles]
        text=text.replace('/* '+marker+' */','\n'.join(parts));methods.extend(name+':'+needle for needle in needles)
    original=(source/'MainActivity.java').read_text();anchor='status.setOnClickListener(v->'
    assert original.count(anchor)==1,'Production status must have one actual click listener'
    start=original.index(anchor)+len(anchor);click=original[start:original.index(');root.addView(status',start)]
    text=text.replace('/* STATUS_CLICK */',click if click.startswith('{') else '{'+click+';}')
    methods.append('MainActivity.java:actual status OnClickListener body')
    with tempfile.TemporaryDirectory(prefix='page-recovery-host-') as tmp:
        tmp=pathlib.Path(tmp);java=tmp/'local/pocketchat/PageRecoveryHost.java';java.parent.mkdir(parents=True);java.write_text(text)
        uri=tmp/'android/net/Uri.java';uri.parent.mkdir(parents=True);uri.write_text('package android.net; public class Uri { java.net.URI u; public static Uri parse(String x){Uri v=new Uri();v.u=java.net.URI.create(x);return v;}public String getPath(){return u.getPath();}}')
        clock=tmp/'android/os/SystemClock.java';clock.parent.mkdir(parents=True);clock.write_text('package android.os;public class SystemClock {public static long elapsedRealtime(){return 100000;}}')
        subprocess.run(['javac','-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(tmp),str(java),str(uri),str(clock),str(source/'BrowserBridgeRequests.java')],check=True)
        result=subprocess.run(['java','-cp',str(tmp)+os.pathsep+str(a.json_jar.resolve()),'local.pocketchat.PageRecoveryHost'],text=True,capture_output=True)
        if result.returncode:
            print(result.stderr,file=sys.stderr);result.check_returncode()
        report=json.loads(result.stdout);report.update(actualAndroidExecution=False,productionMembers=methods,scope='Exact production Java members with controlled Android adapters; no phone or live-network acceptance')
        from reload_request import run as run_reload_request
        report['reloadRequest']=run_reload_request(a.json_jar)
        if report['reloadRequest']['status']!='passed' or not report['reloadRequest']['executionInputsUnchanged']:
            report['status']='failed-reload-request'
        unchanged=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items())
        report.update(sourceCommit=commit,sourceFiles=hashes,jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=unchanged)
        if not unchanged:report['status']='invalid-source-changed'
        print(json.dumps(report,ensure_ascii=False))
        if report['status']!='passed':raise SystemExit(1)
        if not unchanged:raise SystemExit(1)
if __name__=='__main__':main()
