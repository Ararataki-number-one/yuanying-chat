"""Failure-only fixture observation controls; no Android or recovery acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/gecko/GeckoPerformanceIntegrationActivity.java'
SPEC=importlib.util.spec_from_file_location('manual_snapshot_source_member',ROOT/'tests/chrome-network-state-host/run.py')
EXTRACT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(EXTRACT)
MEMBERS=['@Override public void evaluateJavascript(', 'static JSONObject manualSnapshotState(',
         'static JSONObject manualSnapshotShape(', 'void manualSnapshotFailure(']
PINS={'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
      '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed',
      'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}
HOST=r'''package local.pocketchat;
import org.json.*;import java.nio.charset.StandardCharsets;
public final class ManualSnapshotHost{
 static int checks;static void check(boolean value){if(!value)throw new AssertionError("manual diagnostic control "+checks);checks++;}
 static String code="window.__pocketReadDriver(\"page-state\",{})";
 static JSONObject snapshot(String draft){return J.obj("ok",true,"draft",draft,"draftLength",draft.length(),"draftComplete",true,"documentId","secret-document","url","https://secret.test/page","reason","secret-reason");}
 static void heldInspectionControls()throws Exception{
  ChatSession owner=new ChatSession();FixtureView view=new FixtureView(owner);int[] callbacks={0};String raw=J.obj("ok",true,"busy",false).toString();
  String inspection="window.__pocketReadDriver(\"web-inspect\",{})";
  view.holdNextInspection=true;view.evaluateJavascript(inspection,value->{check(raw.equals(value));callbacks[0]++;});view.deliver(raw);
  check(view.calls==1&&callbacks[0]==0&&!view.holdNextInspection);
  check(view.heldInspection!=null&&raw.equals(view.heldInspectionRaw)&&view.productionInspect.optBoolean("ok"));
  check(view.pageStateReads==0&&view.manualSnapshotLast.length()==0&&Log.messages.length()==0&&SystemClock.calls==0);
  view.heldInspection.onReceiveValue(view.heldInspectionRaw);check(callbacks[0]==1);
  view.heldInspection=null;view.heldInspectionRaw=null;view.evaluateJavascript(inspection,value->callbacks[0]++);view.deliver(raw);
  check(view.calls==2&&callbacks[0]==2&&view.heldInspection==null&&view.heldInspectionRaw==null);
  view.holdNextInspection=true;view.evaluateJavascript(code,value->callbacks[0]++);view.deliver(snapshot("secret-draft").toString());
  check(view.calls==3&&callbacks[0]==3&&view.holdNextInspection&&view.pageStateReads==1&&view.pageStateDraft.equals("secret-draft"));
  view.evaluateJavascript(inspection,null);view.deliver(raw);
  check(view.calls==4&&callbacks[0]==3&&!view.holdNextInspection&&view.heldInspection==null&&raw.equals(view.heldInspectionRaw));
  System.out.println(J.obj("status","passed","checks",checks,"actualAndroidExecution",false,"newBridgeReads",false,"scope","Current extracted callback with explicit synthetic Gecko response boundary"));
 }
 public static void main(String[]args)throws Exception{
  if(args.length==1&&"held-inspection".equals(args[0])){heldInspectionControls();return;}
  ChatSession owner=new ChatSession();FixtureView view=new FixtureView(owner);int[] callbacks={0};JSONObject original=snapshot("secret-draft");
  view.evaluateJavascript(code,raw->{callbacks[0]++;check(raw.equals(original.toString()));});view.deliver(original.toString());
  check(view.calls==1&&callbacks[0]==1&&view.pageStateReads==1&&view.pageStateDraft.equals("secret-draft"));
  check(view.manualSnapshotLast.length()==0&&Log.messages.length()==0&&SystemClock.calls==0);
  view.manualSnapshotDiagnostics=true;owner.networkReady=false;owner.guard.blocked=true;owner.websiteRecovering=false;
  view.evaluateJavascript(code,raw->{callbacks[0]++;owner.websiteRecovering=false;});owner.networkReady=true;owner.guard.blocked=false;owner.websiteRecovering=true;view.deliver(original.toString());
  JSONObject last=view.manualSnapshotLast,issue=last.getJSONObject("issue"),callback=last.getJSONObject("callback"),shape=last.getJSONObject("shape");
  check(last.getBoolean("issueObserved")&&!issue.getBoolean("networkReady")&&issue.getBoolean("guardBlocked")&&!issue.getBoolean("websiteRecovering"));
  check(callback.getBoolean("networkReady")&&!callback.getBoolean("guardBlocked")&&callback.getBoolean("websiteRecovering")&&last.getString("callbackStage").equals("before-production-consumer"));
  check(issue.getLong("epoch")==7&&issue.getLong("connection")==4&&issue.getString("pendingIdHash").equals(Sha256.hash("secret-job")));
  check(shape.getBoolean("readable")&&shape.getBoolean("complete")&&shape.getBoolean("draftString")&&shape.getInt("draftLength")==12&&shape.getString("draftHash").equals(Sha256.hash("secret-draft")));
  check(view.calls==2&&callbacks[0]==2&&Log.messages.length()==0&&!owner.websiteRecovering);
  view.manualSnapshotFailure(1,"secret-draft",7,4);check(Log.messages.length()==1);
  String logged=Log.messages.getString(0);JSONObject failure=J.parse(logged).getJSONObject("value");
  check(logged.getBytes(StandardCharsets.UTF_8).length<=3500&&!logged.contains("secret-draft")&&!logged.contains("secret-document")&&!logged.contains("secret-job")&&!logged.contains("https://secret.test/page"));
  check(failure.getBoolean("draftMatches")&&!failure.getJSONObject("current").getBoolean("websiteRecovering")&&failure.getJSONObject("lastPageState").getJSONObject("callback").getBoolean("websiteRecovering"));
  view.manualSnapshotDiagnostics=false;view.evaluateJavascript(code,raw->callbacks[0]++);view.manualSnapshotDiagnostics=true;view.deliver(original.toString());
  check(!view.manualSnapshotLast.getBoolean("issueObserved")&&view.manualSnapshotLast.isNull("issue")&&view.calls==3&&callbacks[0]==3);
  JSONObject incomplete=snapshot("secret-draft").put("draftComplete",false);check(!FixtureView.manualSnapshotShape(incomplete).getBoolean("complete"));
  check(!FixtureView.manualSnapshotShape(J.obj("ok",true,"draft",JSONObject.NULL)).getBoolean("draftString"));
  view.evaluateJavascript(code,raw->callbacks[0]++);view.deliver("null");check(!view.manualSnapshotLast.getJSONObject("shape").getBoolean("readable")&&!view.manualSnapshotLast.getJSONObject("shape").getBoolean("complete"));
  StringBuilder huge=new StringBuilder();for(int i=0;i<300001;i++)huge.append('x');JSONObject large=FixtureView.manualSnapshotShape(snapshot(huge.toString()));
  check(!large.getBoolean("complete")&&large.getInt("draftLength")==300001&&large.toString().length()<700);
  view.manualSnapshotLast=J.obj("unexpected",huge.toString());view.manualSnapshotFailure(2,"secret-draft",7,4);
  check(J.parse(Log.messages.getString(1)).getJSONObject("value").getBoolean("payloadOmitted")&&Log.messages.getString(1).length()<300);
  Log.throwNext=true;view.manualSnapshotFailure(1,"secret-draft",7,4);check(!Log.throwNext&&view.calls==4&&callbacks[0]==4);
  System.out.println(J.obj("status","passed","checks",checks,"actualAndroidExecution",false,"newBridgeReads",false));
 }
}
class FixtureView extends GeckoWebView{
 boolean semanticRoute=true,inspectPending,inputTracing,manualSnapshotDiagnostics;JSONObject productionPoll,productionInspect,manualSnapshotLast=new JSONObject();int pageStateReads,stableBeforeInspectedPoll,completionBeforeInspectedPoll,inputEvaluateSequence;String pageStateDraft="";
 boolean holdNextInspection;android.webkit.ValueCallback<String> heldInspection;String heldInspectionRaw;
 FixtureView(ChatSession owner){super(owner);}void inputEvaluation(String phase,int sequence,String code){}
 __METHODS__
}
class GeckoWebView{final ChatSession owner;int calls;android.webkit.ValueCallback<String> pendingCallback;GeckoWebView(ChatSession owner){this.owner=owner;}public void evaluateJavascript(String code,android.webkit.ValueCallback<String> callback){calls++;pendingCallback=callback;}void deliver(String raw){android.webkit.ValueCallback<String> callback=pendingCallback;pendingCallback=null;callback.onReceiveValue(raw);}}
class ChatSession{boolean networkReady=true,websiteRecovering,navigating;long navigationEpoch=7,connectionEpoch=4;int stableTicks;String lastDocumentId="secret-document";JSONObject pending=J.obj("id","secret-job");final Guard guard=new Guard();final Observer webObserver=new Observer();}
class Guard{boolean blocked;boolean allowed(){throw new AssertionError("Unexpected route query");}}
class Observer{int completionSamples;}
class SystemClock{static int calls;static long elapsedRealtime(){return ++calls;}}
class Log{static final JSONArray messages=new JSONArray();static boolean throwNext;static int i(String tag,String value){if(throwNext){throwNext=false;throw new IllegalStateException("controlled logger failure");}messages.put(value);return 0;}}
class PageMemory{__COMPLETE__}
'''


class ManualSnapshotDiagnosticTests(unittest.TestCase):
 def test_added_observations_reverse_to_the_entire_original_fixture(self):
  from dual_browser_source_compatibility import source_input
  from browser_observation_v2_performance_source_compatibility import source_input as performance_input
  relative='tests/gecko/GeckoPerformanceIntegrationActivity.java'
  source=source_input(performance_input(FIXTURE.read_bytes(),relative),relative).decode('utf-8')
  additions=[
   '    // Scalar observations exist only while the two manual-recovery races run.\n    boolean manualSnapshotDiagnostics;JSONObject manualSnapshotLast=new JSONObject();\n',
   '      JSONObject observedManualIssue=null;\n      if(manualSnapshotDiagnostics&&semanticRoute&&code.contains("window.__pocketReadDriver(\\"page-state\\","))try{observedManualIssue=manualSnapshotState(owner);}catch(RuntimeException ignored){}\n      final JSONObject manualIssue=observedManualIssue;\n',
   '      if(manualSnapshotDiagnostics&&semanticRoute&&code.contains("window.__pocketReadDriver(\\"page-state\\",")){\n        try{manualSnapshotLast=J.obj("issueObserved",manualIssue!=null,"issue",manualIssue==null?JSONObject.NULL:manualIssue,"callback",manualSnapshotState(owner),"callbackStage","before-production-consumer","shape",manualSnapshotShape(J.parse(raw)));}catch(RuntimeException ignored){}\n      }\n',
   '    ((FixtureView)session.web).manualSnapshotDiagnostics=true;\n',
   '      view.manualSnapshotLast=new JSONObject();\n',
   '            ((FixtureView)session.web).manualSnapshotDiagnostics=false;\n']
  for signature in MEMBERS[1:]:additions.append('    '+EXTRACT.member(source,signature)+'\n')
  for literal in additions:self.assertEqual(source.count(literal),1);source=source.replace(literal,'',1)
  original='    if(!session.websiteRecovering||!manualDraft.equals(view.pageStateDraft))throw new IllegalStateException("Manual recovery snapshot failed before the controlled race");\n'
  diagnostic='    if(!session.websiteRecovering||!manualDraft.equals(view.pageStateDraft)){view.manualSnapshotFailure(index,manualDraft,manualEpoch,manualConnection);throw new IllegalStateException("Manual recovery snapshot failed before the controlled race");}\n'
  self.assertEqual(source.count(diagnostic),1);source=source.replace(diagnostic,original,1)
  self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),'f604d079aaa5761a1374d583c6f8cca5bcf965c71b0fb59edbc3b99ae9cee301')

 def test_actual_existing_callback_records_only_bounded_failure_observations(self):
  candidates=[os.environ.get('PROFILE_JSON_JAR'),os.environ.get('PROFILE_ANDROID_JSON_JAR'),ROOT/'work/profile-host/json.jar',ROOT/'work/profile-host/android-json.jar']
  jars={}
  for value in candidates:
   if value and Path(value).is_file():
    p=Path(value);digest=hashlib.sha256(p.read_bytes()).hexdigest();self.assertIn(digest,PINS);jars.setdefault(digest,p)
  self.assertTrue(jars,'Pinned JSON required')
  java=os.environ.get('PROFILE_JAVA')or shutil.which('java');self.assertTrue(java)
  fixture=FIXTURE.read_text();code=HOST.replace('__METHODS__','\n'.join(EXTRACT.member(fixture,n)for n in MEMBERS)).replace('__COMPLETE__',EXTRACT.member((ROOT/'app/src/main/java/local/pocketchat/PageMemory.java').read_text(),'static boolean completeDraft('))
  rows=[]
  for digest,jar in jars.items():
   with tempfile.TemporaryDirectory(prefix='manual-snapshot-host-')as name:
    base=Path(name);source=base/'ManualSnapshotHost.java';source.write_text(code)
    callback=base/'android/webkit/ValueCallback.java';callback.parent.mkdir(parents=True);callback.write_text('package android.webkit;public interface ValueCallback<T>{void onReceiveValue(T value);}')
    command=[java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',name,str(source),str(callback),str(ROOT/'app/src/main/java/local/pocketchat/J.java'),str(ROOT/'app/src/main/java/local/pocketchat/Sha256.java')]
    compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30);self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
    run=subprocess.run([java,'-cp',name+os.pathsep+str(jar),'local.pocketchat.ManualSnapshotHost'],capture_output=True,text=True,timeout=15);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
    report=json.loads(run.stdout);self.assertEqual(report['status'],'passed');self.assertEqual(report['checks'],18);self.assertIs(report['newBridgeReads'],False)
    held=subprocess.run([java,'-cp',name+os.pathsep+str(jar),'local.pocketchat.ManualSnapshotHost','held-inspection'],capture_output=True,text=True,timeout=15);self.assertEqual(held.returncode,0,held.stdout+held.stderr)
    held_report=json.loads(held.stdout);self.assertEqual(held_report['status'],'passed');self.assertEqual(held_report['checks'],8);self.assertIs(held_report['newBridgeReads'],False);self.assertIs(held_report['actualAndroidExecution'],False)
    rows.append(dict(jsonSha256=digest,compileStdout=compiled.stdout,compileStderr=compiled.stderr,stdout=run.stdout,stderr=run.stderr,heldInspectionStdout=held.stdout,heldInspectionStderr=held.stderr))
  output=ROOT/'work/manual-snapshot-host';output.mkdir(parents=True,exist_ok=True)
  (output/'results.json').write_text(json.dumps(dict(status='passed',sourceSha256=hashlib.sha256(fixture.encode()).hexdigest(),actualAndroidExecution=False,runs=rows),indent=2)+'\n')


class BrowserObservationPerformanceInputs(unittest.TestCase):
 def test_exact_whole_source_inverse_and_forward_keep_both_versions(self):
  import browser_observation_v2_performance_source_compatibility as compatibility
  current=FIXTURE.read_bytes();value=compatibility.manifest();previous=compatibility.source_input(current,compatibility.SOURCE_PATH)
  self.assertEqual((len(current),hashlib.sha256(current).hexdigest()),(84404,'8a4c44e37338cdda817b5428dcf8672f93441af11af45f76447a8103eaeb79ed'))
  self.assertEqual((len(previous),hashlib.sha256(previous).hexdigest()),(105250,'13062ecb571592ceb8fb7347dbfd18223ec848328657fa54df0addc55896c36f'))
  self.assertEqual(compatibility.source_input(previous,compatibility.SOURCE_PATH),previous)
  self.assertEqual(len(value['deltas']),10)
  forward=previous
  for delta in value['deltas']:
   before,after=delta['previous'].encode(),delta['current'].encode()
   self.assertEqual((previous.count(before),current.count(after),forward.count(before)),(1,1,1))
   self.assertEqual((hashlib.sha256(before).hexdigest(),hashlib.sha256(after).hexdigest()),(delta['previousSha256'],delta['currentSha256']))
   forward=forward.replace(before,after,1)
  self.assertEqual(forward,current)
  self.assertEqual(compatibility.source_input(forward,compatibility.SOURCE_PATH),previous)

 def test_missing_duplicate_mutated_relocated_and_unknown_sources_rejected(self):
  import browser_observation_v2_performance_source_compatibility as compatibility
  current=FIXTURE.read_bytes();rejected=0
  for delta in compatibility.manifest()['deltas']:
   chunk=delta['current'].encode();self.assertEqual(current.count(chunk),1)
   missing=current.replace(chunk,b'',1);moved=missing+chunk
   if moved==current:moved=chunk+missing
   for candidate in (missing,current.replace(chunk,chunk*2,1),current.replace(chunk,chunk+b' ',1),moved):
    with self.subTest(context=delta['id'],mutant=hashlib.sha256(candidate).hexdigest()):
     self.assertNotEqual(candidate,current)
     with self.assertRaises(ValueError):compatibility.source_input(candidate,compatibility.SOURCE_PATH)
     rejected+=1
  for candidate in (current+b' ',current[:80],b'unknown performance source'):
   with self.assertRaises(ValueError):compatibility.source_input(candidate,compatibility.SOURCE_PATH)
   rejected+=1
  self.assertEqual(rejected,43)

 def test_types_paths_and_changed_fixture_cannot_expand_the_version_scope(self):
  import browser_observation_v2_performance_source_compatibility as compatibility
  current=FIXTURE.read_bytes()
  for relative in (compatibility.SOURCE_PATH+'.other','../'+compatibility.SOURCE_PATH,'/'+compatibility.SOURCE_PATH,Path(compatibility.SOURCE_PATH),None):
   with self.subTest(path=relative),self.assertRaises(ValueError):compatibility.source_input(current,relative)
  for value in (current.decode(),bytearray(current),None):
   with self.assertRaises(ValueError):compatibility.source_input(value,compatibility.SOURCE_PATH)
  raw=compatibility.DELTA_PATH.read_bytes()
  changed=raw.replace(b'"browserObservationContract": 2',b'"browserObservationContract": 3',1)
  self.assertNotEqual(changed,raw);self.assertEqual(len(changed),len(raw))
  with tempfile.TemporaryDirectory(prefix='performance-v2-source-negative-')as directory:
   path=Path(directory)/'deltas.json'
   for candidate in (raw+b' ',raw[:-1],changed):
    path.write_bytes(candidate)
    with patch.object(compatibility,'DELTA_PATH',path),self.assertRaises(ValueError):compatibility.source_input(current,compatibility.SOURCE_PATH)


if __name__=='__main__':unittest.main()
