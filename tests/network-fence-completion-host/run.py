#!/usr/bin/env python3
"""Actual production finish/release and fixture owner proofs on declared JVM boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def digest(data): return hashlib.sha256(data).hexdigest()

def method(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1; end = brace + 1
    while depth:
        if text[end] == '{': depth += 1
        if text[end] == '}': depth -= 1
        end += 1
    value = text[start:end]
    if text.count(signature) != 1: raise ValueError('Method signature ambiguous: ' + signature)
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--java-home', type=Path, default=Path(os.environ.get('JAVA_HOME', '/usr/lib/jvm/java-17-openjdk-amd64')))
    p.add_argument('--json-jar', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    production = ROOT / 'app/src/main/java/local/pocketchat/NetworkUiProvider.java'
    fixture = ROOT / 'tests/gecko/NetworkSafeIdleIntegrationActivity.java'
    prod, fix = production.read_text(), fixture.read_text()
    template = (HERE / 'Boundaries.java').read_text()
    snippets = {}
    for key, source, signature in [
        ('PRODUCTION_INTERNAL', prod, '  static boolean internalJob('),
        ('PRODUCTION_RECORD', prod, '  void recordResult(String id,boolean ok,String message,JSONObject operationResult)'),
        ('PRODUCTION_CAPTURE', prod, '  void captureTransition('),
        ('PRODUCTION_GATE', prod, '  void commitGate('),
        ('PRODUCTION_RELEASE', prod, '  void releaseCapture('),
        ('PRODUCTION_FINISH', prod, '  void finish('),
        ('FIXTURE_RECORD', fix, '    @Override void recordResult('),
        ('FIXTURE_INTERNAL', fix, '  static boolean internalJobId('),
        ('FIXTURE_OWNER', fix, '  NetworkUiProvider.Transition caseOwner('),
        ('FIXTURE_COMPLETION', fix, '  JSONObject completionState('),
        ('FIXTURE_CURRENT', fix, '  JSONObject currentOwnership('),
        ('FIXTURE_REQUIRE', fix, '  static void requireCompletionOwner('),
    ]:
        snippets[key] = method(source, signature)
    predicate = '!state.optBoolean("operation")&&!state.optBoolean("configurationCapture")&&state.optBoolean("touchRestored")'
    assert fix.count(predicate) == 1
    snippets['ORIGINAL_PREDICATE'] = predicate
    rendered = template
    for key, value in snippets.items(): rendered = rendered.replace('@' + key + '@', value)
    assert not re.search(r'@[A-Z_]+@', rendered)
    inputs = [production, fixture, ROOT/'app/src/main/java/local/pocketchat/J.java', ROOT/'app/src/main/java/local/pocketchat/ChromiumRouteLease.java', HERE/'run.py', HERE/'Boundaries.java']
    hashes = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in inputs}
    cases = []
    for variant in ['pristine', 'touch-mutant', 'capture-mutant']:
        work = out / variant; work.mkdir(exist_ok=True)
        source = rendered
        if variant == 'touch-mutant':
            old = 'session.web.setOnTouchListener(transition.previousTouch)'
            assert source.count(old) == 1
            source = source.replace(old, 'session.web.setOnTouchListener(transition.touchFence)')
        elif variant == 'capture-mutant':
            old = 'session.configurationCapture=false;session.operation=false;transition.capture=false;session.wakePolling();'
            assert source.count(old) == 1
            source = source.replace(old, 'session.wakePolling();')
        java = work/'Boundaries.java'; java.write_text(source)
        classes=work/'classes'; classes.mkdir(exist_ok=True)
        command=[str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(classes),str(java),str(ROOT/'app/src/main/java/local/pocketchat/J.java'),str(ROOT/'app/src/main/java/local/pocketchat/ChromiumRouteLease.java')]
        compiled=subprocess.run(command,capture_output=True,text=True)
        (work/'javac.log').write_text(compiled.stdout+compiled.stderr)
        if compiled.returncode: raise RuntimeError((compiled.stdout+compiled.stderr)[-12000:])
        modes=['closed','interleave','wrong-owner','missing-proof','unowned-global','direct-later','callbacks'] if variant=='pristine' else [variant]
        for mode in modes:
            ran=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar.resolve()),'local.pocketchat.FenceCompletionHost',mode],capture_output=True,text=True,timeout=30)
            log=work/(mode+'.log'); log.write_text(ran.stdout+ran.stderr)
            expected=0 if variant=='pristine' else 1
            if expected==0: assert ran.returncode==0,(mode,ran.stdout,ran.stderr)
            else:
                assert ran.returncode!=0,(mode,ran.stdout)
                failure='complete-late-save: capture and touch fence released' if variant=='touch-mutant' else 'Missing or invalid original completion proof'
                assert failure in ran.stderr,(mode,ran.stderr)
            cases.append(dict(variant=variant,mode=mode,status='passed',expectedRejection=bool(expected),exitCode=ran.returncode,generatedSourceSha256=digest(java.read_bytes()),logSha256=digest(log.read_bytes()),checks=json.loads(ran.stdout)['checks'] if not expected else 1))
    stable=all(digest(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report=dict(status='passed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),actualAndroidExecution=False,actualGeckoExecution=False,actualPublicWebsite=False,sourceUnchangedDuringChecks=stable,sourceFiles=hashes,methodSha256={key:digest(value.encode()) for key,value in snippets.items()},jsonJarSha256=digest(a.json_jar.read_bytes()),javaVersion=subprocess.check_output([str(a.java_home/'bin/java'),'-version'],stderr=subprocess.STDOUT,text=True),cases=cases,checks=sum(case['checks'] for case in cases),scope='Verbatim production captureTransition/commitGate/finish/releaseCapture/recordResult plus actual fixture owner/collector methods, JVM main/view/observer/identity/route boundaries declared in Boundaries.java. Non-chat controlled capture document avoids Gecko/JS branch. Controlled old-completion then later-internal capture and single-hunk leak mutations; no device or APK acceptance.')
    assert stable
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='passed',cases=len(cases),checks=report['checks'],sourceUnchangedDuringChecks=stable)))

if __name__=='__main__': main()
