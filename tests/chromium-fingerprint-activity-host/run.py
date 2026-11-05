#!/usr/bin/env python3
"""Execute current BrowserActivity method bodies with explicit lifecycle boundaries."""
import argparse, hashlib, json, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
ACTIVITY=PRODUCTION/'BrowserActivity.java'
METHODS=['live','sameFingerprintPolicy','fingerprintProviderMatches','fingerprintTraffic','fingerprintCurrent','syncFingerprintTraffic','fingerprintProblem','fingerprintNativeFields','fingerprintBinding','retireFingerprintBinding','startFingerprintSurface','denyFingerprintPopup','invalidateFingerprintObservation','beforeFingerprintNavigation','fingerprintFileChoiceCurrent','cancelFingerprintFileResult','drainFingerprintFileResult','fingerprintFileResult','observeFingerprint','fingerprintObservation','finishFingerprintObservation','go']

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
    source=ACTIVITY.read_text();templates=[HERE/'ActivityHost.java.in',HERE/'PolicyHost.java.in']
    actual=[PRODUCTION/name for name in ['ChromiumFingerprintStore.java','ChromiumFingerprintSpec.java','EnvironmentSpec.java','J.java','BrowserAddressPolicy.java']]
    adapters=ROOT/'tests/chromium-fingerprint-store-host/ChromiumFingerprintStoreHost.java'
    inputs=actual+[ACTIVITY,adapters,Path(__file__).resolve()]+templates;hashes={str(p.relative_to(ROOT)):digest(p) for p in inputs}
    results=[];negative_controls=[]
    with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-activity-host-') as temporary:
        base=Path(temporary)
        for template in templates:
            name=template.name.split('.')[0];work=base/name;work.mkdir();context=work/'android/content/Context.java';context.parent.mkdir(parents=True);context.write_text('package android.content;import java.io.File;public abstract class Context {public abstract Context getApplicationContext();public abstract File getNoBackupFilesDir();}\n')
            selected=METHODS if name=='ActivityHost' else ['live','sameFingerprintPolicy','fingerprintProviderMatches','fingerprintTraffic','fingerprintCurrent','fingerprintObservation','fingerprintNativeFields']
            generated=template.read_text().replace('__METHODS__','\n'.join(method(source,item) for item in selected)).replace('__TAB__',nested(source,'Tab')).replace('__CHOICE__',nested(source,'FingerprintFileChoice'));java=work/(name+'.java');java.write_text(generated)
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve()),'-d',str(work/'classes'),*[str(p) for p in actual],str(adapters),str(context),str(java)],capture_output=True,text=True)
            if compiled.returncode:raise RuntimeError(name+' compile:\n'+compiled.stderr)
            executed=subprocess.run([tool('java'),'-cp',str(work/'classes')+':'+str(args.json_jar.resolve()),'local.pocketchat.'+name,str(work/'state')],capture_output=True,text=True,timeout=60)
            if executed.returncode:raise RuntimeError(name+' execution:\n'+executed.stderr)
            results.append(json.loads(executed.stdout))
            if name=='ActivityHost':
                mutants=[
                    ('Immediate original-style file delivery races resume recheck','fingerprintFileResult=new Intent(data);fingerprintFileRequest=request;message("正在确认原网页与指纹配置，确认后交付所选文件…");fingerprintMain.post(this::drainFingerprintFileResult);return true;','return files.result(request,result,data);','Result before resume never reaches blocked renderer'),
                    ('Dropped explicit address during identity recheck','selected.fingerprintNavigation=url;','', 'Address entered during recheck remains queued and old DOM retained'),
                    ('Old observation callback accepts retired document','if(operation!=fingerprintObservationGeneration||!fingerprintCurrent(tab,view,state,binding)||tab.loading||!Objects.equals(url,view.getUrl()))return;','', 'Late observation cannot enqueue receipt after navigation')]
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
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,results=results,negativeControls=negative_controls,sourceChecks=[label for label,_ in checks],sourceFiles=hashes,jsonJarSha256=digest(args.json_jar),executionInputsUnchanged=unchanged,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualChromiumExecution=False,actualAesExecution=False,scope='Current production BrowserActivity method bodies plus whole production Store/Spec/EnvironmentSpec/J/AddressPolicy. Real JVM files/locks with explicit plain-vault/catalog adapters. Manual UI and worker queues, WebView/provider/native preparation and chooser callback boundaries exercise lifecycle/ownership ordering, positive file callback network readiness, pending addresses, actual durable receipt and bounded synthetic response parsing. Three compiled behavior counterfeits must fail their exact behavioral assertion. This does not execute Android lifecycle, URI permission validation, WebView network requests, UA-CH or page fingerprint APIs.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],passed=total,total=total,output=str(args.output))))
    if not unchanged:raise SystemExit(1)

if __name__=='__main__':main()
