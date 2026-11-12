package local.pocketchat;
import java.util.*;import java.net.URI;import org.json.*;import android.net.Uri;
/** The runner substitutes exact source members, not rewritten policy copies. */
public class PageRecoveryHost {
 static int checks;
 static int syntheticTimeZoneRetirements;
 static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks++;}
 static JSONObject j(Object... parts){return J.obj(parts);}
 static ChatSession route(){LocalDraftPolicy.allowed=true;NativeNetwork.network=new NativeNetwork();ProfileCatalog.generation=4;ProfileCatalog.available=true;ProfileCatalog.deleting=false;ProfileCatalog.resetting=false;SystemClock.now=1000;return new ChatSession();}
 static JSONObject snapshot(ChatSession s,String text){return j("ok",true,"url",s.web.url,"documentId",s.lastDocumentId,"draft",text,"draftComplete",true,"draftLength",text.length());}
 static GeckoWebView lifecycle(int attempts,boolean visible){ChatSession s=route();s.pending=j("id","retained-lifecycle-task","kind","web","confirmed",true);s.uiVisible=visible;s.status="已连接";GeckoWebView view=new GeckoWebView(s);view.contentRecoveries=attempts;view.recoveryWindow=1000;SystemClock.now=10000;return view;}
 static int currentPolicyAndCleanup(){
   int start=checks;
   for(String target:new String[]{"https://www.wikipedia.org/wiki/Main_Page","http://example.com/article"}){
     ChatSession s=route();s.web.url=target;
     check("Public website remains a browser destination: "+target,GeckoNavigationPolicy.publicWeb(target));
     s.sync();check("Generic website cannot dispatch ChatGPT synchronization: "+target,!s.chatAutomationAllowed()&&s.bridgeCalls==0&&s.driverResult==null&&!s.inFlight);
   }
   for(String target:new String[]{"http://chatgpt.com/c/current","https://chatgpt.com.evil/c/current","https://user@chatgpt.com/c/current","https://chatgpt.com:444/c/current","about:blank","invalid URL"}){
     ChatSession s=route();s.web.url=target;s.sync();check("Current production origin policy refuses non-ChatGPT automation: "+target,!s.chatAutomationAllowed()&&s.bridgeCalls==0&&s.driverResult==null);
   }
   ChatSession s=route();s.web.url="https://chatgpt.com:443/c/current";s.sync();check("Exact HTTPS ChatGPT origin still dispatches current synchronization",s.chatAutomationAllowed()&&s.bridgeCalls==1&&s.driverResult!=null);
   s=route();s.deleted=true;s.sync();check("Deleted environment cannot synchronize an otherwise valid ChatGPT origin",!s.chatAutomationAllowed()&&s.bridgeCalls==0);
   check("No prior case owns a generic route lease",!ChromiumRouteLease.held());
   GeckoWebView view=lifecycle(2,false);GeckoSession stopped=view.current,other=new GeckoSession();
   ChromiumRouteLease.Handle stoppedLease=ChromiumRouteLease.acquireSurface(),otherLease=ChromiumRouteLease.acquireSurface(),download=ChromiumRouteLease.acquireDownload();
   try{
     view.generalSessions.add(stopped);view.generalSessions.add(other);view.generalRoutes.put(stopped,stoppedLease);view.generalRoutes.put(other,otherLease);
     view.deferredGeneralLoads.put(stopped,"https://example.com/stopped");view.deferredGeneralLoads.put(other,"https://example.org/retained");
     view.stopOther(new GeckoSession());check("Unowned content exit leaves both real leases and deferred targets intact",ChromiumRouteLease.snapshot().surfaces==2&&view.generalSessions.size()==2&&view.deferredGeneralLoads.size()==2);
     view.stop();
     check("Stopped content retires only its desired session and deferred target",!view.generalSessions.contains(stopped)&&!view.deferredGeneralLoads.containsKey(stopped)&&view.generalSessions.contains(other)&&view.deferredGeneralLoads.containsKey(other));
     check("Stopped content closes its real surface lease without losing popup or native download",stoppedLease.closed&&ChromiumRouteLease.snapshot().surfaces==1&&ChromiumRouteLease.snapshot().downloads==1&&view.generalRoutes.get(other)==otherLease&&!otherLease.closed);
     view.forgetGeneralRoute(stopped);check("Duplicate stopped-session cleanup never decrements another real lease",ChromiumRouteLease.snapshot().surfaces==1&&ChromiumRouteLease.snapshot().downloads==1);
     view.forgetGeneralRoute(other);check("Final page cleanup preserves the independently owned download",ChromiumRouteLease.snapshot().surfaces==0&&ChromiumRouteLease.snapshot().downloads==1&&ChromiumRouteLease.held());
     download.close();check("Closing final native work releases the actual process registry",!ChromiumRouteLease.held());
   }finally{stoppedLease.close();otherLease.close();download.close();}
   return checks-start;
 }
 static int navigationOwners(){
   int start=checks;
   GeckoWebView view=new GeckoWebView(route());
   view.states.put(view.current,new GeckoSession.SessionState(view.url));
   view.timezoneConfigurationChanged();
   check("Owned time zone reset reopens and retains its matching checkpoint",view.reopens==1&&view.loads==1&&view.startupState!=null&&view.loadedUrl.equals(view.url));
   for(int mutation=0;mutation<3;mutation++){
     view=new GeckoWebView(route());final GeckoWebView changed=view;
     final int change=mutation;
     changed.owner.onStatus=()->{
       if(change==0){changed.owner.navigationEpoch++;changed.queued="https://example.com/newer";}
       else if(change==1)changed.current=new GeckoSession();
       else changed.owner.deleted=true;
     };
     changed.timezoneConfigurationChanged();
     check("Time zone reset cannot overwrite a synchronous newer URL or surface "+mutation,changed.reopens==0&&changed.loads==0&&(mutation!=0||changed.queued.equals("https://example.com/newer")));
   }
   for(boolean saved:new boolean[]{false,true}){
     view=new GeckoWebView(route());view.crashed.add(view.current);
     if(saved)view.states.put(view.current,new GeckoSession.SessionState(view.url));
     check("Owned closed-page recovery remains accepted "+saved,view.recoverClosed());
     check("Owned closed-page recovery keeps its original load or checkpoint path "+saved,view.reopens==1&&(saved?view.restores==1&&view.loads==0:view.loads==1&&view.restores==0));
     view=new GeckoWebView(route());view.crashed.add(view.current);
     if(saved)view.states.put(view.current,new GeckoSession.SessionState(view.url));
     final GeckoWebView newer=view;newer.owner.onStatus=()->newer.owner.navigationEpoch++;
     check("Superseded closed-page recovery consumes the request without a fallback reload "+saved,newer.recoverClosed()&&newer.loads==0&&newer.restores==0);
   }
   view=new GeckoWebView(route());view.crashed.add(view.current);final GeckoWebView reopened=view;
   reopened.onReopen=()->reopened.owner.navigationEpoch++;
   check("Native reopen reentry cannot start an older recovery navigation",reopened.recoverClosed()&&reopened.loads==0&&reopened.restores==0&&reopened.owner.navigationEpoch==8);
   view=new GeckoWebView(route());view.stop();
   check("Owned content exit retains its existing delayed recovery",view.owner.handler.delays.contains(250L));
   view=new GeckoWebView(route());final GeckoWebView stopped=view;
   stopped.owner.onStatus=()->stopped.owner.navigationEpoch++;
   stopped.stop();
   check("Superseded content exit cannot schedule its older recovery",!stopped.owner.handler.delays.contains(250L));
   for(int reentry=0;reentry<4;reentry++){
     view=new GeckoWebView(route());final GeckoWebView popupView=view;
     GeckoSession parent=view.current,popup=new GeckoSession();
     view.popups.add(popup);view.current=popup;view.locations.put(popup,"https://example.com/popup");
     view.ports.put(popup,new WebExtension.Port());view.painted.add(parent);
     WebViewClient receiver=new WebViewClient();view.client=receiver;
     ChromiumRouteLease.Handle popupLease=ChromiumRouteLease.acquireSurface(),download=ChromiumRouteLease.acquireDownload();
     view.generalSessions.add(popup);view.generalRoutes.put(popup,popupLease);
     if(reentry==1)view.owner.onStatus=()->popupView.owner.navigationEpoch++;
     else if(reentry==2)receiver.onCommit=()->popupView.owner.navigationEpoch++;
     else if(reentry==3)view.onActivate=()->popupView.owner.navigationEpoch++;
     try{
       check("Closing popup is accepted and always retires the old native surface "+reentry,view.close(popup)&&!popup.isOpen()&&!view.locations.containsKey(popup)&&!view.ports.containsKey(popup)&&popupLease.closed);
       check("Closing popup preserves an independent native download "+reentry,ChromiumRouteLease.snapshot().surfaces==0&&ChromiumRouteLease.snapshot().downloads==1&&!download.closed);
       check("Popup callbacks belong only to the navigation that returned to its parent "+reentry,receiver.commits==(reentry==0||reentry==2?1:0)&&receiver.finished==(reentry==0?1:0));
     }finally{popupLease.close();download.close();}
   }
   return checks-start;
 }
 static int closeAllOwners(){
   int start=checks;
   for(int reentry=-1;reentry<4;reentry++){
     GeckoWebView view=new GeckoWebView(route());GeckoSession parent=view.current,first=new GeckoSession(),second=new GeckoSession();
     view.popups.add(first);view.popups.add(second);view.current=second;view.client=new WebViewClient();
     List<ChromiumRouteLease.Handle> leases=new ArrayList<>();
     for(GeckoSession page:new GeckoSession[]{parent,first,second}){
       view.locations.put(page,"https://example.com/old");view.ports.put(page,new WebExtension.Port());view.painted.add(page);
       view.states.put(page,new GeckoSession.SessionState("https://example.com/old"));view.generalSessions.add(page);
       ChromiumRouteLease.Handle lease=ChromiumRouteLease.acquireSurface();leases.add(lease);view.generalRoutes.put(page,lease);
     }
     ChromiumRouteLease.Handle download=ChromiumRouteLease.acquireDownload();
     long navigation=view.owner.prepareBrowserNavigation();
     Runnable browse=()->{
       view.owner.beginNavigation("https://example.com/newer","New user navigation");
       GeckoSession page=view.current;view.queued="https://example.com/newer";view.url=view.queued;
       view.locations.put(page,view.queued);view.states.put(page,new GeckoSession.SessionState(view.queued));view.painted.add(page);
       view.ports.put(page,new WebExtension.Port());view.loadUrl(view.queued);
       if(!view.generalRoutes.containsKey(page)){ChromiumRouteLease.Handle lease=ChromiumRouteLease.acquireSurface();leases.add(lease);view.generalRoutes.put(page,lease);view.generalSessions.add(page);}
     };
     if(reentry==0)view.callbacks.add(view.ports.get(first),ignored->browse.run(),1000);
     else if(reentry==1)view.callbacks.add(view.ports.get(parent),ignored->browse.run(),1000);
     else if(reentry==2)parent.onStop=browse;
     else if(reentry==3){GeckoWebView.TimeZoneGate gate=new GeckoWebView.TimeZoneGate();gate.waiting.add(ready->browse.run());view.timeZoneGates.put(parent,gate);}
     try{
       boolean accepted=view.closeWebsitePages();
       if(reentry<0){
         check("Close-all retains one navigation owner across multiple popups",accepted&&view.owner.navigationEpoch==navigation&&view.current==parent&&view.popups.isEmpty()&&view.client.commits==0&&view.client.finished==0);
         check("Close-all releases its page leases and native popups while retaining downloads",!first.isOpen()&&!second.isOpen()&&view.ports.isEmpty()&&view.reopens==1&&ChromiumRouteLease.snapshot().surfaces==0&&ChromiumRouteLease.snapshot().downloads==1&&!download.closed);
         if(accepted&&view.owner.navigationEpoch==navigation){view.owner.beginNavigation("https://chatgpt.com/","Return home");view.loadUrl("https://chatgpt.com/");}
         check("Close-all permits the single final ChatGPT home navigation",view.owner.navigationEpoch==navigation+1&&view.loads==1&&view.loadedUrl.equals("https://chatgpt.com/"));
       }else{
         String boundary=reentry==0?"popup callback":reentry==1?"main-page callback":reentry==2?"native stop":"time-zone retirement";
         check("Close-all stops before erasing a newer document after "+boundary,!accepted&&view.owner.navigationEpoch==navigation+1&&view.current.isOpen()&&view.locations.get(view.current).equals("https://example.com/newer")&&view.states.get(view.current).url.equals("https://example.com/newer")&&view.painted.contains(view.current)&&view.ports.containsKey(view.current)&&view.loads==1&&view.reopens==0);
         check("Interrupted close-all keeps completed old cleanup and independent downloads after "+boundary,(reentry==0?first.isOpen()&&second.isOpen():!first.isOpen()&&!second.isOpen())&&ChromiumRouteLease.snapshot().surfaces==(reentry==0?3:1)&&ChromiumRouteLease.snapshot().downloads==1&&!download.closed);
       }
     }finally{for(ChromiumRouteLease.Handle lease:leases)lease.close();download.close();}
   }
   GeckoWebView refused=new GeckoWebView(route());refused.reopenAllowed=false;
   check("Close-all reports native reopen refusal to its home-navigation caller",!refused.closeWebsitePages());
   return checks-start;
 }
 public static void main(String[] args)throws Exception{
   ChatSession s=route();s.networkReady=false;s.recoveryScheduled=true;s.recoveryToken=41;s.recoveryAttempt=3;s.manualAttention=true;s.networkIssue="service disconnected";s.connectionStage="waiting";s.status="service disconnected";s.navigationFailed=true;
   s.acceptTranscript(j("ok",true,"url",s.web.url,"entries",new JSONArray().put(j("id","answer"))),j("composer",true,"model","test"),true);
   check("Late ready DOM cannot clear a scheduled network retry",s.recoveryScheduled&&s.recoveryToken==41&&s.recoveryAttempt==3&&s.manualAttention&&!s.networkReady&&s.networkIssue.equals("service disconnected")&&s.connectionStage.equals("waiting"));
   check("Late ready DOM still updates visible page contents",!s.navigationFailed&&s.entries.length()==1&&s.pageMemory.restores==1);
   s.inspectPageStatus(j("modelKnown",true,"model","late-ready"));check("Late inspect cannot replace a disconnected status with connected",s.status.equals("service disconnected")&&s.recoveryScheduled&&s.recoveryToken==41);
   s.awaitLogin("login page ready");check("Late login callback cannot clear route error or retry token",s.recoveryScheduled&&s.recoveryToken==41&&s.manualAttention&&s.status.equals("service disconnected"));
   s=route();s.sync();ChatSession.Result late=s.driverResult;s.networkStatus("core disconnected",false);long retry=s.recoveryToken;String recovering=s.status;late.accept(j("url",s.web.url,"documentId",s.lastDocumentId,"modelKnown",true,"model","late","composer",true));check("Real sync callback after networkStatus preserves scheduled retry and its displayed state",s.recoveryScheduled&&s.recoveryToken==retry&&!s.networkReady&&s.networkIssue.equals("core disconnected")&&s.status.equals(recovering));
   s=route();s.networkReady=false;s.scheduleRecovery();long token=s.recoveryToken;s.finishNavigation("HTTP 403",false);
   check("Manual page error does not block pending service recovery",!s.manualAttention&&s.recoveryScheduled&&s.recoveryToken==token&&s.pageError.equals("HTTP 403")&&s.networkIssue.isEmpty());s.runRecovery(token);check("Original scheduled reconnect remains runnable",s.opened==1&&s.recoveryAttempt==1);
   s=route();s.finishNavigation("website failure",true);check("Page failure alone cannot reconnect a healthy route",s.scheduled==0&&s.networkReady&&!s.manualAttention);
   s=route();s.navigating=true;s.web.visible=false;s.web.url="about:blank";s.recoveryToken=41;s.recoveryAttempt=3;s.networkIssue="retained route diagnostic";s.navigationTimeout(s.navigationEpoch);
   check("Empty document timeout exposes a page error without mutating verified route or retry ownership",s.navigationFailed&&!s.navigating&&!s.manualAttention&&!s.recoveryScheduled&&s.networkReady&&s.guard.allowed()&&s.pageError.equals("网页还未显示，请重试或检查网络")&&s.status.equals(s.pageError)&&s.recoveryToken==41&&s.recoveryAttempt==3&&s.networkIssue.equals("retained route diagnostic")&&s.connectionEpoch==4&&s.navigationEpoch==7&&s.opened==0&&s.loads==0&&s.scheduled==0);
   MainActivity emptyUi=new MainActivity(s);emptyUi.status(s.status);check("Production status makes empty document recovery visible and clickable with host widgets",emptyUi.status.visibility==View.VISIBLE&&emptyUi.status.clickable&&emptyUi.status.text.equals(s.pageError));
   ReplyState.websiteConnection(emptyUi);AppAppearance.last.positive.onClick(null,1);check("Production page recovery dialog exposes explicit reload action without automatic reload in host",AppAppearance.last.shown&&AppAppearance.last.message.contains(s.pageError)&&AppAppearance.last.positiveLabel.equals("恢复网页连接")&&emptyUi.reloadRequests==1&&s.loads==0&&s.opened==0);
   s=route();s.navigating=true;s.web.visible=false;s.networkReady=false;s.networkIssue="pending service retry";s.recoveryScheduled=true;s.recoveryToken=43;s.recoveryAttempt=2;s.navigationTimeout(s.navigationEpoch);check("Empty document timeout preserves an independently scheduled service retry",s.navigationFailed&&!s.navigating&&!s.manualAttention&&s.recoveryScheduled&&s.recoveryToken==43&&s.recoveryAttempt==2&&s.networkIssue.equals("pending service retry")&&s.connectionEpoch==4&&s.opened==0&&s.loads==0&&s.scheduled==0);
   s=route();s.networkReady=false;s.manualAttention=true;s.scheduleRecovery();check("Actual connection manual block still suppresses retries",!s.recoveryScheduled);
   s=route();s.networkReady=false;NativeNetwork.network.recoveryBlocked=true;s.scheduleRecovery();check("Fixed exit block still suppresses retries",s.manualAttention&&!s.recoveryScheduled);
   s=route();JSONObject huge=j("ok",true,"draft",JSONObject.NULL,"draftComplete",false,"hasDraft",true,"draftLength",300001);
   check("Incomplete snapshot cannot masquerade as an empty captured draft",!PageMemory.completeDraft(huge)&&PageMemory.hasDraft(huge));check("Complete normal snapshot remains usable",PageMemory.completeDraft(snapshot(s,"draft")));check("Mismatched length cannot authorize draft capture",!PageMemory.completeDraft(j("ok",true,"draft","draft","draftComplete",true,"draftLength",1)));
   s=route();CapturedMemory memory=new CapturedMemory(s);int[] captureDone={0};memory.capture(()->captureDone[0]++);ChatSession.Result oldCapture=s.driverResult;JSONObject newest=snapshot(s,"new current draft"),older=snapshot(s,"old delayed draft");memory.remember(memory.scope(),s.web.url,newest);oldCapture.accept(older);check("Old capture cannot overwrite a newer explicit pre-reload snapshot",memory.pages.get(memory.scope()+"|"+memory.address(s.web.url))==newest&&captureDone[0]==1);
   s=route();ChatSession.ReloadTarget target=s.reloadTarget();JSONObject page=snapshot(s,"keep draft");s.reloadConfirmed(target,page,false);check("Archived reload bypasses old bridge and second capture",s.loads==1&&s.bridgeCalls==0&&s.captures==0&&!s.lastCapture&&s.pageMemory.remembered==page&&s.pageMemory.restorePending);
   s=route();target=s.reloadTarget();s.reloadConfirmed(target,null,true);check("Independent confirmation performs no bridge access or capture",s.loads==1&&s.bridgeCalls==0&&s.captures==0&&s.pageMemory.forgot==1&&!s.pageMemory.restorePending);
   for(int mutation=0;mutation<9;mutation++){
     s=route();target=s.reloadTarget();switch(mutation){case 0:s.navigationEpoch++;break;case 1:s.web.url="https://chatgpt.com/c/other";break;case 2:s.lastDocumentId="new-doc";break;case 3:s.web.current=new Browser();break;case 4:s.pending=j("id","new-send");break;case 5:s.appliedIdentity="other-route";break;case 6:s.deleted=true;break;case 7:ProfileCatalog.generation++;break;case 8:ProfileCatalog.available=false;break;}
     s.reloadConfirmed(target,null,true);check("Stale reload rejected for identity field "+mutation,s.loads==0);
   }
   s=route();target=s.reloadTarget();ChatSession other=route();other.reloadConfirmed(target,null,true);check("Other session cannot use captured confirmation",other.loads==0);
   s=route();target=s.reloadTarget();s.fileWorkGeneration++;s.fileBusy=true;s.reloadConfirmed(target,snapshot(s,""),false);check("New upload between capture and reload invalidates old interruption consent",s.loads==0);
   s=route();target=s.reloadTarget();s.replyBusy=true;s.reloadConfirmed(target,snapshot(s,""),false);check("New reply between capture and reload requires new consent",s.loads==0);
   s=route();target=s.reloadTarget();s.recoveryScheduled=true;s.reloadConfirmed(target,null,true);check("Independent reload cannot bypass an outstanding connection check",s.loads==0&&s.recoveryScheduled);
   s=route();s.websiteConnectionIssue=true;s.pageError="socket closed";s.observeWebsiteProbe(s.connectionEpoch,s.navigationEpoch,s.web.url,j("ok",false,"probeMs",55));check("HEAD failure preserves route and page and explains unknown webpage status",s.loads==0&&s.networkReady&&s.websiteConnectionIssue&&s.pageError.equals("socket closed")&&!s.websiteProbeIssue.isEmpty());
   String probe=s.websiteProbeIssue;s.observeWebsiteProbe(s.connectionEpoch-1,s.navigationEpoch,s.web.url,j("ok",true));check("Old connection probe cannot clear current page diagnostic",s.websiteProbeIssue.equals(probe));
   s=route();s.observeWebsiteProbe(s.connectionEpoch,s.navigationEpoch,s.web.url,j("ok",false));check("HEAD failure alone cannot create page failure or trigger reload",s.loads==0&&!s.navigationFailed&&!s.websiteConnectionIssue&&s.pageError.isEmpty()&&s.networkReady);
   s=route();s.keepPageCandidate=true;target=s.reloadTarget();s.networkReady=false;s.connecting=true;s.guard.setBlocked(true);NativeNetwork.RecoveryOutcome retained=new NativeNetwork.RecoveryOutcome("original verification uncertain");boolean accepted=s.retainExistingConnection(s.connectionEpoch,target,NativeNetwork.network,retained);check("Retained exact route remains admitted without claiming recovery or refreshing",accepted&&s.networkReady&&!s.guard.blocked&&!s.connecting&&!s.networkIssue.isEmpty()&&s.connectionStage.equals("沿用已核验线路")&&s.loads==0&&s.bridgeCalls==0&&s.opened==0&&!s.recoveryScheduled);
   s=route();s.keepPageCandidate=true;target=s.reloadTarget();s.networkReady=false;s.guard.setBlocked(true);NativeNetwork.network.retainedCurrent=false;check("A stale native receipt cannot authorize retained page networking",!s.retainExistingConnection(s.connectionEpoch,target,NativeNetwork.network,retained)&&!s.networkReady&&s.guard.blocked);
   s=route();s.keepPageCandidate=true;target=s.reloadTarget();s.currentNetworkIdentity="different-configuration";check("A different route configuration cannot reuse old page admission",!s.retainExistingConnection(s.connectionEpoch,target,NativeNetwork.network,retained));
   s=route();s.keepPageCandidate=true;target=s.reloadTarget();s.navigationEpoch++;check("Replacement document cannot receive retained route callback",!s.retainExistingConnection(s.connectionEpoch,target,NativeNetwork.network,retained));
   s=route();s.keepPageCandidate=true;target=s.reloadTarget();s.guard.protectedRoute=false;check("A lost VPN or route guard cannot be reopened by retained callback",!s.retainExistingConnection(s.connectionEpoch,target,NativeNetwork.network,retained));
   s=route();target=s.reloadTarget();ProfileCatalog.deleting=true;check("Deleting environment invalidates confirmation",!target.matches(s));ProfileCatalog.deleting=false;ProfileCatalog.resetting=true;check("Resetting environment invalidates confirmation",!target.matches(s));ProfileCatalog.resetting=false;
   s=route();SystemClock.now=100000;JSONObject omitted=j("ok",true,"url",s.web.url,"documentId",s.lastDocumentId,"draft",JSONObject.NULL,"draftComplete",false,"hasDraft",true,"draftLength",300001);JSONObject beforeOmission=j("url",s.web.url,"draft",omitted.optString("draft"),"draftRaw",omitted.optString("draft"));DraftArchive.saves=0;DeferredBrowserSettings.applied=0;DeferredBrowserSettings.drain(s);s.driverResult.accept(beforeOmission);s.driverResult.accept(omitted);check("Deferred settings reject incomplete snapshot even when JSON-null text aliases previous draft",DraftArchive.saves==0&&DeferredBrowserSettings.applied==0&&!s.operation&&!s.configurationCapture);
   s=route();MainActivity editor=new MainActivity(s);boolean[] applied={true};EnvironmentEditorUi.applied=0;EnvironmentEditorUi.applySafely(editor,j("name","test","privacyLevel",2),new EditText(),()->true,result->applied[0]=result);s.driverResult.accept(beforeOmission);s.driverResult.accept(omitted);check("Editor rejects incomplete snapshot before archive or settings apply",!applied[0]&&EnvironmentEditorUi.applied==0&&DraftArchive.saves==0&&!s.operation);
   s=route();editor=new MainActivity(s);applied[0]=false;EnvironmentEditorUi.applySafely(editor,j("name","test","privacyLevel",2),new EditText(),()->true,result->applied[0]=result);s.driverResult.accept(j("url",s.web.url,"draft","safe","draftRaw","safe"));s.driverResult.accept(snapshot(s,"safe"));check("Complete editor snapshot still archives and applies",applied[0]&&DraftArchive.saves==1&&EnvironmentEditorUi.applied==1);
   s=route();NetworkUiProvider provider=new NetworkUiProvider(s);NetworkUiProvider.Transition transition=new NetworkUiProvider.Transition(s);DraftArchive.saves=0;provider.captureTransition(transition);s.driverResult.accept(beforeOmission);s.driverResult.accept(omitted);check("Network settings reject incomplete page snapshot before archive and commit",provider.deferred==1&&provider.committed==0&&DraftArchive.saves==0&&transition.page==null);
   s=route();provider=new NetworkUiProvider(s);transition=new NetworkUiProvider.Transition(s);provider.captureTransition(transition);s.driverResult.accept(j("url",s.web.url,"draft","safe","documentId",s.lastDocumentId));s.driverResult.accept(snapshot(s,"safe"));s.driverResult.accept(j("url",s.web.url,"draft","safe","documentId",s.lastDocumentId));check("Complete network settings snapshot still archives and commits",provider.deferred==0&&provider.committed==1&&DraftArchive.saves==1);
   s=route();MainActivity a=new MainActivity(s);target=s.reloadTarget();a.confirmIndependentReload(target,"bridge unavailable");check("Broken bridge has a native explicit loss confirmation",a.reloadDialog!=null&&a.reloadDialog.positiveLabel.equals("已保存，重新加载"));a.reloadDialog.positive.run();check("Explicit native confirmation reaches independent reload",s.loads==1&&s.bridgeCalls==0);
   s=route();a=new MainActivity(s);a.confirmIndependentReload(s.reloadTarget(),"oversize");s.navigationEpoch++;a.reloadDialog.positive.run();check("Document change while independent dialog is open rejects reload",s.loads==0);
   s=route();JSONObject job=j("id","waiting"),poll=j("submitted",true,"busy",true,"thinking",true,"replyKey","r");s.pending=job;s.observeReplyProgress(job,poll,"",true,1000);s.observeReplyProgress(job,poll,"",true,121000);
   check("Long thinking is visible without terminating original pending work",s.replyStalled&&s.pending==job&&s.networkReady&&NativeNetwork.network.diagnostics==1);
   s.observeReplyProgress(job,poll,"",true,130000);check("Repeated no-progress polling throttles read-only diagnostic",NativeNetwork.network.diagnostics==1);
   NativeNetwork.Callback callback=NativeNetwork.network.callback;callback.done(false,"diagnostic uncertain");check("Read-only failure preserves pending and route",s.pending==job&&s.networkReady&&s.replyHealthStatus.equals("diagnostic uncertain"));
   s.navigationEpoch++;callback.done(true,"stale health");check("Late diagnostic cannot update a replacement document",s.replyHealthStatus.equals("diagnostic uncertain"));
   s.observeReplyProgress(job,poll,"new content",true,140000);check("Real reply progress clears stalled state",!s.replyStalled&&s.replyHealthStatus.isEmpty());
   s=route();s.pending=job;s.networkReady=false;s.status="recovering";ReplyState.checkWithoutRecovery(s);check("Read-only Continue check cannot reconnect a disconnected pending reply",s.pending==job&&s.opened==0&&!s.networkReady&&s.driverResult==null&&!s.replyHealthStatus.isEmpty());
   String waiting=ReplyState.describe(poll,job,0,120000);check("Long thinking text is independent of normal busy prefix",waiting.startsWith("回复长时间无进展"));
   s.replyStalled=true;s.status=waiting;a=new MainActivity(s);a.status(waiting);check("Long waiting remains visible and actionable",a.status.visibility==View.VISIBLE&&a.status.clickable);
   s.replyStalled=false;s.status="正在思考…";a.status(s.status);check("Normal short thinking stays quiet",a.status.visibility==View.GONE);
   s=route();String previous=s.lastDocumentId;long beforeEpoch=s.navigationEpoch;ChatSession.ReloadTarget previousTarget=s.reloadTarget();s.beginNavigation(s.web.url,"new navigation");check("Production navigation moves the observed document into prior scope and invalidates the old target",s.lastDocumentId.isEmpty()&&s.priorDocumentId.equals(previous)&&s.awaitNewDocument&&s.navigationEpoch==beforeEpoch+1&&!previousTarget.matches(s));
   s.sync();ChatSession.Result oldDocument=s.driverResult;oldDocument.accept(j("url",s.web.url,"documentId",previous,"composer",true,"busy",false));check("Production sync refuses a prior document before new navigation has committed",s.lastDocumentId.isEmpty()&&s.awaitNewDocument&&!s.inFlight&&s.stateEpoch!=s.navigationEpoch);
   s.sync();s.driverResult.accept(j("url",s.web.url,"documentId","fresh-navigation-document-0002","composer",false,"busy",false));check("Production sync registers the new document in the new epoch without replacing its prior proof",s.lastDocumentId.equals("fresh-navigation-document-0002")&&s.priorDocumentId.equals(previous)&&!s.awaitNewDocument&&s.stateEpoch==s.navigationEpoch);
   s=route();s.sync();ChatSession.Result oldEpoch=s.driverResult;s.beginNavigation(s.web.url,"superseding callback");oldEpoch.accept(j("url",s.web.url,"documentId","late-previous-epoch-document","composer",true,"busy",false));check("A late production sync callback from the previous epoch cannot populate the cleared document",s.lastDocumentId.isEmpty()&&s.awaitNewDocument&&s.stateEpoch!=s.navigationEpoch);
   s=route();LocalDraftPolicy.allowed=false;DeferredBrowserSettings.applied=0;DraftArchive.saves=0;DeferredBrowserSettings.drain(s);s.driverResult.accept(j("url",s.web.url,"draft","keep","draftRaw","keep"));s.driverResult.accept(snapshot(s,"keep"));
   check("Disabled draft saving defers browser changes without archiving or discarding the input",DeferredBrowserSettings.applied==0&&DraftArchive.saves==0&&!s.operation&&!s.configurationCapture);
   s=route();LocalDraftPolicy.allowed=false;provider=new NetworkUiProvider(s);transition=new NetworkUiProvider.Transition(s);DraftArchive.saves=0;Object retainedCaptureDocument=s.web.current;long retainedCaptureEpoch=s.navigationEpoch;String retainedCaptureUrl=s.web.url;int retainedCaptureLoads=s.loads;provider.captureTransition(transition);s.driverResult.accept(j("url",s.web.url,"draft","keep","documentId",s.lastDocumentId));s.driverResult.accept(snapshot(s,"keep"));
   check("Disabled draft saving keeps a real nonempty network transition pending",provider.deferred==0&&provider.committed==0&&DraftArchive.saves==0&&s.operation&&s.configurationCapture&&transition.capture&&transition.page!=null&&transition.page.optString("draft").equals("keep")&&transition.page.optString("documentId").equals(s.lastDocumentId));
   s.driverResult.accept(j("url",s.web.url,"draft","keep","documentId",s.lastDocumentId));
   check("Disabled draft saving finishes same-document capture only after fresh inspection without archiving input",provider.deferred==0&&provider.committed==1&&DraftArchive.saves==0&&s.web.current==retainedCaptureDocument&&s.navigationEpoch==retainedCaptureEpoch&&s.web.url.equals(retainedCaptureUrl)&&s.loads==retainedCaptureLoads);
   LocalDraftPolicy.allowed=true;
   s=route();s.stateEpoch=s.navigationEpoch;s.state=j("url",s.web.url,"documentId",s.lastDocumentId,"composer",true);check("Status details use the current document's observed composer",NetworkStatusUi.pageStatus(s).contains("已显示网页输入区"));
   for(int mutation=0;mutation<5;mutation++){
     s=route();s.stateEpoch=s.navigationEpoch;s.state=j("url",s.web.url,"documentId",s.lastDocumentId,"composer",true);
     switch(mutation){case 0:s.state.put("documentId","another-document");break;case 1:s.stateEpoch--;break;case 2:s.state.put("url","https://chatgpt.com/c/other");break;case 3:s.web.ports.clear();break;case 4:s.web.current=null;break;}
     check("Status details refuse stale or unbound document observation "+mutation,NetworkStatusUi.pageStatus(s).contains("尚未确认"));
   }
   s=route();s.web.url="https://auth.openai.com/login";check("Login page is not described using previous chat state",NetworkStatusUi.pageStatus(s).contains("完成登录"));
   s=route();s.networkReady=true;s.connectionStage="线路已恢复";s.websiteConnectionIssue=true;check("A recovered route never hides a failed website socket",NetworkStatusUi.connectionReady(s)&&NetworkStatusUi.pageStatus(s).contains("网页连接已中断"));
   s=route();check("No native waiting task does not claim website completion",NetworkStatusUi.sendStatus(s).contains("没有本机等待任务")&&NetworkStatusUi.sendStatus(s).contains("不代表网页任务已完成"));
   s.pending=j("id","unconfirmed-send");check("Observed gesture does not claim website acceptance",NetworkStatusUi.sendStatus(s).contains("网页是否接收尚未确认"));
   s.pending.put("confirmed",true);check("Bound question does not claim completed reply",NetworkStatusUi.sendStatus(s).contains("网页已确认提问")&&NetworkStatusUi.sendStatus(s).contains("回复完成尚未确认"));
   s.pending.put("webSuspended",true);check("Suspended send keeps an explicit uncertain result",NetworkStatusUi.sendStatus(s).contains("发送结果待核对"));
   s=route();s.pending=j("id","current-unconfirmed");s.status="发送结果待确认 · 不会自动重发";a=new MainActivity(s);a.status(s.status);NetworkStatusUi.shows=0;a.clickStatus();check("Clickable unconfirmed send opens actual reply details",a.status.visibility==View.VISIBLE&&a.status.clickable&&AppAppearance.last.title.equals("回复状态")&&AppAppearance.last.message.contains("网页是否接收尚未确认")&&NetworkStatusUi.shows==0);
   s=route();s.pending=j("id","offline-send");JSONObject kept=s.pending;s.networkReady=false;s.offline=true;a=new MainActivity(s);a.clickStatus();RecoveryDialog offlineDialog=AppAppearance.last;check("Disconnected send exposes a connection-status action",offlineDialog.positiveLabel.equals("连接状态"));NetworkStatusUi.shows=0;offlineDialog.positive.onClick(null,1);check("Connection action opens existing details without reconnecting or resending",NetworkStatusUi.shows==1&&s.opened==0&&s.loads==0&&s.pending==kept);
   s=route();s.pending=j("id","old-dialog-send");s.networkReady=false;a=new MainActivity(s);ReplyState.show(a);RecoveryDialog replaced=AppAppearance.last;NetworkStatusUi.shows=0;a.session=route();replaced.positive.onClick(null,1);check("A replaced session cannot act through old reply details",NetworkStatusUi.shows==0&&s.opened==0);
   s=route();s.status="连接中断";a=new MainActivity(s);NetworkStatusUi.shows=0;a.clickStatus();check("Network-only errors keep the original network-details entry",NetworkStatusUi.shows==1);
   for(int mutation=0;mutation<5;mutation++){
     s=route();s.pending=j("id","guarded-send");a=new MainActivity(s);switch(mutation){case 0:a.destroyed=true;break;case 1:a.finishing=true;break;case 2:a.session=route();break;case 3:a.remote=route().web;break;case 4:s.deleted=true;break;}
     check("Status details reject an inactive host or session "+mutation,!NetworkStatusUi.current(a,s));
   }
   s=route();s.status="对话已改变，请检查上次发送；不会自动重发";a=new MainActivity(s);a.status(s.status);check("Conversation-change diagnostic still has no persistent banner",a.status.visibility==View.GONE);
   int lifecycleStart=checks;GeckoWebView stopped=lifecycle(2,false);s=stopped.owner;JSONObject retainedTask=s.pending;long oldRetry=s.recoveryToken,oldConnection=s.connectionEpoch;WebExtension.Port oldPort=stopped.ports.get(stopped.current);String[] oldResult={"pending"};int oldRequest=stopped.callbacks.add(oldPort,value->oldResult[0]=value,1000);stopped.current.open=false;stopped.stop();
   check("Background content exit retires its exact port and bridge request",stopped.failed&&!stopped.hasVisibleDocument()&&stopped.ports.get(stopped.current)==null&&stopped.callbacks.size()==0&&oldResult[0].equals("null")&&!stopped.callbacks.complete(oldPort,oldRequest,"late"));
   check("Background content exit waits to show foreground recovery instructions",s.pageError.isEmpty()&&s.status.equals("已连接")&&stopped.recoveryDispatches==0);
   s.uiVisible=true;stopped.onResume();check("Exhausted background recovery exposes existing manual failure without changing route or task",s.pageError.contains("自动恢复已暂停")&&s.pending==retainedTask&&s.recoveryToken==oldRetry&&s.connectionEpoch==oldConnection&&s.loads==0&&s.opened==0&&stopped.recoveryDispatches==0&&stopped.contentRecoveries==2);
   a=new MainActivity(s);a.status(s.status);check("Resumed exhausted page has a visible actionable native failure",a.status.visibility==View.VISIBLE&&a.status.clickable);
   stopped=lifecycle(2,true);stopped.current.open=false;stopped.stop();String foregroundFailure=stopped.owner.pageError;stopped.onResume();check("Existing foreground exhaustion keeps its original page error",!foregroundFailure.isEmpty()&&stopped.owner.pageError.equals(foregroundFailure)&&stopped.recoveryDispatches==0);
   stopped=lifecycle(0,false);stopped.current.open=false;stopped.stop();stopped.owner.uiVisible=true;stopped.onResume();check("Available-budget background resume keeps existing recovery dispatch",stopped.recoveryDispatches==1&&stopped.owner.pageError.isEmpty());
   stopped=lifecycle(2,false);stopped.current.open=false;stopped.stop();stopped.owner.uiVisible=true;SystemClock.now=62000;stopped.onResume();check("Expired recovery window still resets the existing budget",stopped.recoveryDispatches==1&&stopped.contentRecoveries==0&&stopped.owner.pageError.isEmpty());
   stopped=lifecycle(2,false);stopped.stopOther(new GeckoSession());check("Unrelated session cannot fail the current document",!stopped.failed&&stopped.crashed.isEmpty()&&stopped.owner.pageError.isEmpty());
   stopped=lifecycle(2,true);stopped.onResume();check("Healthy foreground session keeps its original activation",stopped.current.activeCalls==1&&stopped.owner.pageError.isEmpty()&&stopped.recoveryDispatches==0);
   stopped=lifecycle(2,true);stopped.crashed.add(stopped.current);stopped.onResume();check("A crashed marker alone does not create a new failure or change activation",!stopped.failed&&stopped.current.activeCalls==1&&stopped.owner.pageError.isEmpty());
   stopped=lifecycle(2,false);stopped.current.open=false;stopped.stop();stopped.owner.uiVisible=true;stopped.destroyed=true;stopped.onResume();check("A destroyed browser cannot publish the new foreground notice",stopped.owner.pageError.isEmpty()&&stopped.recoveryDispatches==0);
   stopped=lifecycle(2,false);stopped.current.open=false;stopped.stop();stopped.onResume();check("The new manual notice does not run while still backgrounded",stopped.owner.pageError.isEmpty()&&stopped.recoveryDispatches==0);
   stopped=lifecycle(2,false);s=stopped.owner;s.networkReady=false;s.navigating=true;s.recoveryToken=51;s.recoveryAttempt=3;s.networkIssue="unavailable route";s.connectionStage="needs network";retainedTask=s.pending;oldConnection=s.connectionEpoch;stopped.current.open=false;stopped.stop();s.uiVisible=true;stopped.onResume();
   check("Exhausted foreground notice on an unavailable route cannot create a network retry",s.pageError.contains("自动恢复已暂停")&&s.status.equals(s.pageError)&&!s.navigating&&s.navigationFailed&&!s.recoveryScheduled&&s.scheduled==0&&s.recoveryToken==51&&s.recoveryAttempt==3&&!s.manualAttention&&s.networkIssue.equals("unavailable route")&&s.connectionStage.equals("needs network")&&s.pending==retainedTask&&s.connectionEpoch==oldConnection&&s.loads==0&&s.opened==0&&stopped.recoveryDispatches==0&&stopped.contentRecoveries==2);
   stopped=lifecycle(2,false);s=stopped.owner;s.networkReady=false;s.scheduleRecovery();oldRetry=s.recoveryToken;int existingScheduled=s.scheduled;String existingStage=s.connectionStage;retainedTask=s.pending;stopped.current.open=false;stopped.stop();s.uiVisible=true;stopped.onResume();
   check("Exhausted foreground notice preserves an independently scheduled network retry",s.pageError.contains("自动恢复已暂停")&&s.status.equals(s.pageError)&&s.recoveryScheduled&&s.scheduled==existingScheduled&&s.recoveryToken==oldRetry&&s.recoveryAttempt==0&&s.connectionStage.equals(existingStage)&&s.pending==retainedTask&&s.loads==0&&s.opened==0&&stopped.recoveryDispatches==0&&stopped.contentRecoveries==2);
   s.runRecovery(oldRetry);check("Independent network retry remains runnable after the pure foreground notice",s.opened==1&&s.recoveryAttempt==1&&s.recoveryToken==oldRetry&&!s.recoveryScheduled&&s.pending==retainedTask&&stopped.recoveryDispatches==0);
   int lifecycleChecks=checks-lifecycleStart;
   int originalChecks=checks,currentPolicyChecks=currentPolicyAndCleanup();
   int navigationOwnerChecks=navigationOwners();
   int closeAllOwnerChecks=closeAllOwners();
   System.out.println(j("status","passed","checks",checks,"contentLifecycleChecks",lifecycleChecks,"originalChecks",originalChecks,"currentPolicyAndCleanupChecks",currentPolicyChecks,"navigationOwnerChecks",navigationOwnerChecks,"closeAllOwnerChecks",closeAllOwnerChecks,"syntheticTimeZoneRetirements",syntheticTimeZoneRetirements,"actualNativeTimeZoneExecution",false));
 }
}
class ChatSession {
 // Declared host boundary: legacy capture scenarios are foreground-only;
 // the global background-reply policy is exercised by its separate hosts.
 boolean replyObservationAllowed(){return uiVisible;}
 final WebReplyObserver webObserver=new WebReplyObserver(this);final Object context=new Object();final int environmentGeneration=4;final String environmentId="environment-one";final Web web=new Web();final Guard guard=new Guard();final Memory pageMemory=new Memory();final Prefs prefs=new Prefs();final Trace trace=new Trace();final Mirror webMirror=new Mirror();final Store webStore=new Store();final Cache cache=new Cache();final Handler handler=new Handler(this);final Audit audit=new Audit();final Privacy privacy=new Privacy();final Identity identity=new Identity();final TimeZoneBoundary timeZone=new TimeZoneBoundary();Result driverResult;
 String navigationLabel="";long navigationStarted,navigationMono,firstPageVisible;boolean documentNavigationSeen,browserNavigationStopped,browserNavigationChosen;
 long resourceUploadCheckGeneration;boolean resourceUploadChecking,backgroundAttachmentCheck;int backgroundAttachmentStable;
 boolean deleted,navigating,navigationFailed,showingCache,offline,connecting,recoveryScheduled,manualAttention,submitting,operation,websiteRecovering,replyStalled,websiteConnectionIssue,uiVisible=true,networkReady=true;int recoveryAttempt,scheduled,opened,loads,captures,bridgeCalls,stableTicks,resourceFilePreparations,spaStable;boolean keepPageCandidate,configurationCapture,identityApplicationPending;boolean lastCapture=true,inFlight,navigationDispatched=true,awaitNewDocument,spaTransition,fileBusy,replyBusy;
 long lastDeferredBrowserAttempt,webWorkGeneration,resourceWebsiteEpoch=-1,resourceObserverEpoch=-1,resourceObserverSequence;Object resourceObserverPort;String resourceObserverBinding="",resourceObserverDocument="",resourceObserverUrl="";long fileWorkGeneration,resourceInspectionGeneration,syncRun,stateEpoch,lastWebSnapshot;long recoveryToken,navigationEpoch=7,connectionEpoch=4,pageUsableAt,lastReplyDiagnostic,lastReplyProgress;String networkIssue="",connectionStage="connected",status="",pageError="",navigationTarget="https://chatgpt.com/c/current",conversation=navigationTarget,lastDocumentId="document-one",appliedIdentity="route-one",websiteProbeIssue="",replyHealthStatus="",currentNetworkIdentity="route-one",progressJob="",progressSignature="",stableReply="",priorDocumentId="",spaBefore="",spaSignature="",lastWebUrl="https://chatgpt.com/c/current";
 JSONObject state=new JSONObject();JSONObject pending,sentAttachments=new JSONObject();JSONArray entries=new JSONArray();
 Runnable onStatus;
 void changed(){}void setStatus(String x){status=x;Runnable callback=onStatus;onStatus=null;if(callback!=null)callback.run();}String resumeUrl(){return web.url;}boolean internalNetwork(){return true;}static long retryDelay(int n){return 1000;}void openConnection(boolean a,boolean b){opened++;}boolean targetMatches(String u){return navigationTarget.equals(u);}void runDriver(String x,JSONObject a,Result done){bridgeCalls++;if(x.equals("web-inspect")||x.equals("page-state"))driverResult=done;}void asyncDriver(String action,JSONObject args,long timeout,Result done){driverResult=done;}interface Result{void accept(JSONObject x);}
 boolean resourceFilesUncertain(){return false;}boolean fileWorkActive(){return fileBusy;}String networkIdentity(){return currentNetworkIdentity;}void wakePolling(){}boolean currentReplyActive(){return replyBusy;}boolean webPerformance(){return true;}void finishResourceInspection(){inFlight=false;}void updateBrowserActivity(boolean p){}void resetReplyStability(){}void archiveWebsiteNavigation(JSONObject p){}void pollSync(long epoch,long run,boolean optimized){}
 boolean navigate(String url,String label,boolean capture){lastCapture=capture;if(capture)captures++;loads++;navigationEpoch++;pageMemory.restorePending=true;return true;}
 /* CHAT */
}
class PageMemory {/* MEMORY */}
class MainActivity {
 ChatSession session;Web remote;boolean destroyed,finishing,reloadChecking;ReferenceUi.Modal reloadDialog;Text status=new Text();AppHub hub=new AppHub();String lastUiStatus="";
 int reloadRequests,shownPages;void requestReload(){reloadRequests++;}void showPage(boolean show){shownPages++;}void clickStatus() /* STATUS_CLICK */ MainActivity(ChatSession s){session=s;remote=s.web;}boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}
 /* MAIN */
}
class ReplyState {/* REPLY */}
class NetworkStatusUi{static int shows;static void show(MainActivity a){shows++;}/* NETWORK */}
class AppAppearance{static RecoveryDialog last;static RecoveryDialog dialog(MainActivity a){return last=new RecoveryDialog();}}
class RecoveryDialog{interface Click{void onClick(Object dialog,int which);}boolean shown;String title,message,positiveLabel;Click positive;RecoveryDialog setTitle(String s){title=s;return this;}RecoveryDialog setMessage(String s){message=s;return this;}RecoveryDialog setPositiveButton(String s,Click c){positiveLabel=s;positive=c;return this;}RecoveryDialog setNeutralButton(String s,Click c){return this;}RecoveryDialog setNegativeButton(String s,Click c){return this;}void show(){shown=true;}}
class ReferenceUi {static class Modal{Runnable positive;String positiveLabel;java.util.function.Consumer<Object> dismiss;Modal(Object x,String s){}void note(String s){}void setOnDismissListener(java.util.function.Consumer<Object>x){dismiss=x;}void dismiss(){if(dismiss!=null)dismiss.accept(this);}void buttons(String l,Runnable a,String r,Runnable b){positive=b;positiveLabel=r;}void show(){}}}
class J {static JSONObject obj(Object...p){JSONObject o=new JSONObject();try{for(int i=0;i<p.length;i+=2)o.put((String)p[i],p[i+1]);}catch(Exception e){throw new RuntimeException(e);}return o;}}
class Text {int visibility;boolean clickable;String text="";String getText(){return text;}void setText(String s){text=s;}void setTextColor(int c){}void setClickable(boolean b){clickable=b;}void setContentDescription(String s){}void setVisibility(int v){visibility=v;}}
class TextUtils{static boolean equals(Object a,Object b){return Objects.equals(a,b);}}class DesignUi{static int RED=1,MUTED=2;}class View{static int VISIBLE=0,GONE=8;}class AppHub{static int CHAT=0;int page=0;void feedback(String s,boolean b){}}
class Browser {boolean isOpen(){return true;}void reload(){}}class Web{boolean failed,resourceDeferred,visible=true;String url="https://chatgpt.com/c/current";Browser current=new Browser();final Map<Object,Object> ports=new IdentityHashMap<>();Web(){ports.put(current,new Object());}String getUrl(){return url;}boolean hasVisibleDocument(){return visible;}void checkpointState(){}void stopLoading(){}}
class Guard{boolean blocked,protectedRoute=true;void setBlocked(boolean b){blocked=b;}boolean allowed(){return !blocked;}boolean routeProtected(){return protectedRoute;}}
class Profiles{static int slot(Object c){return 2;}}
class ProfileCatalog{static int generation=4;static boolean available=true,deleting,resetting;static ProfileCatalog get(Object c){return new ProfileCatalog();}boolean available(int n){return available;}JSONObject item(int n){return J.obj("generation",generation,"environmentId","environment-one","created",available,"deleting",deleting,"resetting",resetting);}}
class BrowserRuntimePolicy{static boolean sameDocument(String a,String b){return Objects.equals(a,b);}}class WebReplyObserver{final ChatSession session;WebReplyObserver(ChatSession session){this.session=session;}JSONObject lastNavigationArchivedJob;long navigationArchiveSequence;static boolean same(String a,String b){return Objects.equals(a,b);}void suspendUnconfirmed(String reason){/* Lifecycle scenarios use confirmed tasks, whose production path returns unchanged. */}
 // beginNavigation is exercised here only without a web task. Actual archival
 // and its preference-listener callbacks run in the independent reload host.
 void navigationStarted(String target){if(session.pending!=null)throw new AssertionError("Pending observation navigation belongs to the reload-request host");}
}
class Memory{int restores,forgot;JSONObject remembered;boolean restorePending;void restore(String u,long e){restores++;}void forget(String u){forgot++;restorePending=false;}void remember(String n,String u,JSONObject p){remembered=p;}String scope(){return "scope";}}
class SystemClock{static long now;static long elapsedRealtime(){return now;}}
class Handler{ChatSession s;final List<Long> delays=new ArrayList<>();Handler(ChatSession s){this.s=s;}void postDelayed(Runnable r,long n){s.scheduled++;delays.add(n);}void post(Runnable r){r.run();}void removeCallbacks(Runnable r){}}
class NativeNetwork{interface Callback{void done(boolean ok,String msg);}static NativeNetwork network=new NativeNetwork();static class RecoveryOutcome{final String message;RecoveryOutcome(String m){message=m;}}boolean retainedCurrent=true;boolean retainedOutcomeCurrent(RecoveryOutcome o){return retainedCurrent;}boolean recoveryBlocked,starting;String message="fixed exit blocked";int diagnostics;Callback callback;static NativeNetwork get(Object c){return network;}void diagnoseReadOnly(Callback c){diagnostics++;callback=c;}}
class Prefs{boolean getBoolean(String x,boolean b){return true;}Prefs edit(){return this;}Prefs putString(String k,String v){return this;}void apply(){}}
class ConnectionTrace{static double bounded(double v){return v;}}
class Trace{long usable,recoveryProbe;void page(String label){}void timing(JSONObject p){}}
class Mirror{String documentId="document-one";JSONObject arguments(){return new JSONObject();}JSONArray accept(JSONObject d,JSONArray e,String c){return d.optJSONArray("entries");}}
class Store{final java.util.concurrent.Executor worker=Runnable::run;void offer(String u,JSONArray e){}void nativeSnapshot(String s){}}
class Cache{JSONArray withEarlier(String u,JSONArray a){return a;}void saveMessages(String u,JSONArray e){}}

