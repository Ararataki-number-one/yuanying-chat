package local.pocketchat;

import android.os.*;
import android.view.*;
import android.view.inspector.WindowInspector;
import android.widget.*;
import java.io.*;
import java.lang.reflect.Field;
import java.util.*;
import java.util.function.Consumer;
import org.json.*;
import org.mozilla.geckoview.*;

/** Additional real production-UI policy gate. No production admission override or TLS exception. */
public final class GeckoEnvironmentPolicyIntegrationActivity extends MainActivity {
  static final String ROOT="https://"+BrowserFingerprintFixture.A+"/env-policy?phase=";
  static final String MARKER="synthetic-gecko-timezone-preserved";
  final Handler probe=new Handler(Looper.getMainLooper());
  final JSONArray checks=new JSONArray(),samples=new JSONArray(),transitionSamples=new JSONArray(),nativeEvents=new JSONArray();
  final Map<GeckoSession,JSONObject> securities=new IdentityHashMap<>();
  BrowserFingerprintFixture fixture;JSONObject build,staleTicketProof=new JSONObject(),staleRevisionProof=new JSONObject(),popupProof=new JSONObject(),rfpConflictProof=new JSONObject(),lifecycle=new JSONObject();
  String nonce,stage="startup",failure="",failedAtStage="";boolean terminal,enterpriseRootsReadback;long deadline,wholeDeadline;int popupCallbacks,restoreRequests;
  GeckoTimeZoneStore.Ticket retainedTicket;JSONObject retainedReceipt;JSONObject lastSample,lastPageObservation=new JSONObject(),lastNativeReadback=new JSONObject(),rfpResetBaseline=new JSONObject(),rfpFinalObservation=new JSONObject();
  interface Ready{boolean get()throws Exception;}interface Step{void run()throws Exception;}

