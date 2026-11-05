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
      'CHAT':('ChatSession.java',['boolean chatAutomationAllowed(','void beginNavigation(','void awaitLogin(','boolean pageMayReportConnected(','void inspectPageStatus(','void sync(','void networkStatus(','void navigationTimeout(','void finishNavigation(String error,boolean retry)','void scheduleRecovery(','void runRecovery(','void acceptTranscript(','static final class ReloadTarget','ReloadTarget reloadTarget(','void reloadConfirmed(','void observeReplyProgress(','void diagnoseStalledReply(','void observeWebsiteProbe(','boolean retainExistingConnection(']),
      'PROVIDER':('NetworkUiProvider.java',['void captureTransition(']),
      'DEFERRED':('DeferredBrowserSettings.java',['static void drain(','static void release(']),
      'EDITOR':('EnvironmentEditorUi.java',['static void applySafely(MainActivity a,JSONObject value,EditText name,java.util.function.BooleanSupplier current,java.util.function.Consumer<Boolean> done)']),
      'CAPTURE':('PageMemory.java',['void remember(','void capture(']),
      'MEMORY':('PageMemory.java',['static boolean completeDraft(','static boolean hasDraft(']),
      'MAIN':('MainActivity.java',['static boolean chatUrl(','void status(','void showStatusDetails(','boolean reloadMatches(','void confirmIndependentReload(']),
      'REPLY':('ReplyState.java',['static String describe(','static long elapsedSeconds(','static void show(','static void checkWithoutRecovery(','static void websiteConnection(']),
      'NETWORK':('NetworkStatusUi.java',['static boolean current(','static boolean connectionReady(','static String pageStatus(','static String sendStatus(']),
      'LOGIN':('LoginPagePolicy.java',['static String host(','static boolean login(']),
      'LIFECYCLE':('GeckoWebView.java',['void forgetGeneralRoute(','private void contentStopped(','private boolean canRecoverAutomatically(','public void onResume(','boolean hasVisibleDocument(','private void failure('])}
    fixture=pathlib.Path(__file__).parent/'PageRecoveryHost.java'
    inputs={source/name for name,_ in selections.values()}|{source/name for name in ('WebReplyObserver.java','BrowserRuntimePolicy.java','BrowserSettingsPolicy.java','BrowserBridgeRequests.java','ChromiumRouteLease.java','GeckoNavigationPolicy.java','BrowserAddressPolicy.java')}|{fixture,pathlib.Path(__file__).resolve(),fixture.with_name('ReloadRequestHost.java'),fixture.with_name('reload_request.py'),fixture.with_name('README.md')}
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(inputs)}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    text=fixture.read_text()
    methods=[]
    for marker,(name,needles) in selections.items():
        original=(source/name).read_text();parts=[member(original,needle) for needle in needles]
        text=text.replace('/* '+marker+' */','\n'.join(parts));methods.extend(name+':'+needle for needle in needles)
    route_source=(source/'GeckoWebView.java').read_text();route_fields=[]
    for prefix in ('final Set<GeckoSession> generalSessions=', 'final Map<GeckoSession,ChromiumRouteLease.Handle> generalRoutes=', 'final Map<GeckoSession,String> deferredGeneralLoads='):
        matches=[line.strip() for line in route_source.splitlines() if line.strip().startswith(prefix)]
        if len(matches)!=1:raise ValueError('Expected one current route field: '+prefix)
        route_fields.append(matches[0]);methods.append('GeckoWebView.java:'+prefix)
    text=text.replace('/* ROUTE_FIELDS */','\n'.join(route_fields))
    original=(source/'MainActivity.java').read_text();anchor='status.setOnClickListener(v->'
    assert original.count(anchor)==1,'Production status must have one actual click listener'
    start=original.index(anchor)+len(anchor);click=original[start:original.index(');root.addView(status',start)]
    text=text.replace('/* STATUS_CLICK */',click if click.startswith('{') else '{'+click+';}')
    methods.append('MainActivity.java:actual status OnClickListener body')
    with tempfile.TemporaryDirectory(prefix='page-recovery-host-') as tmp:
        tmp=pathlib.Path(tmp);java=tmp/'local/pocketchat/PageRecoveryHost.java';java.parent.mkdir(parents=True);java.write_text(text)
        uri=tmp/'android/net/Uri.java';uri.parent.mkdir(parents=True);uri.write_text('package android.net; public class Uri { java.net.URI u; public static Uri parse(String x){Uri v=new Uri();v.u=java.net.URI.create(x);return v;}public String getPath(){return u.getPath();}public String getScheme(){return u.getScheme();}public String getHost(){return u.getHost();}public String getUserInfo(){return u.getUserInfo();}public int getPort(){return u.getPort();}}')
        clock=tmp/'android/os/SystemClock.java';clock.parent.mkdir(parents=True);clock.write_text('package android.os;public class SystemClock {public static long elapsedRealtime(){return 100000;}}')
        complete=[source/name for name in ('BrowserBridgeRequests.java','ChromiumRouteLease.java','GeckoNavigationPolicy.java','BrowserAddressPolicy.java')]
        def execute(generated,label):
            selected=tmp/label;selected.mkdir();selected_java=selected/'PageRecoveryHost.java';selected_java.write_text(generated)
            built=subprocess.run(['javac','-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(selected),str(selected_java),str(uri),str(clock),*map(str,complete)],capture_output=True,text=True)
            if built.returncode:raise RuntimeError('Current source host compilation failed: '+built.stderr)
            return subprocess.run(['java','-cp',str(selected)+os.pathsep+str(a.json_jar.resolve()),'local.pocketchat.PageRecoveryHost'],text=True,capture_output=True)
        result=execute(text,'current')
        if result.returncode:
            print(result.stderr,file=sys.stderr);result.check_returncode()
        report=json.loads(result.stdout)
        if report['syntheticTimeZoneRetirements']<=0 or report['actualNativeTimeZoneExecution'] is not False:raise AssertionError('Owned content exit must reach the counted synthetic system time-zone retirement boundary')
        report.update(actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimeZoneExecution=False,actualDateOrEngineExecution=False,syntheticTimeZoneFacade='default-system retirement counter only; custom scope throws',actualGeneralRouteRegistryExecution=True,productionMembers=methods,generatedHostSha256=hashlib.sha256(text.encode()).hexdigest(),scope='Exact current production Java members, complete public URL policies and actual ChromiumRouteLease registry with controlled Android/session/widget adapters. retireTimeZone is an explicit counted default-system collaborator boundary; custom scope throws. Android Uri is backed by java.net.URI; no GeckoTimeZoneController, Date/engine, device, Gecko SDK, live-network or complete application execution.')
        controls=[]
        for label,before,after,expected in (
            ('generic-automation','return !deleted&&MainActivity.chatUrl(web.getUrl());','return !deleted;','Generic website cannot dispatch ChatGPT synchronization:'),
            ('forget-session','generalSessions.remove(session);deferredGeneralLoads.remove(session);','generalSessions.contains(session);deferredGeneralLoads.remove(session);','Stopped content retires only its desired session and deferred target'),
            ('forget-lease','if(lease!=null)lease.close();','if(lease!=null){}','Stopped content closes its real surface lease without losing popup or native download'),
        ):
            if text.count(before)!=1:raise ValueError('Counterfeit must replace exactly one current production expression: '+label)
            counterfeit=text.replace(before,after,1);failed=execute(counterfeit,label)
            if failed.returncode==0 or 'java.lang.AssertionError: '+expected not in failed.stderr:
                raise AssertionError('Compiled counterfeit escaped its required semantic assertion: '+label+' / '+failed.stderr)
            controls.append(dict(name=label,compiled=True,exitCode=failed.returncode,expectedAssertion=expected,generatedHostSha256=hashlib.sha256(counterfeit.encode()).hexdigest(),stderrSha256=hashlib.sha256(failed.stderr.encode()).hexdigest()))
        report['compiledCounterfeits']=controls
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
