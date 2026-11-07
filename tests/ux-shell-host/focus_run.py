#!/usr/bin/env python3
"""Run verbatim MainActivity focus members with explicit JVM native adapters.

This executes neither Android views nor Gecko. Workspace selection, layout,
visibility, overlays and accessibility announcements use deterministic adapters.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'


def member(text,needle):
    start=text.index(needle)
    opened=text.index('{',start)
    depth=0
    quote=None
    escape=line=block=False
    i=opened
    while i<len(text):
        c=text[i]
        pair=text[i:i+2]
        if line:
            if c=='\n':line=False
        elif block:
            if pair=='*/':block=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif pair=='//':line=True;i+=1
        elif pair=='/*':block=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
        i+=1
    raise ValueError('Unclosed member: '+needle)


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-focus-integration/results.json')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    source=PRODUCTION/'MainActivity.java'
    inputs=[source,PRODUCTION/'AppHub.java',PRODUCTION/'FocusReadingPolicy.java',PRODUCTION/'LoginPagePolicy.java',PRODUCTION/'BrowserAddressPolicy.java',HERE/'focus_host.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in inputs}
    original=source.read_text()
    needles=['static boolean chatUrl(','void updateReadingLayout(','boolean focusActive(','void setFocusReading(','void applyFocusLayout(','static void chromeVisibility(','@Override public void onBackPressed(']
    selected={needle:member(original,needle) for needle in needles}
    exit_lines=[line.strip() for line in original.splitlines() if line.strip().startswith('focusExit=DesignUi.button(')]
    if len(exit_lines)!=1:raise ValueError('Expected exactly one real focus exit button initialization')
    exit_initialization=exit_lines[0]
    fixture=(HERE/'focus_host.java').read_text()
    generated=fixture.replace('/* PRODUCTION_METHODS */','\n'.join(selected.values())).replace('/* EXIT_INITIALIZATION */',exit_initialization).replace('/* HUB_KEYBOARD */',member((PRODUCTION/'AppHub.java').read_text(),'void keyboard('))
    if generated==fixture or '/* PRODUCTION_METHODS */' in generated:raise ValueError('Source extraction was not applied')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    with tempfile.TemporaryDirectory(prefix='focus-integration-host-') as temporary:
        work=Path(temporary)
        java=work/'focus_host.java';java.write_text(generated)
        uri=work/'android/net/Uri.java';uri.parent.mkdir(parents=True)
        uri.write_text('package android.net;public final class Uri {private java.net.URI value;public static Uri parse(String text){Uri result=new Uri();result.value=java.net.URI.create(text);return result;}public String getScheme(){return value.getScheme();}public String getHost(){return value.getHost();}public String getUserInfo(){return value.getUserInfo();}public int getPort(){return value.getPort();}}\n')
        classes=work/'classes'
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),str(java),str(uri),str(PRODUCTION/'FocusReadingPolicy.java'),str(PRODUCTION/'LoginPagePolicy.java'),str(PRODUCTION/'BrowserAddressPolicy.java')],text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        ran=subprocess.run([tool('java'),'-cp',str(classes),'local.pocketchat.FocusIntegrationHost'],text=True,capture_output=True)
        if ran.returncode:raise RuntimeError(ran.stderr)
        report=json.loads(ran.stdout)
    stable=all(path.is_file() and digest(path.read_bytes())==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report.update(sourceCommit=commit,sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        actualAndroidExecution=False,actualGeckoExecution=False,syntheticAdapters=True,
        executionInputsUnchanged=stable,sourceFiles=hashes,
        extractedMethods={name:digest(text.encode()) for name,text in selected.items()},
        focusExitInitializationSha256=digest(exit_initialization.encode()),
        generatedHarnessSha256=digest(generated.encode()),
        scope='Verbatim MainActivity focusActive/setFocusReading/applyFocusLayout/updateReadingLayout/onBackPressed/chatUrl and real focus-exit initialization statement, plus complete production FocusReadingPolicy, LoginPagePolicy and BrowserAddressPolicy. Deterministic native View, hub selection, browser visibility/history, session, overlay and accessibility adapters. No actual Android layout, input, Activity lifecycle, Gecko document, device or network acceptance.')
    if not stable:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'actualAndroidExecution':False,'actualGeckoExecution':False,'output':str(args.output)},ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
