"""Compile actual fixture IPC/API35; pure guard controls never claim an AVD/VPN run."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import unittest
import xml.etree.ElementTree as ET

from experience46_host_evidence import emit_evidence, new_attempt, run_recorded, INVOCATION_FILES

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('queued_vpn46_existing_member', ROOT/'tests/page-recovery-host/run.py')
_members = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_members)
PROVIDER = 'tests/gecko/QueuedChangesVpnProvider.java'
HELPER = 'tests/gecko/QueuedChangesVpn46.java'
SERVICE = 'tests/gecko/NetworkProtectionFixtureVpnService.java'
ANDROID35 = '4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b'
STUBS = r'''
package local.pocketchat;
import android.app.Activity;import android.content.*;import android.os.Handler;import org.json.*;
class GeckoIntegrationTestActivity extends Activity {ChatSession session;long run;int slot;JSONObject eventBuildIdentity;IntegrationEventStore eventStore;QueuedChangesVpn46 queuedVpn;void event(long n,String k,JSONObject v){}}
class IntegrationEventStore {String nonce;}
class ChatSession {int environmentGeneration;String environmentId,networkIdentity;boolean deleted,offline,connecting,recoveryScheduled,networkReady;long navigationEpoch,connectionEpoch;SharedPreferences prefs;Handler handler;TestWeb web;TestGuard guard;static ChatSession peek(){return null;}long beginNetworkApplication(EnvironmentSpec.Identity i){return 0;}boolean adoptNetworkApplication(long l,Object p){return false;}}
class TestWeb {Object current;String getUrl(){return "";}}
class TestGuard {boolean requiresVpn(){return false;}boolean vpnActive(){return false;}String vpnDefaultRouteIssue(){return "";}boolean routeProtected(){return false;}boolean allowed(){return false;}}
class GeckoQueuedChangesObservation {static void validateOwner(String u,int s)throws java.io.IOException{}}
class ProfileCatalog {static ProfileCatalog get(Context c){return null;}EnvironmentSpec.Identity identity(int s){return null;}}
class EnvironmentSpec {long desiredRevision,appliedRevision;Identity identity;boolean pending(){return false;}static class Identity {int slot,generation;String environmentId;}}
class EnvironmentSpecRepository {EnvironmentSpecRepository(Context c){}EnvironmentSpec load(){return null;}}
class NetworkChanges {static JSONObject pendingStrict(Context c)throws Exception{return null;}}
class NetworkApplyCoordinator {static String candidateId(JSONObject value)throws Exception{return "";}}
class NetworkCatalog {static void put(JSONObject v,String k,Object x){}}
'''
CONTROLS = r'''
package local.pocketchat;
import org.json.*;
public final class QueuedVpn46Controls {
 static int checks;static final String RUN="a".repeat(32),SOURCE="b".repeat(40);
 static void check(String name,boolean value){checks++;if(!value)throw new AssertionError(name);}
 static void reject(String name,Runnable action){try{action.run();throw new AssertionError("accepted "+name);}catch(SecurityException expected){checks++;}}
 interface IoAction {void run()throws Exception;}
 static void rejectIo(String name,IoAction action)throws Exception{try{action.run();throw new AssertionError("accepted "+name);}catch(java.io.IOException expected){checks++;}}
 static JSONObject copy(JSONObject x){return J.parse(x.toString());}
 public static void main(String[] args)throws Exception{
  QueuedChangesVpnProvider.requireCaller("local.pocketchat.test",123,123);checks++;
  reject("other UID",()->QueuedChangesVpnProvider.requireCaller("local.pocketchat.test",124,123));
  reject("formal package",()->QueuedChangesVpnProvider.requireCaller("local.pocketchat",123,123));
  QueuedChangesVpnProvider.requireIdentity(RUN,SOURCE,SOURCE);checks++;
  for(String bad:new String[]{"",RUN.substring(1),RUN+"a","A".repeat(32),"0/".repeat(16)})reject("run format",()->QueuedChangesVpnProvider.requireIdentity(bad,SOURCE,SOURCE));
  reject("foreign source",()->QueuedChangesVpnProvider.requireIdentity(RUN,"c".repeat(40),SOURCE));
  reject("source format",()->QueuedChangesVpnProvider.requireIdentity(RUN,"b".repeat(39),SOURCE));
  JSONObject initial=J.obj("runNonce","","sourceCommit","","generation",0,"running",false);
  check("fresh start",QueuedChangesVpnProvider.mayStart(initial,RUN,SOURCE,0));
  for(String field:new String[]{"runNonce","sourceCommit","generation","running"}){JSONObject bad=copy(initial);bad.remove(field);check("missing initial "+field,!QueuedChangesVpnProvider.mayStart(bad,RUN,SOURCE,0));}
  for(Object bad:new Object[]{"0",0.5,true,JSONObject.NULL}){JSONObject row=copy(initial);row.put("generation",bad);check("bad start type",!QueuedChangesVpnProvider.mayStart(row,RUN,SOURCE,0));}
  check("negative expected generation",!QueuedChangesVpnProvider.mayStart(initial,RUN,SOURCE,-1));
  JSONObject live=J.obj("runNonce",RUN,"sourceCommit",SOURCE,"generation",7L,"running",true);
  check("exact live stop owner",QueuedChangesVpnProvider.matches(live,RUN,SOURCE,7));
  check("live start forbidden",!QueuedChangesVpnProvider.mayStart(live,RUN,SOURCE,7));
  check("foreign run cannot stop",!QueuedChangesVpnProvider.matches(live,"c".repeat(32),SOURCE,7));
  check("foreign source cannot stop",!QueuedChangesVpnProvider.matches(live,RUN,"c".repeat(40),7));
  for(long bad:new long[]{-1,0,6,8})check("stale stop generation",!QueuedChangesVpnProvider.matches(live,RUN,SOURCE,bad));
  for(Object bad:new Object[]{"7",7.5,true,JSONObject.NULL}){JSONObject row=copy(live);row.put("generation",bad);check("bad stop type",!QueuedChangesVpnProvider.matches(row,RUN,SOURCE,7));}
  JSONObject prior=copy(live);prior.put("running",false);check("own stopped service",QueuedChangesVpnProvider.mayStart(prior,RUN,SOURCE,7));
  check("foreign prior owner",!QueuedChangesVpnProvider.mayStart(prior,"c".repeat(32),SOURCE,7));
  JSONObject cm=J.obj("vpn",true,"internet",true,"network","123","observerNetwork","123","offline",false,"connecting",false,"recoveryScheduled",false,"guardCoverageIssue","");
  check("full observed route",QueuedChangesVpn46.covered(cm));
  for(String key:new String[]{"vpn","internet","network","observerNetwork","offline","connecting","recoveryScheduled","guardCoverageIssue"}){JSONObject bad=copy(cm);bad.remove(key);check("missing CM "+key,!QueuedChangesVpn46.covered(bad));}
  for(String key:new String[]{"vpn","internet"}){JSONObject bad=copy(cm);bad.put(key,false);check("false "+key,!QueuedChangesVpn46.covered(bad));}
  for(String key:new String[]{"offline","connecting","recoveryScheduled"}){JSONObject bad=copy(cm);bad.put(key,true);check("busy CM "+key,!QueuedChangesVpn46.covered(bad));}
  JSONObject mismatch=copy(cm);mismatch.put("observerNetwork","122");check("stale observer",!QueuedChangesVpn46.covered(mismatch));
  mismatch=copy(cm);mismatch.put("guardCoverageIssue","vpn-default-missing");check("split route",!QueuedChangesVpn46.covered(mismatch));
  JSONObject closed=J.obj("vpn",false,"guardVpnActive",false,"guardRequiresVpn",true,"guardAllowed",false);check("actual removed route and guard",QueuedChangesVpn46.closed(closed));
  for(String key:new String[]{"vpn","guardVpnActive","guardRequiresVpn","guardAllowed"}){JSONObject bad=copy(closed);bad.remove(key);check("missing close "+key,!QueuedChangesVpn46.closed(bad));bad=copy(closed);bad.put(key,!closed.getBoolean(key));check("false close "+key,!QueuedChangesVpn46.closed(bad));}
  JSONObject requested=J.obj("running",false,"fdCloseSucceeded",true,"generation",7L,"events",J.arr(J.obj("kind","tun-closed","detail","requested-stop","generation",7L)));
  check("actual requested descriptor close",QueuedChangesVpn46.requestedClose(requested,7));
  for(String key:new String[]{"running","fdCloseSucceeded","events"}){JSONObject bad=copy(requested);bad.remove(key);check("missing requested close "+key,!QueuedChangesVpn46.requestedClose(bad,7));}
  check("old close generation",!QueuedChangesVpn46.requestedClose(requested,6));
  JSONObject badClose=copy(requested);badClose.getJSONArray("events").getJSONObject(0).put("detail","read-error");check("unexpected system close",!QueuedChangesVpn46.requestedClose(badClose,7));
  badClose=copy(requested);badClose.getJSONArray("events").getJSONObject(0).put("generation",6);check("old close event",!QueuedChangesVpn46.requestedClose(badClose,7));
  badClose=copy(requested);badClose.put("fdCloseSucceeded",false);check("failed descriptor close",!QueuedChangesVpn46.requestedClose(badClose,7));
  badClose=copy(requested);badClose.put("running",true);check("still running",!QueuedChangesVpn46.requestedClose(badClose,7));
  badClose=copy(requested);badClose.remove("generation");check("unbound close generation",!QueuedChangesVpn46.requestedClose(badClose,7));
  check("abort before START observation does not guess",QueuedChangesVpn46.cleanupGeneration(initial,RUN,SOURCE,-1)==-1);
  check("late actual START supplies cleanup generation",QueuedChangesVpn46.cleanupGeneration(live,RUN,SOURCE,-1)==7);
  check("known own cleanup generation",QueuedChangesVpn46.cleanupGeneration(live,RUN,SOURCE,7)==7);
  rejectIo("cleanup foreign run",()->QueuedChangesVpn46.cleanupGeneration(live,"c".repeat(32),SOURCE,-1));
  rejectIo("cleanup foreign source",()->QueuedChangesVpn46.cleanupGeneration(live,RUN,"c".repeat(40),-1));
  rejectIo("cleanup replacement generation",()->QueuedChangesVpn46.cleanupGeneration(live,RUN,SOURCE,8));
  for(Object bad:new Object[]{"7",7.5,true,JSONObject.NULL}){JSONObject row=copy(live);row.put("generation",bad);rejectIo("invalid cleanup type",()->QueuedChangesVpn46.cleanupGeneration(row,RUN,SOURCE,-1));}
  JSONObject badInitial=copy(live);badInitial.put("generation",0);rejectIo("owner without real generation",()->QueuedChangesVpn46.cleanupGeneration(badInitial,RUN,SOURCE,-1));
  JSONObject noOwner=copy(live);noOwner.remove("runNonce");rejectIo("cleanup absent owner",()->QueuedChangesVpn46.cleanupGeneration(noOwner,RUN,SOURCE,-1));
  String environment="11111111-1111-1111-1111-111111111111";
  JSONObject receipt=J.obj("environmentId",environment,"generation",2,"candidateId","candidate:46","savedRevision",4L,"appliedRevision",0,"saveState","saved","applicationState","pending","scope","session");
  JSONObject snapshot=J.obj("operationResult",receipt);check("actual frozen DEFER receipt",QueuedChangesVpn46.expectedCandidate(snapshot,environment,2).toString().equals(receipt.toString()));
  rejectIo("missing save receipt",()->QueuedChangesVpn46.expectedCandidate(new JSONObject(),environment,2));
  rejectIo("foreign receipt environment",()->QueuedChangesVpn46.expectedCandidate(snapshot,"other",2));
  rejectIo("foreign receipt generation",()->QueuedChangesVpn46.expectedCandidate(snapshot,environment,3));
  for(String key:new String[]{"generation","savedRevision","appliedRevision","candidateId","saveState","applicationState","scope"}){JSONObject row=copy(receipt);row.remove(key);rejectIo("missing frozen receipt "+key,()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",row),environment,2));}
  for(Object bad:new Object[]{"4",4.5,0}){JSONObject row=copy(receipt);row.put("savedRevision",bad);rejectIo("bad receipt revision",()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",row),environment,2));}
  JSONObject wrongApplied=copy(receipt);wrongApplied.put("appliedRevision",4);rejectIo("save is not application",()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",wrongApplied),environment,2));
  JSONObject wrongState=copy(receipt);wrongState.put("applicationState","applied");rejectIo("wrong callback phase",()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",wrongState),environment,2));
  JSONObject wrongType=copy(receipt);wrongType.put("generation",true);rejectIo("boolean receipt generation",()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",wrongType),environment,2));
  JSONObject overflowGeneration=copy(receipt);overflowGeneration.put("generation",4294967298L);rejectIo("long generation does not truncate",()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",overflowGeneration),environment,2));
  JSONObject wrongCandidate=copy(receipt);wrongCandidate.put("candidateId","UPPERCASE");rejectIo("bad candidate identity",()->QueuedChangesVpn46.expectedCandidate(J.obj("operationResult",wrongCandidate),environment,2));
  System.out.println(J.obj("schema",1,"status","passed","checks",checks,"actualAndroidExecution",false,"actualVpnExecution",false,"physicalPhoneAcceptance",false,"scope","Actual fixture pure owner, cleanup, receipt and observation members; CM, Binder, service and TUN execution require the fresh AVD cohort"));
 }
}
'''


class QueuedVpn46Tests(unittest.TestCase):
    def test_private_provider_shares_the_existing_real_service_process(self):
        app = ET.parse(ROOT / 'tests/gecko/AndroidManifest.xml').getroot().find('application')
        ns = '{http://schemas.android.com/apk/res/android}'
        services = [x for x in app.findall('service') if x.get(ns+'name') == 'local.pocketchat.NetworkProtectionFixtureVpnService']
        providers = [x for x in app.findall('provider') if x.get(ns+'name') == 'local.pocketchat.QueuedChangesVpnProvider']
        self.assertEqual(len(services), 1)
        self.assertEqual(len(providers), 1)
        self.assertEqual(services[0].get(ns+'process'), ':network_protection')
        self.assertEqual(providers[0].get(ns+'process'), services[0].get(ns+'process'))
        self.assertEqual(providers[0].get(ns+'exported'), 'false')
        self.assertEqual(providers[0].get(ns+'authorities'), 'local.pocketchat.test.queued-vpn-fixture')
        formal = (ROOT / 'app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('QueuedChangesVpn', formal)

    def test_actual_members_both_json_controls_and_available_api35_compilation(self):
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java')).resolve()
        javac = java.parent/'javac'
        android = Path(os.environ.get('PROFILE_ANDROID_JAR', '/tmp/pocketchat-shared-tools/android-35/android.jar'))
        if os.environ.get('PROFILE_ANDROID_JAR'):
            self.assertTrue(android.is_file(), 'Configured Android35 API must exist')
        if android.is_file():
            self.assertEqual(hashlib.sha256(android.read_bytes()).hexdigest(), ANDROID35)
        jars = [Path(os.environ.get('PROFILE_JSON_JAR', ROOT/'work/profile-host/json.jar')),
                Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT/'work/profile-host/android-json.jar'))]
        for index, jar in enumerate(jars):
            self.assertTrue(jar.is_file())
            out = new_attempt(ROOT/'work/profile-host/queued-vpn46', 'android-json' if index else 'desktop-json')
            (out/'src/local/pocketchat').mkdir(parents=True)
            (out/'android-src/local/pocketchat').mkdir(parents=True)
            (out/'compile').mkdir()
            (out/'android-api-compile').mkdir()
            package = out/'src/local/pocketchat'
            api_package = out/'android-src/local/pocketchat'
            inputs = {}
            for name in [PROVIDER, HELPER, SERVICE, 'app/src/main/java/local/pocketchat/J.java']:
                raw = (ROOT/name).read_bytes()
                inputs[name] = hashlib.sha256(raw).hexdigest()
                (api_package/Path(name).name).write_bytes(raw)
            inputs[str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            inputs['tests/page-recovery-host/run.py'] = hashlib.sha256((ROOT/'tests/page-recovery-host/run.py').read_bytes()).hexdigest()
            (api_package/'BoundaryStubs.java').write_text(STUBS)
            provider = (ROOT/PROVIDER).read_text()
            helper = (ROOT/HELPER).read_text()
            provider_members = ['static void requireCaller(', 'static void requireIdentity(', 'static boolean matches(',
                                'static boolean integer(', 'static boolean mayStart(']
            helper_members = ['static boolean covered(', 'static boolean closed(', 'static boolean requestedClose(',
                              'static long cleanupGeneration(', 'static JSONObject expectedCandidate(']
            for name, text, members in [('QueuedChangesVpnProvider', provider, provider_members),
                                        ('QueuedChangesVpn46', helper, helper_members)]:
                exact = '\n'.join(_members.member(text, item) for item in members)
                (package/(name+'.java')).write_text('package local.pocketchat;import org.json.*;import java.io.*;final class '+name+'{\n'+exact+'\n}\n')
            (package/'J.java').write_bytes((ROOT/'app/src/main/java/local/pocketchat/J.java').read_bytes())
            (package/'QueuedVpn46Controls.java').write_text(CONTROLS)
            (out/'source-hashes.json').write_text(json.dumps(inputs, sort_keys=True)+'\n')
            try:
                cp = str(jar)
                if android.is_file():
                    api_compile = run_recorded([str(javac), '-encoding', 'UTF-8', '-cp', os.pathsep.join([str(jar), str(android)]),
                                               '-d', str(out/'android-classes'), *map(str, sorted(api_package.glob('*.java')))],
                                              out/'android-api-compile', cwd=ROOT, timeout=60)
                    self.assertEqual(api_compile.returncode, 0, api_compile.stderr.decode(errors='replace'))
                compiled = run_recorded([str(javac), '-encoding', 'UTF-8', '-cp', cp, '-d', str(out/'classes'),
                                         *map(str, sorted(package.glob('*.java')))], out/'compile', cwd=ROOT, timeout=60)
                self.assertEqual(compiled.returncode, 0, compiled.stderr.decode(errors='replace'))
                ran = run_recorded([str(java), '-cp', os.pathsep.join([str(out/'classes'), cp]),
                                    'local.pocketchat.QueuedVpn46Controls'], out, cwd=ROOT, timeout=30)
                self.assertEqual(ran.returncode, 0, ran.stderr.decode(errors='replace'))
                report = json.loads(ran.stdout)
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(report['checks'], 101)
                self.assertIs(report['actualAndroidExecution'], False)
                self.assertIs(report['actualVpnExecution'], False)
                report['wholeFixtureAndroid35ApiCompiled'] = android.is_file()
                report['android35JarSha256'] = ANDROID35 if android.is_file() else None
                report['wholeFixtureApiBoundary'] = ('Actual whole fixture with declared application/Gecko adapters; no Android execution.'
                                                     if android.is_file() else 'Android35 unavailable in this host phase; original official SDK assembleIntegration remains mandatory.')
                (out/'results.json').write_text(json.dumps(report, sort_keys=True)+'\n')
            finally:
                emit_evidence(out, ('results.json', 'source-hashes.json', *INVOCATION_FILES,
                                   *('compile/'+p for p in INVOCATION_FILES),
                                   *('android-api-compile/'+p for p in INVOCATION_FILES)),
                              label='queued-vpn46-'+('android-json' if index else 'desktop-json'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
