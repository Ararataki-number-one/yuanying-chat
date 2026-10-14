package local.pocketchat;

import android.content.Context;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Actual production bridge/runtime admission with explicitly synthetic pressure.
 * Platform readings are observations, never a physical capacity or login verdict. */
public final class ResourcePressureIntegrationActivity extends GeckoIdentityPrototypeIntegrationActivity {
  final JSONArray resourceChecks=new JSONArray(),resourceEvaluationTrace=new JSONArray();int resourceEvaluationDropped;JSONObject platform=new JSONObject(),allocation=new JSONObject();
  ChatSession.Observer pressureObserver;boolean coldChecked,controlsStarted,resourceDone;String target,pendingBytes;int readyAttempts;
  final Object fixtureDocument=new Object();String documentId;JSONObject resourcePortControls=new JSONObject();final List<JSONObject> resourceRequests=new ArrayList<>();
  class PressureView extends FixtureView {
    boolean low=true;int pauses,resumes,closures;
    PressureView(Context c,ChatSession s){super(c,s);}
    @Override ResourcePressureController.MemorySample resourceMemory(){return new ResourcePressureController.MemorySample(true,low,1024,4096,2048,SystemClock.elapsedRealtime(),"synthetic-pressure-control");}
    @Override boolean resourcePage(String value){return value!=null&&value.startsWith(origin+"/");}
    @Override boolean resourceSamePage(String a,String b){return a!=null&&a.equals(b)&&resourcePage(a);}
    @Override public void onPause(){pauses++;super.onPause();}
    @Override public void onResume(){resumes++;super.onResume();}
    @Override public void destroy(){closures++;super.destroy();}
  }
  @Override FixtureView createFixtureView(Context context,ChatSession session){return new PressureView(context,session);}
  @Override String reportFile(){return "resource-pressure-results.json";}
  @Override String reportTag(){return "PocketResourceFixture";}
  static String bootstrapDocument(String method,Map<String,String> query,String nonce){
    if(!"GET".equals(method)||query==null||nonce==null||!nonce.matches("[0-9a-f]{32}")||query.size()!=2||!query.keySet().equals(new HashSet<>(Arrays.asList("run","phase")))||!nonce.equals(query.get("run")))return null;
    String phase=query.get("phase");if(!"parent".equals(phase)&&!"popup".equals(phase))return null;
    return "<!doctype html><meta charset=utf-8><title>Controlled resource fixture</title><body><p>Controlled resource "+phase+"</p><input id=resource-ready value="+phase+"></body>";
  }
  @Override String resourceFixtureDocument(String method,Map<String,String> query){return bootstrapDocument(method,query,run);}
  @Override void resourceFixtureResponse(int connection,String parsedRequestLine,String method,String requestTarget,Map<String,String> query,Map<String,String> headers,String document,long requestAt,long responseAt)throws IOException{
    synchronized(resourceRequests){if(resourceRequests.size()>=4)throw new IOException("Too many controlled resource requests");resourceRequests.add(J.obj("sourceCommit",source,"runNonce",run,"sequence",resourceRequests.size()+1,"connection",connection,"method",method,"path",requestTarget,"phase",query.get("phase"),"userAgent",headers.getOrDefault("user-agent",""),"acceptLanguage",headers.getOrDefault("accept-language",""),"requestAt",requestAt,"responseAt",responseAt,"responseStatus",200,"responseBytes",document.getBytes(StandardCharsets.UTF_8).length,"responseSha256",NativeNetwork.hash(document),"parsedRequestLine",parsedRequestLine,"parsedRequestLineBytes",parsedRequestLine.getBytes(StandardCharsets.ISO_8859_1).length,"parsedRequestLineSha256",NativeNetwork.hash(parsedRequestLine),"requestLineScope","Parsed HTTP request line without CRLF; not a raw socket-byte capture"));}
  }
  void resourceCheck(String name,boolean value){resourceChecks.put(J.obj("name",name,"pass",value));check(name,value);}
  @Override void openBrowser(){
    super.openBrowser();if(finished||view==null)return;
    try{
      ResourcePressureController.MemorySample actual=ResourcePressureController.read(this);
      platform=J.obj("source",actual.source,"known",actual.known,"lowMemory",actual.lowMemory,"availableBytes",actual.availableBytes,"totalBytes",actual.totalBytes,"thresholdBytes",actual.thresholdBytes,"sampledAt",actual.sampledAt,"observedAt",SystemClock.elapsedRealtime(),"scope","Actual Android ActivityManager snapshot; not a device capacity measurement");
      storage.execute(()->{android.os.Debug.MemoryInfo info=new android.os.Debug.MemoryInfo();Debug.getMemoryInfo(info);Runtime java=Runtime.getRuntime();JSONObject process=J.obj("source","android-Debug.MemoryInfo","pid",android.os.Process.myPid(),"totalPssKb",info.getTotalPss(),"javaUsedBytes",java.totalMemory()-java.freeMemory(),"javaMaxBytes",java.maxMemory(),"scope","Current fixture app PID only; Gecko child processes excluded; no capacity budget");handler.post(()->reportPut(platform,"process",process));});
      target=origin+"/resource?run="+run+"&phase=parent";documentId=java.util.UUID.randomUUID().toString();
      owner.beginNavigation(target,"Controlled cold allocation");view.loadUrl(target);
      pressureObserver=()->{if(!coldChecked&&view.resourceDeferred)try{coldAllocation();}catch(Throwable failure){finish(failure);}};owner.add(pressureObserver);
    }catch(Throwable failure){finish(failure);}
  }
  void coldAllocation()throws Exception{
    coldChecked=true;owner.remove(pressureObserver);owner.handler.removeCallbacks(owner.tick);
    resourceCheck("Cold low memory reaches the production typed deferral",view.resourceDeferred&&view.resourceAdmission==ResourcePressureController.Admission.DEFER);
    resourceCheck("Cold low memory creates zero actual Gecko runtimes",view.runtime==null&&owner.resources.created==0&&owner.resources.deferred>0);
    resourceCheck("Cold foreground and default template are not false recovery work",owner.uiVisible&&!owner.resourceRestoreWork());
    long oldEpoch=owner.navigationEpoch;owner.navigationTimeout(oldEpoch);
    resourceCheck("Memory wait does not become page failure or network recovery",owner.navigating&&!owner.navigationFailed&&!owner.recoveryScheduled&&owner.pageError.isEmpty());
    owner.recoveryScheduled=true;owner.updateBrowserActivity();owner.foreground(true);owner.handler.removeCallbacks(owner.tick);
    resourceCheck("Cold network retry timer cannot bypass low memory admission",view.runtime==null&&owner.resources.created==0&&view.resourceDeferred);
    owner.recoveryScheduled=false;
    resourceCheck("Deferred candidate retains the captured URL",target.equals(view.queued)&&target.equals(owner.navigationTarget));
    view.queued="";owner.pending=J.obj("id","resource-"+run,"kind","web","engine","gecko","attempted",true,"webSuspended",true,"expectedUrl","https://chatgpt.com/","prompt","synthetic resource recovery");pendingBytes=owner.pending.toString();
    if(!owner.prefs.edit().putString("pending",pendingBytes).commit())throw new IOException("Controlled pending persistence failed");owner.deliveries.recover(owner.pending);
    owner.updateBrowserActivity();owner.handler.removeCallbacks(owner.tick);
    resourceCheck("Durable user recovery outranks synthetic low memory",view.runtime!=null&&view.resourceAdmission==ResourcePressureController.Admission.RECOVERY&&owner.resources.created==1);
    resourceCheck("Recovery renews navigation deadline without discarding target",owner.navigationEpoch>oldEpoch&&target.equals(owner.navigationTarget)&&!owner.navigationFailed);
    owner.navigationTimeout(oldEpoch);
    resourceCheck("Old navigation timeout cannot fail the resumed candidate",!owner.navigationFailed);
    allocation=J.obj("coldRuntimeCreates",0,"recoveryRuntimeCreates",owner.resources.created,"pressureSource","synthetic-pressure-control","recoveredTarget",target,"oldEpoch",oldEpoch,"newEpoch",owner.navigationEpoch,"actualRuntimeObject",System.identityHashCode(view.runtime),"physicalCapacityAcceptance",false);
  }
  @Override void beginCase(){
    if(finished)return;if(resourceDone){super.beginCase();return;}
    if(controlsStarted)return;controlsStarted=true;
    // The SDK session is genuinely open. Wait only for this exact document's
    // bounded production extension connection, not for a fabricated ready flag.
    awaitResourceDocument();
  }
  void awaitResourceDocument(){
    if(finished)return;
    if(!target.equals(view.getUrl())||!view.hasVisibleDocument()||view.ports.get(view.current)==null){if(++readyAttempts>100){finish(new IOException("Controlled resource document/port did not become ready"));return;}handler.postDelayed(this::awaitResourceDocument,200);return;}
    evaluate("(()=>{document.body.innerHTML='<form><textarea id=prompt-textarea></textarea><button id=stop data-testid=stop-button>Stop</button><div id=first data-file-name=first.txt data-upload-state=uploading><button aria-label=\"Remove file\">Remove</button></div><div id=second data-file-name=second.txt data-upload-state=ready><button aria-label=\"Remove file\">Remove</button></div></form>';document.body.dataset.sent='0';document.querySelector('form').addEventListener('submit',e=>{e.preventDefault();document.body.dataset.sent=String(Number(document.body.dataset.sent)+1)});return {url:location.href,busy:!!document.getElementById('stop'),uploading:document.getElementById('first').dataset.uploadState==='uploading'}})()",this::workControls);
  }
  void evaluate(String code,java.util.function.Consumer<JSONObject> done){
    final GeckoSession selected=view.current;final Object port=view.ports.get(selected);final long epoch=owner.navigationEpoch,started=SystemClock.elapsedRealtime();final String requestedUrl=view.getUrl();
    view.evaluateJavascript(code,raw->{if(finished)return;try{
      String observed=raw==null?"null":raw;
      if(resourceEvaluationTrace.length()<128)resourceEvaluationTrace.put(J.obj("sequence",resourceEvaluationTrace.length()+1,"sourceCommit",source,"runNonce",run,"scriptSha256",NativeNetwork.hash(code),"startedAt",started,"completedAt",SystemClock.elapsedRealtime(),"requestedSession",System.identityHashCode(selected),"requestedPort",System.identityHashCode(port),"requestedEpoch",epoch,"requestedUrl",requestedUrl,"currentSession",System.identityHashCode(view.current),"currentPort",System.identityHashCode(view.ports.get(view.current)),"currentEpoch",owner.navigationEpoch,"currentUrl",view.getUrl(),"visibleDocument",view.hasVisibleDocument(),"observerDocument",owner.resourceObserverDocument,"observerBinding",owner.resourceObserverBinding,"rawResult",observed.length()>16384?observed.substring(0,16384):observed,"rawResultCharacters",observed.length(),"rawResultTruncated",observed.length()>16384));else resourceEvaluationDropped++;
      JSONObject value=J.parse(raw);if(value.length()==0)throw new IOException("Actual controlled Gecko evaluation returned no observation");done.accept(value);
    }catch(Throwable failure){finish(failure);}});
  }
  // evaluateJavascript returns immediate JSON, so an async production driver
  // needs the same Promise handoff and 2500 ms bound as ChatSession.asyncDriver.
  // This adapter changes only the fixed loopback fixture's result collection.
  final class AttachmentResult {
    final GeckoSession session=view.current;final Object port=view.ports.get(session);final long epoch=owner.navigationEpoch,expires=SystemClock.elapsedRealtime()+2500;
    final String url=target,binding=owner.resourceObserverBinding,document=owner.resourceObserverDocument,key="__pocketResourceAttachment_"+run+"_"+UUID.randomUUID().toString().replace("-","");
    final JSONArray names=owner.resourceUploadNames;final java.util.function.Consumer<JSONObject> done;double timeOrigin;
    AttachmentResult(java.util.function.Consumer<JSONObject> done){this.done=done;}
    boolean owns(){return session!=null&&session.isOpen()&&view.current==session&&port!=null&&view.ports.get(session)==port&&owner.navigationEpoch==epoch&&url.equals(target)&&url.equals(view.getUrl())&&view.hasVisibleDocument()&&owner.resourceObserverPort==port&&owner.resourceObserverEpoch==epoch&&binding.equals(owner.resourceObserverBinding)&&document.equals(owner.resourceObserverDocument)&&owner.resourceUploadNames==names;}
    void verify(JSONObject value)throws Exception{
      if(!owns()||!source.equals(value.optString("sourceCommit"))||!run.equals(value.optString("runNonce"))||!key.equals(value.optString("key"))||!url.equals(value.optString("documentUrl"))||Double.compare(value.getDouble("timeOrigin"),timeOrigin)!=0)throw new IOException("Actual attachment Promise changed source, invocation, document or native ownership");
    }
    void start(String code){
      if(!owns()){finish(new IOException("Actual attachment Promise has no owned SDK document/port"));return;}
      String wrapper="(()=>{const key="+JSONObject.quote(key)+",base={sourceCommit:"+JSONObject.quote(source)+",runNonce:"+JSONObject.quote(run)+",key,documentUrl:location.href,timeOrigin:performance.timeOrigin};if(Object.prototype.hasOwnProperty.call(window,key))throw new Error('Owned attachment result key already exists');window[key]={...base,state:'pending'};Promise.resolve("+code+").then(value=>window[key]={...base,state:'fulfilled',value},error=>window[key]={...base,state:'rejected',error:String(error?.stack||error)});return {...base,state:'armed'};})()";
      evaluate(wrapper,armed->{try{timeOrigin=armed.getDouble("timeOrigin");if(!Double.isFinite(timeOrigin)||timeOrigin<=0||!"armed".equals(armed.optString("state")))throw new IOException("Actual attachment Promise was not armed in a real document");verify(armed);poll();}catch(Throwable failure){finish(failure);}});
    }
    void poll(){
      if(finished)return;if(!owns()){finish(new IOException("Actual attachment Promise lost its native document/port"));return;}if(SystemClock.elapsedRealtime()>expires){finish(new IOException("Actual attachment Promise exceeded the production 2500 ms bound"));return;}
      String pollScript="(()=>({documentUrl:location.href,timeOrigin:performance.timeOrigin,result:window["+JSONObject.quote(key)+"]||null}))()";
      evaluate(pollScript,actual->{try{
        if(!owns()||!url.equals(actual.optString("documentUrl"))||Double.compare(actual.getDouble("timeOrigin"),timeOrigin)!=0||SystemClock.elapsedRealtime()>expires)throw new IOException("Actual attachment Promise lost its owned document or deadline");
        JSONObject result=actual.optJSONObject("result");if(result==null)throw new IOException("Actual owned attachment Promise result disappeared");verify(result);
        String state=result.optString("state");if("pending".equals(state)){handler.postDelayed(this::poll,120);return;}if("rejected".equals(state))throw new IOException("Actual attachment Promise rejected: "+result.optString("error"));if(!"fulfilled".equals(state))throw new IOException("Actual attachment Promise state is invalid");
        JSONObject value=result.optJSONObject("value");if(value==null||value.length()==0||!value.optBoolean("ok")||value.optJSONArray("files")==null)throw new IOException("Actual attachment Promise resolved without attachment observations");
        String cleanupScript="(()=>{delete window["+JSONObject.quote(key)+"];return {removed:true}})()";
        evaluate(cleanupScript,removed->{if(!owns()||SystemClock.elapsedRealtime()>expires||!removed.optBoolean("removed")){finish(new IOException("Actual attachment result cleanup changed native ownership or deadline"));return;}done.accept(value);});
      }catch(Throwable failure){finish(failure);}});
    }
  }
  void workControls(JSONObject actual){
    try{
      owner.handler.removeCallbacks(owner.tick);owner.navigating=false;owner.state=J.obj("url",target,"busy",false);owner.stateEpoch=owner.navigationEpoch;
      resourceCheck("Fallback captured URL loads a real controlled document",target.equals(actual.optString("url"))&&view.current!=null&&view.current.isOpen()&&view.hasVisibleDocument());
      resourceCheck("Recovery preserves attempted task and never resends it",pendingBytes.equals(owner.pending.toString())&&pendingBytes.equals(owner.prefs.getString("pending","")));
      int pause=((PressureView)view).pauses;owner.uiVisible=false;owner.updateBrowserActivity();owner.handler.removeCallbacks(owner.tick);
      resourceCheck("Existing pending recovery retains the open runtime",view.current.isOpen()&&owner.resources.created==1&&((PressureView)view).pauses==pause);
      owner.pending=null;owner.prefs.edit().remove("pending").commit();owner.identityApplicationPending=false;owner.identity.queueUnavailable=false;
      Object realPort=view.ports.get(view.current);owner.resourceObserverConnected(realPort);
      JSONObject observation=J.obj("url",actual.optString("url"),"documentId",documentId,"resourceBinding",owner.resourceObserverBinding,"resourceSequence",1,"busy",actual.optBoolean("busy"),"uploading",actual.optBoolean("uploading"),"capturedAt",System.currentTimeMillis());
      owner.resourceWebsiteObservation(observation,realPort);owner.handler.removeCallbacks(owner.tick);
      resourceCheck("Controlled page task observations protect existing activity",owner.currentReplyActive()&&owner.resourceFilesActive()&&owner.browserWorkActive()&&view.current.isOpen());
      owner.resourceWebsiteObservation(J.obj("url",target,"documentId",documentId,"resourceBinding",owner.resourceObserverBinding,"resourceSequence",1,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),realPort);
      resourceCheck("Late idle resource observation cannot clear newer work",owner.resourceWebsiteBusy&&owner.resourceWebsiteUploading);
      owner.resourceWebsiteObservation(J.obj("url",target,"documentId",java.util.UUID.randomUUID().toString(),"resourceBinding",owner.resourceObserverBinding,"resourceSequence",2,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),realPort);
      resourceCheck("Another document identity cannot clear current work",owner.resourceWebsiteBusy&&owner.resourceWebsiteUploading);
      owner.resourceObserverConnected(fixtureDocument);owner.resourceWebsiteObservation(J.obj("url",target,"documentId",documentId,"resourceBinding",owner.resourceObserverBinding,"resourceSequence",2,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),realPort);
      resourceCheck("Replaced extension port cannot supply an idle observation",owner.resourceWebsiteEpoch==-1);
      owner.resourceObserverConnected(realPort);reportPut(observation,"resourceBinding",owner.resourceObserverBinding);owner.resourceWebsiteObservation(observation,realPort);
      String next=target+"&spa=1";owner.beginNavigation(next,"Controlled same document route");
      evaluate("(()=>{history.pushState({},'',"+JSONObject.quote(next)+");return {url:location.href,documentId:"+JSONObject.quote(documentId)+",resourceBinding:"+JSONObject.quote(owner.resourceObserverBinding)+"}})()",actualRoute->{target=next;awaitSameDocument(actualRoute,realPort,0);});

    }catch(Throwable failure){finish(failure);}
  }
  void awaitSameDocument(JSONObject actual,Object port,int attempt){
    if(finished)return;
    if(!target.equals(view.getUrl())){if(attempt>=50){finish(new IOException("Actual same-document route did not update"));return;}handler.postDelayed(()->awaitSameDocument(actual,port,attempt+1),100);return;}
    try{
      owner.resourceObserverRouteReady(actual,port);owner.resourceWebsiteObservation(J.obj("url",actual.optString("url"),"documentId",actual.optString("documentId"),"resourceBinding",owner.resourceObserverBinding,"resourceSequence",2,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),port);owner.handler.removeCallbacks(owner.tick);
      resourceCheck("Confirmed same document route retains observer port and monotonic sequence",owner.resourceObserverPort==port&&owner.resourceObserverEpoch==owner.navigationEpoch&&owner.resourceObserverSequence==2&&owner.resourceWebsiteEpoch==owner.navigationEpoch);
      owner.navigating=false;attachmentControls();
    }catch(Throwable failure){finish(failure);}
  }
  void attachmentControls(){try{
      owner.resourceWebsiteBusy=false;owner.resourceWebsiteUploading=false;owner.resourceWebsiteEpoch=-1;
      owner.inFlight=true;owner.updateBrowserActivity();owner.handler.removeCallbacks(owner.tick);
      resourceCheck("In flight inspection retains existing browser activity",owner.browserWorkActive()&&!owner.browserPaused&&view.current.isOpen());owner.finishResourceInspection();
      resourceCheck("Inspection completion releases its bounded activity hold",!owner.inFlight);
      resourceCheck("Inspection completion preserves the existing polling cadence",!owner.handler.hasCallbacks(owner.tick));
      owner.resourceFilesPrepared(new Uri[]{Uri.parse("file:///synthetic/first.txt")},owner.navigationEpoch);JSONArray first=owner.resourceUploadNames;
      owner.resourceFilesPrepared(new Uri[]{Uri.parse("file:///synthetic/second.txt")},owner.navigationEpoch);JSONArray both=owner.resourceUploadNames;
      resourceCheck("Repeated selections retain both outstanding file names",both.length()==2&&both.optString(0).equals("first.txt")&&both.optString(1).equals("second.txt"));
      owner.resourceUploadObservation(J.obj("ok",true,"files",J.arr(J.obj("name","first.txt","state","ready"))),owner.navigationEpoch,first,target);
      resourceCheck("Late observation of an older selection cannot release new files",owner.resourceUploadNames==both&&owner.resourceFilesActive());
      inspectAttachments(0);
    }catch(Throwable failure){finish(failure);}
  }
  void inspectAttachments(int step){
    String script=owner.attachmentDriver.replace("location.protocol!=='https:'||location.hostname!=='chatgpt.com'","location.origin!=="+JSONObject.quote(origin)).replace("__ACTION__",JSONObject.quote("attachment-state")).replace("__ARG__",J.obj("names",owner.resourceUploadNames,"url",target).toString());
    new AttachmentResult(actual->{
      try{
        JSONArray names=owner.resourceUploadNames;owner.resourceUploadObservation(actual,owner.navigationEpoch,names,target);owner.handler.removeCallbacks(owner.tick);
        if(step==0){resourceCheck("Actual delayed first attachment retains both selections",owner.resourceFilesActive()&&names.length()==2);evaluate("(()=>{document.getElementById('first').dataset.uploadState='ready';return {updated:true}})()",ignored->inspectAttachments(1));}
        else if(step==1){resourceCheck("One terminal attachment sample does not release selection work",owner.resourceFilesActive()&&owner.resourceUploadStable==1);inspectAttachments(2);}
        else{resourceCheck("Two actual terminal attachment samples release completed selections",!owner.resourceFilesActive()&&owner.resourceUploadNames.length()==0);beginRetainedPortControls();}
      }catch(Throwable failure){finish(failure);}
    }).start(script);
  }
  void beginRetainedPortControls(){
    try{
      owner.uiVisible=true;owner.updateBrowserActivity();owner.handler.removeCallbacks(owner.tick);
      // Explicit fixture-only origin/transport adapters: run the production
      // observer in the actual SDK document, collect its bytes via the existing
      // native evaluate port, then pass them unchanged to production admission.
      // This is not ChatGPT, a real file upload or a physical user gesture.
      owner.webObserver.script=owner.webObserver.script.replace("location.origin !== 'https://chatgpt.com'","location.origin !== "+JSONObject.quote(origin))+"\nwindow.__pocketFixtureResourceEvents=window.__pocketFixtureResourceEvents||[];window.PocketWebReply={postMessage:text=>{const value=JSON.parse(text);if(value.type==='resource-work'){const values=window.__pocketFixtureResourceEvents;values.push(value);if(values.length>32)values.shift();}}};";
      reportPut(resourcePortControls,"sourceCommit",source);reportPut(resourcePortControls,"runNonce",run);reportPut(resourcePortControls,"phaseScope","controlled-production-delegate-sdk-open-load");reportPut(resourcePortControls,"syntheticPopupActivation",true);reportPut(resourcePortControls,"trustedUserGesture",false);reportPut(resourcePortControls,"trustedPopupGesture",false);reportPut(resourcePortControls,"realWebsiteExecution",false);reportPut(resourcePortControls,"observerDelivery","Actual SDK document observer bytes read through native evaluate; unchanged bytes passed to production resource admission");
      evaluate("(()=>{document.getElementById('first').dataset.uploadState='uploading';let stop=document.getElementById('stop');if(!stop){stop=document.createElement('button');stop.id='stop';stop.dataset.testid='stop-button';stop.textContent='Stop';document.querySelector('form').append(stop);}document.getElementById('prompt-textarea').value='retained-resource-draft';document.cookie='resourceRetained=preserved;path=/';return {draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,sent:Number(document.body.dataset.sent),url:location.href}})()",before->{
        reportPut(resourcePortControls,"before",before);owner.resourceObserverConnected(view.ports.get(view.current));owner.webObserver.pageReady();
        awaitResourceSnapshot(true,true,0,initial->openControlledPopup(initial));
      });
    }catch(Throwable failure){finish(failure);}
  }
  void awaitResourceSnapshot(boolean busy,boolean uploading,int attempt,java.util.function.Consumer<JSONObject> done){
    if(finished)return;owner.handler.removeCallbacks(owner.tick);final Object port=view.ports.get(view.current);final String binding=owner.resourceObserverBinding;
    evaluate("(()=>({events:(window.__pocketFixtureResourceEvents||[]).filter(value=>value.resourceBinding==="+JSONObject.quote(binding)+"),documentId:window.__pocketWebReplyObserver?.documentId||'',url:location.href}))()",actual->{
      JSONArray events=actual.optJSONArray("events");JSONObject event=events==null||events.length()==0?null:events.optJSONObject(events.length()-1);
      if(event==null||event.optBoolean("busy")!=busy||event.optBoolean("uploading")!=uploading){if(attempt>=25){finish(new IOException("Actual retained resource snapshot did not become ready"));return;}handler.postDelayed(()->awaitResourceSnapshot(busy,uploading,attempt+1,done),200);return;}
      if(port!=view.ports.get(view.current)||!binding.equals(owner.resourceObserverBinding)||!actual.optString("url").equals(view.getUrl())||!actual.optString("documentId").equals(event.optString("documentId"))){finish(new IOException("Actual resource snapshot changed its SDK port/document ownership"));return;}
      owner.resourceWebsiteObservation(event,port);owner.handler.removeCallbacks(owner.tick);done.accept(event);
    });
  }
  void openControlledPopup(JSONObject initial){
    try{
      GeckoSession parent=view.current;Object parentPort=view.ports.get(parent);String parentBinding=owner.resourceObserverBinding;
      resourceCheck("Actual parent observer captures reply and upload before popup",owner.resourceWebsiteBusy&&owner.resourceWebsiteUploading&&owner.resourceWebsiteEpoch==owner.navigationEpoch&&initial.optString("resourceBinding").equals(parentBinding));
      reportPut(resourcePortControls,"parentBefore",initial);reportPut(resourcePortControls,"parentSession",System.identityHashCode(parent));reportPut(resourcePortControls,"parentPort",System.identityHashCode(parentPort));reportPut(resourcePortControls,"parentEpochBefore",owner.navigationEpoch);reportPut(resourcePortControls,"parentBeforeBinding",owner.resourceObserverBinding);
      String popupTarget=origin+"/resource?run="+run+"&phase=popup";
      // Controlled direct production-delegate invocation, followed by a real
      // official SDK open/load. No synthetic click is called a user gesture.
      parent.getNavigationDelegate().onNewSession(parent,popupTarget).accept(popup->{
        try{if(popup==null)throw new IOException("Controlled production popup delegate refused the fixture");popup.open(view.runtime);popup.loadUri(popupTarget);awaitControlledPopup(parent,parentPort,parentBinding,initial,popup,popupTarget,0);}catch(Throwable failure){finish(failure);}
      },failure->finish(new IOException("Controlled production popup delegate failed",failure)));
    }catch(Throwable failure){finish(failure);}
  }
  void awaitControlledPopup(GeckoSession parent,Object parentPort,String parentBinding,JSONObject initial,GeckoSession popup,String popupTarget,int attempt){
    if(finished)return;owner.handler.removeCallbacks(owner.tick);
    if(view.current!=popup||!popup.isOpen()||!popupTarget.equals(view.getUrl())||!view.hasVisibleDocument()||view.ports.get(popup)==null){if(attempt>=40){finish(new IOException("Actual SDK popup/port did not become ready"));return;}handler.postDelayed(()->awaitControlledPopup(parent,parentPort,parentBinding,initial,popup,popupTarget,attempt+1),200);return;}
    try{
      resourceCheck("Production popup activation owns a distinct actual SDK port",owner.resourceObserverPort==view.ports.get(popup)&&owner.resourceObserverPort!=parentPort&&!owner.resourceObserverBinding.equals(parentBinding));
      evaluate("(()=>{document.body.innerHTML='<form><textarea id=prompt-textarea></textarea><button data-testid=stop-button>Stop</button><div data-upload-state=uploading></div></form>';return {url:location.href}})()",actual->{
        owner.webObserver.pageReady();awaitResourceSnapshot(true,true,0,popupEvent->{
          try{
            Object popupPort=view.ports.get(popup);reportPut(resourcePortControls,"popup",popupEvent);reportPut(resourcePortControls,"popupSession",System.identityHashCode(popup));reportPut(resourcePortControls,"popupPort",System.identityHashCode(popupPort));reportPut(resourcePortControls,"popupEpoch",owner.navigationEpoch);reportPut(resourcePortControls,"popupBinding",owner.resourceObserverBinding);
            if(!view.closePopup())throw new IOException("Production closePopup refused its actual current popup");owner.handler.removeCallbacks(owner.tick);
            resourceCheck("Returning from actual SDK popup rebinds retained parent port",view.current==parent&&parent.isOpen()&&!popup.isOpen()&&view.ports.get(parent)==parentPort&&owner.resourceObserverPort==parentPort&&owner.resourceObserverEpoch==owner.navigationEpoch);
            resourceCheck("Retained parent activation renews the observation binding",!owner.resourceObserverBinding.equals(parentBinding)&&!owner.resourceObserverBinding.equals(popupEvent.optString("resourceBinding"))&&owner.resourceWebsiteEpoch==-1);
            owner.resourceWebsiteObservation(popupEvent,popupPort);
            reportPut(resourcePortControls,"stalePopupAfter",retainedNativeState());
            resourceCheck("Closed popup observations cannot authorize retained parent state",owner.resourceWebsiteEpoch==-1&&owner.resourceObserverPort==parentPort);
            owner.resourceWebsiteObservation(initial,parentPort);
            reportPut(resourcePortControls,"staleParentAfter",retainedNativeState());
            resourceCheck("Queued old parent binding cannot authorize retained state",owner.resourceWebsiteEpoch==-1&&owner.resourceObserverSequence==0);
            awaitResourceSnapshot(true,true,0,returned->finishRetainedPortControls(initial,returned));
          }catch(Throwable failure){finish(failure);}
        });
      });
    }catch(Throwable failure){finish(failure);}
  }
  JSONObject retainedNativeState(){return J.obj("websiteEpoch",owner.resourceWebsiteEpoch,"sequence",owner.resourceObserverSequence,"observerBinding",owner.resourceObserverBinding,"observerPort",System.identityHashCode(owner.resourceObserverPort),"navigationEpoch",owner.navigationEpoch);}
  void finishRetainedPortControls(JSONObject initial,JSONObject returned){
    try{
      reportPut(resourcePortControls,"parentReturned",returned);reportPut(resourcePortControls,"returnEpoch",owner.navigationEpoch);reportPut(resourcePortControls,"parentReturnedBinding",owner.resourceObserverBinding);reportPut(resourcePortControls,"returnedSession",System.identityHashCode(view.current));reportPut(resourcePortControls,"returnedPort",System.identityHashCode(view.ports.get(view.current)));
      resourceCheck("Retained document refresh captures actual reply and upload without mutation",owner.resourceWebsiteBusy&&owner.resourceWebsiteUploading&&owner.resourceWebsiteEpoch==owner.navigationEpoch&&returned.optString("documentId").equals(initial.optString("documentId"))&&returned.optLong("resourceSequence")>initial.optLong("resourceSequence"));
      evaluate("(()=>({draft:document.getElementById('prompt-textarea').value,cookie:document.cookie,sent:Number(document.body.dataset.sent),url:location.href}))()",after->{
        try{
          JSONObject before=resourcePortControls.optJSONObject("before");reportPut(resourcePortControls,"after",after);
          resourceCheck("Retained observer rebind preserves draft login marker and send count",before!=null&&before.optString("draft").equals(after.optString("draft"))&&before.optString("cookie").equals(after.optString("cookie"))&&after.optInt("sent",-1)==0&&target.equals(after.optString("url")));
          evaluate("(()=>{document.getElementById('stop').remove();document.getElementById('first').dataset.uploadState='ready';return {updated:true}})()",ignored->awaitResourceSnapshot(false,false,0,idle->{
            try{reportPut(resourcePortControls,"parentIdle",idle);resourceCheck("Actual post return terminal observation releases reply and upload protection",!owner.resourceWebsiteBusy&&!owner.resourceWebsiteUploading&&owner.resourceWebsiteEpoch==owner.navigationEpoch&&idle.optLong("resourceSequence")>returned.optLong("resourceSequence"));finishControls();}catch(Throwable failure){finish(failure);}
          }));
        }catch(Throwable failure){finish(failure);}
      });
    }catch(Throwable failure){finish(failure);}
  }
  void finishControls(){
    evaluate("(()=>({sent:Number(document.body.dataset.sent),url:location.href}))()",actual->{
      try{
        resourceCheck("Resource handling sends no controlled website message",actual.optInt("sent",-1)==0&&target.equals(actual.optString("url")));
        resourceCheck("Pressure handling never hard closes the live bridge",((PressureView)view).closures==0&&view.current.isOpen()&&owner.resources.created==1);
        reportPut(allocation,"requestHeaders",site.allRecords());synchronized(site){site.wire.clear();}
        owner.uiVisible=true;owner.inFlight=false;owner.navigating=false;owner.recoveryScheduled=false;owner.resourceObserverDisconnected(fixtureDocument);owner.handler.removeCallbacks(owner.tick);
        resourceDone=true;super.beginCase();
      }catch(Throwable failure){finish(failure);}
    });
  }
  @Override void configureReport(JSONObject report){
    reportPut(report,"fixtureType","production-resource-pressure-controlled-v1");reportPut(report,"diagnosticOnly",true);reportPut(report,"releaseAcceptance",false);reportPut(report,"capacityAcceptance",false);reportPut(report,"physicalDeviceAcceptance",false);reportPut(report,"fullDesktopUaConsistency",false);reportPut(report,"fingerprintTemplateAcceptance",false);reportPut(report,"fullTemplateAcceptance",false);JSONObject nativeInventory=new JSONObject();for(NativeCapabilityManifest.Capability capability:NativeCapabilityManifest.Capability.values())reportPut(nativeInventory,capability.name(),NativeCapabilityManifest.officialGecko().status(capability).name());reportPut(report,"nativeCustomCapabilities",nativeInventory);reportPut(report,"resourceChecks",resourceChecks);reportPut(report,"resourceChecksCompleted",resourceDone);reportPut(report,"resourcePortControls",resourcePortControls);reportPut(report,"resourceEvaluationTrace",resourceEvaluationTrace);reportPut(report,"resourceEvaluationTraceDropped",resourceEvaluationDropped);reportPut(report,"platformMemory",platform);reportPut(report,"allocation",allocation);
    reportPut(report,"scope","Actual official Gecko runtime creation/retained session and controlled local document through production admission, navigation and attachment bookkeeping. Pressure values and pending recovery task are synthetic controls. Android MemoryInfo and current app PID PSS are observations, not physical capacity, ChatGPT, upload picker, native IME or performance acceptance. Session UA and document headers do not establish desktop Worker fetch UA consistency; inherited raw mismatch scope remains unsupported.");
    synchronized(resourceRequests){reportPut(report,"resourceRequests",new JSONArray(resourceRequests));}
    reportPut(report,"resourceUncovered",J.arr("physical ARM capacity","Gecko child process PSS","real ChatGPT tasks","native file chooser gesture","real upload/download throughput","independent process restoration","desktop Worker fetch UA consistency"));
  }
}
