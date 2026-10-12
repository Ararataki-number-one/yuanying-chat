#!/usr/bin/env python3
"""Real Android production source/provider startup and guarded Gecko H2 route proof."""
import argparse
import hashlib
import json
import pathlib
import select
import subprocess
import sys
import tempfile
import time

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

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adb',required=True)
    parser.add_argument('--serial',default='emulator-5554');parser.add_argument('--timeout',type=int,default=420);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ['network-source-route-results.json','network-source-route-log.txt','network-source-route-server.json',
                 'network-source-route-failure-log.txt','network-source-route-server-failure.json']:(OUT/name).unlink(missing_ok=True)
    def adb(*parts,check=True):
        result=subprocess.run([args.adb,'-s',args.serial,*parts],text=True,capture_output=True,timeout=30,check=check);return result.stdout
    def log():return adb('logcat','-d','-s','PocketNetworkSourceRoute:I','AndroidRuntime:E','*:S')
    with tempfile.TemporaryDirectory(prefix='pocket-source-route-') as temporary:
        d=pathlib.Path(temporary)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','1','-subj','/CN=127.0.0.1',
                        '-addext','subjectAltName=IP:127.0.0.1','-keyout',str(d/'key.pem'),'-out',str(d/'cert.pem')],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        (d/'fixture.js').write_text(NODE);process=subprocess.Popen(['node',str(d/'fixture.js'),str(d/'key.pem'),str(d/'cert.pem'),str(d/'server.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            ready,_,_=select.select([process.stdout],[],[],10);assert ready and json.loads(process.stdout.readline())=={'ready':True,'port':PORT,'protocol':'h2'}
            adb('reverse','tcp:'+str(PORT),'tcp:'+str(PORT));adb('shell','am','force-stop',PACKAGE);adb('shell','pm','clear',PACKAGE);adb('logcat','-c')
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.NetworkSourcesRouteIntegrationActivity')
            deadline=time.monotonic()+args.timeout;report=None
            while time.monotonic()<deadline:
                raw=log()
                if 'FATAL EXCEPTION' in raw:raise AssertionError(raw)
                if any('PocketNetworkSourceRoute' in line and '"kind":"complete"' in line for line in raw.splitlines()):
                    value=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/network-source-route');report=json.loads(value);break
                time.sleep(1)
            if report is None:raise TimeoutError('No completed actual Android source route report')
            source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();report['sourceCommit']=source
            report['androidSdk']=int(adb('shell','getprop','ro.build.version.sdk').strip());server=json.loads((d/'server.json').read_text());report['server']=server
            (OUT/'network-source-route-results.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'network-source-route-log.txt').write_text(raw)
            (OUT/'network-source-route-server.json').write_text(json.dumps(server,indent=2)+'\n')
            receipt=json.loads((ROOT/'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text());result=verify(report,server,receipt,source)
            print(json.dumps({'status':'passed','sourceCommit':source,**result}),flush=True)
        except BaseException:
            (OUT/'network-source-route-failure-log.txt').write_text(adb('logcat','-d',check=False))
            if (d/'server.json').exists():(OUT/'network-source-route-server-failure.json').write_bytes((d/'server.json').read_bytes())
            raise
        finally:
            adb('shell','am','force-stop',PACKAGE,check=False);adb('reverse','--remove','tcp:'+str(PORT),check=False);process.terminate()
            try:process.communicate(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.communicate()


if __name__=='__main__':main()
