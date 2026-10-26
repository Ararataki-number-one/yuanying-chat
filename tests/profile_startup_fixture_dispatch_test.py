"""Real startup dispatch + fixture URL hierarchy on JVM; no Android/native HTTP.

The pre-fix fixture only overrides startupProbe(3 args), while production search
calls startupProbe(4 args). Execute the real dispatcher, rather than infer a
successful hook from its signature. The native HEAD/time/cleanup checks stay
byte-for-byte preserved outside the two override/forwarding adaptations.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat/NativeNetwork.java'
FIXTURE=ROOT/'tests/gecko/NativeProbeIntegrationActivity.java'
PARENT=ROOT/'tests/gecko/NetworkOptimizationIntegrationActivity.java'
HELPER=ROOT/'tools/gecko/run_network_core_host.py'
ORIGINAL_FIXTURE_SHA256='20230412fd838aea0017607a92bf98bdd12c48c6ee4d23bd4efcac3564ec81c7'
OLD_OVERRIDE='@Override RouteProbe startupProbe(String name,int index,String epoch){'
NEW_OVERRIDE='@Override RouteProbe startupProbe(String name,int index,String epoch,RecoveryRoute recovery){'
OLD_FORWARD='super.startupProbe(name,index,epoch)'
NEW_FORWARD='super.startupProbe(name,index,epoch,recovery)'
spec=importlib.util.spec_from_file_location('startup_dispatch_extract',HELPER)
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
block=helper.block
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def original_fixture(current):
    if sha(current.encode())==ORIGINAL_FIXTURE_SHA256:
        return current
    if current.count(NEW_OVERRIDE)!=1 or current.count(NEW_FORWARD)!=1:
        raise ValueError('Exact startup fixture adapter/forward is missing or ambiguous')
    old=current.replace(NEW_OVERRIDE,OLD_OVERRIDE,1).replace(NEW_FORWARD,OLD_FORWARD,1)
    if sha(old.encode())!=ORIGINAL_FIXTURE_SHA256:
        raise ValueError('Native startup fixture changed beyond its override and forwarding signature')
    return old


HOST=r'''
package local.pocketchat;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import android.os.SystemClock;
class NativeNetwork {
  static class RecoveryRoute {final long deadline=SystemClock.elapsedRealtime()+45000;}
  static class StartupRoute {}
  static class StartupRouteFailure extends IOException {}
  static class RouteTransactionFailure extends IOException {RouteTransactionFailure(String text,Throwable cause){super(text,cause);}}
  static class RetainedRouteFailure extends IOException {}
  static class ExitMismatch extends IOException {}
  static class ExitCheckUnavailable extends IOException {}
  static class ProbeResult {final int delay;final RecoveryRoute recovery;final String target;
    ProbeResult(int delay,RecoveryRoute recovery,String target){this.delay=delay;this.recovery=recovery;this.target=target;}
    JSONObject publicSummary(){return J.obj("controlledTarget",target);}}
  static class Quality {void record(String name,int delay,long at){}void record(String name,int delay,long at,String kind,JSONObject value){}}
  final List<String> names=Arrays.asList("Entry|winner","Entry|loser");final String token="synthetic-epoch";
  final ThreadLocal<NetworkWork> maintenance=new ThreadLocal<>();
  final ExecutorService probes=Executors.newFixedThreadPool(4),closers=Executors.newFixedThreadPool(2);
  final List<JSONObject> producerCalls=Collections.synchronizedList(new ArrayList<>());
  final CountDownLatch loserEntered=new CountDownLatch(1),fallbackEntered=new CountDownLatch(2);
  final Quality quality=new Quality();JSONArray results=new JSONArray();String startupPath="",selected="",currentEntry="Entry|winner";Object verifiedRoute;long lastScan;
  RecoveryRoute expectedRecovery;boolean selectionRecoverySame;
  void maintenanceCheck()throws InterruptedIOException{NetworkWork work=maintenance.get();if(work!=null)work.check();}
  void report(String text){}static String display(String name){return name;}
  long startupSearchBudgetMs(){return 45000;}
  JSONObject api(String method,String path,JSONObject body,int timeout)throws Exception{maintenanceCheck();return new JSONObject();}
  boolean probeCurrent(ProbeResult sample){return sample!=null;}
  void recordProbe(ProbeResult sample,long now){}
  JSONObject recoveryState(RecoveryRoute recovery){return new JSONObject();}
  static boolean ordinaryRecoveryFailure(Exception failure){return failure instanceof IOException;}
  // Only the probe/exit API boundary is synthetic. Each real startupProbe calls
  // this with its actual URL hierarchy and actual received RecoveryRoute object.
  ProbeResult probeMeasured(String proxy,String name,RecoveryRoute recovery){
    String target=probeUrl();producerCalls.add(J.obj("proxy",proxy,"entry",name,"target",target,"recoverySame",recovery==expectedRecovery));
    try {
      // The real parent plain fixture defaults to probeStatus=204. A wrong URL
      // can therefore look healthy; do not invent a transport/API failure here.
      if(target.equals("http://127.0.0.1:9123/probe")){fallbackEntered.countDown();if(!fallbackEntered.await(2,TimeUnit.SECONDS))throw new IOException("Both controlled fallback reads did not enter");return new ProbeResult(20,recovery,target);}
      if(target.equals("https://127.0.0.1:9456/startup-loser")){
        loserEntered.countDown();new CountDownLatch(1).await(10,TimeUnit.SECONDS);return new ProbeResult(-1,recovery,target);
      }
      if(target.equals("https://127.0.0.1:9456/startup-win")){
        if(!loserEntered.await(2,TimeUnit.SECONDS))throw new IOException("Controlled loser probe did not enter");
        return new ProbeResult(20,recovery,target);
      }
      return new ProbeResult(-1,recovery,target);
    }catch(InterruptedException stopped){Thread.currentThread().interrupt();return new ProbeResult(-1,recovery,target);}
    catch(IOException failed){return new ProbeResult(-1,recovery,target);}
  }
  void selectVerifiedRoute(String name,boolean measure,StartupRoute startup,RecoveryRoute recovery)throws Exception{
    selected=name;selectionRecoverySame=recovery==expectedRecovery;verifyExit();
  }
  String verifyExit()throws Exception{return "203.0.113.8";}
  String probeUrl(){return "https://www.gstatic.com/generate_204";}
  /* ACTUAL_PRODUCTION */
  static final class Context {File getNoBackupFilesDir(){return new File("synthetic-no-files-created");}}
  static final class ProbeFixture {final List<String> hookPaths=Collections.synchronizedList(new ArrayList<>());
    String url(String path){hookPaths.add(path);return "https://127.0.0.1:9456"+path;}}
  static class ProbeNetwork extends NetworkOptimizationIntegrationActivity.TestNetwork {
    volatile String controlledProbeUrl="";
    ProbeNetwork(Context context,NetworkOptimizationIntegrationActivity.HttpFixture site,NetworkOptimizationIntegrationActivity.HttpFixture plain,String cert,File directory){super(site,plain);}
    /* ACTUAL_PROBE_NETWORK_URL */
  }
  /* ACTUAL_STARTUP_FIXTURE */
  static JSONObject runCase(boolean scoped)throws Exception{
    Context context=new Context();ProbeFixture target=new ProbeFixture();
    StartupNetwork network=new StartupNetwork(context,new NetworkOptimizationIntegrationActivity.HttpFixture("https://127.0.0.1:9457"),new NetworkOptimizationIntegrationActivity.HttpFixture("http://127.0.0.1:9123"),"synthetic-unused-certificate",target);
    network.mode="winner-cleanup";RecoveryRoute recovery=scoped?new RecoveryRoute():null;network.expectedRecovery=recovery;
    String failure="";boolean completed=false,parentInterrupted=false;
    try{network.firstVerifiedRoute("",null,recovery);completed=true;}catch(Exception failed){failure=failed.getClass().getSimpleName();}
    finally{parentInterrupted=Thread.currentThread().isInterrupted();Thread.interrupted();network.probes.shutdownNow();network.closers.shutdownNow();network.probes.awaitTermination(2,TimeUnit.SECONDS);}
    return J.obj("completed",completed,"failure",failure,"scoped",scoped,"hookCalls",target.hookPaths.size(),"hookPaths",new JSONArray(target.hookPaths),"producerCalls",new JSONArray(network.producerCalls),"selected",network.selected,"selectionRecoverySame",network.selectionRecoverySame,"verifiedWinnerAt",network.verifiedWinnerAt,"parentInterruptedBeforeHostCleanup",parentInterrupted);
  }
  public static void main(String[] args)throws Exception{System.out.println(J.obj("unscoped",runCase(false),"scoped",runCase(true),"actualAndroidExecution",false,"actualNativeExecution",false,"actualSocketExecution",false));}
}
class NetworkOptimizationIntegrationActivity {
  static final class HttpFixture {final String origin;HttpFixture(String origin){this.origin=origin;}String url(String path){return origin+path;}}
  static class TestNetwork extends NativeNetwork {
    final HttpFixture site,plain;TestNetwork(HttpFixture site,HttpFixture plain){this.site=site;this.plain=plain;}
    /* ACTUAL_PARENT_URL */
  }
}
class J {static JSONObject obj(Object... pairs){JSONObject value=new JSONObject();try{for(int i=0;i<pairs.length;i+=2)value.put((String)pairs[i],pairs[i+1]);}catch(Exception failed){throw new RuntimeException(failed);}return value;}}
'''


def host_source(fixture):
    production=PRODUCTION.read_text();parent=PARENT.read_text()
    signatures=['  static final class RouteProbe','  RouteProbe startupProbe(String name,int index,String epoch)',
        '  RouteProbe startupProbe(String name,int index,String epoch,RecoveryRoute recovery)',
        '  void firstVerifiedRoute(String rejected)',
        '  void firstVerifiedRoute(String rejected,StartupRoute bootstrap)',
        '  void firstVerifiedRoute(String rejected,StartupRoute bootstrap,RecoveryRoute recovery)']
    selected={signature:block(production,signature) for signature in signatures}
    selected['parentUrl']=block(block(parent,'  static class TestNetwork '),'    @Override String probeUrl(')
    selected['probeNetworkUrl']=block(block(fixture,'  static class ProbeNetwork '),'    @Override String probeUrl(')
    selected['startupFixture']=block(fixture,'  static final class StartupNetwork ')
    result=HOST.replace('/* ACTUAL_PRODUCTION */','\n'.join(selected[s] for s in signatures))
    result=result.replace('/* ACTUAL_PARENT_URL */',selected['parentUrl']).replace('/* ACTUAL_PROBE_NETWORK_URL */',selected['probeNetworkUrl']).replace('/* ACTUAL_STARTUP_FIXTURE */',selected['startupFixture'])
    if any(result.count(body)!=1 for body in selected.values()):
        raise ValueError('A complete selected production/fixture block was rewritten or duplicated')
    return result,{signature:sha(body.encode()) for signature,body in selected.items()}


class StartupFixtureDispatchTest(unittest.TestCase):
    def test_actual_dispatch_and_fixture_recovery_forwarding(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java');self.assertTrue(java,'Java17 required')
        candidates=[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')]
        jar=next((Path(p) for p in candidates if p and Path(p).is_file()),None)
        self.assertIsNotNone(jar,'Existing host JSON dependency required')
        current=FIXTURE.read_text();old=original_fixture(current)
        mutant=current.replace(NEW_FORWARD,'super.startupProbe(name,index,epoch,null)',1)
        paths=[PRODUCTION,FIXTURE,PARENT,ROOT/'app/src/main/java/local/pocketchat/NetworkWork.java',HELPER,Path(__file__)]
        hashes={str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in paths};runs={}
        with tempfile.TemporaryDirectory(prefix='startup-dispatch-') as directory:
            root=Path(directory)
            for name,fixture in [('before',old),('current',current),('wrongForward',mutant)]:
                out=root/name;out.mkdir();source,blocks=host_source(fixture);(out/'NativeNetwork.java').write_text(source)
                clock=out/'SystemClock.java';clock.write_text('package android.os;public class SystemClock{public static long elapsedRealtime(){return System.nanoTime()/1000000;}}')
                compiled=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(out),str(out/'NativeNetwork.java'),str(clock),str(ROOT/'app/src/main/java/local/pocketchat/NetworkWork.java')],text=True,capture_output=True,timeout=30)
                self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
                ran=subprocess.run([java,'-cp',str(out)+os.pathsep+str(jar),'local.pocketchat.NativeNetwork'],text=True,capture_output=True,timeout=15)
                self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
                runs[name]=dict(report=json.loads(ran.stdout),selectedBlocksSha256=blocks,harnessSha256=sha(source.encode()),compileStdout=compiled.stdout,compileStderr=compiled.stderr,runtimeStdout=ran.stdout,runtimeStderr=ran.stderr)
        report=dict(sourceFiles=hashes,jsonJarSha256=sha(jar.read_bytes()),runs=runs,actualAndroidExecution=False,actualNativeExecution=False,actualSocketExecution=False,
            scope='Verbatim production full firstVerifiedRoute dispatch/startupProbe overloads, exact StartupNetwork and both actual parent probeUrl overrides; real Java executors/NetworkWork. Synthetic probe/exit/controller and Android context/clock boundaries. This verifies method dispatch, target URL and recovery reference forwarding only; no HEAD/socket/native acceptance.')
        self.assertTrue(all(sha((ROOT/path).read_bytes())==digest for path,digest in hashes.items()));report['executionInputsUnchanged']=True
        output=Path(os.environ.get('STARTUP_FIXTURE_DISPATCH_REPORT',str(ROOT/'work/profile-host/startup-fixture-dispatch-host-results.json')))
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        for scoped in ('unscoped','scoped'):
            baseline=runs['before']['report'][scoped]
            self.assertEqual(baseline['hookCalls'],0)
            self.assertTrue(baseline['completed'])
            self.assertEqual([row['target'] for row in baseline['producerCalls']],['http://127.0.0.1:9123/probe']*2)
            fixed=runs['current']['report'][scoped]
            self.assertTrue(fixed['completed'],fixed)
            self.assertEqual(fixed['selected'],'Entry|winner')
            self.assertEqual(fixed['hookCalls'],2)
            self.assertCountEqual(fixed['hookPaths'],['/startup-win','/startup-loser'])
            self.assertCountEqual([row['target'] for row in fixed['producerCalls']],['https://127.0.0.1:9456/startup-win','https://127.0.0.1:9456/startup-loser'])
            self.assertTrue(all(row['recoverySame'] is True for row in fixed['producerCalls']))
            self.assertTrue(fixed['selectionRecoverySame'])
            self.assertGreater(fixed['verifiedWinnerAt'],0)
            self.assertFalse(fixed['parentInterruptedBeforeHostCleanup'])
        rejected=runs['wrongForward']['report']['scoped']
        self.assertFalse(rejected['completed'])
        self.assertEqual(rejected['hookCalls'],2)
        self.assertTrue(all(row['recoverySame'] is False for row in rejected['producerCalls']))

    def test_only_the_fixture_override_and_super_forwarding_change(self):
        current=FIXTURE.read_text();self.assertEqual(current.count(NEW_OVERRIDE),1);self.assertEqual(current.count(NEW_FORWARD),1)
        self.assertEqual(sha(original_fixture(current).encode()),ORIGINAL_FIXTURE_SHA256)

    def test_native_head_timing_and_assertion_mutations_are_rejected(self):
        current=FIXTURE.read_text()
        for old,new in [('await(5,TimeUnit.SECONDS)','await(6,TimeUnit.SECONDS)'),('winner.get(6,TimeUnit.SECONDS)','winner.get(7,TimeUnit.SECONDS)'),('await(1500,TimeUnit.MILLISECONDS)','await(1600,TimeUnit.MILLISECONDS)'),('target.count("/startup-loser")==1','true'),('target.count("/startup-win")==2','true')]:
            self.assertIn(old,current)
            with self.subTest(mutation=old),self.assertRaises(ValueError):original_fixture(current.replace(old,new,1))


if __name__=='__main__':unittest.main()
