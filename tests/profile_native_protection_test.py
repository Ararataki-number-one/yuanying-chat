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
NAVIGATION=ROOT/'app/src/main/java/local/pocketchat/GeckoNavigationPolicy.java'
ADDRESS=ROOT/'app/src/main/java/local/pocketchat/BrowserAddressPolicy.java'
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

class CompiledControllerRejection(AssertionError):
    def __init__(self,result,generated,parts):
        super().__init__(result.stdout+result.stderr)
        self.receipt=dict(status='rejected',compiled=True,compilerExitCode=0,runtimeExitCode=result.returncode,
            stderr=result.stderr,generatedSha256=hashlib.sha256(generated.encode()).hexdigest(),
            executedProductionSha256={key:hashlib.sha256(value.encode()).hexdigest() for key,value in parts.items()},
            actualAndroidExecution=False,actualCpuPolicyExecution=False,nativeSettingReadback=False)

def execute(source_override=None,cpu_gate_removed=False):
    source=VIEW.read_text() if source_override is None else source_override
    if cpu_gate_removed:
        gate='owner.cpu.readyFor(runtime)&&nativeProtection.allows(owner.privacy.level())'
        if source.count(gate)!=1:raise AssertionError('Exact current CPU admission expression required')
        source=source.replace(gate,'nativeProtection.allows(owner.privacy.level())',1)
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
        '__DISABLED_NAVIGATION__':member(source,'boolean rejectDisabledNavigation(GeckoSession session,String target)'),
        '__TIMEZONE_INTENT_FIELDS__':'\n'.join(source[source.index(signature):source.index(';',source.index(signature))+1] for signature in (
            'final Map<GeckoSession,String> timeZoneLoads=',
            'final Map<GeckoSession,Object> timeZoneIntents=',
            'final Map<GeckoSession,Object> nativeTimeZoneIntents=',
        )),
        '__TIMEZONE_INTENT_METHODS__':'\n'.join(member(source,signature) for signature in (
            'Object claimTimeZoneIntent(GeckoSession session,boolean restore)',
            'boolean hasTimeZoneIntent(GeckoSession session)',
            'void clearTimeZoneIntent(GeckoSession session,Object intent)',
        )),
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
        command=[java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-d',temp,str(POLICY),str(NAVIGATION),str(ADDRESS),str(host)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        result=subprocess.run([java,'-cp',temp,'local.pocketchat.NativeProtectionControllerHost'],capture_output=True,text=True,timeout=15)
        if result.returncode:raise CompiledControllerRejection(result,generated,parts)
    report=json.loads(result.stdout)
    report.update(scope='Actual production pure-Java state plus byte-extracted native controller, route, navigation, load, checkpoint restore, port-message and diagnostic URL policy methods. Handler, Gecko/Android, environment lifecycle, network guard and JSON boundaries are synthetic; no actual network or SDK execution.',
                  auxiliaryPageBoundary='Default absent; close returns false only while absent, and any auxiliary freshness/close behavior fails explicitly. Real auxiliary lifecycle is not exercised.',
                  actualRequestHeaderPolicyExecution=False,actualTimeZonePolicyExecution=False,
                  actualAddonLifecycleExecution=False,addonBoundary='The original 98 protection cases explicitly assume an enabled independent add-on. Separate checks execute the current byte-extracted disabled-navigation guard and its original call sites against counted application/SDK boundaries; no real add-on lifecycle or native navigation is exercised.',
                  actualCpuPolicyExecution=False,
                  cpuBoundaryScope='Only automatic with explicit declared readiness for one opaque fixture runtime; counted protection invalidation, native-refresh facade and readyFor checks. Independent denial/custom/unknown/null runtime controls execute current protection admission; no CPU native/profile/Worker execution or ACK is represented.',
                  requestHeaderBoundary='Independent header filter is explicitly installed at fixture creation; retirement is counted only. Real header installation, policy replies and HTTP wire behavior are not executed here.',
                  timeZoneBoundary='Independent system timezone is explicitly ready, with counted checks, popup admission, preparation and retirement. Custom-timezone deferral fails explicitly; real timezone/session policy executes in separate current-policy hosts. The intent maps and claim/clear/has helpers are byte-extracted current production, not readiness facades.',
                  newNetworkRequestsActuallySent=False,fullFingerprintProtectionAccepted=False,
                  sourceSha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [VIEW,POLICY,NAVIGATION,ADDRESS,IDENTITY,TEMPLATE,Path(__file__)]},
                  extractedProductionSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in parts.items()})
    configured_jar=os.environ.get('PROFILE_JSON_JAR')
    report['jsonBoundary']=dict(kind='synthetic-hashmap',configuredJarSha256=hashlib.sha256(Path(configured_jar).read_bytes()).hexdigest() if configured_jar and Path(configured_jar).is_file() else None,configuredJarConsumed=False,actualJsonParserExecution=False)
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
    def test_current_cpu_dependency_is_explicit_and_independently_closed(self):
        report=execute();boundary=report['cpuBoundary']
        self.assertEqual(boundary['status'],'passed')
        self.assertEqual(boundary['mode'],'automatic-only')
        self.assertEqual(boundary['passed'],20)
        self.assertEqual(len(boundary['checks']),20)
        self.assertTrue(all(value['pass'] is True for value in boundary['checks']))
        self.assertTrue(boundary['trace'])
        self.assertFalse(boundary['actualCpuPolicyExecution'])
        self.assertFalse(boundary['nativeSettingReadback'])
        self.assertFalse(boundary['actualAndroidExecution'])
        output=ROOT/'work/profile-host/native-protection-cpu-boundary-results.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    def test_removing_actual_cpu_admission_gate_fails_after_successful_compilation(self):
        with self.assertRaisesRegex(CompiledControllerRejection,'Independent CPU refusal closes actual protection admission') as rejected:
            execute(cpu_gate_removed=True)
        receipt=rejected.exception.receipt
        self.assertEqual(receipt['runtimeExitCode'],1)
        self.assertTrue(receipt['compiled'])
        receipt.update(productionSourceSha256=hashlib.sha256(VIEW.read_bytes()).hexdigest(),
            mutation='Only remove owner.cpu.readyFor(runtime)&& from actual current protectionAllowsNetwork',
            compilerFailureAccepted=False,actualJsonParserExecution=False)
        output=ROOT/'work/profile-host/native-protection-cpu-gate-negative.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
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
    def test_current_disabled_addon_guard_and_its_navigation_call_sites(self):
        report=execute()
        self.assertEqual(report['passed'],98)
        self.assertEqual(report['addonBoundaryPassed'],8)
        self.assertTrue(all(item['pass'] is True for item in report['addonBoundaryChecks']))
        source=VIEW.read_text()
        actual=member(source,'boolean rejectDisabledNavigation(GeckoSession session,String target)')
        mutant=source.replace(actual,'boolean rejectDisabledNavigation(GeckoSession session,String target){return false;}',1)
        self.assertNotEqual(source,mutant)
        with self.assertRaisesRegex(AssertionError,'Disabled addon rejects the actual current navigation'):
            execute(mutant)

if __name__=='__main__':unittest.main()
