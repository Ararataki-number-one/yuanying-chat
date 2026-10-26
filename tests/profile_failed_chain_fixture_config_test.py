"""Exact production health/recovery/probe with fixture fault setup; JVM boundaries only."""
import hashlib,importlib.util,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
FIXTURE=ROOT/'tests/gecko/NetworkOptimizationIntegrationActivity.java'
HELPER=ROOT/'tools/gecko/run_network_core_host.py'
ORIGINAL_SHA='0d20c86583ba2dae72b6d89821e21461e949b200a1fc63bd327748403953fb53'
DISPLAY_OLD='String mode=n.settings.optString("entryMode");NetworkCatalog.put(n.settings,"entryMode","random");n.failures=1;'
DISPLAY_NEW='String mode=n.settings.optString("entryMode");n.failures=1;'
REPAIR_OLD='n.startNow();NetworkCatalog.put(n.settings,"entryMode","random");'
LEGACY_REPAIR_NEW='JSONObject savedRepairConfiguration=n.secrets.settings(),repairConfiguration=J.parse(savedRepairConfiguration.toString());NetworkCatalog.put(repairConfiguration,"entryMode","random");\n    try{\n    n.stopNow();n.secrets.save(repairConfiguration);n.startNow();'
LEGACY_REPAIR_RESTORE='\n    }finally{n.stopNow();n.secrets.save(savedRepairConfiguration);n.startNow();}'
REPAIR_NEW=LEGACY_REPAIR_NEW.replace('\n    try{','\n    Throwable repairFailure=null;\n    try{',1)
REPAIR_RESTORE='\n    }catch(Exception|Error failure){repairFailure=failure;throw failure;}\n    finally{try{n.stopNow();n.secrets.save(savedRepairConfiguration);n.startNow();}catch(Exception|Error restoreFailure){if(repairFailure==null)throw restoreFailure;if(restoreFailure!=repairFailure)repairFailure.addSuppressed(restoreFailure);}}'
ORACLE='Actual failed-chain recovery performs exactly one full exit verification for the new entry'

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
extract=module('one_exit_extract',HELPER);block=extract.block
suite=module('one_exit_recovery_suite',ROOT/'tests/network-recovery-host/run.py')
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def original_fixture(current):
 if sha(current.encode())==ORIGINAL_SHA:return current
 repair_setup,repair_restore=(REPAIR_NEW,REPAIR_RESTORE) if current.count(REPAIR_NEW)==1 else (LEGACY_REPAIR_NEW,LEGACY_REPAIR_RESTORE)
 if current.count(DISPLAY_NEW)!=1 or current.count(repair_setup)!=1 or current.count(repair_restore)!=1:raise ValueError('Fixture mode adapters missing')
 # The repair location is identified by its following exact identity capture.
 repair_new=repair_setup+'\n    final String token=n.token,entry=n.currentEntry;'
 repair_old=REPAIR_OLD+'\n    final String token=n.token,entry=n.currentEntry;'
 if current.count(repair_new)!=1:raise ValueError('Unique repair startup adapter missing')
 old=current.replace(DISPLAY_NEW,DISPLAY_OLD,1).replace(repair_new,repair_old,1).replace(repair_restore,'',1)
 if sha(old.encode())!=ORIGINAL_SHA:raise ValueError('Fixture changed outside its display mode fix and durable random setup/restore wrapper')
 return old

def display_fragment(fixture):
 method=block(fixture,'  void displaySchedulingChecks(')
 begin=method.index('String mode=n.settings.optString("entryMode");')
 line=next(line.strip() for line in method.splitlines() if 'check("'+ORACLE+'"' in line)
 end=method.index(line)
 predicate=line.split('",',1)[1][:-2]
 return method[begin:end]+'boolean oracle='+predicate+';',line

