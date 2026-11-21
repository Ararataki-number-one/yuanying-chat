#!/usr/bin/env python3
"""Execute complete browser preferences and verbatim Main dispatch with Android adapters."""
import argparse,hashlib,importlib.util,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
spec=importlib.util.spec_from_file_location('extract',ROOT/'tests/chrome-network-state-host/run.py')
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)

def main():
    p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);args=p.parse_args()
    paths=[PROD/name for name in ['BrowserPreferences.java','BrowserAddressPolicy.java','EnvironmentEngine.java','MainActivity.java','BrowserActivity.java','BrowserSettingsUi.java','ProfileContext.java']]+[HERE/'BrowserPreferencesHost.java',pathlib.Path(__file__).resolve(),ROOT/'tests/chrome-network-state-host/run.py']
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    main_source=(PROD/'MainActivity.java').read_text()
    dispatch=extract.member(main_source,'boolean dispatchBrowser(')
    opening=extract.member(main_source,'void handleOpening(')
    native_pending=extract.member(main_source,'boolean nativeFileWorkPending(')
    gecko_pending=extract.member(main_source,'boolean geckoWorkPending(')
    gecko_website=extract.member(main_source,'boolean openWebsite(')
    chat_url=extract.member(main_source,'static boolean chatUrl(')
    settings_source=(PROD/'BrowserSettingsUi.java').read_text()
    settings_pending=extract.member(settings_source,'static boolean browserWorkPending(')
    settings_ownership='\n'.join(
        [line.strip() for line in settings_source.splitlines() if
         line.strip().startswith(('private static final String OWNER_', 'private static final String OPEN_DIALOG='))]
        +[extract.member(settings_source,signature) for signature in (
            'static EnvironmentSpec.Identity workspaceIdentity(', 'static void openWorkspace(',
            'private static Intent ownerIntent(', 'static boolean ownerOpening(',
            'private static EnvironmentSpec.Identity ownerIdentity(', 'static void showRequestedOwner(',
            'private static boolean current(', 'private static void unavailable(')]
    )
    profile_storage=extract.member((PROD/'ProfileContext.java').read_text(),'String name(')
    source=(HERE/'BrowserPreferencesHost.java').read_text().replace('/* DISPATCH_METHOD */',dispatch).replace('/* HANDLE_OPENING */',opening).replace('/* SETTINGS_OWNERSHIP */',settings_ownership).replace('/* NATIVE_PENDING */',native_pending).replace('/* GECKO_PENDING */',gecko_pending).replace('/* GECKO_OPEN_WEBSITE */',gecko_website).replace('/* CHAT_URL */',chat_url).replace('/* PROFILE_STORAGE_NAME */',profile_storage).replace('/* SETTINGS_WORK_PENDING */',settings_pending)
    browser=(PROD/'BrowserActivity.java').read_text()
    browser_methods={marker:extract.member(browser,signature) for marker,signature in (
        ('BROWSER_ACTIVITY','static Class<?> activity('),('BROWSER_RESUME','static void resume('),
        ('BROWSER_OPEN','static void open('),('BROWSER_INTENT_ADDRESS','static String intentAddress('),
        ('BROWSER_PENDING_FILE','boolean fileOperationPending('),('BROWSER_ENGINE_DISPATCH','boolean dispatchBoundEngine('),('BROWSER_OPEN_ADDRESS','void openAddress('),('BROWSER_NEW_INTENT','protected void onNewIntent('),
        ('BROWSER_LIVE','boolean live('),('BROWSER_NAVIGATION_CURRENT','boolean pageNavigationCurrent('),
        ('BROWSER_SITE_PERMISSIONS','void sitePermissions('))}
    for marker,method in browser_methods.items():source=source.replace('/* '+marker+' */',method)
    stubs={
      'android/content/Context.java':'package android.content;public abstract class Context{public static final int MODE_PRIVATE=0;public abstract SharedPreferences getSharedPreferences(String name,int mode);}',
      'android/content/SharedPreferences.java':'package android.content;public interface SharedPreferences{String getString(String key,String fallback);Editor edit();interface Editor{Editor putString(String key,String value);boolean commit();}}',
      'android/app/Activity.java':'package android.app;public abstract class Activity extends android.content.Context{public int finishes;public android.content.Intent intent;public void finish(){finishes++;}public boolean isFinishing(){return finishes>0;}public boolean isDestroyed(){return false;}public void startActivity(android.content.Intent value){throw new AssertionError("Unmodeled host launch");}public void setIntent(android.content.Intent value){intent=value;}public android.content.Intent getIntent(){return intent;}protected void onNewIntent(android.content.Intent value){}}',
      'android/net/Uri.java':'package android.net;public final class Uri{private final java.net.URI value;private Uri(String s){value=java.net.URI.create(s);}public static Uri parse(String s){return new Uri(s);}public String getScheme(){return value.getScheme();}public String getHost(){return value.getHost();}public String getUserInfo(){return value.getUserInfo();}public int getPort(){return value.getPort();}public String toString(){return value.toString();}}',
      'android/content/Intent.java':'package android.content;public final class Intent{public static final String ACTION_VIEW="android.intent.action.VIEW";public static final int FLAG_ACTIVITY_NEW_TASK=0x10000000,FLAG_ACTIVITY_REORDER_TO_FRONT=0x00020000;private final java.util.Map<String,Object> extras=new java.util.LinkedHashMap<>();private android.net.Uri data;private String action;private int flags;public Context owner;public Class<?> target;public Intent(){}public Intent(Context host,Class<?> destination){owner=host;target=destination;}public Intent addFlags(int value){flags|=value;return this;}public int getFlags(){return flags;}public Intent setAction(String value){action=value;return this;}public String getAction(){return action;}public Intent putExtra(String k,String v){extras.put(k,v);return this;}public Intent putExtra(String k,boolean v){extras.put(k,v);return this;}public Intent putExtra(String k,int v){extras.put(k,v);return this;}public int getIntExtra(String k,int f){Object v=extras.get(k);return v instanceof Integer?(Integer)v:f;}public boolean getBooleanExtra(String k,boolean f){Object v=extras.get(k);return v instanceof Boolean?(Boolean)v:f;}public String getStringExtra(String k){Object v=extras.get(k);return v instanceof String?(String)v:null;}public boolean hasExtra(String k){return extras.containsKey(k);}public void removeExtra(String k){extras.remove(k);}public Intent setData(android.net.Uri v){data=v;return this;}public android.net.Uri getData(){return data;}public String describe(){return extras.toString()+(data==null?"":" "+data);}}'
    }
    with tempfile.TemporaryDirectory(prefix='browser-preferences-host-') as raw:
        base=pathlib.Path(raw);src=base/'src';src.mkdir();(src/'BrowserPreferencesHost.java').write_text(source)
        for name in ['BrowserPreferences.java','BrowserAddressPolicy.java','EnvironmentEngine.java']:(src/name).write_bytes((PROD/name).read_bytes())
        for name,text in stubs.items():path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        classes=base/'classes';compiled=subprocess.run([str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),*map(str,src.rglob('*.java'))],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        run=subprocess.run([str(args.java_home/'bin/java'),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.BrowserPreferencesHost'],capture_output=True,text=True)
        if not run.stdout:raise RuntimeError(run.stderr)
        report=json.loads(run.stdout)
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,extractedMainDispatchSha256=hashlib.sha256(dispatch.encode()).hexdigest(),extractedAddressAndStorageSha256={name:hashlib.sha256(method.encode()).hexdigest() for name,method in {"nativeFileWorkPending":native_pending,"geckoWorkPending":gecko_pending,"openWebsite":gecko_website,"chatUrl":chat_url,"profileStorageName":profile_storage}.items()},extractedSettingsGuardSha256=hashlib.sha256(settings_pending.encode()).hexdigest(),extractedBrowserEntryPointsSha256={name:hashlib.sha256(method.encode()).hexdigest() for name,method in browser_methods.items()},jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),executionInputsUnchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in paths),actualAndroidExecution=False,actualBrowserExecution=False,scope='Complete production BrowserPreferences and BrowserAddressPolicy, exact MainActivity dispatch and ChatGPT address check, exact ProfileContext preference-name calculation, exact standalone settings ownership and native-opening methods, and exact BrowserActivity entry points, live document check and site-permissions dialog. Controlled Android persistence, Intent/Uri/Activity, catalog availability, file operation state and tab adapters. Checks defaults and existing settings, homepage validation, isolated same-engine preference names, engine selection after re-entry, web and native destination precedence, settings guards for retained file operations, exact tab preservation, and destructive dialog confirmation ownership. The host tests cold and recreated settings dispatch under adapters. Actual Android activity lifecycle, dialogs, engine cookie storage and file activity delivery are outside this host.')
    if not report['executionInputsUnchanged']:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','passed','total']},ensure_ascii=False))
    if run.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
