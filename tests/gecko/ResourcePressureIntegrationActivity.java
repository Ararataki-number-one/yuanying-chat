package local.pocketchat;

import android.content.Context;
import android.net.Uri;
import android.os.*;
import android.webkit.*;
import java.io.*;
import org.json.*;
import org.mozilla.geckoview.*;

/** Actual production bridge/runtime admission with explicitly synthetic pressure.
 * Platform readings are observations, never a physical capacity or login verdict. */
public final class ResourcePressureIntegrationActivity extends GeckoIdentityPrototypeIntegrationActivity {
  final JSONArray resourceChecks=new JSONArray();JSONObject platform=new JSONObject(),allocation=new JSONObject();
  ChatSession.Observer pressureObserver;boolean coldChecked,controlsStarted,resourceDone;String target,pendingBytes;int readyAttempts;
  final Object fixtureDocument=new Object();String documentId;
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
  void resourceCheck(String name,boolean value){resourceChecks.put(J.obj("name",name,"pass",value));check(name,value);}
  @Override void openBrowser(){
    super.openBrowser();if(finished||view==null)return;
    try{
      ResourcePressureController.MemorySample actual=ResourcePressureController.read(this);
      platform=J.obj("source",actual.source,"known",actual.known,"lowMemory",actual.lowMemory,"availableBytes",actual.availableBytes,"totalBytes",actual.totalBytes,"thresholdBytes",actual.thresholdBytes,"sampledAt",actual.sampledAt,"observedAt",SystemClock.elapsedRealtime(),"scope","Actual Android ActivityManager snapshot; not a device capacity measurement");
      storage.execute(()->{android.os.Debug.MemoryInfo info=new android.os.Debug.MemoryInfo();Debug.getMemoryInfo(info);Runtime java=Runtime.getRuntime();JSONObject process=J.obj("source","android-Debug.MemoryInfo","pid",android.os.Process.myPid(),"totalPssKb",info.getTotalPss(),"javaUsedBytes",java.totalMemory()-java.freeMemory(),"javaMaxBytes",java.maxMemory(),"scope","Current fixture app PID only; Gecko child processes excluded; no capacity budget");handler.post(()->reportPut(platform,"process",process));});
      target=origin+"/frame?run="+run+"&case=4&session=secondary";documentId=java.util.UUID.randomUUID().toString();
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
  void evaluate(String code,java.util.function.Consumer<JSONObject> done){view.evaluateJavascript(code,raw->{if(finished)return;try{JSONObject value=J.parse(raw);if(value.length()==0)throw new IOException("Actual controlled Gecko evaluation returned no observation");done.accept(value);}catch(Throwable failure){finish(failure);}});}
  void workControls(JSONObject actual){
    try{
      owner.handler.removeCallbacks(owner.tick);owner.navigating=false;owner.state=J.obj("url",target,"busy",false);owner.stateEpoch=owner.navigationEpoch;
      resourceCheck("Fallback captured URL loads a real controlled document",target.equals(actual.optString("url"))&&view.current!=null&&view.current.isOpen()&&view.hasVisibleDocument());
      resourceCheck("Recovery preserves attempted task and never resends it",pendingBytes.equals(owner.pending.toString())&&pendingBytes.equals(owner.prefs.getString("pending","")));
      int pause=((PressureView)view).pauses;owner.uiVisible=false;owner.updateBrowserActivity();owner.handler.removeCallbacks(owner.tick);
      resourceCheck("Existing pending recovery retains the open runtime",view.current.isOpen()&&owner.resources.created==1&&((PressureView)view).pauses==pause);
      owner.pending=null;owner.prefs.edit().remove("pending").commit();owner.identityApplicationPending=false;owner.identity.queueUnavailable=false;
      Object realPort=view.ports.get(view.current);owner.resourceObserverConnected(realPort);
      JSONObject observation=J.obj("url",actual.optString("url"),"documentId",documentId,"resourceSequence",1,"busy",actual.optBoolean("busy"),"uploading",actual.optBoolean("uploading"),"capturedAt",System.currentTimeMillis());
      owner.resourceWebsiteObservation(observation,realPort);owner.handler.removeCallbacks(owner.tick);
      resourceCheck("Controlled page task observations protect existing activity",owner.currentReplyActive()&&owner.resourceFilesActive()&&owner.browserWorkActive()&&view.current.isOpen());
      owner.resourceWebsiteObservation(J.obj("url",target,"documentId",documentId,"resourceSequence",1,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),realPort);
      resourceCheck("Late idle resource observation cannot clear newer work",owner.resourceWebsiteBusy&&owner.resourceWebsiteUploading);
      owner.resourceWebsiteObservation(J.obj("url",target,"documentId",java.util.UUID.randomUUID().toString(),"resourceSequence",2,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),realPort);
      resourceCheck("Another document identity cannot clear current work",owner.resourceWebsiteBusy&&owner.resourceWebsiteUploading);
      owner.resourceObserverConnected(fixtureDocument);owner.resourceWebsiteObservation(J.obj("url",target,"documentId",documentId,"resourceSequence",2,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),realPort);
      resourceCheck("Replaced extension port cannot supply an idle observation",owner.resourceWebsiteEpoch==-1);
      owner.resourceObserverConnected(realPort);owner.resourceWebsiteObservation(observation,realPort);
      String next=target+"&spa=1";owner.beginNavigation(next,"Controlled same document route");
      evaluate("(()=>{history.pushState({},'',"+JSONObject.quote(next)+");return {url:location.href,documentId:"+JSONObject.quote(documentId)+"}})()",actualRoute->{target=next;awaitSameDocument(actualRoute,realPort,0);});

    }catch(Throwable failure){finish(failure);}
  }
  void awaitSameDocument(JSONObject actual,Object port,int attempt){
    if(finished)return;
    if(!target.equals(view.getUrl())){if(attempt>=50){finish(new IOException("Actual same-document route did not update"));return;}handler.postDelayed(()->awaitSameDocument(actual,port,attempt+1),100);return;}
    try{
      owner.resourceObserverRouteReady(actual,port);owner.resourceWebsiteObservation(J.obj("url",actual.optString("url"),"documentId",actual.optString("documentId"),"resourceSequence",2,"busy",false,"uploading",false,"capturedAt",System.currentTimeMillis()),port);owner.handler.removeCallbacks(owner.tick);
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
    evaluate(script,actual->{
      try{
        JSONArray names=owner.resourceUploadNames;owner.resourceUploadObservation(actual,owner.navigationEpoch,names,target);owner.handler.removeCallbacks(owner.tick);
        if(step==0){resourceCheck("Actual delayed first attachment retains both selections",owner.resourceFilesActive()&&names.length()==2);evaluate("(()=>{document.getElementById('first').dataset.uploadState='ready';return {updated:true}})()",ignored->inspectAttachments(1));}
        else if(step==1){resourceCheck("One terminal attachment sample does not release selection work",owner.resourceFilesActive()&&owner.resourceUploadStable==1);inspectAttachments(2);}
        else{resourceCheck("Two actual terminal attachment samples release completed selections",!owner.resourceFilesActive()&&owner.resourceUploadNames.length()==0);finishControls();}
      }catch(Throwable failure){finish(failure);}
    });
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
    reportPut(report,"fixtureType","production-resource-pressure-controlled-v1");reportPut(report,"diagnosticOnly",true);reportPut(report,"releaseAcceptance",false);reportPut(report,"capacityAcceptance",false);reportPut(report,"physicalDeviceAcceptance",false);reportPut(report,"fullDesktopUaConsistency",false);reportPut(report,"fingerprintTemplateAcceptance",false);reportPut(report,"fullTemplateAcceptance",false);JSONObject nativeInventory=new JSONObject();for(NativeCapabilityManifest.Capability capability:NativeCapabilityManifest.Capability.values())reportPut(nativeInventory,capability.name(),NativeCapabilityManifest.officialGecko().status(capability).name());reportPut(report,"nativeCustomCapabilities",nativeInventory);reportPut(report,"resourceChecks",resourceChecks);reportPut(report,"resourceChecksCompleted",resourceDone);reportPut(report,"platformMemory",platform);reportPut(report,"allocation",allocation);
    reportPut(report,"scope","Actual official Gecko runtime creation/retained session and controlled local document through production admission, navigation and attachment bookkeeping. Pressure values and pending recovery task are synthetic controls. Android MemoryInfo and current app PID PSS are observations, not physical capacity, ChatGPT, upload picker, native IME or performance acceptance. Session UA and document headers do not establish desktop Worker fetch UA consistency; inherited raw mismatch scope remains unsupported.");
    reportPut(report,"resourceUncovered",J.arr("physical ARM capacity","Gecko child process PSS","real ChatGPT tasks","native file chooser gesture","real upload/download throughput","independent process restoration","desktop Worker fetch UA consistency"));
  }
}