EXTRA=r'''
  static final String PROBE="https://www.gstatic.com/generate_204";
  final java.util.concurrent.atomic.AtomicLong probeSequence=new java.util.concurrent.atomic.AtomicLong();
  final ThreadLocal<ProbeTicket> probeTicket=new ThreadLocal<>();
  String exitIp="203.0.113.8",healthProbeRoute="";long healthProbeMeasurement;int optimizationRounds;boolean starting;
  JSONObject savedSettings,firstRecoveryControllerRead;final List<String> lifecycleEvents=new ArrayList<>();boolean streamOpen,restoreFailureArmed;Throwable injectedRestoreFailure;final Secrets secrets=new Secrets(this);HttpFixture siteForVerification;
  static final class Secrets {final NativeNetwork owner;byte[] bytes;Secrets(NativeNetwork owner){this.owner=owner;}byte[] get(String key){return bytes==null?null:bytes.clone();}void put(String key,byte[] value)throws Exception{String mode=J.parse(new String(value,StandardCharsets.UTF_8)).optString("entryMode");owner.lifecycleEvents.add("save:"+mode);if(owner.restoreFailureArmed&&owner.injectedRestoreFailure!=null&&mode.equals("latency")){if(owner.injectedRestoreFailure instanceof Exception)throw (Exception)owner.injectedRestoreFailure;throw (Error)owner.injectedRestoreFailure;}bytes=value.clone();}/* ACTUAL_SECRET_SERIALIZATION */}
  static final class HttpFixture {int ipDelay;String websiteTransportFailure="";final java.util.concurrent.atomic.AtomicInteger ipRequests=new java.util.concurrent.atomic.AtomicInteger(),forcedProbeFailures=new java.util.concurrent.atomic.AtomicInteger();}
  static final class Stream {final java.util.concurrent.atomic.AtomicInteger echoes=new java.util.concurrent.atomic.AtomicInteger();}
  static final class LifecycleStream implements AutoCloseable {final NativeNetwork owner;LifecycleStream(NativeNetwork owner){this.owner=owner;owner.streamOpen=true;owner.lifecycleEvents.add("stream-open");}public void close(){owner.streamOpen=false;owner.lifecycleEvents.add("stream-close");}}
  boolean backgroundIdle(){return false;}
  List<String> optimizationBatch(){return names;}
  void scanSubset(List<String> values,boolean force,boolean background){throw new AssertionError("Recovery must return before optional optimization");}
  String probeRouteKey(){return token+":"+routeSerial;}
  boolean stopNow(NetworkDiagnostics.Reason reason){clearReadyState();if(process!=null)process.destroy();return true;}
  boolean stopNow(){if(streamOpen)throw new AssertionError("Core restarted during the protected stream");lifecycleEvents.add("stop");clearReadyState();if(process!=null)process.destroy();return true;}
  void startNow(){if(streamOpen)throw new AssertionError("Core restarted during the protected stream");settings=secrets.settings();process=new Alive();verifiedRoute=new ExitRouteReceipt(this,null);ready=true;lifecycleEvents.add("start:"+settings.optString("entryMode"));}
  void recordProbe(ProbeResult sample,long now){}
  JSONObject api(String method,String path,JSONObject body,int timeout)throws Exception{
    maintenanceCheck();
    if(path.contains("/delay?")){
      ProbeTicket ticket=probeTicket.get();trace.add("probe:"+ticket.binding.entry);
      int delay=ticket.binding.current?-1:20;
      return J.obj("delay",delay,"probe",J.obj("schema",1,"kind","warm","firstMs",25,"warmMs",20,"totalMs",45,"warmAttempted",true,"warmSucceeded",true,"secondConnectionReused",true,"warmError","","firstStatus",204,"secondStatus",204));
    }
    if(path.startsWith("/proxies/ProbeExit")||path.equals("/proxies/FixedExit"))return J.obj("extra",J.obj(probeUrl(),J.obj("alive",true,"history",new JSONArray().put(J.obj("time",java.time.Instant.now().toString(),"delay",20)))));
    if(firstRecoveryControllerRead==null&&method.equals("GET")&&path.equals("/proxies/EntryChoice"))firstRecoveryControllerRead=J.obj("runtimeMode",settings.optString("entryMode"),"durableMode",secrets.settings().optString("entryMode"),"receiptMatchesRam",verifiedRoute!=null&&verifiedRoute.configuration.equals(transportFingerprint(settings)),"durableMatchesRam",configurationMatches());
    return selectionApi(method,path,body,timeout);
  }
  String verifyExit()throws Exception{
    verifications++;siteForVerification.ipRequests.incrementAndGet();trace.add("verify:"+currentEntry);
    verifiedRoute=new ExitRouteReceipt(this,transport==null?null:transport.state);admission=NetworkHealthPolicy.Admission.VERIFIED;lastVerified=System.currentTimeMillis();exitCheckFailures=0;nextExitCheckAt=0;return exitIp;
  }
  /* ACTUAL_ADDITIONAL_METHODS */
  static JSONObject replay(boolean before)throws Exception{
    NativeNetwork n=new NativeNetwork("one-entry-recovery");HttpFixture site=new HttpFixture(),plain=new HttpFixture();Stream stream=new Stream();
    // A synthetic core-start boundary, not a mutation of the Android fixture's
    // live receipt: each independent replay starts from the same applied tuple.
    n.settings=J.obj("entryMode","latency","subscriptionUrl","https://synthetic.invalid/unused","exitHost","127.0.0.1","exitPort",1080,"entryPool",new JSONArray().put("Entry|A").put("Entry|B"));
    n.savedSettings=new JSONObject(n.settings.toString());n.secrets.save(n.settings);n.names=Arrays.asList("Entry|A","Entry|B");n.currentEntry=n.controllerEntry="Entry|A";n.verifiedRoute=new ExitRouteReceipt(n,null);n.siteForVerification=site;
    String applied=n.verifiedRoute.configuration,entry=n.currentEntry;JSONObject evidence=new JSONObject();int echoes=0;
    if(before){/* BEFORE_FRAGMENT */}else{/* CURRENT_FRAGMENT */}
    JSONObject result=J.obj("oracle",evidence.optBoolean("oracle"),"exitRequests",site.ipRequests.get(),"verificationCalls",n.verifications,"entryChanged",!entry.equals(n.currentEntry),"selected",n.currentEntry,"verified",n.verifiedRouteCurrent(),"ready",n.ready,"coreAlive",n.coreAlive(),"message",n.message,"trace",new JSONArray(n.trace),"appliedFingerprint",applied,"durableFingerprint",transportFingerprint(n.secrets.settings()),"restoredRuntimeFingerprint",transportFingerprint(n.settings),"stateAtFirstRecoveryControllerRead",n.firstRecoveryControllerRead);
    n.close();return result;
  }
  static JSONObject repairReplay(boolean before)throws Exception{
    NativeNetwork n=new NativeNetwork("repair-backoff");HttpFixture site=new HttpFixture();n.siteForVerification=site;
    n.settings=J.obj("entryMode","latency","subscriptionUrl","https://synthetic.invalid/unused","exitHost","127.0.0.1","exitPort",1080,"entryPool",new JSONArray().put("Entry|A").put("Entry|B"));
    n.savedSettings=new JSONObject(n.settings.toString());n.secrets.save(n.settings);n.names=Arrays.asList("Entry|A","Entry|B");n.currentEntry=n.controllerEntry="Entry|A";n.verifiedRoute=new ExitRouteReceipt(n,null);n.lifecycleEvents.clear();
    JSONObject value;
    if(before){/* BEFORE_REPAIR_SETUP */value=repairExercise(n,site);}else{/* CURRENT_REPAIR_SETUP */value=repairExercise(n,site);value.put("cloneDistinct",savedRepairConfiguration!=repairConfiguration);value.put("savedSnapshotUnchanged",savedRepairConfiguration.toString().equals(n.savedSettings.toString()));/* CURRENT_REPAIR_RESTORE */}
    value.put("restoredRuntimeMode",n.settings.optString("entryMode"));value.put("restoredDurableMode",n.secrets.settings().optString("entryMode"));value.put("lifecycleCalls",new JSONArray(n.lifecycleEvents));n.close();return value;
  }
  static JSONObject repairExercise(NativeNetwork n,HttpFixture site)throws Exception{
    // The original repair case performs this intervening verification before
    // its backoff recovery. It can refresh a RAM-mode receipt, but not durable config.
    n.verifyExit();boolean receiptMatchesRam=n.verifiedRoute.configuration.equals(transportFingerprint(n.settings)),durableMatchesRam=n.configurationMatches();
    int ipBefore=site.ipRequests.get(),verificationsBefore=n.verifications;n.exitCheckFailures=1;n.nextExitCheckAt=android.os.SystemClock.elapsedRealtime()+60000;n.admission=NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION;n.failures=1;
    String inputMode=n.settings.optString("entryMode");n.health();return J.obj("exitRequestDelta",site.ipRequests.get()-ipBefore,"verificationDelta",n.verifications-verificationsBefore,"inputReceiptMatchesRam",receiptMatchesRam,"inputDurableMatchesRam",durableMatchesRam,"inputMode",inputMode,"ready",n.ready,"verified",n.verifiedRouteCurrent(),"entryChanged",!n.currentEntry.equals("Entry|A"),"detectorRetryReset",n.exitCheckFailures==0&&n.nextExitCheckAt==0,"message",n.message,"trace",new JSONArray(n.trace),"stateAtFirstRecoveryControllerRead",n.firstRecoveryControllerRead);
  }
  static JSONObject lifecycleReplay(boolean fail)throws Exception{
    NativeNetwork n=new NativeNetwork("lifecycle");n.secrets.save(J.obj("entryMode","latency","subscriptionUrl","https://synthetic.invalid/unused","exitHost","127.0.0.1","exitPort",1080,"entryPool",new JSONArray().put("Entry|A").put("Entry|B")));n.startNow();String original=n.secrets.settings().toString();n.lifecycleEvents.clear();boolean failed=false,cloneDistinct=false;JSONObject[] savedObject={null};
    try{/* CURRENT_REPAIR_SETUP */savedObject[0]=savedRepairConfiguration;cloneDistinct=savedRepairConfiguration!=repairConfiguration;n.lifecycleEvents.add("identity:"+n.settings.optString("entryMode"));try(LifecycleStream stream=new LifecycleStream(n)){if(fail)throw new IOException("controlled body failure");}/* CURRENT_REPAIR_RESTORE */}catch(IOException expected){failed=true;}
    JSONObject value=J.obj("failedBody",failed,"cloneDistinct",cloneDistinct,"savedObjectUnchanged",savedObject[0]!=null&&original.equals(savedObject[0].toString()),"runtimeMode",n.settings.optString("entryMode"),"durableMode",n.secrets.settings().optString("entryMode"),"configurationMatches",n.configurationMatches(),"calls",new JSONArray(n.lifecycleEvents));n.close();return value;
  }
  static JSONObject causeReplay(String scenario,boolean error)throws Exception{
    NativeNetwork n=new NativeNetwork("cause");n.secrets.save(J.obj("entryMode","latency","subscriptionUrl","https://synthetic.invalid/unused","exitHost","127.0.0.1","exitPort",1080,"entryPool",new JSONArray().put("Entry|A").put("Entry|B")));n.startNow();n.lifecycleEvents.clear();
    Throwable body=(scenario.equals("body-only")||scenario.equals("both")||scenario.equals("same-reference"))?(error?new AssertionError("controlled body error"):new IOException("controlled body failure")):null;
    Throwable restore=(scenario.equals("restore-only")||scenario.equals("both"))?(error?new AssertionError("controlled restore error"):new IOException("controlled restore failure")):scenario.equals("same-reference")?body:null;
    Throwable observed=null;
    try{/* CURRENT_REPAIR_SETUP */n.injectedRestoreFailure=restore;n.restoreFailureArmed=true;n.lifecycleEvents.add("identity:"+n.settings.optString("entryMode"));try(LifecycleStream stream=new LifecycleStream(n)){if(body instanceof Exception)throw (Exception)body;if(body instanceof Error)throw (Error)body;}/* CURRENT_REPAIR_RESTORE */}catch(Exception|Error failure){observed=failure;}
    Throwable[] suppressed=observed==null?new Throwable[0]:observed.getSuppressed();JSONObject result=J.obj("scenario",scenario,"kind",error?"Error":"Exception","observed",observed==null?"":observed.toString(),"observedIsBody",body!=null&&observed==body,"observedIsRestore",restore!=null&&observed==restore,"suppressedCount",suppressed.length,"suppressedIsRestore",suppressed.length==1&&suppressed[0]==restore,"runtimeMode",n.settings.optString("entryMode"),"durableMode",n.secrets.settings().optString("entryMode"),"calls",new JSONArray(n.lifecycleEvents));n.close();return result;
  }
  public static void main(String[] args)throws Exception{JSONArray causes=new JSONArray();for(boolean error:new boolean[]{false,true})for(String scenario:new String[]{"normal","body-only","restore-only","both","same-reference"})causes.put(causeReplay(scenario,error));System.out.println(J.obj("before",replay(true),"current",replay(false),"beforeRepair",repairReplay(true),"currentRepair",repairReplay(false),"lifecycleSuccess",lifecycleReplay(false),"lifecycleFailure",lifecycleReplay(true),"failureCauses",causes,"actualAndroidExecution",false,"actualNativeExecution",false,"actualSocketExecution",false));}
'''

