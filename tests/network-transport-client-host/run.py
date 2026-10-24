#!/usr/bin/env python3
"""Execute the full production Client against explicit, controlled Android API adapters."""
import argparse, hashlib, json, pathlib, re, shutil, subprocess, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PRODUCTION='app/src/main/java/local/pocketchat/NetworkTransportClient.java'
BEFORE='3eac2891438d37aa62f695b34a90f0aa02215ca2'
KNOWN_OLD_FAILURES={
    'Null binding releases framework binding exactly once',
    'Null binding retires bound state',
    'Next explicit demand performs a new bind after null',
    'Disconnect releases the already captured gate',
    'Binding death releases captured gate',
    'Retired onServiceConnected cannot replace new target',
    'Old reply endpoint cannot publish stale pushed state',
    'Synchronous connected callback does not expose unaccepted binder',
}
CASE_NAMES={'null lifecycle','disconnect during bind wait','binding death','stale callbacks',
            'pending requests and reply epochs','terminal pending requests','false and exceptional binds',
            'synchronous callbacks','detach fencing','normal call and errors','interruptions',
            'real reply timeout and duplicate completion'}
EXPECTED_CHECK_COUNT=74

def sha(raw):return hashlib.sha256(raw).hexdigest()

def verify_report(value,*,expect_pass):
    if not isinstance(value,dict) or set(value)!={'status','checkCount','failedCount','checks','cases','replyTimeoutObservation','actualAndroidExecution','actualBinderExecution','actualServiceExecution'}:
        raise ValueError('Incomplete lifecycle report structure')
    if (type(value['checkCount']) is not int or value['checkCount']!=EXPECTED_CHECK_COUNT
            or type(value['failedCount']) is not int or not isinstance(value['checks'],list)
            or len(value['checks'])!=EXPECTED_CHECK_COUNT or not isinstance(value['cases'],list)
            or len(value['cases'])!=len(CASE_NAMES)
            or any(value[key] is not False for key in ('actualAndroidExecution','actualBinderExecution','actualServiceExecution'))):
        raise ValueError('Lifecycle count or execution scope differs')
    names=[];failed=[]
    for row in value['checks']:
        if (not isinstance(row,dict) or set(row)!={'name','pass'} or not isinstance(row['name'],str)
                or not row['name'].strip() or type(row['pass']) is not bool):
            raise ValueError('Missing lifecycle check or nonboolean outcome')
        names.append(row['name'])
        if row['pass'] is False:failed.append(row['name'])
    if len(set(names))!=EXPECTED_CHECK_COUNT or len(failed)!=value['failedCount']:
        raise ValueError('Duplicate check or inconsistent failure count')
    case_names=[]
    for row in value['cases']:
        if (not isinstance(row,dict) or set(row)!={'case','failedChecks'} or row['case'] not in CASE_NAMES
                or type(row['failedChecks']) is not int or row['failedChecks']<0):
            raise ValueError('Lifecycle case missing or incomplete')
        case_names.append(row['case'])
    if set(case_names)!=CASE_NAMES or sum(row['failedChecks'] for row in value['cases'])!=len(failed):
        raise ValueError('Lifecycle cases do not cover the complete checks')
    timeout=value['replyTimeoutObservation']
    if (not isinstance(timeout,dict) or set(timeout)!={'configuredTimeoutSeconds','observedElapsedNanos','exceptionClass','requestId'}
            or type(timeout['configuredTimeoutSeconds']) is not int or timeout['configuredTimeoutSeconds']!=15
            or type(timeout['observedElapsedNanos']) is not int or timeout['observedElapsedNanos']<14900000000
            or timeout['exceptionClass']!='java.util.concurrent.TimeoutException'
            or not isinstance(timeout['requestId'],str) or re.fullmatch('[0-9a-f-]{36}',timeout['requestId']) is None):
        raise ValueError('Real unchanged fifteen second reply timeout was not observed')
    if expect_pass:
        if value['status']!='passed' or failed:raise ValueError('Candidate lifecycle check failed')
    elif value['status']!='failed' or not KNOWN_OLD_FAILURES<=set(failed):
        raise ValueError('Immutable before-source failures were not reproduced')
    return value

