"""Production photo handoff gate against declared JVM adapters, not Android proof."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
STUBS={
'org/mozilla/geckoview/GeckoSession.java':'''package org.mozilla.geckoview;public class GeckoSession {public boolean open=true;public boolean isOpen(){return open;}String getId(){return "native-session-1";}}''',
'org/mozilla/geckoview/WebExtension.java':'''package org.mozilla.geckoview;import java.util.*;import org.json.*;public class WebExtension {public static class Port {public final List<JSONObject> sent=new ArrayList<>();public void postMessage(JSONObject value){sent.add(value);}}}''',
'local/pocketchat/PhotoPermissionHost.java':r'''package local.pocketchat;
import java.util.*;import java.util.function.Consumer;import org.json.*;import org.mozilla.geckoview.*;
public class PhotoPermissionHost {
 static int checks;
 static void check(String name,boolean result){if(!result)throw new AssertionError(name);checks++;}
 static class Run {GeckoWebView web=new GeckoWebView();GeckoPhotoPermission gate=new GeckoPhotoPermission(web,web.current);boolean ready,settled;AttachmentIssue issue;JSONObject capture;
  void begin(){gate.capture(()->ready=true);capture=last();}
  JSONObject last(){return web.routePort.sent.isEmpty()?new JSONObject():web.routePort.sent.get(web.routePort.sent.size()-1);}
  JSONObject ack(JSONObject request,String status){return J.obj("schema",1,"status",status,"sessionId",request.optString("sessionId"),"requestToken",request.optString("requestToken"),"origin","https://photos.example","documentId","123456","scope","origin-and-origin-attributes","expiresAt","granted".equals(status)?System.currentTimeMillis()+120000:0);}
  void reply(JSONObject request,JSONObject value){web.cookieCallbacks.complete(web.routePort,request.optInt("id"),value.toString());}
  void captured(){begin();reply(capture,ack(capture,"captured"));check("picker remains open after capture",ready);}
  JSONObject allow(){gate.allow(true,value->{settled=true;issue=value;});return last();}
 }
 static void stale(String name,Consumer<Run> change){Run r=new Run();r.captured();JSONObject grant=r.allow();change.accept(r);r.reply(grant,r.ack(grant,"granted"));check(name+" cannot hand off a photo",r.issue!=null);}
 public static void main(String[] args){
  Run r=new Run();r.web.owner.privacy.level=1;r.gate=new GeckoPhotoPermission(r.web,r.web.current);r.begin();r.gate.allow(true,value->rUnused(value));check("standard mode opens chooser without native permissions",r.ready&&r.web.routePort.sent.isEmpty());
  r=new Run();r.begin();check("picker opens while capture is pending",r.ready&&r.capture.optString("kind").equals("photoCanvasCapture"));r.reply(r.capture,r.ack(r.capture,"captured"));check("capture does not itself grant",r.ready&&r.web.routePort.sent.size()==1);JSONObject grant=r.allow();check("actual photo asks native grant",grant.optString("kind").equals("photoCanvasGrant")&&r.issue==null);r.reply(grant,r.ack(grant,"granted"));check("bound current grant admits photo",r.settled&&r.issue==null);int sent=r.web.routePort.sent.size();r.gate.handedOff();r.gate.cancel();check("a handed photo keeps its native document lease",r.web.routePort.sent.size()==sent);
  r=new Run();r.begin();final Run textRun=r;r.gate.allow(false,value->{textRun.settled=true;textRun.issue=value;});
  check("ordinary files do not wait for canvas capture or grant",r.settled&&r.issue==null&&r.last().optString("kind").equals("photoCanvasRelease"));
  r.gate.handedOff();r.reply(r.capture,r.ack(r.capture,"captured"));check("late capture does not grant a lease to a selected document",r.web.routePort.sent.size()==2);
  r=new Run();r.begin();r.allow();
  check("a photo selected before capture waits without asking for a grant",r.issue==null&&r.web.routePort.sent.size()==1);
  r.reply(r.capture,r.ack(r.capture,"captured"));grant=r.last();
  check("a bound capture resumes pending photo selection",grant.optString("kind").equals("photoCanvasGrant")&&r.issue==null);
  r.reply(grant,r.ack(grant,"granted"));check("the pending photo still needs the matching grant",r.settled&&r.issue==null);
  r=new Run();r.begin();r.allow();r.gate.cancel();AttachmentIssue cancelled=r.issue;
  r.reply(r.capture,r.ack(r.capture,"captured"));
  check("cancelling while capture is pending settles the photo and denies any late grant",cancelled==AttachmentIssue.PAGE_CHANGED&&cancelled==r.issue&&r.web.routePort.sent.size()==2);
  r=new Run();r.begin();r.allow();r.web.timer.fire();
  check("capture timeout dismisses a pending image without closing the initial picker",r.ready&&r.issue!=null&&r.last().optString("kind").equals("photoCanvasRelease"));
  for(String status:new String[]{"denied","failed","not-required"}){r=new Run();r.captured();grant=r.allow();r.reply(grant,r.ack(grant,status));check(status+" cannot admit a photo while enhanced mode is still requested",r.issue==("denied".equals(status)?AttachmentIssue.PHOTO_DENIED:AttachmentIssue.PHOTO_UNCONFIRMED)&&r.last().optString("kind").equals("photoCanvasRelease"));}
  for(String bad:new String[]{"documentId","origin","sessionId","requestToken","scope","expiresAt"}){r=new Run();r.captured();grant=r.allow();JSONObject ack=r.ack(grant,"granted");try{ack.put(bad,bad.equals("expiresAt")?System.currentTimeMillis()+900000:"different");}catch(Exception e){throw new AssertionError(e);}r.reply(grant,ack);check("wrong "+bad+" cannot admit a photo",r.issue!=null);}
  stale("navigation epoch",x->x.web.owner.navigationEpoch++);stale("same URL reload",x->x.web.appearanceLoads.put(x.web.current,2L));stale("replaced page",x->x.web.locations.put(x.web.current,"https://photos.example/other"));stale("pending document load",x->x.web.pendingLoads.add(x.web.current));stale("closed session",x->x.web.current.open=false);stale("environment retired",x->x.web.owner.deleted=true);stale("browser replaced",x->x.web.owner.web=null);
  r=new Run();r.captured();grant=r.allow();r.gate.cancel();r.reply(grant,r.ack(grant,"granted"));check("cancellation during native grant rejects a late allowance",r.issue!=null);
  r=new Run();r.captured();grant=r.allow();r.web.timer.fire();check("native grant deadline refuses unsafe photo handoff",r.issue!=null);AttachmentIssue before=r.issue;r.reply(grant,r.ack(grant,"granted"));check("late native result cannot replace a timeout",before.equals(r.issue));
  System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false}");
 }
 static void rUnused(AttachmentIssue value){check("standard image needs no exception",value==null);}
}
class FakeTimer implements BrowserBridgeRequests.Timer {final List<Runnable> tasks=new ArrayList<>();public void schedule(Runnable action,long delay){tasks.add(action);}public void cancel(Runnable action){tasks.remove(action);}void fire(){for(Runnable task:new ArrayList<>(tasks))task.run();}}
class GeckoWebView {boolean destroyed;final ChatSession owner=new ChatSession();final FakeTimer timer=new FakeTimer();final BrowserBridgeRequests cookieCallbacks=new BrowserBridgeRequests(timer,null);WebExtension.Port routePort=new WebExtension.Port();GeckoSession current=new GeckoSession();final Map<GeckoSession,String> locations=new HashMap<>();final Map<GeckoSession,Long> appearanceLoads=new HashMap<>();final Set<GeckoSession> pendingLoads=new HashSet<>();GeckoWebView(){owner.web=this;locations.put(current,"https://photos.example/page");appearanceLoads.put(current,1L);}String photoUploadOrigin(GeckoSession s){return "https://photos.example";}}
class ChatSession {boolean deleted;long navigationEpoch;GeckoWebView web;final BrowserPrivacy privacy=new BrowserPrivacy();}
class BrowserPrivacy {int level=2;int level(){return level;}}
'''}

class PhotoPermissionTest(unittest.TestCase):
 def test_actual_java_gate(self):
  java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
  jar=Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/profile-host/json.jar'))
  self.assertTrue(jar.is_file(),'Existing JSON host dependency is required')
  with tempfile.TemporaryDirectory(prefix='photo-permission-host-') as folder:
   temp=Path(folder);sources=[]
   for relative,source in STUBS.items():
    file=temp/relative;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(source);sources.append(file)
   production=ROOT/'app/src/main/java'
   sources += [production/'local/pocketchat'/name for name in ('J.java','AttachmentIssue.java','BrowserBridgeRequests.java','GeckoPhotoPermission.java')]
   sources += [production/'org/mozilla/geckoview/AppSessionIdentity.java']
   classes=temp/'classes';classes.mkdir()
   built=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(classes),*map(str,sources)],capture_output=True,text=True)
   self.assertEqual(built.returncode,0,built.stdout+built.stderr)
   run=subprocess.run([java,'-cp',str(classes)+os.pathsep+str(jar),'local.pocketchat.PhotoPermissionHost'],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr);print(run.stdout.strip())

if __name__=='__main__':unittest.main()