def generated(fixture):
 source=(PRODUCTION/'NativeNetwork.java').read_text();harness,classes,methods=suite.production_harness(source)
 removed=['  static class Binding ','  static class ProbeResult ','  ProbeResult probeMeasured(String proxy,String entry)','  ProbeResult probeMeasured(String proxy,String entry,RecoveryRoute recovery)','  boolean probeCurrent(','  void recordProbe(','  String verifyExit(','  boolean configurationMatches(','  static String transportFingerprint(','  public static void main(']
 for signature in removed:harness=harness.replace(block(harness,signature),'')
 harness=harness.replace('  JSONObject api(','  JSONObject selectionApi(',1)
 selected=['  static final class ProbeTicket ','  static final class ProbeResult ','  ProbeResult probeMeasured(String proxy,String exactEntry)','  ProbeResult probeMeasured(String proxy,String exactEntry,RecoveryRoute recovery)','  boolean probeCurrent(','  boolean probeBindingCurrent(','  boolean probeCallCurrent(','  static LatencyProbePolicy.Trace probeTrace(','  int probe(','  String probeUrl(',
 '  void health()','  void health(boolean reuseRecent)','  boolean configurationMatches(','  static String transportFingerprint(','  static boolean subscribedExit(','  static String hash(','  boolean lowLatency(','  static boolean freshLatency(','  boolean maintenanceCancelled(','  boolean cancelledVerifiedRouteCurrent(','  boolean retainedFailure(','  boolean retainVerifiedRoute(','  void verifyExitWhenDue(']
 bodies={signature:block(source,signature) for signature in selected}
 extra=EXTRA.replace('/* ACTUAL_ADDITIONAL_METHODS */','\n'.join(bodies.values()))
 old=original_fixture(fixture);before,_=display_fragment(old);current,oracle=display_fragment(fixture)
 # The Boolean is the unchanged exact Android predicate, recorded after replay.
 before=before+'NetworkCatalog.put(evidence,"oracle",oracle);'
 current=current+'NetworkCatalog.put(evidence,"oracle",oracle);'
 old_repair=block(old,'  void networkRepairChecks(');current_repair=block(fixture,'  void networkRepairChecks(')
 old_setup=old_repair[old_repair.index('n.startNow();'):old_repair.index('\n    final String token=n.token,entry=n.currentEntry;')]
 setup=current_repair[current_repair.index('JSONObject savedRepairConfiguration='):current_repair.index('\n    final String token=n.token,entry=n.currentEntry;')]
 restore=(REPAIR_RESTORE if REPAIR_RESTORE in current_repair else LEGACY_REPAIR_RESTORE).strip()
 secret=(PRODUCTION/'SecretStore.java').read_text();serialization=block(secret,'  JSONObject settings()')+'\n'+block(secret,'  void save(JSONObject o)')
 extra=extra.replace('/* BEFORE_FRAGMENT */',before).replace('/* CURRENT_FRAGMENT */',current).replace('/* BEFORE_REPAIR_SETUP */',old_setup).replace('/* CURRENT_REPAIR_SETUP */',setup).replace('/* CURRENT_REPAIR_RESTORE */',restore).replace('/* ACTUAL_SECRET_SERIALIZATION */',serialization)
 harness=harness.replace('  static class ExitMismatch ',extra+'\n  static class ExitMismatch ',1).replace('import java.io.*;','import java.io.*;\nimport java.net.*;\nimport java.time.Instant;\nimport java.nio.charset.StandardCharsets;')
 harness=harness.replace('class J {','class J {'+block((PRODUCTION/'J.java').read_text(),'  static JSONObject parse('),1)
 strings=block((PRODUCTION/'EntrySelection.java').read_text(),'  static List<String> strings(')
 keys=block((PRODUCTION/'NetworkSourceSelection.java').read_text(),'  static List<String> keys(')
 harness+='\nclass EntrySelection {'+strings+'}\nclass NetworkSourceSelection {'+keys+'}\nclass NetworkCatalog {static void put(JSONObject value,String key,Object data){try{value.put(key,data);}catch(Exception error){throw new RuntimeException(error);}}}\n'
 if any(harness.count(body)!=1 for body in bodies.values()):raise ValueError('Complete production health/probe/config/recovery block drifted')
 return harness,{name:sha(body.encode()) for name,body in bodies.items()},oracle

