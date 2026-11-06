#!/usr/bin/env python3
"""Exercise actual closed-world fixture admission and original external routing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
ACTIVITY = ROOT / 'tests/gecko/GeckoCpuIpComboIntegrationActivity.java'
sys.path.insert(0, str(ROOT / 'tests/gecko-navigation-host'))
from run import member_at


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(text, needle):
    at = [m.start() for m in re.finditer(re.escape(needle), text)
          if not text[text.rfind('\n', 0, m.start())+1:m.start()].strip()]
    if len(at) != 1:
        raise ValueError('One actual declaration required: '+needle)
    return member_at(text, at[0])


def field(text, prefix):
    rows = [line.strip() for line in text.splitlines() if line.strip().startswith(prefix)]
    if len(rows) != 1 or not rows[0].endswith(';'):
        raise ValueError('One complete actual field required: '+prefix)
    return rows[0]


TLS_EXTRA_TEMPLATE='class TlsOriginalRouteBoundary extends WebBoundary {\n  int originalCalls;JSONObject forced;\n  TlsOriginalRouteBoundary(OwnerBoundary owner){super(owner);}\n  @Override JSONObject protectedNetworkRoute(String target){originalCalls++;return forced==null?super.protectedNetworkRoute(target):forced;}\n}\nfinal class TlsFixtureBoundary {\n  boolean terminal;String failure="",stage="running";int publishes;\n  void publish(){publishes++;}\n@TLS_HELPERS@\n  final class Observed extends TlsOriginalRouteBoundary {\n@TLS_FIELD@\n    Observed(OwnerBoundary owner){super(owner);}\n@TLS_OVERRIDES@\n  }\n}\nfinal class TlsAdmissionExtraHost {\n  static int checks;static void check(String name,boolean yes){if(!yes)throw new AssertionError(name);checks++;}\n  public static void main(String[]args)throws Exception{\n    String[] exact={"https://firefox.settings.services.mozilla.com/v2/","https://firefox-settings-attachments.cdn.mozilla.net/file","https://firefox.settings.services.mozilla.com:443/v2/"};\n    for(String target:exact){TlsFixtureBoundary f=new TlsFixtureBoundary();TlsFixtureBoundary.Observed v=f.new Observed(new OwnerBoundary());JSONObject actual=v.protectedNetworkRoute(target);check("TLS exact RS uses actual original super",v.originalCalls==1&&TlsFixtureBoundary.closedNativeRefusal(actual)&&!f.terminal);check("TLS call owner restored",v.admissionCall.get()==null);}\n    String[] ordinary={"https://fp-a.pocketchat.test/env-policy","https://fp-b.pocketchat.test/frame","https://ipwho.is/8.8.8.8","wss://firefox.settings.services.mozilla.com/ws","http://firefox.settings.services.mozilla.com/","https://FIREFOX.settings.services.mozilla.com/","https://user@firefox.settings.services.mozilla.com/","https://firefox.settings.services.mozilla.com:444/","https://firefox.settings.services.mozilla.com./","https://firefox.settings.services.mozilla.com.evil/"};\n    for(String target:ordinary){OwnerBoundary o=new OwnerBoundary();WebBoundary base=new WebBoundary(o);TlsFixtureBoundary f=new TlsFixtureBoundary();TlsFixtureBoundary.Observed v=f.new Observed(o);check("TLS unknown and WSS preserve original route",ComboNativeAdmissionHost.same(base.protectedNetworkRoute(target),v.protectedNetworkRoute(target))&&v.originalCalls==1&&!f.terminal&&v.admissionCall.get()==null);}\n    TlsFixtureBoundary f=new TlsFixtureBoundary();TlsFixtureBoundary.Observed v=f.new Observed(new OwnerBoundary());f.terminal=true;f.stage="complete";v.forced=J.obj("type","direct");JSONObject actual=v.protectedNetworkRoute(exact[0]);check("TLS nonclosed actual route is not forged",actual==v.forced);check("TLS late bad route retires old success",f.terminal&&!f.failure.isEmpty()&&f.publishes==1);\n    System.out.println(J.obj("status","passed","passed",checks,"actualAndroidExecution",false));\n  }\n}\n'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def tool(name):
        path = str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not path:
            parser.error('Provide --java-home containing '+name)
        return path
    versions = []
    for name, flag in (('java','-version'),('javac','-version')):
        result = subprocess.run([tool(name),flag],text=True,capture_output=True,timeout=10)
        if result.returncode:
            raise RuntimeError(result.stderr)
        versions.append(result.stdout+result.stderr)
    if not re.search(r'version "17[.]',versions[0]) or not re.search(r'javac 17[.]',versions[1]):
        parser.error('Use actual JDK 17 for this host scope')
    complete = [PROD/name for name in ('J.java','BrowserAddressPolicy.java','GeckoNavigationPolicy.java')]
    inputs = [ROOT/'tests/gecko/GeckoTlsCpuIpComboIntegrationActivity.java', ACTIVITY, PROD/'GeckoWebView.java', PROD/'AppPrefs.java', Path(__file__).resolve(),
        HERE/'ComboNativeAdmissionHost.java.in',HERE/'README.md',ROOT/'tests/gecko-navigation-host/run.py']+complete
    hashes = {str(path.relative_to(ROOT)):digest(path) for path in inputs}
    jar_hash = digest(args.json_jar)
    activity = ACTIVITY.read_text();gecko = (PROD/'GeckoWebView.java').read_text()
    selected = {
        'role': declaration(activity,'static String remoteSettingsRole('),
        'closed': declaration(activity,'static boolean closedNativeRefusal('),
        'record': declaration(activity,'void recordNativeRefusal('),
        'publish': declaration(activity,'void publishNativeRefusals('),
        'fatal-admission': declaration(activity,'void failNativeAdmission('),
        'failed': declaration(activity,'void failed('),
        'observed-allow': declaration(activity,'@Override protected boolean allowedUrl('),
        'observed-route': declaration(activity,'@Override JSONObject protectedNetworkRoute('),
        'blocked': declaration(gecko,'JSONObject blocked('),
        'base-route': declaration(gecko,'JSONObject protectedNetworkRoute('),
        'base-allow': declaration(gecko,'protected boolean allowedUrl('),
        'pref-enabled': declaration((PROD/'AppPrefs.java').read_text(),'static boolean enabled('),
        'admission-file':field(activity,'static final String ADMISSION_FILE='),
        'admission-fields':field(activity,'final JSONArray nativeRefusals='),
        'call-field':field(activity,'final ThreadLocal<String[]> admissionCall='),
    }
    tls_source=(ROOT/'tests/gecko/GeckoTlsCpuIpComboIntegrationActivity.java').read_text()
    tls_selected={name:declaration(tls_source,needle) for name,needle in (
        ('role','static String remoteSettingsRole('),('closed','static boolean closedNativeRefusal('),
        ('allow','@Override protected boolean allowedUrl('),('route','@Override JSONObject protectedNetworkRoute('),('failed','void failed('))}
    tls_selected['field']=field(tls_source,'final ThreadLocal<String[]> admissionCall=')
    if tls_selected['role']!=selected['role'] or tls_selected['closed']!=selected['closed']:raise ValueError('TLS fixture must copy the exact proven narrow functions')
    clear_at=tls_source.index('getSharedPreferences("chat",0).edit().clear()')
    if not(clear_at<tls_source.index('AppPrefs.apply(this,J.obj("automaticLatencyChecks",false))')<tls_source.index('super.onCreate(null)')):raise ValueError('TLS fixture preference must follow clear and precede MainActivity')
    template = (HERE/'ComboNativeAdmissionHost.java.in').read_text()
    aliases = (
        ('android.os.Process','ProcessBoundary'),('android.app.Application','ApplicationBoundary'),
        ('AppSessionIdentity','SessionIdentityBoundary'),('BrowserNetworkGuard','GuardPolicyBoundary'),
        ('MainActivity','ProxyPolicyBoundary'),('NativeNetwork','NetworkBoundary'),
        ('Profiles','ProfileBoundary'),('AtomicFile','AtomicFileBoundary'),('Uri','UriBoundary'),
        ('Context c','ContextBoundary c'),
    )
    def adapt(text):
        for before,after in aliases:
            text=re.sub(r'(?<![\w$])'+re.escape(before)+r'(?![\w$])',lambda _:after,text)
        return text
    def generate(m):
        return template.replace('@FIXTURE_FIELDS@',m['admission-file']+'\n'+m['admission-fields']).replace(
            '@FIXTURE_METHODS@',adapt('\n'.join(m[k] for k in ('role','closed','record','publish','fatal-admission','failed')))).replace(
            '@OBSERVED_FIELDS@',m['call-field']).replace('@OBSERVED_METHODS@',adapt(m['observed-allow']+'\n'+m['observed-route'])).replace(
            '@BASE_METHODS@',adapt('\n'.join(m[k] for k in ('blocked','base-route','base-allow')))).replace(
            '@PREFERENCE_METHOD@',adapt(m['pref-enabled']))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    artifacts=args.output.parent/(args.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
    controls=[]
    with tempfile.TemporaryDirectory(prefix='combo-native-admission-host-') as temporary:
        work=Path(temporary)
        invocations=0
        def tls_extra(m):
            return TLS_EXTRA_TEMPLATE.replace('@TLS_HELPERS@',adapt(m['role']+'\n'+m['closed']+'\n'+m['failed'])).replace('@TLS_FIELD@',m['field']).replace('@TLS_OVERRIDES@',adapt(m['allow']+'\n'+m['route']))
        def compile_members(m,label,tls_members=None):
            out=artifacts/label;out.mkdir(exist_ok=True)
            host=out/'ComboNativeAdmissionHost.java';host.write_text(generate(m)+tls_extra(tls_selected if tls_members is None else tls_members))
            classes=work/label
            command=[tool('javac'),'--release','17','-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(classes),str(host)]+[str(p) for p in complete]
            result=subprocess.run(command,text=True,capture_output=True,timeout=60)
            (out/'compile.command.json').write_text(json.dumps(command)+'\n');(out/'compile.stderr.log').write_text(result.stderr)
            if result.returncode:raise RuntimeError(result.stderr)
            return classes,out
        def execute(classes,out,focus=None):
            nonlocal invocations
            invocations+=1
            invocation=Path(tempfile.mkdtemp(prefix='runtime-'+(focus or 'all')+'-'+str(invocations)+'-',dir=out))
            command=[tool('java'),'-Dhost.outputDirectory='+str(invocation),'-cp',str(classes)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.ComboNativeAdmissionHost']+([focus] if focus else [])
            result=subprocess.run(command,text=True,capture_output=True,timeout=30)
            suffix='-'+focus if focus else ''
            (out/('run'+suffix+'.command.json')).write_text(json.dumps(command)+'\n')
            (out/('run'+suffix+'.stdout.log')).write_text(result.stdout);(out/('run'+suffix+'.stderr.log')).write_text(result.stderr)
            return result
        classes,out=compile_members(selected,'current');result=execute(classes,out)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        report=json.loads(result.stdout)
        virtual='||!allowedUrl(target.startsWith("wss://")?"https"+target.substring(3):target.startsWith("ws://")?"http"+target.substring(2):target)'
        mutations=[
            ('https-only','role','!"https".equals(uri.getScheme())','false','scope','A close or unknown variant is outside the exact fixture classifier'),
            ('raw-authority','role','||!(host.equals(authority)||(host+":443").equals(authority))','','scope','A close or unknown variant is outside the exact fixture classifier'),
            ('case-sensitive','role','"firefox.settings.services.mozilla.com".equals(host)','"firefox.settings.services.mozilla.com".equalsIgnoreCase(host)','scope','A close or unknown variant is outside the exact fixture classifier'),
            ('original-virtual-admission','base-route',virtual,'','exact','Exact HTTPS targets use the original closed native route'),
            ('five-original-keys','closed','actual.length()==5&&','','proof','Strict closed-route proof rejects an altered route'),
            ('typed-port','closed','actual.opt("port") instanceof Integer&&','','proof','Strict closed-route proof rejects an altered route'),
            ('only-role-recorded','observed-route','if(!role.isEmpty())recordNativeRefusal','recordNativeRefusal','main','Main target traffic creates no Remote Settings refusal row'),
            ('honest-predicate','observed-route','role.equals(observed[0])','true','causal','An earlier original guard remains closed without claiming the admission predicate'),
            ('event-cap','record','if(nativeRefusals.length()<128)','if(true)','binding','The actual recorder caps rows while preserving the refusal total'),
            ('nonce-binding','publish','"runNonce",nonce','"runNonce","stale-boundary-nonce"','binding','The published diagnostic binds the current source build and nonce'),
            ('terminal-route-failure','fatal-admission','if(terminal&&failure.isEmpty())terminal=false;','','fatal','A late invalid native route invalidates an already terminal success'),
            ('terminal-io-failure','publish','probe.post(()->failNativeAdmission(error))','probe.post(()->failed(error))','fatal','A queued publisher IO error invalidates an already terminal success'),
        ]
        for label,member,before,after,focus,assertion in mutations:
            if selected[member].count(before)!=1:raise ValueError('One exact current mutation required: '+label)
            pristine=execute(classes,out,focus)
            if pristine.returncode:raise AssertionError('Pristine control failed: '+label+pristine.stderr)
            m=dict(selected);m[member]=m[member].replace(before,after,1)
            mutant_classes,mutant_out=compile_members(m,'mutant-'+label);mutant=execute(mutant_classes,mutant_out,focus)
            if mutant.returncode==0 or 'AssertionError: '+assertion not in mutant.stderr:raise AssertionError('Precise semantic mutation must fail: '+label+mutant.stderr)
            controls.append(dict(case=label,pristinePassed=True,mutantRejected=True,assertion=assertion))
        def tls_run(classes):
            invocation=Path(tempfile.mkdtemp(prefix='tls-runtime-',dir=work))
            return subprocess.run([tool('java'),'-Dhost.outputDirectory='+str(invocation),'-cp',str(classes)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.TlsAdmissionExtraHost'],text=True,capture_output=True,timeout=30)
        pristine_tls=tls_run(classes)
        if pristine_tls.returncode:raise RuntimeError(pristine_tls.stderr)
        tls_report=json.loads(pristine_tls.stdout);tls_controls=[]
        for label,key,before,after,assertion in [
            ('tls-super-bypass','route','super.protectedNetworkRoute(target)','blocked()','TLS exact RS uses actual original super'),
            ('tls-wss-overreach','allow','if(observed!=null&&observed[1].isEmpty())return super.allowedUrl(target);','','TLS unknown and WSS preserve original route'),
            ('tls-unsafe-route','route','!role.isEmpty()&&!closedNativeRefusal(actual)','false','TLS late bad route retires old success')]:
            if tls_selected[key].count(before)!=1:raise ValueError('Unique TLS current mutant required: '+label)
            changed=dict(tls_selected);changed[key]=changed[key].replace(before,after,1);mutated,_=compile_members(selected,label,changed);bad=tls_run(mutated)
            if bad.returncode==0 or 'AssertionError: '+assertion not in bad.stderr:raise AssertionError('Actual TLS route mutant escaped '+label+bad.stderr)
            tls_controls.append(dict(name=label,compiled=True,rejected=True,assertion=assertion))
        report['tlsFixture']=dict(tls_report,negativeControls=tls_controls,actualSourceMembersSha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in tls_selected.items()})
    stable=all(digest(path)==hashes[str(path.relative_to(ROOT))] for path in inputs) and digest(args.json_jar)==jar_hash
    report.update(sourceFiles=hashes,jsonJarSha256=jar_hash,javaVersion='\n'.join(versions).strip(),productionMembers=list(selected),negativeControls=controls,executionInputsUnchanged=stable,
        boundaries=[
            'Actual production GeckoWebView blocked/allowedUrl/protectedNetworkRoute and complete actual public URL policies execute; the actual fixture classifier, predicate, two overrides, recorder, and async publisher execute.',
            'Context/preferences/process/SDK session identity/route readiness/proxy validation and AtomicFile are explicitly named boundaries, not Android/Gecko packages.',
            'External SOCKS route JSON is real production output; native-core internal branches are deliberately outside scope and unexpected use throws.',
            'Real JVM file writes exercise the publisher over a declared AtomicFile facade and queued executor/handler; they do not prove Android atomic persistence or native runtime identities.',
            'The original actual failed method and new native-admission failure helper execute; the full activity publish output is a counted boundary after actual terminal/failure state changes.',
        ],scope='Source-bound fixture admission and causal refusal diagnostics at explicit JVM boundaries; no Android, Gecko, socket, public request, server error exemption, fixture acceptance or historical failure attribution.')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'] if stable else 'source-changed',passed=report['passed'],negativeControls=len(controls),executionInputsUnchanged=stable,output=str(args.output))))
    if not stable:raise SystemExit(1)


if __name__=='__main__':main()
