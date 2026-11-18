#!/usr/bin/env python3
"""Execute current BrowserActivity method bodies with explicit lifecycle boundaries."""
import argparse, base64, hashlib, json, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
ACTIVITY=PRODUCTION/'BrowserActivity.java'
METHODS=['onActivityResult','live','sameFingerprintPolicy','fingerprintProviderMatches','fingerprintTraffic','fingerprintBindingCurrent','fingerprintCurrent','syncFingerprintTraffic','fingerprintProblem','fingerprintNativeFields','fingerprintBinding','retireFingerprintBinding','startFingerprintSurface','denyFingerprintPopup','invalidateFingerprintObservation','beforeFingerprintNavigation','beginPageNavigation','pageNavigationCurrent','finishedPage','fingerprintFileChoiceCurrent','cancelFingerprintFileResult','drainFingerprintFileResult','fingerprintFileResult','observeFingerprint','fingerprintObservation','finishFingerprintObservation','fingerprintObservationCurrent','pauseFingerprintObservation','go','history','reloadOrStop']
PREPARATION_METHODS=['live','sameFingerprintPolicy','fingerprintProviderKey','fingerprintProviderMatches','fingerprintTraffic','fingerprintBindingCurrent','fingerprintCurrent','syncFingerprintTraffic','fingerprintProblem','loadFingerprintState','fingerprintNativeFields','fingerprintBinding','retireFingerprintBinding','validateFingerprintSurface','ensureFingerprintBinding','saveFingerprint']

def declarations(java, path):
    parsed = subprocess.run([java, str(HERE/'JavaMembers.java'), str(path)],
                            capture_output=True, text=True, check=True)
    members = {}
    for row in parsed.stdout.splitlines():
        kind, name, encoded = row.split('\t')
        members.setdefault((kind,name), []).append(base64.b64decode(encoded).decode())
    return members

