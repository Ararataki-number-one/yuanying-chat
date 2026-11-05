#!/usr/bin/env python3
"""Execute actual Gecko page-finish/HTTP-error callbacks with declared JVM interfaces."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from run import ROOT, HERE, PROD, digest, member_at


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path,required=True)
    parser.add_argument('--json-jar',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=PROD/'ChatSession.java';observer=PROD/'WebReplyObserver.java';template=HERE/'ClientReadyHost.java.in'
    complete=[PROD/name for name in ['BrowserAddressPolicy.java','GeckoNavigationPolicy.java','BrowserRuntimePolicy.java','LoginPagePolicy.java','J.java']]
    files=[source,observer,template,Path(__file__).resolve(),HERE/'run.py',*complete]
    hashes={str(path.relative_to(ROOT)):digest(path) for path in files};json_hash=digest(args.json_jar)
    raw=source.read_text();selected={needle:member_at(raw,raw.index(needle)) for needle in ['public void onPageFinished(','public void onReceivedHttpError(']}
    ready=member_at(observer.read_text(),observer.read_text().index('void pageReady('))
    def generate(callbacks,install):
        text='\n'.join(callbacks.values()).replace('WebResourceRequest','RequestBoundary').replace('WebResourceResponse','ResponseBoundary').replace('WebView','WebBoundary')
        return template.read_text().replace('@CALLBACKS@',text).replace('@OBSERVER_READY@',install)
    generated=generate(selected,ready);args.output.parent.mkdir(parents=True,exist_ok=True)
    artifacts=args.output.parent/(args.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='gecko-client-ready-host-') as temporary:
        work=Path(temporary)
        def run(text,label,focus=None):
            folder=work/label;folder.mkdir();java=folder/'ClientReadyHost.java';java.write_text(text);classes=folder/'classes';logs=artifacts/label;logs.mkdir(exist_ok=True)
            (logs/'ClientReadyHost.java').write_text(text)
            command=[str(args.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),str(java),*map(str,complete)]
            compiled=subprocess.run(command,capture_output=True,text=True,timeout=60);(logs/'compile.command.json').write_text(json.dumps(command)+'\n');(logs/'compile.stdout.log').write_text(compiled.stdout);(logs/'compile.stderr.log').write_text(compiled.stderr)
            if compiled.returncode:raise RuntimeError(compiled.stderr)
            command=[str(args.java_home/'bin/java'),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.ClientReadyHost',*([focus] if focus else [])]
            ran=subprocess.run(command,capture_output=True,text=True,timeout=30);(logs/'run.command.json').write_text(json.dumps(command)+'\n');(logs/'run.stdout.log').write_text(ran.stdout);(logs/'run.stderr.log').write_text(ran.stderr);return ran
        current=run(generated,'current')
        if current.returncode:raise RuntimeError(current.stdout+current.stderr)
        report=json.loads(current.stdout)
        mutations=[
            ('google-body-read','public void onPageFinished(','webObserver.pageReady();','webObserver.pageReady();if(LoginPagePolicy.google(url))checkGoogleLogin(url);','google','Google login ready does not inspect website DOM'),
            ('external-login-ready','public void onPageFinished(','if(!MainActivity.chatUrl(url)){','if(!MainActivity.chatUrl(url)&&!LoginPagePolicy.login(url)){','logins','External login is browser ready: accounts.google.com'),
            ('external-http-error','public void onReceivedHttpError(','MainActivity.chatUrl(r.getUrl().toString())&&','', 'errors','External login HTTP error is a website error: accounts.google.com'),
            ('observer-origin','observer',' && session.web.resourcePage(session.web.getUrl())','', 'generic','Public page is ready without ChatGPT script: https://example.org/form'),
            ('stale-page-finish','public void onPageFinished(','if(!url.equals(web.getUrl()))return;','', 'chat','Stale finish callback changes no current page state'),
        ]
        for name,member,before,after,focus,assertion in mutations:
            pristine=run(generated,'pristine-'+name,focus)
            if pristine.returncode:raise AssertionError('Pristine failed: '+name+pristine.stderr)
            changed=dict(selected);changed_ready=ready
            original=ready if member=='observer' else changed[member]
            if original.count(before)!=1:raise ValueError('Review exact mutation: '+name)
            if member=='observer':changed_ready=ready.replace(before,after,1)
            else:changed[member]=original.replace(before,after,1)
            mutant=generate(changed,changed_ready);rejected=run(mutant,'mutation-'+name,focus)
            if rejected.returncode==0 or 'AssertionError: '+assertion not in rejected.stderr:raise AssertionError('Expected focused assertion did not reject: '+name+rejected.stdout+rejected.stderr)
            controls.append(dict(case=name,productionMember=member,removed=before,replacement=after,pristinePassed=True,mutantRejected=True,expectedAssertion=assertion,generatedSha256=hashlib.sha256(mutant.encode()).hexdigest()))
    stable=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in files) and digest(args.json_jar)==json_hash
    report.update(status='passed' if stable else 'source-changed',sourceFiles=hashes,jsonJarSha256=json_hash,executionInputsUnchanged=stable,negativeControls=controls,productionMethodsSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in {**selected,'WebReplyObserver.pageReady':ready}.items()},generatedSourceSha256=hashlib.sha256(generated.encode()).hexdigest(),scope='Actual ChatSession onPageFinished/onReceivedHttpError and WebReplyObserver.pageReady bodies. Declared JVM WebView callback/request/response/reading/audit/prefs/trace boundaries; observer script dispatch is recorded, not evaluated as a DOM. Actual LoginPagePolicy and BrowserRuntimePolicy official-origin predicate. No Android, Gecko SDK, network, credentials or website DOM execution.')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],negativeControls=len(controls),executionInputsUnchanged=stable,output=str(args.output))))
    if not stable:raise SystemExit(1)


if __name__=='__main__':main()
