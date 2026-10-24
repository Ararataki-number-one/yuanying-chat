#!/usr/bin/env python3
"""Real Android production source/provider startup and guarded Gecko H2 route proof."""
import argparse
import hashlib
import json
import pathlib
import re
import select
import subprocess
import sys
import tempfile
import time
import uuid

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'work/gecko-integration'
PACKAGE='local.pocketchat.test'
PORT=9879
from run_gecko_pool import NODE as BASE_NODE
NODE=BASE_NODE.replace('port=9877','port=9879')
PAYLOAD='pool-payload-'*700
SUCCESS={'subscribed-a','subscribed-b','after-probes','restored-subscription','legacy-manual'}
FAILURE={'invalid-entry-snapshot-sha','invalid-exit-snapshot-sha','same-name-changed-exit','same-name-changed-entry'}


sys.path.insert(0,str(ROOT))
from tools.gecko.network_sources_contract import verify_source_route as verify
from tools.gecko.profile_invocation_contract import expected_build, verify_installed
from source_route_cleanup import RouteCleanupFence

def capture_logcat(adb_path, serial, filters=(), stem='network-source-route-logcat', check=True):
    """Preserve original log bytes; decoded text is diagnostic display only."""
    command=[adb_path,'-s',serial,'logcat','-d','-v','threadtime',*filters]
    def save(stdout, stderr, returncode, timed_out=False):
        streams={}
        for label, raw in (('stdout',stdout or b''),('stderr',stderr or b'')):
            (OUT/(stem+'-'+label+'.raw.log')).write_bytes(raw)
            invalid=None
            try:raw.decode('utf-8',errors='strict')
            except UnicodeDecodeError as error:invalid=dict(start=error.start,end=error.end,reason=error.reason)
            streams[label]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),invalidUtf8=invalid)
        display=(stdout or b'').decode('utf-8',errors='backslashreplace')
        (OUT/(stem+'-display.txt')).write_text(display,encoding='utf-8')
        (OUT/(stem+'-decode.json')).write_text(json.dumps(dict(schema=1,scope='Diagnostic display only; never structured acceptance evidence',encoding='utf-8',errors='backslashreplace',returncode=returncode,timedOut=timed_out,streams=streams),indent=2)+'\n',encoding='utf-8')
        return display
    try:result=subprocess.run(command,capture_output=True,timeout=30,check=False)
    except subprocess.TimeoutExpired as error:
        save(error.stdout,error.stderr,None,True)
        raise
    display=save(result.stdout,result.stderr,result.returncode)
    if check and result.returncode:raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
    return display


def save_failure_diagnostics(adb_path, serial, server_path):
    """Best effort collection must not replace the active runner exception."""
    failures=[]
    try:
        if server_path.exists():(OUT/'network-source-route-server-failure.json').write_bytes(server_path.read_bytes())
    except Exception as error:failures.append(dict(stage='server-copy',error=repr(error)))
    try:
        display=capture_logcat(adb_path,serial,stem='network-source-route-failure-logcat',check=False)
        (OUT/'network-source-route-failure-log.txt').write_text(display,encoding='utf-8')
    except Exception as error:failures.append(dict(stage='logcat',error=repr(error)))
    if failures:
        try:(OUT/'network-source-route-diagnostic-errors.json').write_text(json.dumps(dict(scope='Secondary diagnostic collection errors; original failure retained',errors=failures),indent=2)+'\n',encoding='utf-8')
        except Exception:pass