def member(members, kind, name):
    matches = members.get((kind,name), [])
    if len(matches) != 1:
        raise ValueError(f'Expected one {kind} {name}, found {len(matches)}')
    return matches[0]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--java-home',type=Path);parser.add_argument('--json-jar',required=True,type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    def tool(name):return str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
    source=ACTIVITY.read_text();fixture=ROOT/'tests/gecko/BrowserIntegrationActivity.java';activity_members=declarations(tool('java'),ACTIVITY);fixture_members=declarations(tool('java'),fixture);templates=[HERE/'ActivityHost.java.in',HERE/'PolicyHost.java.in',HERE/'NativePageHost.java.in',HERE/'PreparationHost.java.in']
    actual=[PRODUCTION/name for name in ['ChromiumFingerprintJobs.java','ChromiumFingerprintStore.java','ChromiumFingerprintSpec.java','EnvironmentSpec.java','J.java','BrowserAddressPolicy.java','BrowserLibrary.java']]
    adapters=ROOT/'tests/chromium-fingerprint-store-host/ChromiumFingerprintStoreHost.java'
    inputs=actual+[ACTIVITY,fixture,adapters,HERE/'JavaMembers.java',Path(__file__).resolve()]+templates;hashes={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    results=[];negative_controls=[]
    with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-activity-host-') as temporary:
        base=Path(temporary)
        for template in templates:
            name=template.name.split('.')[0];work=base/name;work.mkdir();context=work/'android/content/Context.java';context.parent.mkdir(parents=True);context.write_text('package android.content;import java.io.File;import java.util.*;public abstract class Context {public abstract Context getApplicationContext();public abstract File getNoBackupFilesDir();public final android.content.res.AssetManager assets=new android.content.res.AssetManager();public android.content.res.AssetManager getAssets(){return assets;}private final Map<String,SharedPreferences> prefs=new HashMap<>();public SharedPreferences getSharedPreferences(String name,int mode){return prefs.computeIfAbsent(name,key->new Memory());}static final class Memory implements SharedPreferences,SharedPreferences.Editor {final Map<String,String> values=new HashMap<>();public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}public SharedPreferences.Editor edit(){return this;}public SharedPreferences.Editor putString(String key,String value){values.put(key,value);return this;}public SharedPreferences.Editor remove(String key){values.remove(key);return this;}public void apply(){}}}\n')
            assets=work/'android/content/res/AssetManager.java';assets.parent.mkdir(parents=True);assets.write_text('package android.content.res;import java.io.*;import java.nio.charset.StandardCharsets;public class AssetManager {public String script=\"host-script\";public boolean failRead;public int opens,closes;public InputStream open(String name)throws IOException{opens++;if(failRead)throw new IOException(\"Injected asset read failure\");if(!name.equals(\"chromium-fingerprint.js\"))throw new IOException(\"Unexpected asset\");return new ByteArrayInputStream(script.getBytes(StandardCharsets.UTF_8)){public void close()throws IOException{closes++;super.close();}};}}\n')
            preferences=work/'android/content/SharedPreferences.java';preferences.write_text('package android.content;public interface SharedPreferences {String getString(String key,String fallback);Editor edit();interface Editor {Editor putString(String key,String value);Editor remove(String key);void apply();}}\n')
            selected=METHODS if name=='ActivityHost' else PREPARATION_METHODS if name=='PreparationHost' else ['live','sameFingerprintPolicy','fingerprintProviderMatches','fingerprintTraffic','fingerprintBindingCurrent','fingerprintCurrent','fingerprintObservation','fingerprintNativeFields']
            callbacks='\n'.join(re.sub(r'@Override\s*','',member(activity_members,'callback',item),count=1) for item in ['onPageStarted','doUpdateVisitedHistory'])
            generated=template.read_text().replace('__METHODS__','\n'.join(member(activity_members,'method',item) for item in selected)).replace('__TAB__',member(activity_members,'class','Tab')).replace('__CHOICE__',member(activity_members,'class','FingerprintFileChoice')).replace('__NATIVE_CALLBACKS__',callbacks);java=work/(name+'.java');java.write_text(generated)
            if name=='NativePageHost':
                old_page=member(fixture_members,'method','page');gate='&&nativePageCompleted(path)'
                if old_page.count(gate)!=1:raise AssertionError('Review original getter-only page negative baseline')
                generated=template.read_text().replace('__COMPLETION_CLASS__',member(fixture_members,'class','NativePageCompletion')).replace('__METHODS__','\n'.join(member(fixture_members,'method',item) for item in ['nativePageCompleted','page','controlledPagePath'])).replace('__OLD_PAGE__',old_page.replace('boolean page(','boolean oldPage(',1).replace(gate,'',1));java.write_text(generated)
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve()),'-d',str(work/'classes'),*[str(p) for p in actual],str(adapters),str(context),str(preferences),str(assets),str(java)],capture_output=True,text=True)
            if compiled.returncode:raise RuntimeError(name+' compile:\n'+compiled.stderr)
            executed=subprocess.run([tool('java'),'-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'local.pocketchat.'+name,str(work/'state')],capture_output=True,text=True,timeout=60)
            if executed.returncode:raise RuntimeError(name+' execution:\n'+executed.stderr)
            results.append(json.loads(executed.stdout))
            if name=='ActivityHost':
                selected=member(activity_members,'method','fingerprintFileResult')
                immediate=selected[:selected.index('{')+1]+'return files.result(request,result,data);}'
                mutants=[
                    ('Immediate original-style file delivery races resume recheck',selected,immediate,'Result before resume never reaches blocked renderer'),
                    ('Dropped explicit address during identity recheck','tab.fingerprintNavigation=url;','', 'Address entered during recheck remains queued and old DOM retained'),
                    ('Old observation callback accepts retired document','if(operation!=fingerprintObservationGeneration||!fingerprintCurrent(tab,view,state,binding)||tab.loading||!Objects.equals(url,view.getUrl()))return;','', 'Late observation cannot enqueue receipt after navigation'),
                    ('Explicit go retains previous idle state before native callback','tab.loading=true;\n        view.loadUrl(url);','view.loadUrl(url);','Explicit go marks loading before getter updates and native start callback'),
                    ('Back dispatch retains previous idle state','tab.loading=true;view.goBack();','view.goBack();','Back dispatch synchronously marks loading'),
                    ('Reload dispatch retains previous idle state','tab.loading=true;view.reload();','view.reload();','Reload dispatch synchronously marks loading'),
                    ('SPA callback starts an unfinished load','tab.generation++;}\n','tab.generation++;tab.loading=true;}\n','SPA history callback remains idle without a native finish'),
                    ('Reentered callback retains authority over a newer navigation','return live(tab,view)&&selected==selection&&tab.generation==navigation;','return live(tab,view);','Picker cancellation cannot overwrite a newer address')]
                for index,(label,before,after,expected) in enumerate(mutants):
                    if generated.count(before)!=1:raise AssertionError('Mutation boundary changed: '+label)
                    java.write_text(generated.replace(before,after,1))
                    compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'-d',str(work/'classes'),str(java)],capture_output=True,text=True)
                    if compiled.returncode:raise RuntimeError('Negative control did not compile: '+label+'\n'+compiled.stderr)
                    executed=subprocess.run([tool('java'),'-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'local.pocketchat.'+name,str(work/('negative-'+str(index)))],capture_output=True,text=True,timeout=60)
                    if executed.returncode==0 or 'AssertionError: '+expected not in executed.stderr:raise AssertionError('Negative control not rejected by expected behavior: '+label+'\n'+executed.stderr)
                    negative_controls.append(label)
    checks=[]
    create=member(activity_members,'method','createSurface');checks.append(('Native runtime preparation precedes validation/start',create.index('ChromiumFingerprintRuntime.prepare(')<create.index('validateFingerprintSurface(')))
    checks.append(('New native surface starts network-blocked before preparation',create.index('setBlockNetworkLoads(true)')<create.index('ChromiumFingerprintRuntime.prepare(')))
    checks.append(('No Activity UA-only late override', 'setUserAgentString(' not in source))
    save=member(activity_members,'method','saveFingerprint');checks.append(('Policy save rebuilds all tabs and discards old restore state',re.search(r'for\(Tab tab:new ArrayList<>\(tabs\)\)\{\s*retire\(tab\);tab.saved=null;',save) is not None and 'for(Tab tab:new ArrayList<>(tabs))createSurface(tab)' in save))
    with tempfile.TemporaryDirectory(prefix='activity-declaration-layout-') as folder:
        variant=Path(folder)/ACTIVITY.name
        original=member(activity_members,'method','fingerprintFileResult')
        signature,count=re.subn(r'\bboolean\s+fingerprintFileResult', 'boolean\n        fingerprintFileResult', original, count=1)
        if count!=1:raise AssertionError('Expected unique file-result declaration')
        variant.write_text(source.replace(original,'  '+signature,1))
        reindented=member(declarations(tool('java'),variant),'method','fingerprintFileResult')
        checks.append(('A multiline, reindented Java declaration still selects the real file-result method',reindented==signature))
    for label,passed in checks:
        if not passed:raise AssertionError(label)
    unchanged=all(digest(ROOT/name)==sha for name,sha in hashes.items());total=sum(item['passed'] for item in results)+len(checks)
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,results=results,negativeControls=negative_controls,sourceChecks=[label for label,_ in checks],sourceFiles=hashes,jsonJarSha256=digest(args.json_jar),executionInputsUnchanged=unchanged,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualChromiumExecution=False,actualAesExecution=False,scope='Current complete ChromiumFingerprintJobs and production BrowserActivity preparation/save/validation/binding methods plus navigation methods/native start/history callbacks and whole Store/Spec/EnvironmentSpec/J/AddressPolicy/BrowserLibrary, plus exact fixture native completion predicates/holder. Real JVM files/locks with explicit plain-vault/catalog and in-memory SharedPreferences adapters. Manual UI/worker queues, WebView/provider/native preparation/chooser boundaries exercise lifecycle, upload network readiness, pending URLs, dispatch-time loading, stop, native completion/history, SPA, durable receipts and bounded parsing. Cancellation reentry exercises latest-intent ownership, tab changes, close, stop and independent-transfer boundaries. Failed protected/Worker observations block traffic before storage; write/rejection errors cannot restore permission, current failed receipts remain displayable, and cleanup reentry cannot affect newer owners. Preparation executes actual Activity load/save/validate/ensure methods with explicit native surface, UI and Worker-confirmation boundaries. Eight compiled behavior counterfeits must fail their exact assertion; a separate getter-only predicate negative baseline must expose early advancement. No Android lifecycle, URI permission validation, native WebView requests, UA-CH or page fingerprint API execution.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],passed=total,total=total,output=str(args.output))))
    if not unchanged:raise SystemExit(1)

if __name__=='__main__':main()
