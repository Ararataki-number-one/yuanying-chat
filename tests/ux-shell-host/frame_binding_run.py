#!/usr/bin/env python3
"""Execute verbatim MainActivity model binding with the real frame scheduler on JVM adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from focus_run import member

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-frame-binding/results.json')
    args=parser.parse_args()
    def tool(name):
        result=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not result:parser.error('Provide --java-home containing '+name)
        return result
    source=PRODUCTION/'MainActivity.java'
    scheduler=PRODUCTION/'UiFrameScheduler.java'
    progress=PRODUCTION/'ChatDownloadProgressUi.java'
    address=PRODUCTION/'GeckoAddressUi.java'
    inputs=[source,scheduler,progress,address,HERE/'frame_binding_host.java',HERE/'focus_run.py',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in inputs}
    original=source.read_text()
    selected={name:member(original,name) for name in ['void syncSessionReferences(','void requestSessionUi(','void requestPresentationUi(','void applySession(','void updateReadingLayout(']}
    address_methods={name:member(address.read_text(),name) for name in ['static boolean canForward(','static boolean available(']}
    ticker=member(original,'final Runnable ticker=')+';'
    observers=[line.strip() for line in progress.read_text().splitlines() if line.strip().startswith('observer=new ContentObserver(')]
    if len(observers)!=1:raise ValueError('Expected one actual download observer initialization')
    fixture=(HERE/'frame_binding_host.java').read_text()
    if fixture.count('/* PRODUCTION_METHODS */')!=1:raise ValueError('Expected one verbatim-method insertion point')
    if fixture.count('/* ADDRESS_METHODS */')!=1:raise ValueError('Expected one address-method insertion point')
    generated=fixture.replace('/* PRODUCTION_METHODS */','\n'.join(selected.values())).replace('/* ADDRESS_METHODS */','\n'.join(address_methods.values())).replace('/* TICKER */',ticker).replace('/* DOWNLOAD_OBSERVER */',observers[0])
    with tempfile.TemporaryDirectory(prefix='frame-binding-host-') as temporary:
        work=Path(temporary);java=work/'frame_binding_host.java';java.write_text(generated);classes=work/'classes'
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),str(java),str(scheduler)],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        ran=subprocess.run([tool('java'),'-cp',str(classes),'local.pocketchat.FrameBindingHost'],capture_output=True,text=True)
        if ran.returncode:raise RuntimeError(ran.stderr)
        report=json.loads(ran.stdout)
        controls=[]
        for name,before,after,expected in [
            ('missing-tools-frame-update','if(toolsPanel!=null)toolsPanel.navigationState(remote.canGoBack(),GeckoAddressUi.canForward(this),session.navigating);','','One coalesced frame updates the open tools panel once'),
            ('stale-tools-loading-state','toolsPanel.navigationState(remote.canGoBack(),GeckoAddressUi.canForward(this),session.navigating);','toolsPanel.navigationState(remote.canGoBack(),GeckoAddressUi.canForward(this),false);','The open tools panel receives the final history and loading state'),
        ]:
            if generated.count(before)!=1:raise ValueError('Expected one production mutation point for '+name)
            mutated=generated.replace(before,after,1);java.write_text(mutated)
            compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),str(java),str(scheduler)],capture_output=True,text=True)
            if compiled.returncode:raise RuntimeError(name+' failed to compile: '+compiled.stderr)
            ran=subprocess.run([tool('java'),'-cp',str(classes),'local.pocketchat.FrameBindingHost'],capture_output=True,text=True)
            if ran.returncode==0 or 'AssertionError: '+expected not in ran.stderr:raise RuntimeError(name+' did not fail at its intended assertion: '+ran.stderr)
            controls.append(dict(name=name,status='rejected',expectedAssertion=expected,generatedHarnessSha256=digest(mutated.encode())))
        report['negativeControls']=controls
    stable=all(path.is_file() and digest(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        actualAndroidExecution=False,actualGeckoExecution=False,syntheticAdapters=True,
        executionInputsUnchanged=stable,sourceFiles=hashes,
        extractedMethods={name:digest(text.encode()) for name,text in selected.items()},
        extractedAddressMethods={name:digest(text.encode()) for name,text in address_methods.items()},
        tickerSha256=digest(ticker.encode()),downloadObserverSha256=digest(observers[0].encode()),
        generatedHarnessSha256=digest(generated.encode()),
        scope='Verbatim MainActivity syncSessionReferences/requestSessionUi/applySession/updateReadingLayout bodies, GeckoAddressUi canForward/available, actual ticker and download observer initialization, complete production UiFrameScheduler. Deterministic session object-identity tokens, browser observations, presentation consumers and frame queue adapters. Reading keyboard callbacks, focus-layout invocations and tools-panel rendering are counted adapters; actual focus-layout and tools-button behavior have separate production-method hosts. Checks immediate model mirroring through1000 observer updates mixed with1000 download notifications and a timer tick, one latest-state presentation frame including current tools history/loading, null/startup fallback and pause/destroy callback cancellation. Metrics-to-chrome is an immediate boundary here; chrome frame coalescing has its own production-method tests. No actual Android layout, Activity lifecycle, renderer, FPS, wall-time speedup or Gecko execution.')
    if not stable:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],burstEvents=report['burstEvents'],burstPaints=report['burstPaints'],immediateModelSnapshotsVerified=report['immediateModelSnapshotsVerified'],output=str(args.output))))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
