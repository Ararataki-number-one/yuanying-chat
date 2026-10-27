"""Run real native protection state/controller code at synthetic SDK boundaries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
VIEW=ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java'
POLICY=ROOT/'app/src/main/java/local/pocketchat/NativeProtectionState.java'
TEMPLATE=ROOT/'tests/native-protection-host/NativeProtectionControllerHost.java.in'
BACKGROUND=ROOT/'app/src/main/assets/gecko/background.js'
SCRIPT=ROOT/'tests/browser-runtime/native-protection-handshake.test.cjs'
IDENTITY=ROOT/'app/src/main/java/local/pocketchat/RequestIdentityAudit.java'

def body(text,start):
    opened=text.index('{',start);depth=0;mode='code';quote='';i=opened
    while i<len(text):
        c=text[i];n=text[i+1:i+2]
        if mode=='line':
            if c=='\n':mode='code'
        elif mode=='comment':
            if c=='*' and n=='/':mode='code';i+=1
        elif mode=='string':
            if c=='\\':i+=1
            elif c==quote:mode='code'
        elif c=='/' and n=='/':mode='line';i+=1
        elif c=='/' and n=='*':mode='comment';i+=1
        elif c in ('"',"'"):mode='string';quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[opened:i+1]
        i+=1
    raise AssertionError('Unterminated production Java member')

def member(text,signature):
    start=text.index(signature)
    return signature+body(text,start)

def execute():
    source=VIEW.read_text()
    identity=IDENTITY.read_text();constant_start=identity.index('static final String PATH=')
    identity_policy=identity[constant_start:identity.index(';',constant_start)+1]+'\n'+'\n'.join(member(identity,signature) for signature in [
        'static String endpoint(String value)',
        'static boolean namespace(String path)',
        'static boolean diagnosticUrl(String target)',
        'static boolean requestAllowed(String target,String endpoint,String nonce,boolean active,boolean registered,boolean fresh,long now,long deadline)',
    ])
    start=source.index('  private void requestProtection(')
    end=source.index('  void configureIdentity(',start)
    methods=source[start:end]
    parts={
        '__PRODUCTION_METHODS__':methods,
        '__PROTECTION_RESTORE__':member(source,'static final class ProtectionRestore '),
        '__MAYBE_OPEN__':member(source,'private void maybeOpen()'),
        '__BLOCKED__':member(source,'JSONObject blocked()'),
        '__ROUTE__':member(source,'JSONObject route(String target)'),
        '__PORT_MESSAGE_BODY__':body(source,source.index('@Override public void onPortMessage(Object message,WebExtension.Port incoming)')),
        '__DISCONNECT_BODY__':body(source,source.index('@Override public void onDisconnect(WebExtension.Port incoming)')),
        '__IDENTITY_POLICY__':identity_policy,
        '__LOAD_URL__':member(source,'public void loadUrl(String target)'),
        '__RESTORE_CHECKPOINT__':member(source,'void restoreCheckpoint(GeckoSession target,GeckoSession.SessionState state,String url,long savedRevision)'),
        '__NAVIGATION_BODY__':body(source,source.index('@Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request)')),
        '__POPUP_BODY__':body(source,source.index('@Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String target)')),
    }
    generated=TEMPLATE.read_text()
    for marker,value in parts.items():
        assert generated.count(marker)==1,marker
        generated=generated.replace(marker,value)
    assert '__PRODUCTION_' not in generated
    java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
    if not java:raise RuntimeError('JDK required for production native-setting controls')
    with tempfile.TemporaryDirectory(prefix='native-protection-host-') as temp:
        host=Path(temp)/'NativeProtectionControllerHost.java';host.write_text(generated)
        command=[java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-d',temp,str(POLICY),str(host)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        result=subprocess.run([java,'-cp',temp,'local.pocketchat.NativeProtectionControllerHost'],capture_output=True,text=True,timeout=15)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
    report=json.loads(result.stdout)
    report.update(scope='Actual production pure-Java state plus byte-extracted native controller, route, navigation, load, checkpoint restore, port-message and diagnostic URL policy methods. Handler, Gecko/Android, environment lifecycle, network guard and JSON boundaries are synthetic; no actual network or SDK execution.',
                  newNetworkRequestsActuallySent=False,fullFingerprintProtectionAccepted=False,
                  sourceSha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [VIEW,POLICY,IDENTITY,TEMPLATE,Path(__file__)]},
                  extractedProductionSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in parts.items()})
    return report

class NativeProtectionTest(unittest.TestCase):
    def test_real_controller_rejects_stale_failed_missing_and_unconfirmed_readback(self):
        report=execute()
        self.assertEqual(report['status'],'passed')
        self.assertEqual(report['passed'],len(report['checks']))
        self.assertEqual(report['passed'],98)
        self.assertTrue(all(x['pass'] for x in report['checks']))
        output=ROOT/'work/profile-host/native-protection-controller-results.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    def test_actual_background_never_releases_a_hung_setting_lock_for_a_new_confirmation(self):
        node=shutil.which('node')
        self.assertTrue(node,'Node required for the production extension controls')
        output=ROOT/'work/profile-host/native-protection-background-results.json'
        result=subprocess.run([node,str(SCRIPT),'--receipt',str(output)],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(output.read_text())
        self.assertEqual(report['status'],'passed')
        self.assertEqual(report['passed'],60)
        self.assertEqual(len(report['checks']),60)
        self.assertTrue(all(x['pass'] for x in report['checks']))
        self.assertEqual(report['sourceSha256'],hashlib.sha256(BACKGROUND.read_bytes()).hexdigest())
        self.assertFalse(report['actualAndroidExecution'])

if __name__=='__main__':unittest.main()
