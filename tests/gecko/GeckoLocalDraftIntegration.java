package local.pocketchat;

import android.content.*;
import android.database.DatabaseErrorHandler;
import android.database.sqlite.SQLiteDatabase;
import android.os.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.mozilla.geckoview.GeckoSession;

/** Actual SDK form capture, private store read after process death, and SDK restore.
 * The store directory and explicit restore are fixture-owned, not automatic startup selection. */
final class GeckoLocalDraftIntegration {
  static final String ACTION="localDraftPolicy", COOKIE="f04Draft", OLD="f04-enabled-", FRESH="f04-fresh-";
  final GeckoIntegrationTestActivity a;final ChatSession s;final long serial,deadline;
  final SharedPreferences prefs;final File directory;
  final ExecutorService worker=Executors.newSingleThreadExecutor();
  final JSONObject result=J.obj("schema",1,"actualAndroidExecution",true,"actualGeckoExecution",true,
    "fixtureOwnedStore",true,"explicitSdkRestore",true,"automaticStartupSelectionAcceptance",false,
    "physicalPhoneAcceptance",false,"realChatGptPageMemoryCapture",false,"pid",android.os.Process.myPid());
  final JSONObject partial=new JSONObject();
  boolean finished;String phase,target;long stableAt,readRevision;int stableSamples;double stableDocument=-1;EnvironmentSpec.Identity environment;
  GeckoLocalDraftIntegration(GeckoIntegrationTestActivity activity,long command){
    a=activity;s=a.session;serial=command;deadline=SystemClock.elapsedRealtime()+40000;
    prefs=a.getSharedPreferences("f04-local-draft-fixture",0);directory=new File(a.getNoBackupFilesDir(),"f04-local-draft-fixture");
  }
  static void run(GeckoIntegrationTestActivity a,long serial){new GeckoLocalDraftIntegration(a,serial).start();}
  boolean current(){return !finished&&serial==a.run;}
  void post(Runnable task){s.handler.post(()->{if(current())try{task.run();}catch(Throwable error){fail(error);}});}
  void later(Runnable task){if(SystemClock.elapsedRealtime()>deadline){fail(new IllegalStateException("F04 readiness deadline exceeded"));return;}s.handler.postDelayed(()->{if(current())try{task.run();}catch(Throwable error){fail(error);}},100);}
  void start(){try{
    phase=a.getIntent().getStringExtra("draftPhase");
    if(!Arrays.asList("seed","off","stale-on","fresh-on").contains(phase))throw new IllegalArgumentException("Unknown F04 phase");
    if(a.slot!=1)throw new IllegalStateException("F04 owns only the controlled second environment");
    environment=ProfileCatalog.get(a).identity(a.slot);result.put("environmentIdentity",environment.json());
    result.put("phase",phase);
    observeStage("start");
    if("seed".equals(phase)){
      if(prefs.contains("target"))throw new IllegalStateException("Unfinished F04 invocation exists");
      boolean original=LocalDraftPolicy.enabled(a);AppPrefs.apply(a,J.obj("saveDraft",true));
      String nonce=a.getIntent().getStringExtra("eventNonce");if(nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IllegalStateException("Missing F04 invocation nonce");
      target="http://127.0.0.1:8765/browser-session?context="+(a.slot+1)+"&localDraft="+nonce;
      prefs.edit().putBoolean("originalEnabled",original).putString("target",target).commit();
      prefs.edit().putString("environmentId",environment.environmentId).putInt("generation",environment.generation).commit();
      result.put("fixtureNonce",nonce).put("profileSlot",a.slot);
      s.web.loadUrl(target);waitSeed(false);
    }else{
      target=prefs.getString("target","");if(!target.matches("http://127[.]0[.]0[.]1:8765/browser-session[?]context=2&localDraft=[0-9a-f]{32}"))throw new IllegalStateException("F04 seed missing or foreign");
      if(!environment.environmentId.equals(prefs.getString("environmentId",""))||environment.generation!=prefs.getInt("generation",-1))throw new IllegalStateException("F04 environment changed across process death");
      result.put("fixtureNonce",target.substring(target.indexOf("&localDraft=")+12)).put("profileSlot",a.slot);
      if("off".equals(phase)&&LocalDraftPolicy.enabled(a)||!"off".equals(phase)&&!LocalDraftPolicy.enabled(a))throw new IllegalStateException("Policy did not survive process death");
      readAndRestore("fresh-on".equals(phase));
    }
  }catch(Throwable error){fail(error);}}
  String text(boolean fresh){return (fresh?FRESH:OLD)+prefs.getString("target",target).substring(prefs.getString("target",target).indexOf("&localDraft=")+12);}
  static String quote(String value){return JSONObject.quote(value);}
  void probe(java.util.function.Consumer<JSONObject> done){
    s.web.evaluateJavascript("(()=>{const e=document.getElementById('session-draft'),n=document.getElementById('f04-sends');return e&&n?{ok:true,url:location.href,draft:e.value,draftLength:e.value.length,draftComplete:true,hasDraft:e.value.length>0,selectionStart:e.selectionStart,selectionEnd:e.selectionEnd,cookie:document.cookie,token:document.getElementById('session-result').textContent,history:history.length,scroll:scrollY,sends:Number(n.textContent),document:performance.timeOrigin}:null})()",raw->{if(current())try{retainPartial("probeRaw",raw);done.accept(J.parse(raw));}catch(Throwable error){fail(error);}});
  }
  void waitSeed(boolean fresh){observeStage("capture-wait-document");probe(value->{
    if(!value.optBoolean("ok")||!value.optString("url").startsWith(target)){later(()->waitSeed(fresh));return;}
    String input=text(fresh);
    s.web.evaluateJavascript("(()=>{const e=document.getElementById('session-draft');e.value="+quote(input)+";e.dispatchEvent(new Event('input',{bubbles:true}));if(!location.hash)history.pushState({f04:true},'',location.href+'#f04-saved');document.cookie='"+COOKIE+"=kept; Path=/browser-session; SameSite=Lax';scrollTo(0,720);return e.value})()",raw->{if(current())awaitCaptured(fresh);});
  });}
  void awaitCaptured(boolean fresh){
    observeStage("capture-wait-sdk");
    s.web.checkpointState();GeckoSession.SessionState state=s.web.states.get(s.web.primary);
    if(state==null){later(()->awaitCaptured(fresh));return;}
    GeckoSession.SessionState copy=new GeckoSession.SessionState(state);
    worker.execute(()->{try{
      String payload=copy.toString();JSONObject source=new JSONObject(payload);
      if(!source.has("formdata")||!source.get("formdata").toString().contains(text(fresh))){post(()->later(()->awaitCaptured(fresh)));return;}
      if(!source.has("history")||!source.has("scrolldata")){post(()->later(()->awaitCaptured(fresh)));return;}
      JSONObject observedSdk=J.obj("sourceSdkFormdataContainsUniqueDraft",source.get("formdata").toString().contains(text(fresh)),
        "formdataRaw",source.get("formdata").toString(),"sourceSdkHistoryPresent",source.has("history"),"sourceSdkScrollDataPresent",source.has("scrolldata"),
        "payloadBytes",payload.getBytes(StandardCharsets.UTF_8).length,"payloadSha256",sha(payload.getBytes(StandardCharsets.UTF_8)));
      post(()->{retainPartial("sdkSource",observedSdk.toString());probe(dom->{
        retainPartial("domSource",dom.toString());
        if(!text(fresh).equals(dom.optString("draft"))||Math.abs(dom.optDouble("scroll")-720)>2||dom.optInt("sends",-1)!=0){later(()->awaitCaptured(fresh));return;}
        if(!dom.optString("cookie").contains(COOKIE+"=kept")||!"synthetic-session-2".equals(dom.optString("token")))throw new IllegalStateException("Live fixture or positive session cookie missing");
        rememberCheck(dom,true);worker.execute(()->storeCaptured(payload,source,dom,fresh));
      });});
    }catch(Throwable error){post(()->fail(error));}});
  }
  static String memoryUrl(String nonce){
    if(nonce==null||!nonce.matches("[0-9a-f]{32}"))throw new IllegalArgumentException("Invalid F04 memory nonce");
    return MainActivity.ORIGIN+"c/f04-"+nonce;
  }
  static JSONObject memoryInput(JSONObject dom,String nonce)throws JSONException{
    if(dom==null)throw new IllegalArgumentException("Missing F04 source document");
    String before=dom.toString();JSONObject copy=new JSONObject(before);copy.put("url",memoryUrl(nonce));
    verifyMemoryInput(dom,copy,nonce);
    if(!before.equals(dom.toString()))throw new IllegalStateException("F04 adapter changed original DOM");
    return copy;
  }
  static void verifyMemoryInput(JSONObject dom,JSONObject copy,String nonce)throws JSONException{
    String logical=memoryUrl(nonce),source="http://127.0.0.1:8765/browser-session?context=2&localDraft="+nonce+"#f04-saved";
    if(dom==null||copy==null||dom==copy||!(dom.opt("url") instanceof String)||!source.equals(dom.getString("url"))||!(copy.opt("url") instanceof String)||!logical.equals(copy.getString("url")))throw new IllegalArgumentException("Foreign F04 source or logical document");
    JSONObject restored=new JSONObject(copy.toString());restored.put("url",source);
    if(!canonical(restored).equals(canonical(dom)))throw new IllegalStateException("F04 adapter changed fields other than URL");
  }
  void rememberCheck(JSONObject dom,boolean enabled){try{
    String scope=s.pageMemory.scope();if(scope.isEmpty())throw new IllegalStateException("Actual PageMemory scope missing");
    String nonce=result.getString("fixtureNonce"),sourceRaw=dom.toString(),sourceUrl=dom.getString("url");
    retainPartial("domSource",sourceRaw);
    JSONObject adapted=memoryInput(dom,nonce);String logical=adapted.getString("url"),adaptedRaw=adapted.toString();
    retainPartial("memoryInput",adaptedRaw);
    String rejectedKey=scope+"|"+PageMemory.address(sourceUrl);long before=s.pageMemory.serial;int count=s.pageMemory.pages.size();
    if(s.pageMemory.pages.containsKey(rejectedKey))throw new IllegalStateException("Unexpected loopback PageMemory entry");
    // Exercise the production ChatGPT-only admission guard before adapting a copy.
    // The SDK state and actual browser document remain the original loopback page.
    s.pageMemory.remember(scope,dom.optString("url"),dom);
    long rejectedSerial=s.pageMemory.serial;boolean rejectedEntry=s.pageMemory.pages.containsKey(rejectedKey);
    if(rejectedEntry||rejectedSerial!=before||s.pageMemory.pages.size()!=count)throw new IllegalStateException("Production loopback admission was not rejected");
    s.pageMemory.remember(scope,logical,adapted);
    JSONObject stored=s.pageMemory.pages.get(scope+"|"+PageMemory.address(logical));
    if(stored!=null)retainPartial("memoryStored",stored.toString());
    if(stored==null||s.pageMemory.serial!=before+1||!sourceRaw.equals(dom.toString())||!adaptedRaw.equals(adapted.toString()))throw new IllegalStateException("F04 adapted memory missing or input changed");
    boolean valid=stored!=null&&(enabled?text("stale-on".equals(phase)||"fresh-on".equals(phase)).equals(stored.optString("draft"))&&LocalDraftPolicy.mayRestore(a,stored):stored.isNull("draft")&&!PageMemory.completeDraft(stored)&&PageMemory.hasDraft(stored)&&!LocalDraftPolicy.mayRestore(a,stored));
    if(!valid)throw new IllegalStateException("Production PageMemory policy mismatch");
    JSONObject adapter=result.optJSONObject("adapter");if(adapter==null){adapter=J.obj("schema",1,"kind","page-memory-remember-url-only","sourceDomUrl",sourceUrl,"logicalMemoryUrl",logical,"onlyUrlAdapted",true,"realChatGPT",false,"checks",new JSONArray());result.put("adapter",adapter);}
    if(!sourceUrl.equals(adapter.getString("sourceDomUrl"))||!logical.equals(adapter.getString("logicalMemoryUrl")))throw new IllegalStateException("F04 adapter identity changed");
    adapter.getJSONArray("checks").put(J.obj("enabled",enabled,"sourceDomRaw",sourceRaw,"sourceDomAfterRaw",dom.toString(),"memoryInputRaw",adaptedRaw,"storedSnapshotRaw",stored.toString(),
      "loopbackSerialBefore",before,"loopbackSerialAfter",rejectedSerial,"storedSerial",s.pageMemory.serial,"loopbackEntryPresent",rejectedEntry,"storedEntryPresent",stored!=null,"policyRevision",LocalDraftPolicy.revision(a)));
    NetworkCatalog.put(result,enabled?"enabledPageMemoryKeepsActualDraft":"disabledPageMemoryRedactsActualDraft",true);
  }catch(Exception error){throw new IllegalStateException("F04 PageMemory fixture failed",error);}}
  void storeCaptured(String payload,JSONObject source,JSONObject dom,boolean fresh){try{
    String name=fresh?"fresh":"original";long revision=LocalDraftPolicy.revision(a);
    BrowserSessionStore store=new BrowserSessionStore(context(name));store.write(payload);
    store.read(read->{try{
      if(!payload.equals(read))throw new IllegalStateException("Enabled store altered actual SDK payload");
      byte[] disk=bytes(store.file.getBaseFile());String hash=sha(disk);
      prefs.edit().putString(name+"Sha256",hash).putLong(name+"Revision",revision)
        .putInt(name+"History",dom.optInt("history")).putString(name+"Cookie",dom.optString("cookie"))
        .putString(name+"Token",dom.optString("token")).putString(name+"Url",dom.optString("url"))
        .putFloat(name+"Scroll",(float)dom.optDouble("scroll")).commit();
      JSONObject proof=J.obj("sourceSdkFormdataContainsUniqueDraft",true,"sourceSdkHistoryPresent",source.has("history"),
        "sourceSdkScrollDataPresent",source.has("scrolldata"),"checkpointSha256",hash,"payloadSha256",sha(payload.getBytes(StandardCharsets.UTF_8)),
        "storedRevision",revision,"sourceHistory",dom.optInt("history"),"sourceScroll",dom.optDouble("scroll"),"sends",dom.optInt("sends"),
        "draftSha256",sha(dom.getString("draft").getBytes(StandardCharsets.UTF_8)),"sourceSessionCookiePresent",true);
      result.put("capture",proof);
      if(!fresh){
        DraftArchive archive=new DraftArchive(context("archive"));
        try{if(!archive.save(target,text(false),"F04 synthetic retained history")||archive.list(target).length()!=1)throw new IllegalStateException("Enabled actual SQLite archive write failed");}finally{archive.close();}
        AppPrefs.apply(a,J.obj("saveDraft",false));
        if(LocalDraftPolicy.enabled(a)||LocalDraftPolicy.revision(a)!=revision+1)throw new IllegalStateException("Production disable revision missing");
        result.put("disabledBeforeProcessDeath",true).put("currentRevision",LocalDraftPolicy.revision(a));
      }
      store.io.shutdown();
      if(!fresh)post(()->probe(live->{
        if(!text(false).equals(live.optString("draft"))||live.optInt("sends",-1)!=0)throw new IllegalStateException("Disabling saving changed live input or sent it");
        rememberCheck(live,false);NetworkCatalog.put(result,"liveDraftPreservedAfterDisable",true);finishAfterCookieCheckpoint(false);
      }));else post(()->finishAfterCookieCheckpoint(false));
    }catch(Throwable error){store.io.shutdown();post(()->fail(error));}});
  }catch(Throwable error){post(()->fail(error));}}
  void readAndRestore(boolean fresh){observeStage("read-scheduled");worker.execute(()->{try{
    String name=fresh?"fresh":"original";Context isolated=context(name);File file=new File(isolated.getNoBackupFilesDir(),"gecko-session.json");
    byte[] disk=bytes(file);if(!sha(disk).equals(prefs.getString(name+"Sha256","")))throw new IllegalStateException("Frozen checkpoint changed across process death");
    String stamped=new String(disk,StandardCharsets.UTF_8);int end=stamped.indexOf('\n');if(end<0||!stamped.startsWith(LocalDraftPolicy.CHECKPOINT_HEADER))throw new IllegalStateException("Production checkpoint header missing");
    String number=stamped.substring(LocalDraftPolicy.CHECKPOINT_HEADER.length(),end);if(!number.matches("0|[1-9][0-9]{0,18}"))throw new IllegalStateException("Actual checkpoint revision malformed");
    long storedRevision=Long.parseLong(number);if(storedRevision!=prefs.getLong(name+"Revision",-1))throw new IllegalStateException("Actual disk revision differs from captured write");readRevision=storedRevision;
    String payload=stamped.substring(end+1);JSONObject original=new JSONObject(payload);
    if(!original.has("formdata")||!original.get("formdata").toString().contains(text(fresh)))throw new IllegalStateException("Negative control has no actual SDK draft");
    BrowserSessionStore store=new BrowserSessionStore(isolated);store.read(filtered->{try{
      if(filtered==null)throw new IllegalStateException("Fresh process private store read failed");
      JSONObject safe=new JSONObject(filtered),expected=new JSONObject(payload);if(!fresh)expected.remove("formdata");
      if(!canonical(safe).equals(canonical(expected)))throw new IllegalStateException("Checkpoint changed fields other than formdata");
      if(fresh?!payload.equals(filtered):safe.has("formdata"))throw new IllegalStateException("Actual formdata policy failed");
      result.put("read",J.obj("checkpointSha256",sha(disk),"sourceSdkFormdataContainsUniqueDraft",true,
        "storedRevision",storedRevision,"currentRevision",LocalDraftPolicy.revision(a),
        "saveDraftEnabled",LocalDraftPolicy.enabled(a),"formsPresent",safe.has("formdata"),"allOtherSdkFieldsUnchanged",true,
        "historyUnchanged",canonical(original.get("history")).equals(canonical(safe.get("history"))),
        "scrollDataUnchanged",canonical(original.get("scrolldata")).equals(canonical(safe.get("scrolldata"))),
        "freshStoreInstance",true,"processId",android.os.Process.myPid()));
      if("off".equals(phase)){
        DraftArchive archive=new DraftArchive(context("archive"));try{
          JSONArray rows=archive.list(target);boolean before=rows.length()==1&&text(false).equals(rows.getJSONObject(0).getString("body"));
          boolean refused=!archive.save(target,"F04 forbidden new disabled copy","F04 off");
          JSONArray after=archive.list(target);if(!before||!refused||after.length()!=1||!canonical(rows).equals(canonical(after)))throw new IllegalStateException("Disabling draft saving changed archive history or accepted new copy");
          result.put("disabledArchiveRejectsNewCopy",true).put("existingArchiveHistoryPreserved",true);
        }finally{archive.close();}
      }
      GeckoSession.SessionState restored=GeckoSession.SessionState.fromString(filtered);
      if(restored==null||restored.size()==0||!GeckoWebView.stateUrl(restored).equals(prefs.getString(name+"Url","")))throw new IllegalStateException("Actual SDK filtered state not restorable");
      store.io.shutdown();post(()->{observeRestoreRead(filtered);observeStage("restore-load-blank");s.web.loadUrl("about:blank");waitBlank(restored,fresh);});
    }catch(Throwable error){store.io.shutdown();post(()->fail(error));}});
  }catch(Throwable error){post(()->fail(error));}});}
  void waitBlank(GeckoSession.SessionState state,boolean fresh){
    observeStage("restore-wait-blank");
    if(!"about:blank".equals(s.web.getUrl())){later(()->waitBlank(state,fresh));return;}
    String name=fresh?"fresh":"original";
    observeStage("restore-dispatch");
    s.web.restoreCheckpoint(s.web.current,state,prefs.getString(name+"Url",""),readRevision);
    awaitRestored(fresh);
  }
  void awaitRestored(boolean fresh){probe(dom->{
    String name=fresh?"fresh":"original";boolean ready=dom.optBoolean("ok")&&dom.optString("url").equals(prefs.getString(name+"Url",""))
      &&(fresh?text(true):"").equals(dom.optString("draft"))&&dom.optInt("history",-1)==prefs.getInt(name+"History",-2)
      &&Math.abs(dom.optDouble("scroll")-prefs.getFloat(name+"Scroll",-100))<=2
      &&sameCookies(dom.optString("cookie"),prefs.getString(name+"Cookie",""))&&dom.optString("token").equals(prefs.getString(name+"Token",""))
      &&dom.optInt("sends",-1)==0&&s.web.painted.contains(s.web.current)&&!s.web.failed;
    long now=SystemClock.elapsedRealtime();double document=dom.optDouble("document",-1);
    observeRestored(fresh,dom,ready,now);
    if(!ready||document!=stableDocument){stableAt=ready?now:0;stableSamples=ready?1:0;stableDocument=document;}
    else stableSamples++;
    if(!ready||stableSamples<5||now-stableAt<1000){later(()->awaitRestored(fresh));return;}
    try{result.put("restored",J.obj("draft",dom.optString("draft"),"history",dom.optInt("history"),"scroll",dom.optDouble("scroll"),
      "sends",dom.optInt("sends"),"cookiePreserved",true,"sessionCookiePreserved",true,"document",document,
      "stableMillis",now-stableAt,"stableSamples",stableSamples,"sdkHistoryAndScrollRestored",true));
      if("off".equals(phase)){
        AppPrefs.apply(a,J.obj("saveDraft",true));result.put("enabledForStaleRead",LocalDraftPolicy.enabled(a)).put("nextRevision",LocalDraftPolicy.revision(a));finishAfterCookieCheckpoint(false);
      }else if("stale-on".equals(phase))waitSeed(true);
      else cleanup();
    }catch(Throwable error){fail(error);}
  });}
  void cleanup(){
    s.web.evaluateJavascript("(()=>{document.cookie='"+COOKIE+"=; Path=/browser-session; Max-Age=0';return !document.cookie.split(';').some(x=>x.trim().startsWith('"+COOKIE+"='))})()",raw->{if(current())try{
      if(!"true".equals(raw))throw new IllegalStateException("Fixture cookie cleanup failed");
      boolean original=prefs.getBoolean("originalEnabled",true);AppPrefs.apply(a,J.obj("saveDraft",original));
      if(LocalDraftPolicy.enabled(a)!=original)throw new IllegalStateException("Original draft setting not restored");
      s.pageMemory.pages.remove(s.pageMemory.scope()+"|"+PageMemory.address(memoryUrl(result.getString("fixtureNonce"))));
      worker.execute(()->{try{deleteOwn(directory,directory.getCanonicalFile());prefs.edit().clear().commit();post(()->{NetworkCatalog.put(result,"ownFixtureCleaned",true);NetworkCatalog.put(result,"originalPolicyRestored",true);finishAfterCookieCheckpoint(true);});}catch(Throwable error){post(()->fail(error));}});
    }catch(Throwable error){fail(error);}});
  }
  void finishAfterCookieCheckpoint(boolean removed){
    // The production cookie read awaits the extension journal's actual
    // storage.local checkpoint before replying; DOM observation alone does not.
    s.web.readCookies(target,nativeCookies->{if(current())try{
      if(nativeCookies==null)throw new IllegalStateException("Native cookie checkpoint failed");
      Set<String> values=new HashSet<>();for(String value:nativeCookies.split(";"))values.add(value.trim());
      if(!values.contains("sessionOnly=synthetic-session-2")||values.contains(COOKIE+"=kept")==removed)throw new IllegalStateException("Cookie journal did not preserve the positive session cookie and owned marker state");
      result.put("cookieJournalCheckpointed",true).put("nativeSessionCookiePresent",true);finish();
    }catch(Throwable error){fail(error);}});
  }
  Context context(String child){
    File root=new File(directory,child);if(!root.isDirectory()&&!root.mkdirs())throw new IllegalStateException("F04 private directory unavailable");
    return new ContextWrapper(a){
      @Override public Context getApplicationContext(){return this;}
      @Override public File getNoBackupFilesDir(){return root;}
      @Override public File getDatabasePath(String name){if(!"draft-archive.db".equals(name))throw new SecurityException("Unexpected F04 database");return new File(root,name);}
      @Override public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory){return SQLiteDatabase.openOrCreateDatabase(getDatabasePath(name),factory);}
      @Override public SQLiteDatabase openOrCreateDatabase(String name,int mode,SQLiteDatabase.CursorFactory factory,DatabaseErrorHandler handler){return SQLiteDatabase.openOrCreateDatabase(getDatabasePath(name).getPath(),factory,handler);}
    };
  }
  void finish(){if(!current())return;try{EnvironmentSpec.Identity after=ProfileCatalog.get(a).identity(a.slot);if(!after.equals(environment))throw new IllegalStateException("F04 environment changed during fixture");result.put("environmentIdentityAfter",after.json());result.put("status","passed").put("actualGeckoSessionState",true);finished=true;worker.shutdown();a.event(serial,ACTION,result);}catch(Throwable error){finished=false;fail(error);}}
  // Bounded latest observations are emitted only with the existing failure.
  // They never establish readiness or change a page, cookie, policy or deadline.
  void observeStage(String stage){try{
    GeckoSession current=s.web.current;Thread thread=Thread.currentThread();
    String raw=J.obj("stage",stage,"phase",phase,"elapsedRealtime",SystemClock.elapsedRealtime(),
      "command",serial,"currentCommand",a.run,"navigationEpoch",s.navigationEpoch,
      "session",current==null?0:System.identityHashCode(current),"primaryIsCurrent",current==s.web.primary,
      "sessionOpen",current!=null&&current.isOpen(),"nativeUrl",s.web.getUrl(),"painted",s.web.painted.contains(current),
      "failed",s.web.failed,"threadId",thread.getId(),"threadName",thread.getName(),
      "onMainLooper",Looper.myLooper()==Looper.getMainLooper()).toString();
    retainPartial("stage",raw);
    if("restore-wait-blank".equals(stage))retainPartial("restoreBlank",raw);
    if("restore-dispatch".equals(stage))retainPartial("restoreDispatch",raw);
  }catch(Exception ignored){}}
  void observeRestoreRead(String filtered){try{
    JSONObject read=result.optJSONObject("read");if(read!=null)retainPartial("restoreRead",read.toString());
    retainPartial("sdkRestore",filtered);
  }catch(Exception ignored){}}
  void observeRestored(boolean fresh,JSONObject dom,boolean ready,long now){try{
    observeStage("restore-await-document");String name=fresh?"fresh":"original";
    JSONObject expected=J.obj("url",prefs.getString(name+"Url",""),"draft",fresh?text(true):"",
      "history",prefs.getInt(name+"History",-2),"scroll",prefs.getFloat(name+"Scroll",-100),
      "cookie",prefs.getString(name+"Cookie",""),"token",prefs.getString(name+"Token",""),"sends",0);
    retainPartial("restoreDom",dom.toString());
    retainPartial("restoreReadiness",J.obj("observedAtElapsedRealtime",now,"readyFromOriginalExpression",ready,
      "expected",expected,"checks",restoreChecks(dom,expected,s.web.painted.contains(s.web.current),s.web.failed),
      "stableAtBeforeUpdate",stableAt,"stableSamplesBeforeUpdate",stableSamples,"stableDocumentBeforeUpdate",stableDocument,
      "deadlineElapsedRealtime",deadline,"saveDraftEnabled",LocalDraftPolicy.enabled(a),
      "policyRevision",LocalDraftPolicy.revision(a),"readRevision",readRevision).toString());
  }catch(Exception ignored){}}
  static JSONObject restoreChecks(JSONObject dom,JSONObject expected,boolean painted,boolean failed){
    return J.obj("ok",dom.optBoolean("ok"),"url",dom.optString("url").equals(expected.optString("url")),
      "draft",expected.optString("draft").equals(dom.optString("draft")),
      "history",dom.optInt("history",-1)==expected.optInt("history",-2),
      "scroll",Math.abs(dom.optDouble("scroll")-expected.optDouble("scroll",-100))<=2,
      "cookie",sameCookies(dom.optString("cookie"),expected.optString("cookie")),
      "token",dom.optString("token").equals(expected.optString("token")),
      "sends",dom.optInt("sends",-1)==0,"painted",painted,"notFailed",!failed);
  }
  void retainPartial(String key,String raw){try{
    if(!Arrays.asList("sdkSource","domSource","memoryInput","memoryStored","probeRaw","stage","restoreRead","sdkRestore","restoreBlank","restoreDispatch","restoreDom","restoreReadiness").contains(key))throw new IllegalArgumentException("Unknown F04 observation");
    byte[] data=raw.getBytes(StandardCharsets.UTF_8);JSONObject observed=J.obj("utf8Bytes",data.length,"sha256",sha(data));
    if(data.length<=8192)observed.put("rawUtf8",raw);else observed.put("rawOmitted",true);
    partial.put(key,observed);
  }catch(Exception ignored){/* Missing diagnostics never establish acceptance or replace the original error. */}}
  void fail(Throwable error){if(!current())return;finished=true;worker.shutdown();a.event(serial,"error",J.obj("error","F04 actual SDK regression: "+error,"phase",phase,"diagnosticOnly",true,"acceptance",false,"partial",partial));}
  static byte[] bytes(File file)throws IOException{try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>BrowserSessionStore.LIMIT+65)throw new IOException("F04 file exceeds existing limit");out.write(b,0,n);}return out.toByteArray();}}
  static String sha(byte[] bytes)throws Exception{StringBuilder value=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))value.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return value.toString();}
  static boolean sameCookies(String left,String right){String[] a=left.split(";"),b=right.split(";");for(int i=0;i<a.length;i++)a[i]=a[i].trim();for(int i=0;i<b.length;i++)b[i]=b[i].trim();Arrays.sort(a);Arrays.sort(b);return Arrays.equals(a,b);}
  static String canonical(Object value)throws JSONException{
    if(value instanceof JSONObject){JSONObject object=(JSONObject)value;ArrayList<String> keys=new ArrayList<>();for(Iterator<String> i=object.keys();i.hasNext();)keys.add(i.next());Collections.sort(keys);StringBuilder out=new StringBuilder("{");for(String key:keys){if(out.length()>1)out.append(',');out.append(quote(key)).append(':').append(canonical(object.get(key)));}return out.append('}').toString();}
    if(value instanceof JSONArray){JSONArray array=(JSONArray)value;StringBuilder out=new StringBuilder("[");for(int i=0;i<array.length();i++){if(i>0)out.append(',');out.append(canonical(array.get(i)));}return out.append(']').toString();}
    return value instanceof String?quote((String)value):String.valueOf(value);
  }
  static void deleteOwn(File file,File allowed)throws IOException{File canonical=file.getCanonicalFile();if(!canonical.equals(allowed)&&!canonical.getPath().startsWith(allowed.getPath()+File.separator))throw new SecurityException("F04 cleanup escaped its directory");File[] children=file.listFiles();if(children!=null)for(File child:children)deleteOwn(child,allowed);if(file.exists()&&!file.delete())throw new IOException("F04 cleanup incomplete");}
}