class Audit{void retirePageCheck(){}boolean requestIdentitySelected;boolean requestIdentityPageSelected(){return requestIdentitySelected;}void refresh(boolean force){}}class ChatService{static boolean running;static void networkLost(Object c){}}class GeckoWebView{
 // This recovery workload has no auxiliary page. Never simulate its lifecycle.
 boolean auxiliaryPageSelected;
 boolean closeExitIpPage(){if(auxiliaryPageSelected)throw new AssertionError("Auxiliary page lifecycle is outside this host");return false;}
 static boolean active(Web w){return true;}final ChatSession owner;GeckoSession current=new GeckoSession(),primary=current;boolean destroyed,enabled=true,failed;long recoveryWindow;int contentRecoveries,recoveryDispatches;String url="https://chatgpt.com/c/lifecycle-current";
 final Map<GeckoSession,String> locations=new IdentityHashMap<>();final Map<GeckoSession,WebExtension.Port> ports=new IdentityHashMap<>();final Set<GeckoSession> crashed=new HashSet<>(),pendingLoads=new HashSet<>(),painted=new HashSet<>(),usable=new HashSet<>();final Runnable recovery=()->recoveryDispatches++;
 final BrowserBridgeRequests callbacks=new BrowserBridgeRequests(new BrowserBridgeRequests.Timer(){public void schedule(Runnable r,long delay){}public void cancel(Runnable r){}},"null");
 /* ROUTE_FIELDS */
 // Native allocation, activation and SDK restore are explicit counters, not
 // emulated Gecko execution. Reentrant hooks represent collaborator callbacks.
 boolean ipRouteNeedsReload,ipRouteObserved,canBack,canForward,reopenAllowed=true;String observedIpRoute="",queued="",loadedUrl="";int reopens,loads,restores;Object generalRestore;
 long startupDraftRevision;GeckoSession.SessionState startupState;WebViewClient client;Runnable onReopen,onActivate;
 final PopupBoundary blockedPopups=new PopupBoundary();final List<GeckoSession> popups=new ArrayList<>();
 final Map<GeckoSession,GeckoSession.SessionState> states=new IdentityHashMap<>();final Map<GeckoSession,Long> stateDraftRevisions=new IdentityHashMap<>();
 final Map<GeckoSession,Object> appearanceLoads=new IdentityHashMap<>(),backStates=new IdentityHashMap<>(),forwardStates=new IdentityHashMap<>(),pageScales=new IdentityHashMap<>(),measuredCompositors=new IdentityHashMap<>(),viewportWidths=new IdentityHashMap<>(),loadingTargets=new IdentityHashMap<>();
 String getUrl(){return url;}boolean allowedUrl(String target){return GeckoNavigationPolicy.publicWeb(target);}boolean protectionAllowsNetwork(){return owner.guard.allowed();}boolean identityRequestAllowed(String target){return true;}
 String stateUrl(GeckoSession.SessionState state){return state.url;}
 boolean reopenCurrent(){retireTimeZone(current);reopens++;if(!reopenAllowed)return false;failed=false;crashed.remove(current);if(onReopen!=null)onReopen.run();return true;}
 void loadUrl(String target){loads++;loadedUrl=target;}void loadSessionUri(GeckoSession session,String target){loads++;loadedUrl=target;}
 void restoreCheckpoint(GeckoSession session,GeckoSession.SessionState state,String target,long revision){restores++;loadedUrl=target;}
 void activate(GeckoSession session){current=session;url=locations.getOrDefault(session,"");if(onActivate!=null)onActivate.run();}
 final Map<GeckoSession,TimeZoneGate> timeZoneGates=new IdentityHashMap<>();final Map<GeckoSession,Object> timeZoneLoads=new IdentityHashMap<>(),timeZoneIntents=new IdentityHashMap<>(),nativeTimeZoneIntents=new IdentityHashMap<>();
 final Map<TimeZoneGate,ChromiumRouteLease.Handle> ipRouteLeases=new IdentityHashMap<>();final TimeZoneMetadata metadata=new TimeZoneMetadata();IpPageBoundary ipNavigationFailure,ipLookup;
 void cancelIpLookup(){throw new AssertionError("Automatic IP lookup is outside this recovery host");}JSONObject timeZoneStatus(){return new JSONObject();}
 GeckoWebView(ChatSession s){owner=s;locations.put(current,url);ports.put(current,new WebExtension.Port());usable.add(current);}void cancelZoom(){}void retireAppearance(WebExtension.Port port){}void stop(){contentStopped(current,"网页进程已退出，点按重新加载可恢复当前环境");}void stopOther(GeckoSession session){contentStopped(session,"other session");}boolean close(GeckoSession session){return closePopup(session);}
 /* LIFECYCLE */
}
class PopupBoundary{void invalidate(){}}
class IpPageBoundary{GeckoSession session;}
class TimeZoneMetadata{JSONObject timeZonePolicy;}
class TimeZoneBoundary{boolean custom;void retire(GeckoSession session,String epoch){if(custom||session==null)throw new AssertionError("Custom native time-zone settings are outside this recovery host");PageRecoveryHost.syntheticTimeZoneRetirements++;}}
class WebViewClient{int commits,finished;Runnable onCommit;void onPageCommitVisible(Object view,String target){commits++;if(onCommit!=null)onCommit.run();}void onPageFinished(Object view,String target){finished++;}}
class GeckoSession{boolean open=true;int activeCalls;Runnable onStop;boolean isOpen(){return open;}void close(){open=false;}void stop(){Runnable callback=onStop;onStop=null;if(callback!=null)callback.run();}void setActive(boolean active){activeCalls++;}static class SessionState{final String url;SessionState(String url){this.url=url;}int size(){return 1;}}}
class WebExtension{static class Port{}}
class LoginPagePolicy{/* LOGIN */}

