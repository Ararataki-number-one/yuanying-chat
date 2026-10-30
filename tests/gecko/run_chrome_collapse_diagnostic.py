#!/usr/bin/env python3
"""Focused synthetic diagnosis; never a replacement for the complete UI workload.

The selected source's exact server, reload statements, and collapse runner are
executed unchanged. Two declared fresh-VM invocations distinguish cold collapse
from the original reload-then-collapse portion. Neither replays the earlier 111
screenshots, native forms, or compact-chrome performance cases.
"""
import argparse
import ast
import hashlib
import http.server
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
import uuid

ROOT=pathlib.Path(__file__).resolve().parents[2]


def selected_program(source,scenario):
    if scenario not in ('cold','after-reload'):
        raise ValueError('Unknown declared diagnostic scenario')
    tree=ast.parse(source)
    phases=[node for node in tree.body if isinstance(node,ast.Try) and any(isinstance(n,ast.ClassDef) and n.name=='ReloadHttp' for n in node.body)]
    if len(phases)!=1:raise ValueError('Selected visual source has no unique reload fixture phase')
    phase=phases[0]
    def assigns(node,name):
        return isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets)
    start=next(i for i,n in enumerate(phase.body) if assigns(n,'spec'))
    end=next(i for i,n in enumerate(phase.body) if assigns(n,'reload_checks'))
    setup=phase.body[start:end]
    assert any(isinstance(n,ast.ClassDef) and n.name=='ReloadHttp' for n in setup)
    functions=[n for n in phase.body if isinstance(n,ast.FunctionDef) and n.name in ('chrome_event','focus')]
    assert {n.name for n in functions}=={'chrome_event','focus'}
    workload=next(n for n in phase.body[end:] if isinstance(n,ast.Try))
    assert not workload.handlers and len(workload.finalbody)>=2
    if scenario=='after-reload':
        definitions=[n for n in phase.body[end:] if n is not workload and isinstance(n,(ast.Assign,ast.FunctionDef))]
        definitions=[n for n in definitions if not isinstance(n,ast.Assign) or all(isinstance(t,ast.Name) and t.id in ('reload_checks','reload_taps') for t in n.targets)]
        required={'reload_check','reload_command','reload_tap','reload_ready'}
        assert {n.name for n in definitions if isinstance(n,ast.FunctionDef)}==required
        nodes=functions+setup+definitions+[workload]
    else:
        body=workload.body
        collapse=next(i for i,n in enumerate(body) if isinstance(n,ast.ImportFrom) and n.module=='run_chrome_collapse')
        assert len(body[collapse:])==2
        nodes=functions+setup+[ast.Try(body=body[collapse:],handlers=[],orelse=[],finalbody=workload.finalbody)]
    return ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--adb',required=True);parser.add_argument('--serial',required=True)
    parser.add_argument('--scenario',required=True,choices=('cold','after-reload'))
    parser.add_argument('--out',required=True,type=pathlib.Path)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip())
    if dirty:raise ValueError('Focused Android diagnosis requires a clean selected source')
    package='local.pocketchat.test';integration=ROOT/'work/gecko-integration'
    def adb(*parts):return subprocess.check_output([args.adb,'-s',args.serial,*parts],timeout=90).decode(errors='replace')
    sys.path[:0]=[str(ROOT/'tests/gecko'),str(ROOT/'tools/gecko')]
    from diagnostic_capture_privacy import checked_text
    # Original collapse runner expects its APK under out/ui-current.apk. Keep the
    # immutable build there and use a separate diagnostic directory for evidence.
    apk=integration/'ui-current.apk'
    if not apk.is_file():raise ValueError('Restored selected-source UI APK is missing')
    original=ROOT/'tests/gecko/run_ui_visuals.py';program=selected_program(original.read_text(),args.scenario)
    inputs=['tests/gecko/run_ui_visuals.py','tests/gecko/run_chrome_collapse.py','tests/gecko/run_chrome_collapse_diagnostic.py','tests/gecko/ChromeCollapseIntegration.java','tools/gecko/chrome_collapse_contract.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs}
    namespace=dict(globals(),checked_text=checked_text,root=ROOT,out=integration,source=source,package=package,args=args,adb=adb,component=package+'/local.pocketchat.CompactChromeIntegrationActivity')
    report=dict(status='running',diagnosticOnly=True,releaseAcceptance=False,fullUiAcceptance=False,
        actualAndroidExecution=False,sourceCommit=source,sourceTree=tree,sourceFiles=hashes,scenario=args.scenario,
        earlierUiPreludeReplayed=False,originalReloadSequenceRequested=args.scenario=='after-reload',
        attempts=1,oracleChanged=False,deadlinesChanged=False)
    failure=None
    try:
        partials=('ui-reload-confirmation.json','ui-reload-log.txt','ui-collapse-server-trace.json')
        if any((integration/name).exists() for name in partials):raise ValueError('Pre-existing partial UI evidence cannot join a new diagnostic invocation')
        # Validate installed source/APK/SDK before either selected workload starts.
        from profile_invocation_contract import expected_build,verify_installed
        gradle=(ROOT/'app/build.gradle').read_text()
        identity=expected_build(apk,source,tree,re.search(r"versionName '([^']+)'",gradle).group(1),int(re.search(r'versionCode (\d+)',gradle).group(1)))
        verify_installed(json.loads(adb('exec-out','content','read','--uri','content://'+package+'.evidence/build-identity')),identity)
        report['buildIdentity']=identity;report['actualAndroidExecution']=True
        exec(compile(program,str(original)+':focused-unmodified-sections','exec'),namespace)
        from chrome_collapse_contract import verify_auto_collapse
        report['autoCollapse']=namespace['auto_collapse']
        report['collapseVerification']=verify_auto_collapse(report['autoCollapse'],source,identity['apkSha256'])
        report['status']='passed'
    except Exception as error:
        failure=error;report['status']='failed';report['error']=repr(error)
    finally:
        if 'reload_confirmation' in namespace:report['reloadConfirmation']=namespace['reload_confirmation']
        if 'reload_checks' in namespace:report['completedReloadChecks']=namespace['reload_checks']
        if 'reload_taps' in namespace:report['actualReloadTaps']=namespace['reload_taps']
        report['sourceInputsUnchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
        if not report['sourceInputsUnchanged']:
            report['status']='failed'
            if failure is None:failure=ValueError('Selected diagnostic source changed during execution');report['error']=repr(failure)
        if 'reload_loopback' in namespace:report['controlledServerEvents']=namespace['reload_loopback'].TRACE
        for name in ('ui-reload-confirmation.json','ui-reload-log.txt','ui-collapse-server-trace.json'):
            path=integration/name
            produced=('reload_confirmation' in namespace if name.startswith('ui-reload-') else 'reload_loopback' in namespace)
            if produced and path.is_file():
                (args.out/name).write_bytes(path.read_bytes())
        try:(args.out/'native-log.txt').write_text(checked_text(adb('logcat','-d'))[0])
        except Exception as error:report['nativeLogError']=type(error).__name__
        try:(args.out/'screen.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        except Exception as error:report['screenError']=type(error).__name__
        (args.out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        for parts in [('shell','settings','put','system','font_scale','1'),('shell','wm','size','reset'),('shell','wm','density','reset')]:
            try:adb(*parts)
            except Exception:pass
    if failure is not None:raise failure


if __name__=='__main__':main()
