"""Exact test-only queued-document adapter; host controls never stand in for Gecko."""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest
from profile_resource_retained_fixture_test import java_method

ROOT=Path(__file__).resolve().parents[1]
JAVA=Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')
PINS={'json.jar':'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796','android-json.jar':'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}
HELPER='tests/gecko/GeckoQueuedChangesObservation.java'

ADAPTERS=r'''package local.pocketchat;
import android.webkit.ValueCallback;import java.util.*;import org.json.*;
class Profiles {static final int MAX=8;}
class GeckoIntegrationTestActivity {static class Store{String nonce="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";}Store eventStore=new Store();JSONObject eventBuildIdentity=J.obj("sourceCommit","b".repeat(40));ChatSession session=new ChatSession();int slot=1;long run=46;void event(long run,String name,JSONObject value){}static class FixtureView {GeckoQueuedChangesObservation queuedObservation;Object current=new Object();Map<Object,Object> ports=new HashMap<>();String lastScript="",url="http://127.0.0.1:8765/fixture?context=2&action=read&command=4";FixtureView(){ports.put(current,new Object());}String getUrl(){return url;}boolean hasVisibleDocument(){return true;}void evaluateJavascript(String script,ValueCallback<String> cb){lastScript=script;}}}
class ChatSession {GeckoIntegrationTestActivity.FixtureView web=new GeckoIntegrationTestActivity.FixtureView();long navigationEpoch=7;int environmentGeneration=2;String environmentId="environment-2",resourceObserverBinding="";Observer webObserver=new Observer();static class Observer {String script;}void resourceObserverConnected(Object port){resourceObserverBinding="actual-port-binding";}void resourceWebsiteObservation(JSONObject value,Object port){}TaskGuardSnapshot taskGuardSnapshot(){return new TaskGuardSnapshot(false,false,false,false,false,false,1,2,environmentId,navigationEpoch,resourceObserverBinding,"",0,0);}}
class NetworkCatalog {static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(Exception e){throw new AssertionError(e);}}}
'''
CONTROLS=r'''package local.pocketchat;
import java.nio.file.*;import org.json.*;
public class QueuedObservationHost {
 static int checks;interface Work {void run()throws Exception;}
 static void yes(boolean value){if(!value)throw new AssertionError("control "+checks);checks++;}
 static void reject(Work work)throws Exception{try{work.run();}catch(java.io.IOException expected){checks++;return;}throw new AssertionError("foreign owner/source accepted");}
 static JSONObject packet(){return J.obj("nonce","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","url",URL,"event",J.obj("type","resource-work","url",URL,"resourceBinding","actual-port-binding","documentId","actual-document-0001","resourceSequence",2,"busy",false,"uploading",false,"capturedAt",100000));}
 static final String URL="http://127.0.0.1:8765/fixture?context=2&action=read&command=4";
 static boolean accepts(JSONObject p){return GeckoQueuedChangesObservation.accepts(p,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",URL,"actual-port-binding","actual-document-0001",1,100000);}
 public static void main(String[] args)throws Exception{
  String original=Files.readString(Path.of(args[0]));GeckoIntegrationTestActivity activity=new GeckoIntegrationTestActivity();activity.session.webObserver.script=original;
  GeckoQueuedChangesObservation helper=new GeckoQueuedChangesObservation(activity,46);helper.begin(()->{});Files.writeString(Path.of(args[1]),activity.session.web.lastScript);
  yes(activity.session.web.lastScript.contains("__pocketReadDriver('observe-install'"));yes(!activity.session.web.lastScript.contains("location.origin !== 'https://chatgpt.com'"));
  for(String invalid:new String[]{"http://127.0.0.1:8765/fixture?context=1&action=read&command=4",URL+"&extra=1",URL+"#x",URL.replace("127.0.0.1","localhost"),URL.replace("http:","https:"),URL.replace("8765","8766"),URL.replace("action=read","action=foreign"),URL.replace("command=4","command=0")})reject(()->GeckoQueuedChangesObservation.validateOwner(invalid,1));
  for(String invalid:new String[]{"",null,"a".repeat(31),"A".repeat(32)})reject(()->GeckoQueuedChangesObservation.adaptedScript(original,URL,invalid));
  for(String guard:new String[]{"location.origin !== 'https://chatgpt.com'","location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'"}){
   reject(()->GeckoQueuedChangesObservation.adaptedScript(original.replace(guard,"false"),URL,"a".repeat(32)));reject(()->GeckoQueuedChangesObservation.adaptedScript(original+guard,URL,"a".repeat(32)));
  }
  yes(accepts(packet()));
  for(String key:new String[]{"nonce","url"}){JSONObject bad=packet();bad.put(key,"foreign");yes(!accepts(bad));}
  for(String key:new String[]{"type","url","resourceBinding","documentId"}){JSONObject bad=packet();bad.getJSONObject("event").put(key,"foreign");yes(!accepts(bad));}
  for(Object[] change:new Object[][]{{"resourceSequence",1},{"capturedAt",89999},{"capturedAt",110001},{"busy","false"},{"uploading",0}}){JSONObject bad=packet();bad.getJSONObject("event").put((String)change[0],change[1]);yes(!accepts(bad));}
  System.out.println("PASS "+checks+" exact adapter/owner/packet controls; JVM boundaries only");
 }
}
'''
NODE=r'''const assert=require('node:assert/strict'),fs=require('node:fs');const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const script=fs.readFileSync(process.argv[2],'utf8'),url='http://127.0.0.1:8765/fixture?context=2&action=read&command=4';
function make(target){const w=new JSDOM('<!doctype html><body><textarea id="unrelated">draft retained</textarea></body>',{url:target,runScripts:'outside-only',pretendToBeVisual:true}).window;Object.defineProperty(w.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});w.Element.prototype.getClientRects=()=>[{}];w.getComputedStyle=()=>({display:'block',visibility:'visible'});w.setTimeout=()=>1;w.clearTimeout=()=>{};return w;}
let checks=0;const yes=(v)=>{assert.ok(v);checks++;};
const w=make(url);w.document.cookie='fixture=preserved;path=/';const busy=w.eval(script);yes(busy.event.busy===true);yes(busy.event.uploading===false);yes(busy.event.resourceBinding==='actual-port-binding');yes(busy.event.documentId===w.__pocketWebReplyObserver.documentId);
const before=w.document.getElementById('unrelated').value,cookie=w.document.cookie,doc=busy.event.documentId;
w.document.getElementById('queued46-stop').remove();w.__pocketWebReplyObserver.requestResources('actual-idle-request-46');const idle=w.__pocketQueued46.event;yes(idle.busy===false);yes(idle.documentId===doc);yes(idle.resourceSequence>busy.event.resourceSequence);yes(idle.guardRequestId==='actual-idle-request-46');yes(w.document.getElementById('unrelated').value===before&&w.document.cookie===cookie);
const seq=idle.resourceSequence;w.__pocketQueued46.nonce='foreign';w.__pocketWebReplyObserver.requestResources('wrong-nonce-request-46');yes(w.__pocketQueued46.event.resourceSequence===seq);
for(const foreign of [url+'&extra=1',url+'#foreign',url.replace('8765','8766'),url.replace('127.0.0.1','localhost')]){const f=make(foreign);const packet=f.eval(script);yes(!packet.event);yes(!f.__pocketWebReplyObserver);f.close();}
w.close();console.log('PASS '+checks+' actual complete observer/driver busy-to-idle and foreign-owner controls; JSDOM only');
'''

class QueuedDocumentObservation46(unittest.TestCase):
 def test_actual_helper_complete_scripts_and_packet_controls(self):
  java=Path(os.environ.get('PROFILE_JAVA') or (str(JAVA) if JAVA.is_file() else shutil.which('java')));javac=java.with_name('javac')
  helper=(ROOT/HELPER).read_bytes();assets={name:(ROOT/'app/src/main/assets'/name).read_bytes() for name in ('web-performance.js','web-reply-observer.js','page-driver.js')}
  production=ROOT/'app/src/main/java/local/pocketchat';guard=java_method((ROOT/'tests/gecko/ResourcePressureIntegrationActivity.java').read_text(),'replaceResourceFixtureGuard')
  with tempfile.TemporaryDirectory(prefix='queued-document46-') as directory:
   base=Path(directory);source=base/'src';source.mkdir();(source/'GeckoQueuedChangesObservation.java').write_bytes(helper);(source/'J.java').write_bytes((production/'J.java').read_bytes());(source/'TaskGuardSnapshot.java').write_bytes((production/'TaskGuardSnapshot.java').read_bytes());(source/'Adapters.java').write_text(ADAPTERS);(source/'ResourcePressureIntegrationActivity.java').write_text('package local.pocketchat;import java.io.*;class ResourcePressureIntegrationActivity{'+guard+'}');(source/'QueuedObservationHost.java').write_text(CONTROLS)
   original=base/'original.js';original.write_text(assets['web-performance.js'].decode()+'\n'+assets['web-reply-observer.js'].decode()+'\nwindow.__pocketReadDriver=(action,arg)=>'+assets['page-driver.js'].decode().replace('__ACTION__','action').replace('__ARG__','arg')+';')
   android=Path(os.environ.get('PROFILE_ANDROID_JAR','/tmp/pocketchat-shared-tools/android-35/android.jar'))
   if android.is_file():
    self.assertEqual(hashlib.sha256(android.read_bytes()).hexdigest(),'4566663c3876e022b4fa4ced8c8697c4ab1688267f090114fd92d027b32e619b')
    built=subprocess.run([str(javac),'-encoding','UTF-8','-cp',str(android),'-d',str(base/'android-api'),*map(str,source.glob('*.java'))],text=True,capture_output=True,timeout=45);self.assertEqual(built.returncode,0,built.stdout+built.stderr)
   (source/'SystemClock.java').write_text('package android.os;public class SystemClock{public static long elapsedRealtime(){return 1000;}}');(source/'ValueCallback.java').write_text('package android.webkit;public interface ValueCallback<T>{void onReceiveValue(T value);}')
   runs=[]
   for name,pin in PINS.items():
    jar=ROOT/'work/profile-host'/name;self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(),pin);classes=base/name;classes.mkdir();result=subprocess.run([str(javac),'-encoding','UTF-8','-cp',str(jar),'-d',str(classes),*map(str,source.glob('*.java'))],text=True,capture_output=True,timeout=45);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    script=base/(name+'.js');result=subprocess.run([str(java),'-cp',str(classes)+os.pathsep+str(jar),'local.pocketchat.QueuedObservationHost',str(original),str(script)],text=True,capture_output=True,timeout=30);self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn('PASS 30 ',result.stdout);runs.append(result.stdout)
    node=base/'host.cjs';node.write_text(NODE);result=subprocess.run(['node',str(node),str(script)],text=True,capture_output=True,cwd=ROOT,timeout=30);self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn('PASS 18 ',result.stdout);runs.append(result.stdout)
   output=os.environ.get('QUEUED_DOCUMENT46_REPORT')
   if output:Path(output).write_text(json.dumps(dict(scope='Exact test-only helper, generated installation script, actual production observer/driver; explicit JVM Android/app boundaries and JSDOM geometry/timer boundaries.',helperSha256=hashlib.sha256(helper).hexdigest(),runs=runs,actualAndroidExecution=False,actualGeckoExecution=False,actualPhoneExecution=False),indent=2)+'\n')
  for name,value in assets.items():self.assertEqual((ROOT/'app/src/main/assets'/name).read_bytes(),value)
  self.assertEqual((ROOT/HELPER).read_bytes(),helper)

if __name__=='__main__':unittest.main(verbosity=2)
