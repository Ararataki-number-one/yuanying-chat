"""Verbatim fixture handoff and production recovery tokens; no Android claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/gecko/NetworkSourcesRouteIntegrationActivity.java'
SESSION=ROOT/'app/src/main/java/local/pocketchat/ChatSession.java'
OBSERVER=ROOT/'tests/gecko/SourceRouteTerminalObserver.java'

def member(text,signature):
 start=text.index(signature);brace=text.index('{',start);depth=0
 for at in range(brace,len(text)):
  if text[at]=='{':depth+=1
  elif text[at]=='}':
   depth-=1
   if not depth:return text[start:at+1]
 raise AssertionError('Incomplete member '+signature)

PREFIX=r'''
import org.json.*;import java.util.*;import java.util.concurrent.*;import java.io.IOException;
public class NetworkSourcesRouteIntegrationActivity {
 static long clock=1_000_000_000L;static int legalClockReads=-1;static long completionDeadline;static class SystemClock {static long elapsedRealtimeNanos(){if(legalClockReads==0){clock=completionDeadline;legalClockReads=-1;}else if(legalClockReads>0)legalClockReads--;return clock;}}
 static class J {static JSONObject obj(Object... values){JSONObject o=new JSONObject();try{for(int i=0;i<values.length;i+=2)o.put((String)values[i],values[i+1]);}catch(Exception e){throw new IllegalArgumentException(e);}return o;}}
 static class NetworkCatalog {static void put(JSONObject o,String k,Object v){try{o.put(k,v);}catch(Exception e){throw new IllegalArgumentException(e);}}}
 static class GeckoSession {}
 static class FixtureView {GeckoSession current=new GeckoSession();int stops;boolean mutateCookie;JSONObject document=J.obj("url","https://127.0.0.1:9879/pool","controlled",true,"timeOrigin",1.5,"draft","unsent pool draft","cookie","controlled=keep","sends",0);
  void evaluateJavascript(String script,java.util.function.Consumer<String> callback){callback.accept(document.toString());}void stopLoading(){stops++;if(mutateCookie)NetworkCatalog.put(document,"cookie","changed");}}
 static class NativeNetwork {boolean starting,ready,recoveryBlocked;Object verifiedRoute,transport=new Object();String message="rejected";RecoveryCallback delegated;
  enum RecoveryState {FAILED,READY}static class RecoveryOutcome {RecoveryState state;String message="controlled failure";Object receipt;RecoveryOutcome(RecoveryState state){this.state=state;}}interface RecoveryCallback {void done(RecoveryOutcome outcome);}void recoverOutcome(RecoveryCallback callback){delegated=callback;}static NativeNetwork get(Object context){return (NativeNetwork)context;}}
 static class Handler {long now;static class Task {Runnable run;long at;Task(Runnable r,long t){run=r;at=t;}}List<Task> tasks=new ArrayList<>();void postDelayed(Runnable r,long delay){tasks.add(new Task(r,now+delay));}void advance(long target){for(;;){Task next=null;for(Task t:tasks)if(t.at<=target&&(next==null||t.at<next.at))next=t;if(next==null)break;tasks.remove(next);now=next.at;next.run.run();}now=target;}}
 static class Guard {boolean blocked;void setBlocked(boolean v){blocked=v;}}static class PageMemory {void capture(Runnable r){r.run();}}static class Prefs {boolean getBoolean(String k,boolean d){return k.equals("networkConfigured");}}
 static class ChatSession {
  static class DiagnosticAudit {boolean requestIdentityPageSelected(){return false;}void cancel(){}void retirePageCheck(){}}
  DiagnosticAudit audit;
  boolean offline,recoveryScheduled,connecting,manualAttention,submitting,operation,networkReady;int recoveryAttempt,requests;long recoveryToken,connectionEpoch,navigationEpoch,pageUsableAt;String connectionStage,networkIssue,status;Object context;Handler handler=new Handler();Prefs prefs=new Prefs();FixtureView web;Guard guard=new Guard();PageMemory pageMemory=new PageMemory();
  boolean internalNetwork(){return true;}void setStatus(String value){status=value;}void resetReplyStability(){}void finishResourceInspection(){}void openConnection(boolean recover,boolean force){requests++;connecting=true;connectionEpoch++;}
__SESSION__
 }
 static class SourceRouteTerminalObserver {
  Scope active;int callbacks;static class Recovery {}static class Scope {String id="previous";JSONObject evidence=J.obj("status","passed");long deadlineNs=clock+22_000_000_000L;Object startupRoot;}
  Recovery recoveryStarted(int request){return active==null?null:new Recovery();}void recoveryFinished(Recovery recovery,NativeNetwork.RecoveryOutcome outcome){callbacks++;}
__OBSERVER__
 }
 static class SourceRouteStartObservation {void recovery(NativeNetwork.RecoveryCallback callback,int request,Object root){}}
 static class RouteNetwork extends NativeNetwork {NetworkSourcesRouteIntegrationActivity test;SourceRouteStartObservation startObservation=new SourceRouteStartObservation();RouteNetwork(NetworkSourcesRouteIntegrationActivity test){this.test=test;}
__RECOVERY_WRAPPER__
 }
 static final String ORIGIN="https://127.0.0.1:9879";
 interface Work<T>{T run()throws Exception;}
 ChatSession session=new ChatSession();FixtureView view=new FixtureView();NativeNetwork network=new NativeNetwork();SourceRouteTerminalObserver terminalObserver=new SourceRouteTerminalObserver();SourceRouteTerminalObserver.Scope previousNegativeScope;CaseRecovery caseRecovery,sourceCaseOwner;JSONArray sourceCaseHandoffs=new JSONArray();String expectedSource="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",runNonce="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";int recoveryRequestSerial,uiCalls;Runnable afterUi;
 NetworkSourcesRouteIntegrationActivity(){session.web=view;session.context=network;}
 void runOnUiThread(Runnable work){work.run();uiCalls++;if(afterUi!=null)afterUi.run();}
 void event(String name,JSONObject value){}void recoveryEvent(String name,JSONObject value){}JSONObject recoveryState(){return J.obj("connecting",session.connecting,"epoch",session.connectionEpoch,"token",session.recoveryToken);}
__FIXTURE__
 static int checks;static void check(boolean condition,String name){if(!condition)throw new AssertionError(name);checks++;}
 static NetworkSourcesRouteIntegrationActivity pending(){NetworkSourcesRouteIntegrationActivity t=new NetworkSourcesRouteIntegrationActivity();t.previousNegativeScope=new SourceRouteTerminalObserver.Scope();t.session.scheduleRecovery();t.session.handler.advance(862);return t;}
 static void rejected(NetworkSourcesRouteIntegrationActivity t,String text)throws Exception {boolean failed=false;try{t.handoffSourceCase("next");}catch(Exception e){failed=true;}check(failed,text);check(t.view.stops==0,text+" cannot invalidate or erase an operation");}
 public static void main(String[] args)throws Exception {
  NetworkSourcesRouteIntegrationActivity old=pending();old.session.handler.advance(1007);check(old.session.requests==1&&old.session.connecting,"original queued1s token crosses a terminal-looking cut");
  NetworkSourcesRouteIntegrationActivity next=pending();long token=next.session.recoveryToken;next.handoffSourceCase("fourth-negative");next.session.handler.advance(1007);check(next.session.requests==0&&!next.session.connecting,"verbatim handoff calls production invalidation before old token runs");check(next.session.recoveryToken==token+1&&!next.session.recoveryScheduled&&next.session.connectionEpoch==1&&next.session.navigationEpoch==1,"real invalidation effects observed");check(next.sourceCaseHandoffs.getJSONObject(0).getString("status").equals("passed"),"new handoff emits actual terminal record");check(next.view.document.getString("draft").equals("unsent pool draft")&&next.view.document.getString("cookie").equals("controlled=keep"),"document and cookie boundary preserved in controlled host");next.session.scheduleRecovery();next.session.handler.advance(2007);check(next.session.requests==1&&next.session.connecting,"a newly scheduled recovery still executes");
  NetworkSourcesRouteIntegrationActivity live=pending();live.session.handler.advance(1007);rejected(live,"unknown in-flight operation stays rejected");check(live.session.connecting,"inflight flag was not fabricated false");
  NetworkSourcesRouteIntegrationActivity stale=pending();stale.session.handler.advance(1007);stale.caseRecovery=new CaseRecovery(stale,++stale.recoveryRequestSerial);stale.session.recoveryToken++;rejected(stale,"expired token cannot authorize handoff");
  NetworkSourcesRouteIntegrationActivity owner=pending();owner.session.handler.advance(1007);owner.caseRecovery=new CaseRecovery(owner,++owner.recoveryRequestSerial);owner.view.current=new GeckoSession();rejected(owner,"replaced SDK session cannot authorize callback ownership");
  NetworkSourcesRouteIntegrationActivity early=pending();early.session.handler.advance(1007);early.caseRecovery=new CaseRecovery(early,++early.recoveryRequestSerial);early.caseRecovery.done.complete(J.obj("outcome","FAILED","hasReceipt",false));rejected(early,"already completed callback cannot hide a still-live operation");
  NetworkSourcesRouteIntegrationActivity expired=pending();expired.previousNegativeScope.deadlineNs=clock-1;rejected(expired,"original22s phase deadline is not extended");
  NetworkSourcesRouteIntegrationActivity wrongProof=pending();NetworkCatalog.put(wrongProof.previousNegativeScope.evidence,"status","failed");rejected(wrongProof,"failed preceding terminal proof remains rejected");
  NetworkSourcesRouteIntegrationActivity nativeActive=pending();nativeActive.network.starting=true;rejected(nativeActive,"unknown native startup cannot be reset");
  NetworkSourcesRouteIntegrationActivity changed=pending();changed.view.mutateCookie=true;boolean rejectedDocument=false;try{changed.handoffSourceCase("next");}catch(Exception e){rejectedDocument=true;}check(rejectedDocument,"document and cookie drift cannot pass");
  NetworkSourcesRouteIntegrationActivity late=pending();late.afterUi=()->{if(late.uiCalls==3){completionDeadline=late.previousNegativeScope.deadlineNs;legalClockReads=2;}};boolean completedLate=false;try{late.handoffSourceCase("next");}catch(IOException error){completedLate=error.getMessage().contains("exceeded the original case phase deadline");}check(completedLate&&late.sourceCaseHandoffs.getJSONObject(0).getString("status").equals("failed")&&late.previousNegativeScope!=null,"last legal document waits cannot pass when parsing and comparison finish at original deadline");
  NetworkSourcesRouteIntegrationActivity waited=pending();waited.session.handler.advance(1007);CaseRecovery original=new CaseRecovery(waited,++waited.recoveryRequestSerial);waited.caseRecovery=original;CountDownLatch selection=new CountDownLatch(1);waited.afterUi=()->{if(waited.uiCalls==2)selection.countDown();};ExecutorService worker=Executors.newSingleThreadExecutor();Future<?> run=worker.submit(()->{try{waited.handoffSourceCase("next");}catch(Exception e){throw new RuntimeException(e);}});check(selection.await(2,TimeUnit.SECONDS),"actual helper selects the real completion future");check(!run.isDone()&&waited.session.connecting&&waited.view.stops==0,"handoff waits and does not clear active flags");check(original.current(waited,true),"callback begins with exact token and owner");waited.session.connectionFailed(original.connection,"controlled failure",true);check(original.current(waited,false),"production callback retains its connection owner");original.done.complete(J.obj("request",original.request,"outcome","FAILED","hasReceipt",false,"completedAtNs",clock));run.get(2,TimeUnit.SECONDS);worker.shutdownNow();check(waited.sourceCaseHandoffs.getJSONObject(0).getJSONArray("waits").length()==1&&waited.view.stops==1,"completed real callback precedes exactly one invalidation");check(!waited.session.connecting&&!waited.session.recoveryScheduled,"new pending retry is invalidated only after callback");
  NetworkSourcesRouteIntegrationActivity wrapped=pending();RouteNetwork route=new RouteNetwork(wrapped);wrapped.network=route;wrapped.session.context=route;wrapped.session.handler.advance(1007);final boolean[] invoked={false};route.recoverOutcome(outcome->{check(!wrapped.caseRecovery.done.isDone(),"fixture future cannot precede real callback");wrapped.session.connectionFailed(wrapped.session.connectionEpoch,outcome.message,true);invoked[0]=true;});check(!wrapped.caseRecovery.done.isDone(),"real delegated recovery has no premature terminal future");route.delegated.done(new NativeNetwork.RecoveryOutcome(NativeNetwork.RecoveryState.FAILED));check(invoked[0]&&wrapped.caseRecovery.done.get().getString("outcome").equals("FAILED")&&wrapped.terminalObserver.callbacks==1,"extracted wrapper completes after original callback and terminal observer");check(!wrapped.session.connecting&&wrapped.session.recoveryScheduled,"extracted callback executes production failure and retry scheduling");
  NetworkSourcesRouteIntegrationActivity oldCallback=pending();RouteNetwork oldRoute=new RouteNetwork(oldCallback);oldCallback.network=oldRoute;oldCallback.session.context=oldRoute;oldCallback.session.handler.advance(1007);final int[] oldCalls={0};oldRoute.recoverOutcome(outcome->oldCalls[0]++);oldCallback.session.recoveryToken++;oldRoute.delegated.done(new NativeNetwork.RecoveryOutcome(NativeNetwork.RecoveryState.FAILED));check(oldCalls[0]==1&&oldCallback.caseRecovery.done.isCompletedExceptionally(),"stale token callback still executes but cannot prove handoff");
  NetworkSourcesRouteIntegrationActivity changedCallback=pending();RouteNetwork changedRoute=new RouteNetwork(changedCallback);changedCallback.network=changedRoute;changedCallback.session.context=changedRoute;changedCallback.session.handler.advance(1007);changedRoute.recoverOutcome(outcome->changedCallback.session.connectionEpoch++);changedRoute.delegated.done(new NativeNetwork.RecoveryOutcome(NativeNetwork.RecoveryState.FAILED));check(changedCallback.caseRecovery.done.isCompletedExceptionally(),"connection owner changing inside actual callback cannot prove handoff");
  NetworkSourcesRouteIntegrationActivity thrownCallback=pending();RouteNetwork thrownRoute=new RouteNetwork(thrownCallback);thrownCallback.network=thrownRoute;thrownCallback.session.context=thrownRoute;thrownCallback.session.handler.advance(1007);RuntimeException originalError=new RuntimeException("original callback failure");thrownRoute.recoverOutcome(outcome->{throw originalError;});boolean preservedThrow=false;try{thrownRoute.delegated.done(new NativeNetwork.RecoveryOutcome(NativeNetwork.RecoveryState.FAILED));}catch(RuntimeException error){preservedThrow=error==originalError;}check(preservedThrow&&thrownCallback.caseRecovery.done.isCompletedExceptionally()&&thrownCallback.terminalObserver.callbacks==1,"actual wrapper preserves thrown callback and original observation without false terminal success");
  System.out.println(J.obj("passed",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"scope","Verbatim fixture handoff and production recovery/invalidation with Handler/network/document boundary doubles").toString());
 }
}
'''

def execute(jar):
 fixture=FIXTURE.read_text();session=SESSION.read_text();observer=OBSERVER.read_text()
 selected={
  'session':[member(session,s) for s in ['void invalidateConnection()','static long retryDelay(int attempt)','void scheduleRecovery()','void runRecovery(long token)','void connectionFailed(long epoch,String message,boolean retry)']],
  'observer':[member(observer,s) for s in ['static long now()','static void require(boolean value,String message)','static long remaining(Scope scope)']],
  'fixture':[member(fixture,s) for s in ['static long now()','<T>T ui(Work<T> work)','static final class CaseRecovery','<T>T caseUi(SourceRouteTerminalObserver.Scope previous,Work<T> work)','JSONObject caseDocument(SourceRouteTerminalObserver.Scope previous)','JSONObject caseState()','void handoffSourceCase(String next)']],
  'recoveryWrapper':[member(fixture,'@Override void recoverOutcome(RecoveryCallback callback)')],
 }
 code=PREFIX.replace('__SESSION__','\n'.join(selected['session'])).replace('__OBSERVER__','\n'.join(selected['observer'])).replace('__FIXTURE__','\n'.join(selected['fixture'])).replace('__RECOVERY_WRAPPER__','\n'.join(selected['recoveryWrapper']))
 java=os.environ.get('PROFILE_JAVA')or shutil.which('java')
 if not java:raise unittest.SkipTest('Java unavailable')
 with tempfile.TemporaryDirectory(prefix='source-case-handoff-')as temp:
  base=Path(temp);source=base/'NetworkSourcesRouteIntegrationActivity.java';source.write_text(code)
  c=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',temp,str(source)],capture_output=True,text=True)
  if c.returncode:raise AssertionError(c.stderr)
  r=subprocess.run([java,'-cp',temp+os.pathsep+str(jar),'NetworkSourcesRouteIntegrationActivity'],capture_output=True,text=True,timeout=20)
  if r.returncode:raise AssertionError(r.stdout+r.stderr)
  report=json.loads(r.stdout);report['selectedMemberSha256']={kind:[hashlib.sha256(s.encode()).hexdigest()for s in values]for kind,values in selected.items()};return report

class SourceCaseHandoffTests(unittest.TestCase):
 def test_verbatim_production_tokens_and_fixture_handoff(self):
  candidates=[('desktop',ROOT/'work/profile-host/json.jar'),('android',ROOT/'work/profile-host/android-json.jar')]
  if not any(p.is_file()for _,p in candidates):candidates=[('desktop',ROOT/'work/gecko-integration/catalog-json.jar'),('android',ROOT/'work/gecko-integration/sharing-android-json.jar')]
  if os.environ.get('PROFILE_JSON_JAR'):candidates=[('explicit',Path(os.environ['PROFILE_JSON_JAR']))]
  if not any(p.is_file()for _,p in candidates):raise unittest.SkipTest('Pinned JSON jars unavailable')
  reports={}
  for name,jar in candidates:
   with self.subTest(runtime=name):self.assertTrue(jar.is_file());reports[name]=execute(jar);self.assertEqual(reports[name]['passed'],36)
  out=ROOT/'work/profile-host/source-case-handoff-results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'scope':'Host regression only; not Android evidence','runtimes':reports},indent=2)+'\n')
 def test_strict_original_observer_guards_and_budgets_remain(self):
  text=OBSERVER.read_text()
  for literal in ['require(active==null&&!test.network.starting&&!test.session.connecting,"a previous operation remains active")','scope.deadlineNs=began+TimeUnit.SECONDS.toNanos(75)','scope.deadlineNs=began+TimeUnit.SECONDS.toNanos(22)','closed(fresh)','before.toString().equals(f.toString())','scope.contacts.toString().equals(contacts.toString())']:
   self.assertEqual(text.count(literal),1,literal)
  fixture=FIXTURE.read_text();body=member(fixture,'void handoffSourceCase(String next)')
  self.assertNotIn('connecting=false',body);self.assertNotIn('recoveryScheduled=false',body);self.assertNotIn('removeCallbacks',body);self.assertEqual(body.count('session.invalidateConnection()'),1)
  self.assertIn('if(session!=null)handoffSourceCase(next)',fixture)

if __name__=='__main__':unittest.main()