def prepare_cleanup_fence(args, source, run_nonce):
    """Reuse the existing source stamp/provider before launching this invocation."""
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip():
        raise ValueError('Source-route execution requires a clean committed source tree')
    settings=(ROOT/'app/build.gradle').read_text()
    version=re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",settings).group(1)
    code=int(re.search(r'versionCode ([0-9]+)',settings).group(1))
    expected=expected_build(args.apk.resolve(),source,tree,version,code)
    # The existing provider is used only before launch. Calling it after failure
    # could start a new process and would destroy the original PID observation.
    command=[args.adb,'-s',args.serial,'exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity']
    actual=subprocess.run(command,capture_output=True,timeout=30,check=False)
    (OUT/'network-source-route-prelaunch-identity.raw.json').write_bytes(actual.stdout)
    (OUT/'network-source-route-prelaunch-identity.stderr.raw.log').write_bytes(actual.stderr)
    if actual.returncode:raise subprocess.CalledProcessError(actual.returncode,command,output=actual.stdout,stderr=actual.stderr)
    installed=verify_installed(json.loads(actual.stdout.decode('utf-8',errors='strict')),expected)
    fence=RouteCleanupFence(args.adb,args.serial,source,run_nonce,installed,run=subprocess.run)
    fence.preflight()
    (OUT/'network-source-route-prelaunch.json').write_text(json.dumps(fence.receipt,indent=2)+'\n')
    return fence


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adb',required=True)
    parser.add_argument('--serial',default='emulator-5554');parser.add_argument('--timeout',type=int,default=420)
    parser.add_argument('--apk',type=pathlib.Path,default=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();run_nonce=uuid.uuid4().hex
    for name in ['network-source-route-results.json','network-source-route-log.txt','network-source-route-server.json',
                 'network-source-route-failure-log.txt','network-source-route-server-failure.json',
                 'network-source-route-server-cleanup-after.json','network-source-route-cleanup-diagnostic-errors.json',
                 'network-source-route-teardown-errors.json']:(OUT/name).unlink(missing_ok=True)
    for stem in ('network-source-route-logcat','network-source-route-failure-logcat','network-source-route-cleanup-logcat'):
        for suffix in ('-stdout.raw.log','-stderr.raw.log','-display.txt','-decode.json'):(OUT/(stem+suffix)).unlink(missing_ok=True)
    (OUT/'network-source-route-diagnostic-errors.json').unlink(missing_ok=True)
    for name in ('network-source-route-cleanup.json','network-source-route-prelaunch.json',
                 'network-source-route-prelaunch-identity.raw.json','network-source-route-prelaunch-identity.stderr.raw.log'):
        (OUT/name).unlink(missing_ok=True)
    def adb(*parts,check=True):
        result=subprocess.run([args.adb,'-s',args.serial,*parts],text=True,capture_output=True,timeout=30,check=check);return result.stdout
    def log():return capture_logcat(args.adb,args.serial,('-s','PocketNetworkSourceRoute:I','AndroidRuntime:E','*:S'))
    try:fence=prepare_cleanup_fence(args,source,run_nonce)
    except BaseException as error:
        # Preflight cannot authorize a stop, including when the existing identity
        # provider itself could not be verified. Keep the original exception.
        try:(OUT/'network-source-route-cleanup.json').write_text(json.dumps(dict(schema=1,
            status='cleanupUnknown',package=PACKAGE,serial=args.serial,sourceCommit=source,
            runNonce=run_nonce,stage='prelaunch',reason=repr(error),forceStopAttempted=False,
            fixtureResultChanged=False,nativeOperationCancelled=False),indent=2)+'\n')
        except Exception:pass
        raise
    with tempfile.TemporaryDirectory(prefix='pocket-source-route-') as temporary:
        d=pathlib.Path(temporary)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','1','-subj','/CN=127.0.0.1',
                        '-addext','subjectAltName=IP:127.0.0.1','-keyout',str(d/'key.pem'),'-out',str(d/'cert.pem')],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        (d/'fixture.js').write_text(NODE);process=subprocess.Popen(['node',str(d/'fixture.js'),str(d/'key.pem'),str(d/'cert.pem'),str(d/'server.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        failed=False;passed_result=None
        try:
            ready,_,_=select.select([process.stdout],[],[],10);assert ready and json.loads(process.stdout.readline())=={'ready':True,'port':PORT,'protocol':'h2'}
            adb('reverse','tcp:'+str(PORT),'tcp:'+str(PORT));adb('shell','am','force-stop',PACKAGE);adb('shell','pm','clear',PACKAGE);adb('logcat','-c')
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.NetworkSourcesRouteIntegrationActivity','--es','sourceCommit',source,'--es','runNonce',run_nonce)
            deadline=time.monotonic()+args.timeout;report=None
            while time.monotonic()<deadline:
                raw=log()
                fence.poll((OUT/'network-source-route-logcat-stdout.raw.log').read_bytes())
                if 'FATAL EXCEPTION' in raw:raise AssertionError(raw)
                if any('PocketNetworkSourceRoute' in line and '"kind":"complete"' in line for line in raw.splitlines()):
                    value=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/network-source-route')
                    report=json.loads(value);break
                time.sleep(1)
            if report is None:raise TimeoutError('No completed actual Android source route report')
            report['runnerInvocation']={'sourceCommit':source,'runNonce':run_nonce}
            report['androidSdk']=int(adb('shell','getprop','ro.build.version.sdk').strip());server=json.loads((d/'server.json').read_text());report['server']=server
            (OUT/'network-source-route-results.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'network-source-route-log.txt').write_text(raw)
            (OUT/'network-source-route-server.json').write_text(json.dumps(server,indent=2)+'\n')
            assert report.get('sourceCommit')==source
            assert isinstance(report.get('buildIdentity'),dict) and report['buildIdentity'].get('sourceCommit')==source
            assert report.get('runNonce')==run_nonce
            receipt=json.loads((ROOT/'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text());result=verify(report,server,receipt,source)
            passed_result={'status':'passed','sourceCommit':source,**result}
        except BaseException:
            failed=True
            save_failure_diagnostics(args.adb,args.serial,d/'server.json')
            raise
        finally:
            teardown_errors=[]
            def teardown_step(stage, action):
                """Every teardown action is bounded and cannot replace a primary failure."""
                try:return True,action()
                except BaseException as error:
                    teardown_errors.append(dict(stage=stage,errorType=type(error).__name__,error=repr(error)))
                    return False,None
            def final_snapshot():
                capture_logcat(args.adb,args.serial,stem='network-source-route-cleanup-logcat',check=False)
                return (OUT/'network-source-route-cleanup-logcat-stdout.raw.log').read_bytes()
            # Preserve the failed original streams/server before any final stop.
            observed,evidence_saved=teardown_step('saved-evidence-inspection',lambda:
                (OUT/('network-source-route-server-failure.json' if failed else 'network-source-route-server.json')).is_file()
                and all((OUT/('network-source-route-logcat-'+label+'.raw.log')).is_file() for label in ('stdout','stderr')))
            cleanup=dict(status='cleanupUnknown',forceStopAttempted=None,fixtureResultChanged=False,nativeOperationCancelled=False)
            def cleanup_package():
                value=fence.cleanup(final_snapshot,observed and evidence_saved)
                if not isinstance(value,dict) or value.get('status') not in ('cleaned','cleanupUnknown'):
                    raise ValueError('Package cleanup returned no valid identity-bound receipt')
                return value
            package_ok,package_receipt=teardown_step('package-cleanup',cleanup_package)
            if package_ok:cleanup=package_receipt
            cleanup['runnerFailed']=failed
            # Preserve the server's currently persisted bytes after the stop
            # attempt, before terminating Node. Late contacts may be absent from
            # the earlier failure copy; neither snapshot is a full network cut.
            def server_after_cleanup():
                late_server=(d/'server.json').read_bytes()
                (OUT/'network-source-route-server-cleanup-after.json').write_bytes(late_server)
                cleanup['serverAfterCleanupSnapshot']=dict(scope='Diagnostic current server bytes after cleanup attempt; not a complete network cutoff',
                    bytes=len(late_server),sha256=hashlib.sha256(late_server).hexdigest())
            server_ok,_=teardown_step('server-after-cleanup-snapshot',server_after_cleanup)
            if not server_ok:
                teardown_step('server-after-cleanup-error-record',lambda:
                    (OUT/'network-source-route-cleanup-diagnostic-errors.json').write_text(json.dumps(dict(
                        scope='Secondary server-after-cleanup diagnostic error; original result retained',
                        error=teardown_errors[-1]),indent=2)+'\n'))
            reverse_ok,_=teardown_step('reverse-remove',lambda:adb('reverse','--remove','tcp:'+str(PORT)))
            terminate_ok,_=teardown_step('node-terminate',process.terminate)
            node_exited,_=teardown_step('node-communicate',lambda:process.communicate(timeout=5))
            kill_ok=None
            if not node_exited:
                kill_ok,_=teardown_step('node-kill',process.kill)
                node_exited,_=teardown_step('node-communicate-after-kill',lambda:process.communicate(timeout=5))
            cleanup['teardown']=dict(reverseRemoved=reverse_ok,nodeTerminateReturned=terminate_ok,
                nodeKillReturned=kill_ok,nodeExitConfirmed=node_exited,errors=teardown_errors)
            if not reverse_ok or not node_exited:cleanup['status']='cleanupUnknown'
            receipt_saved,_=teardown_step('cleanup-receipt-write',lambda:
                (OUT/'network-source-route-cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n'))
            if not receipt_saved:cleanup['status']='cleanupUnknown'
            if teardown_errors:
                teardown_step('teardown-error-record',lambda:
                    (OUT/'network-source-route-teardown-errors.json').write_text(json.dumps(dict(
                        scope='Independent teardown observations; original result retained',
                        status=cleanup['status'],runnerFailed=failed,errors=teardown_errors),indent=2)+'\n'))
            if not failed and cleanup['status']!='cleaned':raise RuntimeError('Source-route cleanupUnknown; no further invocation is qualified')
        if passed_result is not None:print(json.dumps(passed_result),flush=True)


if __name__=='__main__':main()
