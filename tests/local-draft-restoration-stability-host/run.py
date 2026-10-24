#!/usr/bin/env python3
"""Compile complete selected F04 methods, never a copied stability algorithm."""
import argparse, hashlib, importlib.util, json, os, pathlib, re, shutil, subprocess, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
FIXTURE=ROOT/'tests/gecko/GeckoLocalDraftIntegration.java'
NEW='if(!ready||stableSamples==0||document!=stableDocument)'
OLD='if(!ready||document!=stableDocument)'
SIGNATURES=['GeckoLocalDraftIntegration(GeckoIntegrationTestActivity activity,long command)',
    'boolean current(','void later(','String text(','void awaitRestored(boolean fresh)', 'static boolean sameCookies(']

def digest(raw):return hashlib.sha256(raw).hexdigest()

def select_methods(raw):
    spec=importlib.util.spec_from_file_location('f04_actual_member_extractor',ROOT/'tests/page-recovery-host/run.py')
    extractor=importlib.util.module_from_spec(spec);spec.loader.exec_module(extractor)
    return [extractor.member(raw,name) for name in SIGNATURES]

def verify_report(value,source,files,jar_sha,selected):
    """Selected-source host receipts only; counterfeit counts cannot qualify."""
    if (not isinstance(value,dict) or value.get('status')!='passed'
            or value.get('sourceCommit')!=source or value.get('sourceFiles')!=files
            or value.get('jsonJarSha256')!=jar_sha or value.get('selectedMembers')!=selected
            or value.get('oldAwaitRestoredSha256')!='6350f73e7922a795a39faf4a5e55e739e253ddff7bb2b6846aa8d5d57379cec8'
            or value.get('executionInputsUnchanged') is not True
            or value.get('actualAndroidExecution') is not False or value.get('actualGeckoExecution') is not False
            or value.get('actualFixtureMethodExecuted') is not True or value.get('releaseAcceptance') is not False):
        raise ValueError('F04 stability host source or execution scope differs')
    for name,count,status,variant in (('candidate',25,'passed','candidate'),('before',2,'reproduced-old-clock-gap','before-exact-inverse')):
        row=value.get(name)
        if (not isinstance(row,dict) or row.get('status')!=status or row.get('variant')!=variant
                or type(row.get('checkCount')) is not int or row['checkCount']!=count
                or not isinstance(row.get('checks'),list) or len(row['checks'])!=count
                or any(not isinstance(check,dict) or set(check)!={'name','pass'}
                    or not isinstance(check['name'],str) or not check['name'].strip() or check['pass'] is not True for check in row['checks'])
                or len({check['name'] for check in row['checks']})!=count
                or row.get('actualFixtureMethodExecuted') is not True
                or row.get('actualAndroidExecution') is not False or row.get('actualGeckoExecution') is not False
                or row.get('releaseAcceptance') is not False):
            raise ValueError('Incomplete exact F04 stability '+name+' controls')
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=pathlib.Path)
    parser.add_argument('--json-jar',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    inputs={FIXTURE,ROOT/'app/src/main/java/local/pocketchat/J.java',ROOT/'tests/page-recovery-host/run.py',*HERE.glob('*')}
    inputs={p for p in inputs if p.is_file()}
    hashes={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(inputs)}
    raw=FIXTURE.read_text();methods=select_methods(raw)
    complete='\n'.join(methods)
    if complete.count(NEW)!=1 or OLD in complete:raise ValueError('Exact unique reviewed clock reset required')
    before=complete.replace(NEW,OLD,1)
    old_method=select_methods(raw.replace(NEW,OLD,1))[4]
    if digest(old_method.encode())!='6350f73e7922a795a39faf4a5e55e739e253ddff7bb2b6846aa8d5d57379cec8':
        raise ValueError('Exact old full awaitRestored golden changed')
    constant=re.search(r'  static final String ACTION=[^;]+;',raw).group().strip()
    template=(HERE/'StabilityHost.java.in').read_text();variants={}
    java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
    if not java:raise ValueError('JDK17 required')
    for variant,selected in (('candidate',complete),('before',before)):
        with tempfile.TemporaryDirectory(prefix='f04-stability-'+variant+'-') as directory:
            tmp=pathlib.Path(directory);source=tmp/'local/pocketchat/StabilityHost.java';source.parent.mkdir(parents=True)
            source.write_text(template.replace('/* CONSTANTS */',constant).replace('/* METHODS */',selected))
            clock=tmp/'android/os/SystemClock.java';clock.parent.mkdir(parents=True)
            clock.write_text('package android.os; public final class SystemClock { public static long value; public static long elapsedRealtime(){return value;} }')
            compile_run=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',directory,str(source),str(clock),str(ROOT/'app/src/main/java/local/pocketchat/J.java')],capture_output=True,text=True)
            if compile_run.returncode:raise ValueError('Complete selected fixture compile failed: '+compile_run.stdout+compile_run.stderr)
            executed=subprocess.run([java,'-cp',directory+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.StabilityHost',variant],capture_output=True,text=True)
            value=json.loads(executed.stdout)
            wanted=25 if variant=='candidate' else 2
            if (executed.returncode or value.get('status')!=('passed' if variant=='candidate' else 'reproduced-old-clock-gap')
                    or value.get('checkCount')!=wanted or len(value.get('checks',[]))!=wanted
                    or len({row.get('name') for row in value['checks']})!=wanted
                    or not all(row.get('pass') is True for row in value['checks'])
                    or value.get('actualFixtureMethodExecuted') is not True
                    or value.get('actualAndroidExecution') is not False or value.get('actualGeckoExecution') is not False):
                raise ValueError('Incomplete actual fixture clock controls: '+executed.stdout+executed.stderr)
            value.update(compileStdout=compile_run.stdout,compileStderr=compile_run.stderr,runtimeStdout=executed.stdout,runtimeStderr=executed.stderr)
            variants[variant]=value
    unchanged=all(digest((ROOT/p).read_bytes())==h for p,h in hashes.items())
    report=dict(status='passed' if unchanged else 'source-changed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),sourceFiles=hashes,
        selectedMembers=[dict(signature=name,sha256=digest(method.encode())) for name,method in zip(SIGNATURES,methods)],
        oldAwaitRestoredSha256=digest(old_method.encode()),jsonJarSha256=digest(args.json_jar.read_bytes()),executionInputsUnchanged=unchanged,
        actualAndroidExecution=False,actualGeckoExecution=False,actualFixtureMethodExecuted=True,releaseAcceptance=False,
        scope='Complete selected fixture constructor/current/later/text/awaitRestored/sameCookies with controlled DOM, preferences, handler, monotonic clock and terminal callbacks. No Android/Gecko/SDK/disk/cookie/restart acceptance.',**variants)
    verify_report(report,report['sourceCommit'],hashes,report['jsonJarSha256'],report['selectedMembers'])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],candidateChecks=25,beforeChecks=2,actualAndroidExecution=False)))
    if not unchanged:raise SystemExit(1)

if __name__=='__main__':main()