class FailedChainFixtureConfigTest(unittest.TestCase):
 def test_exact_health_and_fixture_case_keep_one_exit_verification(self):
  java=os.environ.get('PROFILE_JAVA') or shutil.which('java');self.assertTrue(java)
  candidates=[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')]
  jar=next((Path(p) for p in candidates if p and Path(p).is_file()),None);self.assertIsNotNone(jar)
  source,blocks,oracle=generated(FIXTURE.read_text());production=[PRODUCTION/name for name in ('NetworkHealthPolicy.java','NetworkOptimizationPolicy.java','NetworkWork.java','NetworkDiagnostics.java','LatencyProbePolicy.java','LatencyRefreshPolicy.java','Sha256.java')]
  paths=[*production,PRODUCTION/'NativeNetwork.java',PRODUCTION/'EntrySelection.java',PRODUCTION/'NetworkSourceSelection.java',PRODUCTION/'SecretStore.java',PRODUCTION/'J.java',FIXTURE,HELPER,ROOT/'tests/network-recovery-host/run.py',ROOT/'tests/network-recovery-host/RecoverySearchHarness.java.txt',Path(__file__)]
  hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
  with tempfile.TemporaryDirectory(prefix='one-exit-recovery-') as temp:
   out=Path(temp);(out/'NativeNetwork.java').write_text(source);clock=out/'SystemClock.java';clock.write_text('package android.os;public class SystemClock{public static long offset;public static long elapsedRealtime(){return System.nanoTime()/1000000+offset;}public static void advance(long value){offset+=value;}}')
   compiled=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(out),str(out/'NativeNetwork.java'),str(clock),*map(str,production)],text=True,capture_output=True,timeout=30);self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
   ran=subprocess.run([java,'-cp',str(out)+os.pathsep+str(jar),'local.pocketchat.NativeNetwork'],text=True,capture_output=True,timeout=15);self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
  value=json.loads(ran.stdout);value.update(sourceFiles=hashes,selectedBlocksSha256=blocks,unchangedAndroidOracle=oracle,harnessSha256=sha(source.encode()),jsonJarSha256=sha(jar.read_bytes()),compileStdout=compiled.stdout,compileStderr=compiled.stderr,runtimeStdout=ran.stdout,runtimeStderr=ran.stderr,
   scope='Complete production health, recovery/search/selection, probe producer and low-level interpretation, real configuration fingerprint and durable comparison. Exact original/current Android fault setup/predicate. Core-start/SecretStore/controller/probe response/exit-request and Android platform boundaries are synthetic; real executors/NetworkWork. No actual sockets, WSS, native or Android acceptance.',
   controlledSecondaryHealth='Always returns TRANSPORT_UNAVAILABLE to represent the injected target transport failure; no secondary socket.',
   controlledReceiptRead='Fixture verifiedRouteCurrent helper uses the actual extracted ExitRouteReceipt.matches/sameCore; no fresh service IPC.',
   syntheticExitCounterMeaning='Counts controlled verifyExit callback invocations, not actual HTTP IP requests; ipDelay/fault setup is replayed but does not drive transport timing.',
   unexecutedContinuingRepairPath='The forced scan/rollback flow is not executed by this host. Repair retains its original random branch through a durable save and genuine Android stop/start in the fixture; host lifecycle start/stop and stream are adapters. Original native rollback/WSS gates remain required.',
   secretSerializationScope='Actual SecretStore.settings/save and J.parse bodies execute; encrypted backing storage and core start/stop remain controlled host adapters.')
  self.assertTrue(all(sha((ROOT/path).read_bytes())==digest for path,digest in hashes.items()));value['executionInputsUnchanged']=True
  report=Path(os.environ.get('FAILED_CHAIN_FIXTURE_CONFIG_REPORT',str(ROOT/'work/profile-host/failed-chain-fixture-config-results.json')));report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
  self.assertEqual(value['before']['exitRequests'],0);self.assertEqual(value['before']['verificationCalls'],0);self.assertFalse(value['before']['ready']);self.assertFalse(value['before']['oracle'])
  self.assertEqual(value['current']['exitRequests'],1);self.assertEqual(value['current']['verificationCalls'],1);self.assertTrue(value['current']['oracle']);self.assertTrue(value['current']['entryChanged']);self.assertTrue(value['current']['verified']);self.assertTrue(value['current']['coreAlive'])
  self.assertTrue(value['beforeRepair']['inputReceiptMatchesRam']);self.assertFalse(value['beforeRepair']['inputDurableMatchesRam']);self.assertEqual(value['beforeRepair']['exitRequestDelta'],0);self.assertFalse(value['beforeRepair']['ready'])
  self.assertTrue(value['currentRepair']['inputReceiptMatchesRam']);self.assertTrue(value['currentRepair']['inputDurableMatchesRam']);self.assertEqual(value['currentRepair']['exitRequestDelta'],1);self.assertEqual(value['currentRepair']['verificationDelta'],1);self.assertTrue(value['currentRepair']['entryChanged']);self.assertTrue(value['currentRepair']['verified']);self.assertTrue(value['currentRepair']['detectorRetryReset'])
  self.assertEqual(value['currentRepair']['inputMode'],'random');self.assertEqual(value['currentRepair']['restoredRuntimeMode'],'latency');self.assertEqual(value['currentRepair']['restoredDurableMode'],'latency');self.assertTrue(value['currentRepair']['cloneDistinct']);self.assertTrue(value['currentRepair']['savedSnapshotUnchanged'])
  for key,failed in [('lifecycleSuccess',False),('lifecycleFailure',True)]:
   lifecycle=value[key];self.assertEqual(lifecycle['failedBody'],failed);self.assertTrue(lifecycle['cloneDistinct']);self.assertTrue(lifecycle['savedObjectUnchanged']);self.assertEqual(lifecycle['runtimeMode'],'latency');self.assertEqual(lifecycle['durableMode'],'latency');self.assertTrue(lifecycle['configurationMatches']);self.assertEqual(lifecycle['calls'],['stop','save:random','start:random','identity:random','stream-open','stream-close','stop','save:latency','start:latency'])
  self.assertEqual(len(value['failureCauses']),10)
  for row in value['failureCauses']:
   with self.subTest(kind=row['kind'],scenario=row['scenario']):
    scenario=row['scenario'];self.assertEqual(row['calls'][:6],['stop','save:random','start:random','identity:random','stream-open','stream-close'])
    if scenario=='normal':self.assertEqual(row['observed'],'');self.assertEqual(row['suppressedCount'],0)
    elif scenario=='restore-only':self.assertTrue(row['observedIsRestore']);self.assertFalse(row['observedIsBody']);self.assertEqual(row['suppressedCount'],0)
    else:self.assertTrue(row['observedIsBody']);self.assertEqual(row['suppressedCount'],1 if scenario=='both' else 0);self.assertEqual(row['suppressedIsRestore'],scenario=='both')
    self.assertEqual(row['durableMode'],'latency' if scenario in ('normal','body-only') else 'random')
    self.assertEqual(row['calls'][6:],['stop','save:latency','start:latency'] if scenario in ('normal','body-only') else ['stop','save:latency'])
 def test_complete_fixture_inverse_preserves_every_original_gate(self):
  current=FIXTURE.read_text();self.assertTrue(DISPLAY_OLD not in current,'Display fault setup still mutates only RAM mode');self.assertTrue(REPAIR_OLD not in current,'Repair startup still mutates only RAM mode');self.assertEqual(current.count(REPAIR_NEW),1,'Primary failure capture must be present');self.assertEqual(current.count(REPAIR_RESTORE),1,'Restoration must retain primary/suppressed causes');self.assertEqual(sha(original_fixture(current).encode()),ORIGINAL_SHA)
 def test_one_exit_oracle_and_wss_timeout_mutations_are_rejected(self):
  current=FIXTURE.read_text()
  for old,new in [('site.ipRequests.get()==ipBefore+1','site.ipRequests.get()==ipBefore+2'),('stream.awaitEchoes(echoes)&&stream.failure==null','true'),('site.ipDelay=250','site.ipDelay=249'),('repairConfiguration=J.parse(savedRepairConfiguration.toString())','repairConfiguration=savedRepairConfiguration'),('n.stopNow();n.secrets.save(repairConfiguration);n.startNow();','n.stopNow();n.startNow();n.secrets.save(repairConfiguration);'),('if(restoreFailure!=repairFailure)','if(true)'),('repairFailure.addSuppressed(restoreFailure)','restoreFailure.addSuppressed(repairFailure)')]:
   self.assertIn(old,current)
   with self.subTest(mutation=old),self.assertRaises(ValueError):original_fixture(current.replace(old,new,1))

if __name__=='__main__':unittest.main()
