#!/usr/bin/env python3
"""Execute current BrowserActivity method bodies with explicit lifecycle boundaries."""
import argparse, hashlib, json, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
ACTIVITY=PRODUCTION/'BrowserActivity.java'
METHODS=['live','sameFingerprintPolicy','fingerprintProviderMatches','fingerprintTraffic','fingerprintCurrent','syncFingerprintTraffic','fingerprintProblem','fingerprintNativeFields','fingerprintBinding','retireFingerprintBinding','startFingerprintSurface','denyFingerprintPopup','invalidateFingerprintObservation','beforeFingerprintNavigation','finishedPage','fingerprintFileChoiceCurrent','cancelFingerprintFileResult','drainFingerprintFileResult','fingerprintFileResult','observeFingerprint','fingerprintObservation','finishFingerprintObservation','go','history','reloadOrStop']

def block(source,start):
    opening=source.index('{',start);depth=0;quote=None;escape=False;line=False;comment=False;i=opening
    while i<len(source):
        c=source[i];n=source[i+1:i+2]
        if line:
            if c=='\n':line=False
        elif comment:
            if c=='*' and n=='/':comment=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif c=='/' and n=='/':line=True;i+=1
        elif c=='/' and n=='*':comment=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return source[start:i+1]
        i+=1
    raise ValueError('Unclosed source block')

def method(source,name):
    matches=list(re.finditer(r'^  (?:(?:@Override|protected|public|static|final)\s+)*[A-Za-z0-9_.$<>?]+(?:\[\])?\s+'+re.escape(name)+r'\(',source,re.M))
    if len(matches)!=1:raise ValueError('Ambiguous method '+name)
    return block(source,matches[0].start())