  @Override public void onCreate(Bundle state){try{
    BrowserFingerprintIntegrationActivity.validateIntent(this);nonce=getIntent().getStringExtra("runNonce");build=IntegrationBuildIdentity.read(this);
    if(!build.getString("sourceCommit").equals(getIntent().getStringExtra("sourceCommit")))throw new SecurityException("Fresh source binding required");
    fixture=new BrowserFingerprintFixture(this,"gecko");fixture.start();BrowserFingerprintIntegrationActivity.configure(this,fixture.port(),ROOT+"gecko-system");
    getSharedPreferences("chat",0).edit().putBoolean("saveDraft",true).putInt("privacyLevel",1).commit();
    ChatSession.browserFactory=(context,owner)->new ObservedGecko(context,owner,this);getIntent().putExtra("legacyChat",true);
    super.onCreate(null);wholeDeadline=SystemClock.elapsedRealtime()+600000;deadline=SystemClock.elapsedRealtime()+90000;publish();
    waitFor("production main surface",this::ready,()->{
      check("gecko.production-main",remote instanceof ObservedGecko&&geckoAddress!=null&&geckoAddress.address.isShown());
      check("trust.enterprise-roots",enterpriseRootsReadback);
      capture("system",true,value->{try{check("clock.system",firstInline(value)&&clockMatches(value,java.util.TimeZone.getDefault().getID()));check("ua.mobile.native",!value.getJSONObject("native").getBoolean("desktop"));lastSample=value;saveZone("America/New_York",()->capture("new-york",true,this::newYork));}catch(Throwable error){failed(error);}});
    });
  }catch(Throwable error){failed(error);}}
  final class ObservedGecko extends GeckoWebView {
    final GeckoEnvironmentPolicyIntegrationActivity test;
    ObservedGecko(android.content.Context context,ChatSession owner,GeckoEnvironmentPolicyIntegrationActivity test){super(context,owner);this.test=test;}
    @Override GeckoSession newSession(){
      runtime.getSettings().setEnterpriseRootsEnabled(true);enterpriseRootsReadback=runtime.getSettings().getEnterpriseRootsEnabled();
      GeckoSession sdk=super.newSession();GeckoSession.ProgressDelegate original=sdk.getProgressDelegate();
      sdk.setProgressDelegate(new GeckoSession.ProgressDelegate(){
        public void onPageStart(GeckoSession s,String url){event("page-start",s,url);original.onPageStart(s,url);}
        public void onPageStop(GeckoSession s,boolean ok){event(ok?"page-stop-true":"page-stop-false",s,loadingTargets.getOrDefault(s,""));original.onPageStop(s,ok);}
        public void onProgressChange(GeckoSession s,int progress){original.onProgressChange(s,progress);}
        public void onSessionStateChange(GeckoSession s,GeckoSession.SessionState saved){original.onSessionStateChange(s,saved);}
        public void onSecurityChange(GeckoSession s,SecurityInformation info){original.onSecurityChange(s,info);try{
          if(!Arrays.asList(BrowserFingerprintFixture.A,BrowserFingerprintFixture.B).contains(info.host))return;
          String leaf=info.certificate==null?"":BrowserFingerprintFixture.sha(info.certificate.getEncoded());
          JSONObject value=J.obj("isSecure",info.isSecure,"isException",info.isException,"host",info.host,"leafDerSha256",leaf,"enterpriseRootsReadback",enterpriseRootsReadback);
          securities.put(s,value);event("security",s,info.origin==null?"":info.origin);
          if(!info.isSecure||info.isException||!leaf.equals(fixture.leafSha256))failed(new SecurityException("Native controlled TLS leaf mismatch"));
        }catch(Throwable error){failed(error);}}
      });
      GeckoSession.NavigationDelegate navigation=sdk.getNavigationDelegate();
      sdk.setNavigationDelegate(new GeckoSession.NavigationDelegate(){
        public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s,LoadRequest request){event("load-request",s,request.uri);return navigation.onLoadRequest(s,request);}
        public GeckoResult<AllowOrDeny> onSubframeLoadRequest(GeckoSession s,LoadRequest request){return navigation.onSubframeLoadRequest(s,request);}
        public void onLocationChange(GeckoSession s,String url,List<GeckoSession.PermissionDelegate.ContentPermission> permissions,Boolean gesture){event("location",s,url);navigation.onLocationChange(s,url,permissions,gesture);}
        public void onCanGoBack(GeckoSession s,boolean value){navigation.onCanGoBack(s,value);}
        public void onCanGoForward(GeckoSession s,boolean value){navigation.onCanGoForward(s,value);}
        public GeckoResult<GeckoSession> onNewSession(GeckoSession s,String url){popupCallbacks++;event("popup",s,url);return navigation.onNewSession(s,url);}
        public GeckoResult<String> onLoadError(GeckoSession s,String url,WebRequestError error){event("load-error-"+error.category+"-"+error.code,s,url);return navigation.onLoadError(s,url,error);}
      });return sdk;
    }
    @Override void restoreCheckpoint(GeckoSession target,GeckoSession.SessionState saved,String url,long revision){restoreRequests++;super.restoreCheckpoint(target,saved,url,revision);}
  }
  void event(String kind,GeckoSession sdk,String url){if(nativeEvents.length()>=180)return;String value=url==null?"":url;nativeEvents.put(J.obj("kind",kind,"url",value.substring(0,Math.min(400,value.length())),"sessionId",sdk==null?"":AppSessionIdentity.id(sdk),"queued",remote==null?"":remote.queued,"navigationEpoch",session==null?0:session.navigationEpoch,"stage",stage));}
  boolean ready(){return !terminal&&session!=null&&remote!=null&&remote.ready&&session.networkReady&&!session.connecting&&!session.navigating&&remote.hasVisibleDocument()&&remote.ports.get(remote.current)!=null&&session.timeZone.status().optBoolean("nativeSettingReadback")&&fixture.accepted.get()>0;}
  void within(String name)throws IOException{if(SystemClock.elapsedRealtime()>deadline||SystemClock.elapsedRealtime()>wholeDeadline)throw new IOException("Policy stage deadline: "+stage+" / "+name);}
  void waitFor(String name,Ready condition,Step next){if(terminal)return;try{within(name);if(condition.get()){next.run();return;}probe.postDelayed(()->waitFor(name,condition,next),75);}catch(Throwable error){failed(error);}}
  void next(String value)throws Exception{stage=value;deadline=SystemClock.elapsedRealtime()+45000;publish();}
  void check(String id,boolean pass)throws Exception{checks.put(J.obj("id",id,"pass",pass));if(!pass)throw new AssertionError(id);}
  static JSONObject decoded(String raw)throws Exception{Object value=new JSONTokener(raw).nextValue();if(value==JSONObject.NULL)return new JSONObject();if(!(value instanceof String))throw new IOException("Actual page DOM receipt absent");return new JSONObject((String)value);}
  void page(Consumer<JSONObject> callback){if(terminal)return;GeckoSession sdk=remote.current;long epoch=session.navigationEpoch;remote.evaluateJavascript("document.documentElement.getAttribute('data-gecko-environment-policy')",raw->{if(terminal)return;try{within("page observation");if(sdk!=remote.current||epoch!=session.navigationEpoch){callback.accept(new JSONObject());return;}if(raw==null||raw.length()>300000)throw new IOException("Bounded synthetic DOM receipt required");JSONObject value=decoded(raw);lastPageObservation=J.parse(value.toString());callback.accept(value);}catch(Throwable error){failed(error);}});}
  boolean firstInline(JSONObject value)throws Exception{return value.getJSONObject("page").getBoolean("firstInline")&&value.getJSONObject("page").getBoolean("secure");}
  static boolean clockMatches(JSONObject sample,String expected)throws Exception{
    JSONObject clock=sample.getJSONObject("page").getJSONObject("nativeTimeZone");java.time.ZoneId zone=java.time.ZoneId.of(expected),observed=java.time.ZoneId.of(clock.getString("timeZone"));
    if(!zone.getRules().equals(observed.getRules()))return false;
    for(String month:new String[]{"january","july"}){java.time.ZonedDateTime value=java.time.Instant.parse(month.equals("january")?"2026-01-15T12:00:00Z":"2026-07-15T12:00:00Z").atZone(zone);JSONObject actual=clock.getJSONObject(month);
      if(actual.getInt("offsetMinutes")!=-value.getOffset().getTotalSeconds()/60||actual.getInt("year")!=value.getYear()||actual.getInt("month")!=value.getMonthValue()||actual.getInt("day")!=value.getDayOfMonth()||actual.getInt("hour")!=value.getHour()||actual.getInt("minute")!=value.getMinute())return false;
    }return true;
  }
  void capture(String label,boolean workers,Consumer<JSONObject> done){
    waitFor(label+" page",this::ready,()->page(value->{try{
      JSONObject early=value.optJSONObject("page");JSONArray frames=value.optJSONArray("frames");
      if(early==null||frames==null||frames.length()!=2||!early.optBoolean("markerComplete")){probe.postDelayed(()->capture(label,workers,done),75);return;}
      if(!nonce.equals(early.optString("runNonce"))||!build.getString("sourceCommit").equals(early.optString("sourceCommit")))throw new SecurityException("Actual page invocation differs");
      for(int i=0;i<frames.length();i++)if(!frames.getJSONObject(i).optBoolean("markerComplete")){probe.postDelayed(()->capture(label,workers,done),75);return;}
      JSONObject measured=value.optJSONObject("workers");
      if(workers&&(measured==null||!measured.optBoolean("started"))){remote.evaluateJavascript("document.dispatchEvent(new CustomEvent('pocketchat-gecko-env-run-workers',{detail:"+JSONObject.quote(nonce)+"}))",ignored->{});probe.postDelayed(()->capture(label,workers,done),75);return;}
      if(workers&&!measured.optBoolean("complete")){if(measured.has("error"))throw new IOException("Actual Worker measurement failed: "+measured.optString("error"));probe.postDelayed(()->capture(label,workers,done),75);return;}
      nativeSample(value,nativeValue->{try{value.put("label",label);value.put("url",remote.getUrl());value.put("native",nativeValue);JSONObject security=securities.get(remote.current);if(security==null)throw new IOException("Native security callback missing");value.put("security",security);if(label.equals("rfp-system-reset"))rfpResetBaseline=value;else if(label.equals("rfp-applied"))rfpFinalObservation=value;else if(label.endsWith("-applied"))transitionSamples.put(value);else samples.put(value);lastSample=value;publish();if(!nativeValue.optBoolean("contextCurrent"))throw new IOException("Stored timezone ticket differs from actual current native context");done.accept(value);}catch(Throwable error){failed(error);}});
    }catch(Throwable error){failed(error);}}));
  }
  @SuppressWarnings("unchecked") GeckoTimeZoneStore.Ticket ticket()throws Exception{
    Field operations=GeckoTimeZoneController.class.getDeclaredField("operations");operations.setAccessible(true);Object operation=((Map<Object,Object>)operations.get(session.timeZone)).get(remote.current);if(operation==null)throw new IOException("Actual controller operation absent");Field field=operation.getClass().getDeclaredField("ticket");field.setAccessible(true);return (GeckoTimeZoneStore.Ticket)field.get(operation);
  }
  void nativeSample(JSONObject value,Consumer<JSONObject> done)throws Exception{
    final GeckoSession sdk=remote.current;final long navigation=session.navigationEpoch;final GeckoTimeZoneStore.Ticket current=ticket();if(current==null)throw new IOException("Native timezone ticket missing");
    final String token=UUID.randomUUID().toString().replace("-","")+UUID.randomUUID().toString().replace("-","");
    remote.sendTimeZone(remote.routePort,sdk,remote.timeZoneGates.get(sdk),"timezoneRead","",token,raw->{try{
      JSONObject fresh=GeckoTimeZonePolicy.contextReadback(raw,token,AppSessionIdentity.id(sdk));lastNativeReadback=J.obj("freshReadback",fresh,"ticketBinding",current.binding.json(),"stage",stage);
    sdk.getUserAgent().accept(ua->{session.environmentIo.execute(()->{try{
      JSONObject receipt=GeckoTimeZoneStore.lastReceipt(session.context,current);GeckoTimeZoneStore.State state=GeckoTimeZoneStore.load(session.context);
      probe.post(()->{try{if(sdk!=remote.current||navigation!=session.navigationEpoch)throw new IOException("Native observation context changed");checkUniqueBridge(receipt,current);done.accept(J.obj("sessionId",AppSessionIdentity.id(sdk),"sessionEpoch",current.binding.sessionEpoch,"contextId",fresh.getString("contextId"),"contextCurrent",current.binding.contextId.equals(fresh.getString("contextId")),"freshReadback",fresh,"desiredRevision",state.revision,"desiredZone",state.spec.zoneId,"timeZonePolicy",session.timeZone.status(sdk,current.binding.sessionEpoch),"receipt",receipt,"userAgent",ua,"desktop",remote.desktop,"headerPolicy",remote.getSettings().requestHeaderPolicy));}catch(Throwable error){failed(error);}});
    }catch(Throwable error){probe.post(()->failed(error));}});},error->failed(error));
    }catch(Throwable error){failed(error);}},this::failed);
  }
  boolean bridgeChecked;
  void checkUniqueBridge(JSONObject receipt,GeckoTimeZoneStore.Ticket current)throws Exception{if(receipt.length()==0)throw new IOException("Actual current stored receipt absent");if(!bridgeChecked){check("bridge.exact-session-context",receipt.getJSONObject("binding").getString("sessionId").equals(AppSessionIdentity.id(remote.current))&&receipt.getJSONObject("binding").getString("contextId").equals(current.binding.contextId));bridgeChecked=true;}}

  static List<View> windows(){return WindowInspector.getGlobalWindowViews();}
  static <T extends View>T first(View root,Class<T> type){if(type.isInstance(root))return type.cast(root);if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){T found=first(((ViewGroup)root).getChildAt(i),type);if(found!=null)return found;}return null;}
  static Button button(View root,String text){if(root instanceof Button&&text.contentEquals(((Button)root).getText()))return (Button)root;if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){Button found=button(((ViewGroup)root).getChildAt(i),text);if(found!=null)return found;}return null;}
  static View window(String text){for(View root:windows())if(root.isAttachedToWindow()&&root.isShown()&&button(root,text)!=null)return root;return null;}
  static void closeWindow(View root,String description){if(root==null)return;ArrayList<View> all=new ArrayList<>();all.add(root);while(!all.isEmpty()){View view=all.remove(all.size()-1);if(description.contentEquals(String.valueOf(view.getContentDescription()))){view.performClick();return;}if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)all.add(((ViewGroup)view).getChildAt(i));}}
  void saveZone(String zone,Step after)throws Exception{
    next("ui-zone-"+(zone.isEmpty()?"system":zone));String previous=lastSample==null?"":lastSample.getJSONObject("page").getString("documentId");GeckoTimeZoneUi.show(this);
    waitFor("timezone actual editor",()->window("应用并重新加载")!=null,()->{
      View editor=window("应用并重新加载");Spinner mode=first(editor,Spinner.class);EditText input=first(editor,EditText.class);if(mode==null||input==null)throw new IOException("Actual timezone UI controls missing");mode.setSelection(zone.isEmpty()?1:zone.equals("UTC")?2:3);input.setText(zone);button(editor,"应用并重新加载").performClick();
      waitFor("timezone actual confirmation",()->window("已保存输入，应用")!=null,()->{
        View confirmation=window("已保存输入，应用");if(confirmation==null)throw new IOException("Explicit input-preservation confirmation absent");button(confirmation,"已保存输入，应用").performClick();
        waitFor("saved current native timezone",()->ready()&&session.timeZone.cached.spec.zoneId.equals(zone),()->page(value->{try{
          if(value.optJSONObject("page")==null||previous.equals(value.getJSONObject("page").optString("documentId"))){probe.postDelayed(()->awaitZoneDocument(editor,previous,after),75);return;}
          closeWindow(editor,"关闭此环境的独立时区");after.run();
        }catch(Throwable error){failed(error);}}));
      });
    });
  }
  void awaitZoneDocument(View editor,String previous,Step after){waitFor("fresh zone document",this::ready,()->page(value->{try{if(value.optJSONObject("page")==null||previous.equals(value.getJSONObject("page").optString("documentId"))){probe.postDelayed(()->awaitZoneDocument(editor,previous,after),75);return;}closeWindow(editor,"关闭此环境的独立时区");after.run();}catch(Throwable error){failed(error);}}));}
  void navigate(String host,String phase,Step after)throws Exception{
    next("address-"+phase);geckoAddress.address.performClick();waitFor("actual address editor",()->window("打开")!=null,()->{View editor=window("打开");EditText input=first(editor,EditText.class);if(input==null)throw new IOException("Actual address field missing");input.setText("https://"+host+"/env-policy?phase="+phase);button(editor,"打开").performClick();waitFor("address committed",()->ready()&&remote.getUrl().equals(input.getText().toString()),after);});
  }
  void saveDisplay(boolean desktop,boolean rfp,Step after)throws Exception{
    next(rfp?"ui-rfp":desktop?"ui-desktop":"ui-mobile");String previous=lastSample.getJSONObject("page").getString("documentId");FingerprintTemplateUi.show(this);waitFor("actual template editor",()->window("保存模板")!=null,()->{
      View editor=window("保存模板");Spinner choices=first(editor,Spinner.class);if(choices==null)throw new IOException("Actual template choices absent");choices.setSelection(rfp?4:desktop?1:0);button(editor,"保存模板").performClick();
      waitFor("saved native display",()->ready()&&remote.desktop==desktop&&session.privacy.level()==(rfp?2:1)&&remote.metadata.policyAcknowledged&&!session.identityApplicationPending&&!DeferredBrowserSettings.pending(session)&&(!rfp||remote.nativeProtection.confirmed()),()->awaitDisplayDocument(editor,previous,after));
    });
  }
  void awaitDisplayDocument(View editor,String previous,Step after){waitFor("fresh template document",this::ready,()->page(value->{try{if(value.optJSONObject("page")==null||previous.equals(value.getJSONObject("page").optString("documentId"))){probe.postDelayed(()->awaitDisplayDocument(editor,previous,after),75);return;}closeWindow(editor,"关闭环境模板");after.run();}catch(Throwable error){failed(error);}}));}

  void newYork(JSONObject value){try{
    check("clock.new-york",firstInline(value)&&clockMatches(value,"America/New_York"));retainedTicket=ticket();retainedReceipt=value.getJSONObject("native").getJSONObject("receipt");
    navigate(BrowserFingerprintFixture.B,"gecko-coop",()->capture("coop",false,coop->{try{
      check("clock.coop",firstInline(coop)&&clockMatches(coop,"America/New_York"));waitFor("host actual COOP response",this::coopResponseObserved,()->{
        lifecycle.put("coop",J.obj("fromOrigin",value.getJSONObject("page").getString("origin"),"toOrigin",coop.getJSONObject("page").getString("origin"),"oldContextId",value.getJSONObject("native").getString("contextId"),"newContextId",coop.getJSONObject("native").getString("contextId"),"contextChanged",!value.getJSONObject("native").getString("contextId").equals(coop.getJSONObject("native").getString("contextId")),"firstInlineZoneCorrect",true,"responseHeaderObserved",coopResponseObserved()));
        staleNativeTicket(coop.getJSONObject("native"),()->saveZone("Asia/Kathmandu",()->capture("kathmandu",true,this::kathmandu)));
      });
    }catch(Throwable error){failed(error);}}));
  }catch(Throwable error){failed(error);}}
  boolean coopResponseObserved(){JSONArray rows=fixture.snapshot().optJSONArray("requests");if(rows==null)return false;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&("https://"+BrowserFingerprintFixture.B).equals(row.optString("origin"))&&"/env-policy".equals(row.optString("path"))&&"gecko-coop".equals(row.optString("phase"))&&"same-origin".equals(row.optString("responseCoop")))return true;}return false;}
  void staleNativeTicket(JSONObject captured,Step after)throws Exception{
    final GeckoTimeZoneStore.Ticket old=retainedTicket;final JSONObject oldReceipt=retainedReceipt;final JSONObject current=captured;
    session.environmentIo.execute(()->{boolean rejected=false,empty=false;try{try{GeckoTimeZoneStore.record(session.context,old,oldReceipt.getJSONObject("nativeReceipt").toString());}catch(Exception expected){rejected=true;}empty=GeckoTimeZoneStore.lastReceipt(session.context,old).length()==0;}catch(Exception ignored){}boolean denial=rejected,absent=empty;probe.post(()->{try{
      staleTicketProof=J.obj("actualStoreRecordAttempt",true,"oldRecordRejected",denial,"oldReceiptEmpty",absent,"oldContextId",old.binding.contextId,"newContextId",current.getString("contextId"),"oldToken",old.requestToken,"newToken",current.getJSONObject("receipt").getString("requestToken"));check("stale.actual-store-record-rejected",denial&&absent);
      after.run();
    }catch(Throwable error){failed(error);}});});
  }
  void staleRevisionTicket(JSONObject captured,Step after)throws Exception{
    final GeckoTimeZoneStore.Ticket old=retainedTicket,active=ticket();final JSONObject oldReceipt=retainedReceipt,current=captured;
    session.environmentIo.execute(()->{boolean recordRejected=false,receiptRejected=false,preserved=false;try{
      try{GeckoTimeZoneStore.record(session.context,old,oldReceipt.getJSONObject("nativeReceipt").toString());}catch(Exception expected){recordRejected=true;}
      try{GeckoTimeZoneStore.lastReceipt(session.context,old);}catch(Exception expected){receiptRejected=true;}
      JSONObject fresh=GeckoTimeZoneStore.lastReceipt(session.context,active);GeckoTimeZoneStore.State desired=GeckoTimeZoneStore.load(session.context);
      preserved=desired.revision==current.getLong("desiredRevision")&&desired.spec.zoneId.equals(current.getString("desiredZone"))&&old.revision<desired.revision&&fresh.getLong("desiredRevision")==desired.revision&&active.requestToken.equals(fresh.getString("requestToken"))&&fresh.getString("requestToken").equals(current.getJSONObject("receipt").getString("requestToken"))&&fresh.getJSONObject("binding").getString("contextId").equals(current.getString("contextId"));
    }catch(Exception ignored){}boolean denial=recordRejected,absent=receiptRejected,kept=preserved;probe.post(()->{try{
      staleRevisionProof=J.obj("actualStoreRecordAttempt",true,"actualStoreReceiptAttempt",true,"currentReceiptRead",true,"oldRecordRejected",denial,"oldReceiptRejected",absent,"currentReceiptPreserved",kept,"oldRevision",old.revision,"newRevision",current.getLong("desiredRevision"),"oldContextId",old.binding.contextId,"newContextId",current.getString("contextId"),"oldToken",old.requestToken,"newToken",current.getJSONObject("receipt").getString("requestToken"));
      check("stale.old-revision-record-rejected",denial);check("stale.old-revision-receipt-rejected",absent);check("stale.current-receipt-preserved",kept);after.run();
    }catch(Throwable error){failed(error);}});});
  }
  void kathmandu(JSONObject value){try{
    check("clock.kathmandu",firstInline(value)&&clockMatches(value,"Asia/Kathmandu"));staleRevisionTicket(value.getJSONObject("native"),()->{
      next("reload");JSONObject before=value;String doc=before.getJSONObject("page").getString("documentId");requestReload();waitFor("actual independent reload confirmation",()->window("已保存，重新加载")!=null,()->{button(window("已保存，重新加载"),"已保存，重新加载").performClick();waitFor("actual reload",this::ready,()->captureAfterNewDocument("reload",doc,false,reloaded->{try{lifecycle.put("reload",transition(before,reloaded));check("navigation.reload",true);prepareRestore(reloaded);}catch(Throwable error){failed(error);}}));});
    });
  }catch(Throwable error){failed(error);}}
  void captureAfterNewDocument(String label,String previous,boolean workers,Consumer<JSONObject> done){if(terminal)return;try{within("new document");}catch(Exception error){failed(error);return;}page(value->{try{if(value.optJSONObject("page")==null||previous.equals(value.getJSONObject("page").optString("documentId"))){probe.postDelayed(()->captureAfterNewDocument(label,previous,workers,done),75);return;}capture(label,workers,done);}catch(Throwable error){failed(error);}});}
  static JSONObject transition(JSONObject before,JSONObject after)throws Exception{return J.obj("beforeDocumentId",before.getJSONObject("page").getString("documentId"),"afterDocumentId",after.getJSONObject("page").getString("documentId"),"beforeContextId",before.getJSONObject("native").getString("contextId"),"afterContextId",after.getJSONObject("native").getString("contextId"));}
  void prepareRestore(JSONObject before)throws Exception{
    next("sdk-checkpoint");final GeckoSession sdk=remote.current;final GeckoSession.SessionState prior=remote.states.get(sdk);remote.evaluateJavascript("(()=>{const e=document.getElementById('gecko-policy-draft');if(!e)return 'missing';e.value="+JSONObject.quote(MARKER)+";e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return 'set'})()",raw->{try{if(!"set".equals(new JSONTokener(raw).nextValue()))throw new IOException("Controlled restore form missing");remote.checkpointState();waitFor("fresh actual SDK checkpoint after edit",()->remote.states.get(sdk)!=null&&remote.states.get(sdk)!=prior&&remote.states.get(sdk).size()>0,()->{
      next("reopen");remote.timezoneConfigurationChanged();waitFor("reopened native context",this::ready,()->captureAfterNewDocument("reopen",before.getJSONObject("page").getString("documentId"),false,reopened->{try{
        lifecycle.put("reopen",transition(before,reopened));check("navigation.reopen",!before.getJSONObject("native").getString("contextId").equals(reopened.getJSONObject("native").getString("contextId")));
        restoreFromFreshCheckpoint(reopened);
      }catch(Throwable error){failed(error);}}));
    });}catch(Throwable error){failed(error);}});
  }
  void restoreFromFreshCheckpoint(JSONObject reopened)throws Exception{
    final GeckoSession sdk=remote.current;final long epoch=session.navigationEpoch;
    remote.evaluateJavascript("document.getElementById('gecko-policy-draft')?.value",raw->{try{
      if(terminal)return;within("reopened form before checkpoint");
      if(sdk!=remote.current||epoch!=session.navigationEpoch||!MARKER.equals(new JSONTokener(raw).nextValue()))throw new IOException("Actual reopened form was not restored before its checkpoint");
      final GeckoSession.SessionState prior=remote.states.get(sdk);remote.checkpointState();
      waitFor("fresh actual SDK checkpoint after reopen",()->{
        if(sdk!=remote.current||epoch!=session.navigationEpoch)throw new IOException("Reopened checkpoint context changed");
        GeckoSession.SessionState fresh=remote.states.get(sdk);return fresh!=null&&fresh!=prior&&fresh.size()>0;
      },()->{
        int count=restoreRequests;next("restore");remote.timezoneConfigurationChanged();waitFor("restored second native context",this::ready,()->captureAfterNewDocument("restore",reopened.getJSONObject("page").getString("documentId"),false,restoredSample->{try{
          remote.evaluateJavascript("document.getElementById('gecko-policy-draft')?.value",value->{try{Object restored=new JSONTokener(value).nextValue();lifecycle.put("restore",J.obj("beforeContextId",reopened.getJSONObject("native").getString("contextId"),"afterContextId",restoredSample.getJSONObject("native").getString("contextId"),"sdkCheckpointAvailable",true,"formValueRestored",MARKER.equals(restored),"actualRestoreRequests",restoreRequests-count));check("navigation.restore",MARKER.equals(restored)&&restoreRequests>count&&!reopened.getJSONObject("native").getString("contextId").equals(restoredSample.getJSONObject("native").getString("contextId")));publish();popupAndDesktop();}catch(Throwable error){failed(error);}});
        }catch(Throwable error){failed(error);}}));
      });
    }catch(Throwable error){failed(error);}});
  }
  void popupAndDesktop(){try{
    next("custom-popup");int before=remote.popups.size(),calls=popupCallbacks;GeckoSession sdk=remote.current;
    sdk.getNavigationDelegate().onNewSession(sdk,"https://"+BrowserFingerprintFixture.A+"/env-policy?phase=gecko-popup").accept(popup->{try{
      popupProof=J.obj("actualNavigationDelegate",popupCallbacks==calls+1,"customRejected",popup==null,"sessionCountBefore",before,"sessionCountAfter",remote.popups.size(),"oldNativeSessionUnchanged",sdk==remote.current,"actualBrowserPopupGesture",false);check("popup.custom-rejected",popup==null&&popupCallbacks==calls+1&&before==remote.popups.size()&&sdk==remote.current);
      saveDisplay(true,false,this::desktopApplied);
    }catch(Throwable error){failed(error);}},this::failed);
  }catch(Throwable error){failed(error);}}
  void desktopApplied(){capture("desktop-applied",false,ignored->{try{navigate(BrowserFingerprintFixture.A,"gecko-desktop",()->capture("desktop",true,desktop->{try{check("ua.desktop.native",desktop.getJSONObject("native").getBoolean("desktop"));saveDisplay(false,false,this::mobileApplied);}catch(Throwable error){failed(error);}}));}catch(Throwable error){failed(error);}});}
  void mobileApplied(){capture("mobile-restored-applied",false,ignored->{try{navigate(BrowserFingerprintFixture.B,"gecko-restored",()->capture("mobile-restored",true,mobile->{try{check("ua.mobile-restored.native",!mobile.getJSONObject("native").getBoolean("desktop"));finishRfp();}catch(Throwable error){failed(error);}}));}catch(Throwable error){failed(error);}});}
  void finishRfp()throws Exception{
    saveZone("",()->capture("rfp-system-reset",false,baseline->{try{saveDisplay(false,true,()->capture("rfp-applied",false,ignored->attemptRfpConflict()));}catch(Throwable error){failed(error);}}));
  }
  static boolean containsText(View root,String text){if(root instanceof TextView&&((TextView)root).getText().toString().contains(text))return true;if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++)if(containsText(((ViewGroup)root).getChildAt(i),text))return true;return false;}
  void attemptRfpConflict(){try{
      next("rfp-conflict");long revision=session.timeZone.cached.revision;String zone=session.timeZone.cached.spec.zoneId;int level=session.privacy.level();GeckoTimeZoneUi.show(this);
      waitFor("RFP timezone editor",()->window("应用并重新加载")!=null,()->{View editor=window("应用并重新加载");first(editor,Spinner.class).setSelection(3);first(editor,EditText.class).setText("America/New_York");button(editor,"应用并重新加载").performClick();waitFor("actual RFP rejection result",()->button(editor,"应用并重新加载").isEnabled()&&containsText(editor,"强化模板优先使用自己的时区策略"),()->{
        rfpConflictProof=J.obj("actualUiAttempt",true,"levelBefore",level,"levelAfter",session.privacy.level(),"rfpConfirmed",remote.nativeProtection.confirmed()&&remote.fingerprintingProtected,"desiredRevisionBefore",revision,"desiredRevisionAfter",session.timeZone.cached.revision,"savedZoneBefore",zone,"savedZoneAfter",session.timeZone.cached.spec.zoneId,"customSaveRejected",session.timeZone.cached.revision==revision&&zone.equals(session.timeZone.cached.spec.zoneId));check("rfp.conflict-preserves-protection",level==2&&session.privacy.level()==2&&rfpConflictProof.getBoolean("rfpConfirmed")&&rfpConflictProof.getBoolean("customSaveRejected"));closeWindow(editor,"关闭此环境的独立时区");
        check("wire.public-only",fixture.snapshot().optInt("upstreamConnections",-1)==0&&!fixture.snapshot().optBoolean("forwardingImplemented",true));
        check("gpt.generic-hotpath-off",!session.chatAutomationAllowed()&&session.driverTarget()==null);check("coverage.worker-scopes-honest",!session.timeZone.status().optBoolean("workerCoverageVerified",true)&&!session.timeZone.status().optBoolean("serviceWorkerCoverageVerified",true));
        terminal=true;stage="complete";publish();
      });});
    }catch(Throwable error){failed(error);}
  }
  void failed(Throwable error){if(terminal)return;terminal=true;failedAtStage=stage;stage="failed";String text=String.valueOf(error.getMessage()).replace('\n',' ').replace('\r',' ');failure=error.getClass().getSimpleName()+": "+text.substring(0,Math.min(300,text.length()));try{publish();}catch(Exception ignored){}}
  void publish()throws Exception{if(build==null)return;JSONObject report=J.obj("schema",1,"fixtureType","gecko-production-environment-policy-v1","engine","gecko","status",terminal?(failure.isEmpty()?"passed":"failed"):"running","stage",stage,"failedAtStage",failedAtStage,"failure",failure,"sourceCommit",build.getString("sourceCommit"),"sourceTree",build.getString("sourceTree"),"runNonce",nonce,"buildIdentity",build,"checks",checks,"samples",samples,"transitionSamples",transitionSamples,"rfpResetBaseline",rfpResetBaseline,"rfpFinalObservation",rfpFinalObservation,"lastNativeReadback",lastNativeReadback,"lastPageObservation",lastPageObservation,"staleTicketProof",staleTicketProof,"staleRevisionProof",staleRevisionProof,"popupProof",popupProof,"rfpConflictProof",rfpConflictProof,"lifecycle",lifecycle,"fixture",fixture==null?new JSONObject():fixture.snapshot(),"nativeEvents",nativeEvents,"currentTimeZonePolicy",session==null?new JSONObject():session.timeZone.status(),"actualAndroidExecution",true,"actualGeckoExecution",remote!=null&&remote.current!=null,"actualAndroidWebViewExecution",false,"actualPublicWebsiteExecution",false,"actualDevicePerformanceMeasurement",false,"fingerprintProtectionVerified",false,"workerCoverageVerified",false,"serviceWorkerCoverageVerified",false,"contentProcessStopExecuted",false,"scope","Actual MainActivity/timezone/template UI and exact-session private native bridge; synthetic CA-trusted HTTPS first-inline Date/Intl and raw Worker/server header observations. Native setting receipts are separate from Worker effects; custom popup callback is invoked directly, not a claimed trusted popup gesture. Original acceptance workloads remain independently mandatory.");BrowserFingerprintIntegrationActivity.write(this,"gecko-environment-policy-results.json",report);}
  @Override protected void onDestroy(){probe.removeCallbacksAndMessages(null);if(fixture!=null)fixture.close();super.onDestroy();}
}
