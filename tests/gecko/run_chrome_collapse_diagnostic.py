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
import os
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


def collect_v2_diagnostics(integration,destination,source,identity):
    """Copy only this invocation's nonce-bound originals, never a passed oracle."""
    candidates={path.name:path for path in integration.glob('chrome-v2-*')}
    if not candidates:return []
    from chrome_collapse_contract_v2 import UI_PHASES
    phases='(?:'+'|'.join(sorted(UI_PHASES))+')'
    partials=[path for name,path in candidates.items() if re.fullmatch(r'chrome-v2-[0-9a-f]{32}-partial\.json',name)]
    if not 1<=len(partials)<=3:raise ValueError('Missing or excessive owned v2 diagnostic cases')
    selected={};cohorts=set()
    def original(path):
        if path.is_symlink() or not path.is_file():raise ValueError('V2 diagnostic must be a regular original file')
        return path.read_bytes()
    def include(metadata,pattern):
        name=metadata['name']
        if type(name) is not str or re.fullmatch(pattern,name) is None:
            raise ValueError('Unowned v2 diagnostic path')
        if name in selected or name not in candidates:raise ValueError('Duplicate or missing v2 diagnostic file')
        raw=original(candidates[name])
        if type(metadata['bytes']) is not int or metadata['bytes']!=len(raw) or metadata['sha256']!=hashlib.sha256(raw).hexdigest():
            raise ValueError('V2 diagnostic original bytes changed')
        selected[name]=raw
        return raw
    for path in sorted(partials):
        raw=original(path);value=json.loads(raw);nonce=path.name[len('chrome-v2-'):-len('-partial.json')]
        if (type(value.get('schema')) is not int or value['schema']!=1 or type(value.get('navigationContract')) is not int or value['navigationContract']!=2
            or value.get('runNonce')!=nonce or value.get('sourceCommit')!=source or value.get('sourceTree')!=identity['sourceTree']
            or value.get('buildIdentity')!=identity or value.get('diagnosticOnly') is not True or value.get('releaseAcceptance') is not False
            or type(value.get('caseCompleted')) is not bool):
            raise ValueError('V2 diagnostic belongs to another source, APK or invocation')
        cohort=(value.get('viewport'),value.get('fontScale'))
        if any(type(n) is not int for n in cohort) or cohort not in ((360,1),(412,1),(360,2)) or cohort in cohorts:raise ValueError('Duplicate or undeclared v2 diagnostic cohort')
        cohorts.add(cohort)
        if value['eventTransfer']['runNonce']!=nonce or value['eventTransfer']['fixtureAction']!='chromeCollapse' or type(value['eventTransfer']['processSlot']) is not int or value['eventTransfer']['processSlot']!=0:
            raise ValueError('V2 partial events belong to another invocation')
        for row in value['eventTransfer']['events']:
            receipt=row['receipt'];payload=row['rawUtf8'].encode('utf-8');envelope=json.loads(payload)
            if (receipt['runNonce']!=nonce or receipt['fixtureAction']!='chromeCollapse' or receipt['processSlot']!=0
                or envelope['runNonce']!=nonce or envelope['sourceCommit']!=source or envelope['buildIdentity']!=identity
                or len(payload)!=receipt['payloadBytes'] or hashlib.sha256(payload).hexdigest()!=receipt['payloadSha256']):
                raise ValueError('V2 original event payload belongs to another invocation or changed bytes')
        if any(item['runNonce']!=nonce or item['sourceCommit']!=source for item in value['nativeUi'].values()):
            raise ValueError('V2 native UI belongs to another invocation')
        if not re.fullmatch('[0-9a-f]{32}',value['captureRunNonce']):raise ValueError('Missing v2 acquisition nonce')
        if type(value['captureAttemptCount']) is not int or value['captureAttemptCount']<0:raise ValueError('Missing actual v2 acquisition count')
        if value['captureFile'] is None:
            if ('chrome-v2-ui-capture-'+nonce+'.json') in candidates or not isinstance(value.get('captureError'),str) or not value['captureError']:
                raise ValueError('Missing v2 capture must retain its actual absence')
            if value['captureStatus']=='not-started':
                if value['captureAttemptCount']!=0 or value['uiAttempts'] or value['rawFiles'] or value['nativeUi'] or value['caseCompleted']:
                    raise ValueError('V2 acquisition was already started')
            elif value['captureStatus']!='missing' or value['captureAttemptCount']==0:
                raise ValueError('Unrecognized missing v2 capture')
        else:
            if value['captureStatus']!='available':raise ValueError('V2 original capture availability differs')
            capture=include(value['captureFile'],'chrome-v2-ui-capture-'+nonce+r'\.json')
            capture_value=json.loads(capture)
            if capture_value['sourceCommit']!=source or capture_value['runNonce']!=value['captureRunNonce'] or capture_value['attemptCount']!=value['captureAttemptCount']:
                raise ValueError('V2 capture belongs to another source or acquisition')
        for metadata in value['rawFiles']:
            include(metadata,'chrome-v2-'+nonce+'-'+phases+r'-attempt-[1-9][0-9]*\.(?:xml|activity\.txt)')
        selected[path.name]=raw
    if set(selected)!=set(candidates):raise ValueError('Unexpected or unowned v2 diagnostic files')
    if any((destination/name).exists() or (destination/name).is_symlink() for name in selected):
        raise ValueError('Pre-existing v2 destination cannot be overwritten')
    records=[]
    for name,raw in sorted(selected.items()):
        with (destination/name).open('xb') as stream:stream.write(raw)
        records.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    return records


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
    inputs=['tests/gecko/run_ui_visuals.py','tests/gecko/run_chrome_collapse.py','tests/gecko/run_chrome_collapse_diagnostic.py','tests/gecko/ChromeCollapseIntegration.java','tools/gecko/chrome_collapse_contract.py',
        'tests/gecko/run_chrome_collapse_v2.py','tools/gecko/chrome_collapse_contract_v2.py',
        'tools/gecko/workspace_navigation_contract.py','tools/gecko/compact_chrome_layout_v2.py','tools/gecko/ui_visual_capture.py',
        'tests/gecko/CompactChromeIntegrationActivity.java','tests/gecko/ReloadWindowCallbackObservation.java',
        'tools/gecko/ui_test_device.py','tests/gecko/ui_settings_services_device11.py']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs}
    namespace=dict(globals(),checked_text=checked_text,root=ROOT,out=integration,source=source,package=package,args=args,adb=adb,component=package+'/local.pocketchat.CompactChromeIntegrationActivity')
    report=dict(status='running',diagnosticOnly=True,releaseAcceptance=False,fullUiAcceptance=False,
        actualAndroidExecution=False,sourceCommit=source,sourceTree=tree,sourceFiles=hashes,scenario=args.scenario,
        earlierUiPreludeReplayed=False,originalReloadSequenceRequested=args.scenario=='after-reload',
        attempts=1,oracleChanged=False,deadlinesChanged=False,rootCauseEstablished=False,sourceInputsUnchanged=False)
    failure=None;settings_services_device11=None;v2_started=False
    try:
        partials=('ui-reload-confirmation.json','ui-reload-log.txt','ui-collapse-server-trace.json')
        if any((integration/name).exists() for name in partials):raise ValueError('Pre-existing partial UI evidence cannot join a new diagnostic invocation')
        if any(integration.glob('chrome-v2-*')):raise ValueError('Pre-existing v2 evidence cannot join a new diagnostic invocation')
        # Validate installed source/APK/SDK before either selected workload starts.
        from profile_invocation_contract import expected_build,verify_installed
        gradle=(ROOT/'app/build.gradle').read_text()
        identity=expected_build(apk,source,tree,re.search(r"versionName '([^']+)'",gradle).group(1),int(re.search(r'versionCode (\d+)',gradle).group(1)))
        verify_installed(json.loads(adb('exec-out','content','read','--uri','content://'+package+'.evidence/build-identity')),identity)
        report['buildIdentity']=identity;report['actualAndroidExecution']=True
        # Reuse the complete UI invocation's device preconditions, not its earlier
        # workload. This setup alignment does not establish a prior failure cause.
        from ui_test_device import prepare_workflow as prepare_ui_test_device
        report['deviceIsolation']=prepare_ui_test_device(adb,serial=args.serial,environment=os.environ)
        (args.out/'ui-test-device-isolation.json').write_text(json.dumps(report['deviceIsolation'],sort_keys=True,indent=2)+'\n')
        from ui_settings_services_device11 import prepare_workflow as prepare_settings_services_device11, finish_workflow as finish_settings_services_device11
        settings_services_device11=prepare_settings_services_device11(adb,serial=args.serial,environment=os.environ,root=ROOT,source=source,record_path=args.out/'ui-settings-services-isolation.json')
        v2_started=True
        exec(compile(program,str(original)+':focused-unmodified-sections','exec'),namespace)
        from chrome_collapse_contract import verify_auto_collapse
        report['autoCollapse']=namespace['auto_collapse']
        report['collapseVerification']=verify_auto_collapse(report['autoCollapse'],source,identity['apkSha256'])
        report['status']='passed'
    except Exception as error:
        failure=error;report['status']='failed';report['error']=repr(error)
    finally:
        try:
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
            if v2_started:
                try:report['v2DiagnosticFiles']=collect_v2_diagnostics(integration,args.out,source,identity)
                except Exception as error:
                    report.update(status='failed',v2DiagnosticCollectionError=repr(error))
                    if failure is None:failure=error;report['error']=repr(error)
            try:(args.out/'native-log.txt').write_text(checked_text(adb('logcat','-d'))[0])
            except Exception as error:report['nativeLogError']=type(error).__name__
            try:(args.out/'screen.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
            except Exception as error:report['screenError']=type(error).__name__
        except Exception as error:
            report.update(status='failed',diagnosticCollectionError=repr(error))
            if failure is None:failure=error;report['error']=repr(error)
        finally:
            # No diagnostic read/write may skip restoration of an acquired lease.
            try:
                if settings_services_device11 is not None:
                    finish_settings_services_device11(settings_services_device11,report)
            except Exception as error:
                report.update(status='failed',deviceRestorationError=repr(error))
                if failure is None:failure=error;report['error']=repr(error)
            finally:
                try:
                    record=args.out/'ui-settings-services-isolation.json'
                    if record.is_file():
                        value=json.loads(record.read_text())
                        report['settingsServicesIsolation']=dict(recordFile=record.name,recordSha256=hashlib.sha256(record.read_bytes()).hexdigest(),
                            status=value.get('status'),mutationAttempted=value.get('mutationAttempted'),restorationVerified=value.get('restorationVerified'))
                except Exception as error:
                    report.update(status='failed',deviceRecordError=repr(error))
                    if failure is None:failure=error;report['error']=repr(error)
                try:(args.out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                except Exception as error:
                    report['status']='failed'
                    if failure is None:failure=error
                finally:
                    for parts in [('shell','settings','put','system','font_scale','1'),('shell','wm','size','reset'),('shell','wm','density','reset')]:
                        try:adb(*parts)
                        except Exception:pass
    if failure is not None:raise failure


if __name__=='__main__':main()
