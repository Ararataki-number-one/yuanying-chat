"""Diagnostic-only native-window observations; no Android or Gecko executes here."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE='44e686fd39a1ecbe0085f0d1b58400d79b8df9dd'
# Complete 3,759-byte declaration extracted from that actual public source.
# CI needs only the source-bound pin, never a parent Git object or network fetch.
BASE_METHOD_SHA256='570704b36cfcf76ead2abe4c3826880218592bd7db7eb1330163a4245600d5a6'
SOURCE=ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java'
EXTRACTOR=ROOT/'tests/gecko-timezone-flow-host/run.py'
spec=importlib.util.spec_from_file_location('window_diagnostic_actual_members',EXTRACTOR)
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
MARKERS=('static final class TimeZoneWindowDiagnostic {','TimeZoneWindowDiagnostic diagnosticWindowStart(',
         'void diagnosticComplete(','private void startTimeZone(')
JAVA_HOME=None;JARS=[];OUTPUT=None

def sha(raw):return hashlib.sha256(raw).hexdigest()

def inverse_start(current):
    """Remove only the declared observations; preserve the entire original method."""
    changes=[
        ('    final TimeZoneWindowDiagnostic diagnostic=diagnosticWindowStart(revalidate);final String[] diagnosticCaller={"none"};\n',''),
        ('if(!once.compareAndSet(false,true))return;diagnostic.reason=diagnosticCaller[0];diagnostic.received=ready;','if(!once.compareAndSet(false,true))return;'),
        ('diagnosticComplete(window,diagnostic,ready&&timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port);','window.complete(ready&&timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port);'),
        ('finished.accept(false);diagnosticCaller[0]="revalidate-error";windowReady.accept(false);return;','finished.accept(false);windowReady.accept(false);return;'),
        ('        diagnostic.consumer=ready;\n',''),
        ('deadline[0]=()->{diagnosticCaller[0]="timeout";windowReady.accept(false);};','deadline[0]=()->windowReady.accept(false);'),
        ('try{session.getUserAgent().accept(value->{diagnosticCaller[0]="success";windowReady.accept(true);},error->{diagnosticCaller[0]="error";windowReady.accept(false);});}catch(RuntimeException unavailable){diagnosticCaller[0]="throw";windowReady.accept(false);}',
         'try{session.getUserAgent().accept(value->windowReady.accept(true),error->windowReady.accept(false));}catch(RuntimeException unavailable){windowReady.accept(false);}')]
    for before,after in changes:
        if current.count(before)!=1:raise ValueError('One exact diagnostic-only startTimeZone hunk required')
        current=current.replace(before,after,1)
    if len(current.encode())!=3759 or sha(current.encode())!=BASE_METHOD_SHA256:raise ValueError('Diagnostic inverse differs from complete original public method')
    return current


HOST=r'''package local.pocketchat;
import java.io.*;import java.util.*;import java.util.function.*;
public final class WindowDiagnosticHost {
 static int checks;static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks++;}
 static final class Fixture {
  final GeckoWebView w=new GeckoWebView();final SessionBoundary session=new SessionBoundary();
  Fixture(){w.start(session,false);}
  GeckoWebView.TimeZoneWindowDiagnostic row(){return w.timeZoneWindowDiagnostics.get(0);}
  void complete(boolean success){if(success)session.sdk.success.accept("sdk-boundary");else session.sdk.failure.accept(new IOException("explicit SDK failure"));}
 }
 static void observed(String kind){
  Fixture f=new Fixture();Runnable deadline=f.w.owner.handler.scheduled.get(0);
  if(kind.equals("success"))f.complete(true);else if(kind.equals("error"))f.complete(false);else deadline.run();
  boolean expected=kind.equals("success");GeckoWebView.TimeZoneWindowDiagnostic row=f.row();ResultBoundary<?> window=ResultBoundary.last;
  check("Actual completed Boolean is preserved: "+kind,window.completions==1&&Boolean.valueOf(expected).equals(window.value)&&Boolean.valueOf(expected).equals(row.ready));
  check("Reason and first consumer observe the original value: "+kind,row.completed&&row.reason.equals(kind)&&Boolean.valueOf(expected).equals(row.consumer)&&Boolean.valueOf(expected).equals(row.received));
  check("Original first consumer preserves manual-system fallback even when window is false: "+kind,f.w.owner.timeZone.prepares==1&&f.w.finished==0);
  int[] read={0};f.w.owner.timeZone.access.read("token",value->read[0]=1,error->read[0]=-1);
  check("Original secondary request still guards a false window: "+kind,expected?read[0]==1&&f.w.sent==1:read[0]==-1&&f.w.sent==0);
  f.complete(!expected);deadline.run();
  check("Late SDK and deadline cannot overwrite CAS winner: "+kind,window.completions==1&&Boolean.valueOf(expected).equals(row.ready)&&row.reason.equals(kind)&&Boolean.valueOf(expected).equals(row.consumer)&&f.w.owner.timeZone.prepares==1);
 }
 static void stale(String kind){
  Fixture f=new Fixture();GeckoWebView.TimeZoneGate gate=f.w.timeZoneGates.get(f.session);
  if(kind.equals("alive"))f.w.alive=false;
  else if(kind.equals("gate"))f.w.timeZoneGates.put(f.session,new GeckoWebView.TimeZoneGate());
  else if(kind.equals("document"))gate.documentSerial++;
  else if(kind.equals("null-port"))f.w.routePort=null;
  else if(kind.equals("port"))f.w.routePort=new PortBoundary();
  f.complete(true);
  check("Original complete RHS rejects stale authority: "+kind,Boolean.TRUE.equals(f.row().received)&&Boolean.FALSE.equals(f.row().ready)&&Boolean.FALSE.equals(ResultBoundary.last.value)&&Boolean.FALSE.equals(f.row().consumer));
  check("Original consumer current guard remains authoritative: "+kind,f.w.owner.timeZone.prepares==0);
 }
 public static void main(String[] args){
  observed("success");observed("error");observed("timeout");
  for(String kind:new String[]{"alive","gate","document","null-port","port"})stale(kind);
  GeckoWebView thrown=new GeckoWebView();SessionBoundary bad=new SessionBoundary();bad.throwUa=true;thrown.start(bad,false);
  check("Synchronous SDK throw is observed without changing completion",thrown.timeZoneWindowDiagnostics.get(0).reason.equals("throw")&&Boolean.FALSE.equals(ResultBoundary.last.value)&&thrown.owner.timeZone.prepares==1);
  GeckoWebView revalidated=new GeckoWebView();revalidated.owner.timeZone.throwRevalidate=true;revalidated.start(new SessionBoundary(),true);
  GeckoWebView.TimeZoneWindowDiagnostic row=revalidated.timeZoneWindowDiagnostics.get(0);
  check("Revalidate error remains a single false completion without first consumer",row.revalidate&&row.reason.equals("revalidate-error")&&Boolean.FALSE.equals(row.ready)&&row.consumer==null&&ResultBoundary.last.completions==1&&revalidated.finished==1&&revalidated.owner.handler.scheduled.isEmpty());
  GeckoWebView bounded=new GeckoWebView();for(int i=0;i<10020;i++)bounded.diagnosticWindowStart(i%2==0);
  check("Observer history and sequence are bounded",bounded.timeZoneWindowDiagnostics.size()==8&&bounded.timeZoneWindowDiagnosticSequence==10000&&bounded.timeZoneWindowDiagnostics.get(0).sequence<=10000);
  System.out.println("{\"status\":\"passed\",\"checks\":"+checks+"}");
 }
}
final class GeckoWebView {
 final OwnerBoundary owner=new OwnerBoundary();final Map<SessionBoundary,TimeZoneGate> timeZoneGates=new IdentityHashMap<>();final Set<SessionBoundary> popups=Collections.newSetFromMap(new IdentityHashMap<>());PortBoundary routePort=new PortBoundary();final MetadataBoundary metadata=new MetadataBoundary();boolean alive=true,ipRouteNeedsReload;int sent,finished;
 static final class TimeZoneGate {long documentSerial;boolean ready,preparing,revalidating;final String epoch="epoch";final List<Consumer<Boolean>> waiting=new ArrayList<>();}
 boolean timeZoneSessionAlive(SessionBoundary session){return alive;}boolean timeZoneAllows(SessionBoundary session){return false;}boolean autoIpMode(){return false;}String ipRouteStamp(){return "route";}
 void lookupIpTimeZone(SessionBoundary session,TimeZoneGate gate,String token,Consumer<String> ok,Consumer<Throwable> fail){throw new AssertionError("No network boundary is invoked in this observer host");}
 void sendTimeZone(PortBoundary port,SessionBoundary session,TimeZoneGate gate,String kind,String zone,String token,Consumer<String> ok,Consumer<Throwable> fail){sent++;ok.accept("explicit host-only native response");}
 void finishTimeZone(SessionBoundary session,TimeZoneGate gate,boolean ok){finished++;}void completeTimeZoneProofs(TimeZoneGate gate,boolean ok){}void completeTimeZoneRequests(TimeZoneGate gate,boolean ok){}Object timeZoneStatus(){return null;}
 void start(SessionBoundary session,boolean revalidate){startTimeZone(session,ignored->{},revalidate);}
 @FIELDS@
 @METHODS@
}
final class OwnerBoundary {final HandlerBoundary handler=new HandlerBoundary();final ControllerBoundary timeZone=new ControllerBoundary();final GuardBoundary guard=new GuardBoundary();}
final class GuardBoundary {boolean allowed(){return true;}}
final class MetadataBoundary {Object timeZonePolicy;}
final class PortBoundary {}
final class IdentityBoundary {static String id(SessionBoundary session){return "explicit-session-boundary";}}
final class SessionBoundary {final SdkBoundary sdk=new SdkBoundary();boolean throwUa;SdkBoundary getUserAgent(){if(throwUa)throw new IllegalStateException("explicit SDK throw");return sdk;}}
final class SdkBoundary {Consumer<String> success;Consumer<Throwable> failure;void accept(Consumer<String> ok,Consumer<Throwable> fail){success=ok;failure=fail;}}
final class HandlerBoundary {final List<Runnable> scheduled=new ArrayList<>();final Set<Runnable> active=new HashSet<>();void postDelayed(Runnable task,long delay){if(delay!=5000)throw new AssertionError("Original SDK-window deadline changed");scheduled.add(task);active.add(task);}void removeCallbacks(Runnable task){active.remove(task);}}
final class ResultBoundary<T> {static ResultBoundary<?> last;T value;int completions;final List<Consumer<T>> consumers=new ArrayList<>();ResultBoundary(){last=this;}void complete(T result){completions++;value=result;for(Consumer<T> next:List.copyOf(consumers))next.accept(result);}void accept(Consumer<T> done,Consumer<Throwable> failure){if(completions>0)done.accept(value);else consumers.add(done);}}
final class GeckoTimeZoneController {interface NativeAccess {boolean current();String ipRouteStamp();void lookupIp(String token,Consumer<String> ok,Consumer<Throwable> fail);void read(String token,Consumer<String> ok,Consumer<Throwable> fail);void apply(String zone,String token,Consumer<String> ok,Consumer<Throwable> fail);}}
final class ControllerBoundary {int prepares;boolean throwRevalidate;GeckoTimeZoneController.NativeAccess access;boolean popupAllowed(){return true;}void prepare(SessionBoundary session,String id,String epoch,GeckoTimeZoneController.NativeAccess access,Consumer<Boolean> finished){prepares++;this.access=access;}void revalidate(SessionBoundary session,String id,String epoch,GeckoTimeZoneController.NativeAccess access,Consumer<Boolean> finished){if(throwRevalidate)throw new IllegalStateException("explicit revalidate failure");this.access=access;}}
'''


class WindowDiagnosticTest(unittest.TestCase):
    def test_complete_original_start_method_is_restored_verbatim(self):
        current=extract.block(SOURCE.read_text(),'private void startTimeZone(')
        original=inverse_start(current)
        self.assertIn('window.accept(ready->{\n        if(!access.current())',original)
        self.assertNotIn('if(!ready||!access.current()){finished.accept(false)',original)
        self.assertIn('owner.handler.postDelayed(deadline[0],5000)',original)

    def test_unapproved_decision_budget_or_guard_changes_are_rejected(self):
        current=extract.block(SOURCE.read_text(),'private void startTimeZone(')
        for before,after in [('        if(!access.current()){finished.accept(false);return;}','        if(false){finished.accept(false);return;}'),('postDelayed(deadline[0],5000)','postDelayed(deadline[0],6000)'),('diagnosticComplete(window,diagnostic,ready&&timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null','diagnosticComplete(window,diagnostic,ready&&timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&port!=null'),('        diagnostic.consumer=ready;','        diagnostic.consumer=ready;\n        if(!ready)return;')]:
            self.assertEqual(current.count(before),1)
            with self.subTest(change=after),self.assertRaises(ValueError):inverse_start(current.replace(before,after,1))

    def test_actual_extracted_java_completion_cas_late_callbacks_and_observer_only_consumer(self):
        source=SOURCE.read_text();members={marker:extract.block(source,marker) for marker in MARKERS}
        fields=re.findall(r'^  final ArrayList<TimeZoneWindowDiagnostic> timeZoneWindowDiagnostics=.*;$',source,re.MULTILINE)
        self.assertEqual(len(fields),1)
        if JAVA_HOME is not None:java=JAVA_HOME/'bin/java'
        elif os.environ.get('PROFILE_JAVA'):java=Path(os.environ['PROFILE_JAVA'])
        elif os.environ.get('PROFILE_JAVA_HOME'):java=Path(os.environ['PROFILE_JAVA_HOME'])/'bin/java'
        elif os.environ.get('JAVA_HOME'):java=Path(os.environ['JAVA_HOME'])/'bin/java'
        else:java=Path(shutil.which('java') or '')
        javac=java.with_name('javac');self.assertTrue(java.is_file() and javac.is_file(),'JDK17 required')
        jars=JARS or [Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/gecko-integration/catalog-json.jar')),Path(os.environ.get('PROFILE_ANDROID_JSON_JAR',ROOT/'work/profile-host/android-json.jar'))]
        self.assertEqual(len(jars),2,'Both real JSON variants are required')
        inputs=[SOURCE,EXTRACTOR,Path(__file__).resolve()];hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in inputs};runs=[];controls=[]
        target=OUTPUT or ROOT/'work/ip-timezone-window-diagnostic/results.json';target.parent.mkdir(parents=True,exist_ok=True)
        artifacts=target.parent/'window-diagnostic-artifacts';artifacts.mkdir(exist_ok=True)
        replacements=[('WebExtension.Port','PortBoundary'),('GeckoSession','SessionBoundary'),('GeckoResult','ResultBoundary'),('AppSessionIdentity','IdentityBoundary')]
        for label,jar in zip(('desktop','android-json'),jars):
            self.assertTrue(jar.is_file(),str(jar))
            selected=[('current',members),('completion-mutant',dict(members,**{'void diagnosticComplete(':members['void diagnosticComplete('].replace('window.complete(result);','window.complete(!result);',1)})),('cas-mutant',dict(members,**{'private void startTimeZone(':members['private void startTimeZone('].replace('if(!once.compareAndSet(false,true))return;','once.compareAndSet(false,true);',1)}))]
            for variant,methods in selected:
                with tempfile.TemporaryDirectory(prefix='timezone-window-observer-') as temporary:
                    folder=Path(temporary);host=HOST.replace('@FIELDS@',fields[0]).replace('@METHODS@','\n'.join(methods.values()))
                    for before,after in replacements:host=host.replace(before,after)
                    path=folder/'WindowDiagnosticHost.java';path.write_text(host);out=artifacts/(label+'-'+variant);out.mkdir(exist_ok=True);(out/'WindowDiagnosticHost.java').write_text(host)
                    compile_command=[str(javac),'--release','17','-encoding','UTF-8','-cp',str(jar.resolve()),'-d',str(folder/'classes'),str(path)]
                    built=subprocess.run(compile_command,capture_output=True,text=True,timeout=30)
                    (out/'compile.stdout.log').write_text(built.stdout);(out/'compile.stderr.log').write_text(built.stderr);self.assertEqual(built.returncode,0,built.stdout+built.stderr)
                    command=[str(java),'-cp',str(folder/'classes')+os.pathsep+str(jar.resolve()),'local.pocketchat.WindowDiagnosticHost']
                    ran=subprocess.run(command,capture_output=True,text=True,timeout=15);(out/'run.stdout.log').write_text(ran.stdout);(out/'run.stderr.log').write_text(ran.stderr)
                    if variant=='current':
                        self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr);runs.append(dict(jsonVariant=label,jsonJarSha256=sha(jar.read_bytes()),hostSha256=sha(host.encode()),report=json.loads(ran.stdout)))
                    else:
                        assertion='Actual completed Boolean is preserved: success' if variant=='completion-mutant' else 'Late SDK and deadline cannot overwrite CAS winner: success'
                        self.assertEqual(ran.returncode,1);self.assertIn('java.lang.AssertionError: '+assertion,ran.stderr);controls.append(dict(jsonVariant=label,variant=variant,compiled=True,assertion=assertion,hostSha256=sha(host.encode())))
        self.assertTrue(all(sha(p.read_bytes())==hashes[str(p.relative_to(ROOT))] for p in inputs))
        report=dict(schema=1,status='passed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),basePublicCommit=BASE,sourceFiles=hashes,productionMethodSha256={marker:sha(body.encode()) for marker,body in members.items()},diagnosticFieldsSha256=sha(fields[0].encode()),originalStartSha256=sha(inverse_start(members['private void startTimeZone(']).encode()),executionInputsUnchanged=True,runs=runs,compiledSemanticMutants=controls,actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimeZoneExecution=False,actualNetworkExecution=False,manualSystemFallbackChanged=False,scope='Actual startTimeZone and diagnostic class/helpers/fields extracted verbatim, with SDK/session/result/Handler/controller/native-send boundaries explicitly controlled. Original first consumer may continue on false window for manual-system fallback; this test observes that unchanged decision. Original RHS, CAS winner, late callback rejection, observer bounds and single completion execute. No Android, Gecko, native timezone setter, public geolocation or policy acceptance is inferred.')
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--java-home',type=Path);parser.add_argument('--json-jar',type=Path);parser.add_argument('--android-json-jar',type=Path);parser.add_argument('--output',type=Path)
    args,remaining=parser.parse_known_args();JAVA_HOME=args.java_home;OUTPUT=args.output
    if args.json_jar is not None or args.android_json_jar is not None:
        if args.json_jar is None or args.android_json_jar is None:parser.error('Both --json-jar and --android-json-jar are required')
        JARS=[args.json_jar,args.android_json_jar]
    unittest.main(argv=[sys.argv[0],*remaining])