def verify_raw_run(record):
    keys={'rawCompileStdout','rawCompileStderr','rawStdout','rawStderr'}
    metadata=record.get('rawStreamMetadata')
    if not isinstance(metadata,dict) or set(metadata)!=keys:
        raise ValueError('Raw lifecycle stream metadata is incomplete')
    for key in keys:
        raw=record.get(key)
        if not isinstance(raw,str):raise ValueError('Raw lifecycle stream is absent')
        data=raw.encode('utf-8');proof=metadata[key]
        if (not isinstance(proof,dict) or set(proof)!={'utf8Bytes','sha256'}
                or type(proof['utf8Bytes']) is not int or proof['utf8Bytes']!=len(data)
                or proof['sha256']!=sha(data)):
            raise ValueError('Raw lifecycle stream byte/SHA binding differs')
    if json.loads(record['rawStdout'])!=record.get('report'):
        raise ValueError('Parsed lifecycle report differs from actual stdout')
    if (type(record.get('compileExitCode')) is not int or record['compileExitCode']!=0
            or type(record.get('exitCode')) is not int or record.get('name') not in ('before','current')
            or not isinstance(record.get('sourceCommit'),str) or re.fullmatch('[0-9a-f]{40}',record['sourceCommit']) is None
            or not isinstance(record.get('clientSha256'),str) or re.fullmatch('[0-9a-f]{64}',record['clientSha256']) is None):
        raise ValueError('Full production Client did not compile')
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=pathlib.Path)
    parser.add_argument('--json-jar',required=True,type=pathlib.Path)
    parser.add_argument('--output',required=True,type=pathlib.Path)
    parser.add_argument('--before-ref',default=BEFORE)
    args=parser.parse_args()
    args.output=args.output.resolve()
    if re.fullmatch('[0-9a-f]{40}',args.before_ref) is None:parser.error('Full immutable before ref required')
    def git(*parts):return subprocess.check_output(['git',*parts],cwd=ROOT,text=True).strip()
    inputs={ROOT/PRODUCTION,ROOT/'app/src/main/java/local/pocketchat/J.java'}|{p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py','.java','.md')}
    before=dict(sourceCommit=git('rev-parse','HEAD'),sourceTree=git('rev-parse','HEAD^{tree}'),sourceDirty=bool(git('status','--porcelain')),
                sourceFiles={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(inputs)})
    baseline=subprocess.check_output(['git','show',args.before_ref+':'+PRODUCTION],cwd=ROOT)
    baseline_json=subprocess.check_output(['git','show',args.before_ref+':app/src/main/java/local/pocketchat/J.java'],cwd=ROOT)
    if baseline_json!=(ROOT/'app/src/main/java/local/pocketchat/J.java').read_bytes():
        raise ValueError('The shared whole J helper changed from the immutable comparison source')
    jar=args.json_jar.resolve();args.output.parent.mkdir(parents=True,exist_ok=True)
    run_dir=args.output.parent/(args.output.stem+'-raw');run_dir.mkdir(exist_ok=True)
    (run_dir/'before-NetworkTransportClient.java').write_bytes(baseline)
    (run_dir/'current-NetworkTransportClient.java').write_bytes((ROOT/PRODUCTION).read_bytes())
    javac=str(args.java_home/'bin/javac') if args.java_home else shutil.which('javac')
    java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
    if not javac or not java:parser.error('JDK17 required')
    records=[]
    for name,client in [('before',baseline),('current',(ROOT/PRODUCTION).read_bytes())]:
        with tempfile.TemporaryDirectory(prefix='network-client-host-') as temp_name:
            temp=pathlib.Path(temp_name);package=temp/'local/pocketchat';package.mkdir(parents=True)
            selected=package/'NetworkTransportClient.java';selected.write_bytes(client)
            classes=temp/'classes';classes.mkdir()
            sources=[selected,ROOT/'app/src/main/java/local/pocketchat/J.java',HERE/'NetworkTransportClientHost.java',*sorted((HERE/'adapters').rglob('*.java'))]
            command=[javac,'-encoding','UTF-8','-cp',str(jar),'-d',str(classes),*map(str,sources)]
            compile_run=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=30)
            (run_dir/(name+'-compile-stdout.log')).write_bytes(compile_run.stdout)
            (run_dir/(name+'-compile-stderr.log')).write_bytes(compile_run.stderr)
            if compile_run.returncode:raise RuntimeError(name+' compile failed: '+compile_run.stderr.decode())
            execute=subprocess.run([java,'-cp',str(classes)+':'+str(jar),'local.pocketchat.NetworkTransportClientHost'],cwd=ROOT,capture_output=True,timeout=45)
            (run_dir/(name+'-stdout.log')).write_bytes(execute.stdout);(run_dir/(name+'-stderr.log')).write_bytes(execute.stderr)
            report=json.loads(execute.stdout)
            (run_dir/(name+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            streams={'rawCompileStdout':compile_run.stdout,'rawCompileStderr':compile_run.stderr,
                     'rawStdout':execute.stdout,'rawStderr':execute.stderr}
            record=dict(name=name,sourceCommit=args.before_ref if name=='before' else before['sourceCommit'],clientSha256=sha(client),
                        compileExitCode=compile_run.returncode,exitCode=execute.returncode,report=report,
                        rawStreamMetadata={key:dict(utf8Bytes=len(value),sha256=sha(value)) for key,value in streams.items()})
            record.update({key:value.decode('utf-8') for key,value in streams.items()})
            verify_raw_run(record);records.append(record)
    observed={row['name'] for row in records[0]['report']['checks'] if row['pass'] is False}
    validation_errors=[]
    try:verify_report(records[0]['report'],expect_pass=False)
    except ValueError as error:validation_errors.append('before: '+str(error))
    old_reproduced=records[0]['exitCode']!=0 and not validation_errors and KNOWN_OLD_FAILURES<=observed
    current=records[1]['report']
    try:verify_report(current,expect_pass=True)
    except ValueError as error:validation_errors.append('current: '+str(error))
    passed=records[1]['exitCode']==0 and not any(error.startswith('current: ') for error in validation_errors)
    unchanged=(before['sourceCommit']==git('rev-parse','HEAD') and all(p.is_file() and sha(p.read_bytes())==before['sourceFiles'][str(p.relative_to(ROOT))] for p in inputs))
    result=dict(schema=1,status='passed' if passed and old_reproduced and unchanged else 'failed',sourceIdentity=before,
        beforeRef=args.before_ref,beforeFailuresRequired=sorted(KNOWN_OLD_FAILURES),oldFailuresReproduced=old_reproduced,
        executionInputsUnchanged=unchanged,actualAndroidExecution=False,actualBinderExecution=False,actualServiceExecution=False,
        scope='Complete unchanged production NetworkTransportClient and J compiled directly. Context/ServiceConnection/main Looper queue/Messenger Binder endpoints/diagnostics are explicit host adapters. Synthetic callback ordering and in-process threads only, no Android lifecycle or user-device root cause acceptance.',
        passed=current['checkCount'] if passed else 0,runs=records,jsonJarSha256=sha(jar.read_bytes()),
        fullSelectedClass=True,beforeClientSha256=sha(baseline),sharedWholeJsonHelperSha256=sha(baseline_json),validationErrors=validation_errors,
        rawEvidence={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(run_dir.iterdir()) if p.is_file()})
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],passed=result['passed'],oldFailuresReproduced=old_reproduced,executionInputsUnchanged=unchanged,output=str(args.output))))
    if result['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
