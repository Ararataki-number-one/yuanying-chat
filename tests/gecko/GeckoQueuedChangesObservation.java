package local.pocketchat;

import android.os.SystemClock;
import android.webkit.ValueCallback;
import org.json.*;
import java.io.IOException;
import java.util.UUID;

/** Test-only exact-document observer adapter. Production admission stays unchanged. */
final class GeckoQueuedChangesObservation {
  final GeckoIntegrationTestActivity activity;final ChatSession session;final GeckoIntegrationTestActivity.FixtureView view;
  final long command,epoch,expires;final int generation;final String environment,url,nonce,binding;final Object sdk,port;
  final JSONArray observations=new JSONArray();final boolean initiallyKnown;String document="";long sequence;boolean failed,retired;Runnable onFailure=()->{};
  GeckoQueuedChangesObservation(GeckoIntegrationTestActivity activity,long command)throws IOException{
    this.activity=activity;this.command=command;session=activity.session;view=(GeckoIntegrationTestActivity.FixtureView)session.web;
    url=view.getUrl();validateOwner(url,activity.slot);nonce=activity.eventStore.nonce;if(!nonce.matches("[0-9a-f]{32}"))throw new IOException("Current queued event nonce required");epoch=session.navigationEpoch;generation=session.environmentGeneration;environment=session.environmentId;sdk=view.current;port=view.ports.get(view.current);expires=SystemClock.elapsedRealtime()+20000;
    if(port==null||!view.hasVisibleDocument())throw new IOException("Queued fixture has no current SDK document port");initiallyKnown=session.taskGuardSnapshot().known;
    session.resourceObserverConnected(port);binding=session.resourceObserverBinding;view.queuedObservation=this;
  }
  static void validateOwner(String url,int slot)throws IOException{
    if(slot<0||slot>=Profiles.MAX||url==null||!url.matches("http://127\\.0\\.0\\.1:8765/fixture\\?context="+(slot+1)+"&action=(read|seed)&command=[1-9][0-9]{0,18}"))throw new IOException("Exact owned queued fixture document required");
  }
  static String adaptedScript(String original,String url,String nonce)throws IOException{
    if(nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IOException("Queued fixture nonce missing");
    if(url==null||!url.matches("http://127\\.0\\.0\\.1:8765/fixture\\?context=[1-8]&action=(read|seed)&command=[1-9][0-9]{0,18}"))throw new IOException("Exact owned queued fixture URL required");
    String guard="(location.href !== "+JSONObject.quote(url)+" || window.__pocketQueued46?.nonce !== "+JSONObject.quote(nonce)+")";
    String result=ResourcePressureIntegrationActivity.replaceResourceFixtureGuard(original,"location.origin !== 'https://chatgpt.com'",guard);
    return ResourcePressureIntegrationActivity.replaceResourceFixtureGuard(result,"location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'",guard);
  }
  boolean ownsUrl(String value){return !failed&&!retired&&activity.run==command&&activity.session==session&&session.environmentGeneration==generation&&environment.equals(session.environmentId)&&session.navigationEpoch==epoch&&view.current==sdk&&view.ports.get(view.current)==port&&SystemClock.elapsedRealtime()<=expires&&url.equals(view.getUrl())&&url.equals(value);}
  static boolean accepts(JSONObject packet,String nonce,String url,String binding,String document,long sequence,long now){
    JSONObject event=packet.optJSONObject("event");return nonce.equals(packet.optString("nonce"))&&url.equals(packet.optString("url"))&&event!=null&&"resource-work".equals(event.optString("type"))&&url.equals(event.optString("url"))&&binding.equals(event.optString("resourceBinding"))&&event.optString("documentId").matches("[a-zA-Z0-9-]{16,80}")&&(document.isEmpty()||document.equals(event.optString("documentId")))&&event.optLong("resourceSequence")>sequence&&event.opt("busy") instanceof Boolean&&event.opt("uploading") instanceof Boolean&&Math.abs(now-event.optLong("capturedAt"))<=10000;
  }
  String packet(){return "({nonce:window.__pocketQueued46?.nonce||'',url:location.href,event:window.__pocketQueued46?.event||null})";}
  void begin(Runnable ready){
    try{
      String install="window.__pocketQueued46={nonce:"+JSONObject.quote(nonce)+",event:null};window.PocketWebReply={postMessage:text=>{if(location.href!=="+JSONObject.quote(url)+"||window.__pocketQueued46?.nonce!=="+JSONObject.quote(nonce)+")return;const value=JSON.parse(text);if(value.type==='resource-work')window.__pocketQueued46.event=value;}};";
      String dom="let stop=document.createElement('button');stop.id='queued46-stop';stop.dataset.testid='stop-button';stop.textContent='Controlled pending reply';document.body.append(stop);";
      String script=adaptedScript(session.webObserver.script,url,nonce);
      view.evaluateJavascript("(()=>{"+install+dom+script+";window.__pocketReadDriver('observe-install',"+J.obj("resourceBinding",binding)+");window.__pocketWebReplyObserver?.requestResources?.("+JSONObject.quote(UUID.randomUUID().toString())+");return "+packet()+"})()",raw->{if(capture(raw,Boolean.TRUE))ready.run();});
    }catch(Exception error){fail(error.toString());}
  }
  boolean intercept(String code,ValueCallback<String> callback){
    if(!ownsUrl(view.getUrl())||!code.startsWith("window.__pocketWebReplyObserver?.requestResources?.("))return false;
    view.evaluateJavascript("(()=>{"+code+";return "+packet()+"})()",raw->{capture(raw,null);if(callback!=null)callback.onReceiveValue("null");});return true;
  }
  void idle(){view.evaluateJavascript("(()=>{document.getElementById('queued46-stop')?.remove();window.__pocketWebReplyObserver?.requestResources?.("+JSONObject.quote(UUID.randomUUID().toString())+");return "+packet()+"})()",raw->capture(raw,Boolean.FALSE));}
  boolean capture(String raw,Boolean expected){
    if(retired)return false;
    if(!ownsUrl(view.getUrl())){fail("Queued observation owner changed");return false;}JSONObject packet=J.parse(raw);
    if(!accepts(packet,nonce,url,binding,document,sequence,System.currentTimeMillis())){fail("Queued SDK observer packet rejected");return false;}
    JSONObject event=packet.optJSONObject("event");session.resourceWebsiteObservation(event,port);TaskGuardSnapshot guard=session.taskGuardSnapshot();
    if(!guard.known||expected!=null&&guard.replyBusy!=expected.booleanValue()){fail("Queued SDK task guard did not reflect the document");return false;}
    document=event.optString("documentId");sequence=event.optLong("resourceSequence");observations.put(J.obj("documentId",document,"sequence",sequence,"busy",guard.replyBusy,"fileBusy",guard.fileBusy,"known",guard.known,"navigationEpoch",guard.navigationEpoch));return true;
  }
  void retireAfterApplied(){JSONObject last=observations.optJSONObject(observations.length()-1);if(last==null||!last.optBoolean("known")||last.optBoolean("busy")){fail("Cannot retire queued observer before actual idle evidence");return;}retired=true;}
  JSONObject attach(JSONObject result){NetworkCatalog.put(result,"queuedDocumentObservation",J.obj("scope","Test-only exact loopback document; actual production observer bytes via SDK evaluate and real port; no public website or phone acceptance","sourceCommit",activity.eventBuildIdentity.optString("sourceCommit"),"runNonce",nonce,"environmentId",environment,"environmentGeneration",generation,"processSlot",activity.slot,"command",command,"resourceBinding",binding,"url",url,"navigationEpoch",epoch,"initiallyKnown",initiallyKnown,"observations",observations,"retiredAfterApplied",retired,"actualSdkSampling",true,"productionAdmissionChanged",false));return result;}
  void fail(String why){if(failed)return;failed=true;onFailure.run();activity.event(command,"error",J.obj("error",why,"stage","queued-document-observation","observations",observations));}
}