class CapturedMemory {final ChatSession session;final LinkedHashMap<String,JSONObject> pages=new LinkedHashMap<>();long serial;CapturedMemory(ChatSession s){session=s;}String scope(){return "scope";}static String address(String url){return url;}/* CAPTURE */}

class DeferredBrowserSettings{static int applied;static boolean candidateAvailable(ChatSession s){return true;}static boolean idle(ChatSession s){return true;}static void apply(ChatSession s){applied++;}/* DEFERRED */}
class EnvironmentEditorUi{static int applied;static boolean guardedApply(MainActivity a,JSONObject v,EditText e,java.util.function.BooleanSupplier c){applied++;return true;}/* EDITOR */}
class BrowserEditIntent{static boolean preserveFailedCandidate(boolean q,JSONObject v){return false;}static boolean browserIntent(boolean q,JSONObject v,boolean change,boolean pending){return change;}}
class EditText{}class ProfileUi{static boolean working(ChatSession s){return s.fileWorkActive();}}class Identity{boolean queueUnavailable;}class Privacy{int level(){return 1;}boolean wantsDesktop(){return false;}}class DraftArchive{static int saves;static DraftArchive get(Object c){return new DraftArchive();}boolean save(String u,String d,String o){saves++;return true;}boolean save(String u,String d,String o,long r){return save(u,d,o);}}

class NetworkUiProvider{static class Transition{ChatSession session;String url,scope,waitReason;long epoch;boolean capture;JSONObject page;Transition(ChatSession s){session=s;}}final java.util.concurrent.Executor io=Runnable::run;final Handler main;int deferred,committed;NetworkUiProvider(ChatSession s){main=s.handler;}boolean fenceIdle(Transition t){return true;}boolean inspectionIdle(Transition t,JSONObject i,JSONObject p){return true;}void deferTransition(Transition t){deferred++;}void commitTransition(Transition t){committed++;}/* PROVIDER */}

class LocalDraftPolicy{static boolean allowed=true;static boolean enabled(Object c){return allowed;}static long revision(Object c){return 0;}static JSONObject snapshot(Object c,JSONObject value){return value;}static JSONObject snapshot(Object c,JSONObject value,long revision){return value;}static String unavailable(Object c){return "draft unavailable";}}

class NetworkCatalog{static void put(JSONObject x,String k,Object v){try{x.put(k,v);}catch(Exception e){throw new RuntimeException(e);}}}