def nested(source,name):
    matches=list(re.finditer(r'^  static final class '+name+r'\s*\{',source,re.M))
    if len(matches)!=1:raise ValueError('Missing class '+name)
    return block(source,matches[0].start())

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--java-home',type=Path);parser.add_argument('--json-jar',required=True,type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    def tool(name):return str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
    source=ACTIVITY.read_text();fixture=ROOT/'tests/gecko/BrowserIntegrationActivity.java';fixture_source=fixture.read_text();templates=[HERE/'ActivityHost.java.in',HERE/'PolicyHost.java.in',HERE/'NativePageHost.java.in']
    actual=[PRODUCTION/name for name in ['ChromiumFingerprintStore.java','ChromiumFingerprintSpec.java','EnvironmentSpec.java','J.java','BrowserAddressPolicy.java','BrowserLibrary.java']]
    adapters=ROOT/'tests/chromium-fingerprint-store-host/ChromiumFingerprintStoreHost.java'
    inputs=actual+[ACTIVITY,fixture,adapters,Path(__file__).resolve()]+templates;hashes={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    results=[];negative_controls=[]
    with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-activity-host-') as temporary:
        base=Path(temporary)
        for template in templates:
            name=template.name.split('.')[0];work=base/name;work.mkdir();context=work/'android/content/Context.java';context.parent.mkdir(parents=True);context.write_text('package android.content;import java.io.File;import java.util.*;public abstract class Context {public abstract Context getApplicationContext();public abstract File getNoBackupFilesDir();private final Map<String,SharedPreferences> prefs=new HashMap<>();public SharedPreferences getSharedPreferences(String name,int mode){return prefs.computeIfAbsent(name,key->new Memory());}static final class Memory implements SharedPreferences,SharedPreferences.Editor {final Map<String,String> values=new HashMap<>();public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}public SharedPreferences.Editor edit(){return this;}public SharedPreferences.Editor putString(String key,String value){values.put(key,value);return this;}public SharedPreferences.Editor remove(String key){values.remove(key);return this;}public void apply(){}}}\n')
            preferences=work/'android/content/SharedPreferences.java';preferences.write_text('package android.content;public interface SharedPreferences {String getString(String key,String fallback);Editor edit();interface Editor {Editor putString(String key,String value);Editor remove(String key);void apply();}}\n')
            selected=METHODS if name=='ActivityHost' else ['live','sameFingerprintPolicy','fingerprintProviderMatches','fingerprintTraffic','fingerprintCurrent','fingerprintObservation','fingerprintNativeFields']
            callbacks='\n'.join(block(source,source.index('@Override public void '+name+'(')).replace('@Override ','',1) for name in ['onPageStarted','doUpdateVisitedHistory'])
            generated=template.read_text().replace('__METHODS__','\n'.join(method(source,item) for item in selected)).replace('__TAB__',nested(source,'Tab')).replace('__CHOICE__',nested(source,'FingerprintFileChoice')).replace('__NATIVE_CALLBACKS__',callbacks);java=work/(name+'.java');java.write_text(generated)
            if name=='NativePageHost':
                old_page=method(fixture_source,'page');gate='&&nativePageCompleted(path)'
                if old_page.count(gate)!=1:raise AssertionError('Review original getter-only page negative baseline')
                generated=template.read_text().replace('__COMPLETION_CLASS__',nested(fixture_source,'NativePageCompletion')).replace('__METHODS__','\n'.join(method(fixture_source,item) for item in ['nativePageCompleted','page','controlledPagePath'])).replace('__OLD_PAGE__',old_page.replace('boolean page(','boolean oldPage(',1).replace(gate,'',1));java.write_text(generated)
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve()),'-d',str(work/'classes'),*[str(p) for p in actual],str(adapters),str(context),str(preferences),str(java)],capture_output=True,text=True)
            if compiled.returncode:raise RuntimeError(name+' compile:\n'+compiled.stderr)
            executed=subprocess.run([tool('java'),'-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'local.pocketchat.'+name,str(work/'state')],capture_output=True,text=True,timeout=60)
            if executed.returncode:raise RuntimeError(name+' execution:\n'+executed.stderr)
            results.append(json.loads(executed.stdout))
            if name=='ActivityHost':
                mutants=[
                    ('Immediate original-style file delivery races resume recheck','fingerprintFileResult=new Intent(data);fingerprintFileRequest=request;message("正在确认原网页与指纹配置，确认后交付所选文件…");fingerprintMain.post(this::drainFingerprintFileResult);return true;','return files.result(request,result,data);','Result before resume never reaches blocked renderer'),
                    ('Dropped explicit address during identity recheck','selected.fingerprintNavigation=url;','', 'Address entered during recheck remains queued and old DOM retained'),
                    ('Old observation callback accepts retired document','if(operation!=fingerprintObservationGeneration||!fingerprintCurrent(tab,view,state,binding)||tab.loading||!Objects.equals(url,view.getUrl()))return;','', 'Late observation cannot enqueue receipt after navigation'),
                    ('Explicit go retains previous idle state before native callback','selected.loading=true;web().loadUrl(url);','web().loadUrl(url);','Explicit go marks loading before getter updates and native start callback'),
                    ('Back dispatch retains previous idle state','selected.loading=true;web().goBack();','web().goBack();','Back dispatch synchronously marks loading'),
                    ('Reload dispatch retains previous idle state','selected.loading=true;web().reload();','web().reload();','Reload dispatch synchronously marks loading'),
                    ('SPA callback starts an unfinished load','tab.generation++;}\n','tab.generation++;tab.loading=true;}\n','SPA history callback remains idle without a native finish')]
                for index,(label,before,after,expected) in enumerate(mutants):
                    if generated.count(before)!=1:raise AssertionError('Mutation boundary changed: '+label)
                    java.write_text(generated.replace(before,after,1))
                    compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'-d',str(work/'classes'),str(java)],capture_output=True,text=True)
                    if compiled.returncode:raise RuntimeError('Negative control did not compile: '+label+'\n'+compiled.stderr)
                    executed=subprocess.run([tool('java'),'-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'local.pocketchat.'+name,str(work/('negative-'+str(index)))],capture_output=True,text=True,timeout=60)
                    if executed.returncode==0 or 'AssertionError: '+expected not in executed.stderr:raise AssertionError('Negative control not rejected by expected behavior: '+label+'\n'+executed.stderr)
                    negative_controls.append(label)
    checks=[]
    create=method(source,'createSurface');checks.append(('Native runtime preparation precedes validation/start',create.index('ChromiumFingerprintRuntime.prepare(')<create.index('validateFingerprintSurface(')))
    checks.append(('New native surface starts network-blocked before preparation',create.index('setBlockNetworkLoads(true)')<create.index('ChromiumFingerprintRuntime.prepare(')))
    checks.append(('No Activity UA-only late override', 'setUserAgentString(' not in source))
    save=method(source,'saveFingerprint');checks.append(('Policy save rebuilds all tabs and discards old restore state','for(Tab tab:new ArrayList<>(tabs)){retire(tab);tab.saved=null;' in save and 'for(Tab tab:new ArrayList<>(tabs))createSurface(tab)' in save))
    checks.append(('Actual lifecycle uses deferred file result before fallback','if(fingerprintFileResult(request,result,data))return;' in method(source,'onActivityResult')))
    for label,passed in checks:
        if not passed:raise AssertionError(label)
    unchanged=all(digest(ROOT/name)==sha for name,sha in hashes.items());total=sum(item['passed'] for item in results)+len(checks)
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,results=results,negativeControls=negative_controls,sourceChecks=[label for label,_ in checks],sourceFiles=hashes,jsonJarSha256=digest(args.json_jar),executionInputsUnchanged=unchanged,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualChromiumExecution=False,actualAesExecution=False,scope='Current production BrowserActivity methods/native start/history callbacks and whole Store/Spec/EnvironmentSpec/J/AddressPolicy/BrowserLibrary, plus exact fixture native completion predicates/holder. Real JVM files/locks with explicit plain-vault/catalog and in-memory SharedPreferences adapters. Manual UI/worker queues, WebView/provider/native preparation/chooser boundaries exercise lifecycle, upload network readiness, pending URLs, dispatch-time loading, stop, native completion/history, SPA, durable receipts and bounded parsing. Seven compiled behavior counterfeits must fail their exact assertion; a separate getter-only predicate negative baseline must expose early advancement. No Android lifecycle, URI permission validation, native WebView requests, UA-CH or page fingerprint API execution.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],passed=total,total=total,output=str(args.output))))
    if not unchanged:raise SystemExit(1)

if __name__=='__main__':main()
