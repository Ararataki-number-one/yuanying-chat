package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.view.Gravity;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** A separate synthetic APK; the runner operates the real Android dialogs with touch input. */
public final class NetworkSourcesUiIntegrationActivity extends Activity {
  static final String ENTRY_URL="https://127.0.0.1:9/entry",EXIT_URL="https://127.0.0.1:9/exit";
  static final String EDITED_ENTRY_URL="https://127.0.0.1:9/edited-entry",EDITED_EXIT_URL="https://127.0.0.1:9/edited-exit";
  final Handler handler=new Handler(Looper.getMainLooper());
  final ExecutorService io=Executors.newSingleThreadExecutor();
  final JSONArray checks=new JSONArray();
  NetworkWorkspaceUi ui;NetworkWorkspaceUi.EditorSession editor;
  Context profile;SecretStore vault;JSONObject initial,parentBefore;
  byte[] originalSettings,entryRaw,exitRaw;String entryId,exitId,manualId,stage="starting";
  boolean ready,finished,nativeEntry,nativeExit;long entrySuccessAt,exitSuccessAt;

  void check(String name,boolean pass){
    checks.put(J.obj("name",name,"pass",pass));
    if(!pass)throw new AssertionError(name);
  }
  @Override public void onCreate(Bundle saved){
    super.onCreate(saved);if(!getPackageName().equals("local.pocketchat.test"))throw new SecurityException("Synthetic UI fixture only");
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    LinearLayout root=DesignUi.column(this);ReferenceUi.insets(this,root);FrameLayout host=new FrameLayout(this);root.addView(host,new LinearLayout.LayoutParams(-1,0,1));
    root.addView(ReferenceUi.nav(this,3,n->{},new android.widget.Button[5]));setContentView(root);ui=new NetworkWorkspaceUi(this,host);ui.show(0);
    handler.post(tick);io.execute(()->{try{seed();}catch(Throwable failed){fail(failed);}});
  }
  byte[] provider(boolean exit){
    JSONArray nodes=new JSONArray();
    nodes.put(J.obj("name",exit?"Tokyo":"Entry A","type","socks5","server","127.0.0.1","port",exit?19111:19110,"username","synthetic","password","synthetic"));
    if(exit){
      nodes.put(J.obj("name","Tokyo Alias","type","socks5","server","127.0.0.1","port",19111,"username","synthetic","password","synthetic"));
      nodes.put(J.obj("name","Unsupported HTTP","type","http","server","127.0.0.1","port",19112));
    }return J.obj("proxies",nodes).toString().getBytes(StandardCharsets.UTF_8);
  }
  void seed()throws Exception{
    NetworkCatalog catalog=new NetworkCatalog(this);JSONObject entry=catalog.addSubscription(NetworkCatalog.ENTRY,"EntrySource",ENTRY_URL),exit=catalog.addSubscription(NetworkCatalog.EXIT,"ExitSource",EXIT_URL),manual=catalog.addExit("ManualSource","Synthetic","127.0.0.1",19120,"synthetic","synthetic");
    entryId=entry.optString("id");exitId=exit.optString("id");manualId=manual.optString("id");entryRaw=provider(false);exitRaw=provider(true);
    profile=Profiles.context(this,6);vault=new SecretStore(profile);ProfileCatalog.get(this).created(6);ProfileCatalog.get(this).rename(6,"UI Window");
    initial=J.obj("subscriptionUrl",ENTRY_URL,"subscriptionName","EntrySource","exitHost","127.0.0.1","exitPort",19120,"exitUser","synthetic","exitPassword","synthetic","exitName","ManualSource","exitLibraryId",manualId,"exitSource","manual","entryMode","manual","entry","Entry|Entry A","entryPool",J.arr("Entry|Entry A"));
    vault.save(initial);originalSettings=vault.get("network");profile.getSharedPreferences("chat",0).edit().putString("networkMode","internal").putBoolean("networkConfigured",true).putString("draft","unchanged synthetic chat draft").commit();
    parse(NetworkCatalog.ENTRY,entryId,entryRaw,()->parse(NetworkCatalog.EXIT,exitId,exitRaw,()->handler.post(()->{
      try{NetworkCatalog latest=new NetworkCatalog(this);JSONObject e=latest.subscription(NetworkCatalog.ENTRY,entryId),x=latest.subscription(NetworkCatalog.EXIT,exitId);entrySuccessAt=e.optLong("lastSuccessAt");exitSuccessAt=x.optLong("lastSuccessAt");
        latest.parsed(entryId,NetworkCatalog.copy(e.optJSONArray("nodes")),entryRaw,entrySuccessAt);e=latest.subscription(NetworkCatalog.ENTRY,entryId);if(e.optJSONArray("nodeDetails").length()!=0||!Arrays.equals(entryRaw,latest.cache(e)))throw new AssertionError("Names-only legacy migration seed was not created");
        check("Real native entrance parser publishes one entrance",nativeEntry&&NetworkSourceSelection.names(e).equals(Collections.singletonList("Entry|Entry A")));
        check("Real native exit parser includes SOCKS5 aliases and HTTP",nativeExit&&NetworkSourceSelection.names(x).size()==3);
        check("Identical exit connection aliases retain one real fingerprint",NetworkSourceSelection.fingerprint(x,"Exit|Tokyo").equals(NetworkSourceSelection.fingerprint(x,"Exit|Tokyo Alias")));
        ui.catalog=latest;ui.windows=WindowNetworkState.windows(this);NetworkWorkspaceUi.readUiMetadata(this,ui.windows);checkDiagnostics();ui.show(0);ready=true;stage="ready";publish();
      }catch(Throwable failed){fail(failed);}
    })));
  }
  void parse(String role,String id,byte[] raw,Runnable next){
    try{NetworkCatalog c=new NetworkCatalog(this);NetworkCatalog.RefreshToken token=c.beginRefresh(role,id);
      NativeNetwork.previewSubscription(this,role,token.url,raw,(ok,message,names,details,bytes)->io.execute(()->{
        try{if(!ok)throw new IOException("Controlled native source parsing failed");if(!Arrays.equals(raw,bytes)||names.length()!=details.length())throw new IOException("Native source payload or metadata length mismatch");for(int i=0;i<details.length();i++){JSONObject detail=details.optJSONObject(i);if(detail==null||detail.optInt("configFingerprintVersion")!=1||!detail.optString("configFingerprint").matches("[0-9a-f]{64}")||detail.optString("type").isEmpty()||detail.has("server")||detail.has("password"))throw new IOException("Native source metadata invalid");}new NetworkCatalog(this).parsed(token,names,details,bytes,System.currentTimeMillis());if(NetworkCatalog.ENTRY.equals(role))nativeEntry=true;else nativeExit=true;next.run();}catch(Throwable failed){fail(failed);}
      }));
    }catch(Throwable failed){fail(failed);}
  }
  JSONObject parent(){return editor==null?new JSONObject():J.obj("entrySource",editor.draft.subscriptionId,"entry",editor.draft.entry,"pool",new JSONArray(editor.draft.pool),"manualExit",editor.draft.exitId,"exitSource",editor.draft.exitSubscriptionId,"exitNodeKey",editor.draft.exitNodeKey,"exitNodeName",editor.draft.exitNodeName);}
  void checkDiagnostics(){
    JSONObject row=window().optJSONObject("row");long now=System.currentTimeMillis();
    JSONObject runtime=J.obj("mode","internal","at",now,"configured",true,"connected",true,"entry","Entry|Entry A","delayEntry","Entry|Entry A","delay",418,"delayAt",now-120000,"exitId",NativeNetwork.exitIdentity(initial),"subscriptionId",NativeNetwork.hash(ENTRY_URL));
    String text=ConnectionTrace.windowDiagnostics(this,new WindowNetworkState(this,row,initial,runtime,true,now));
    check("Window diagnostics use the selected slot rather than the viewing process",text.contains("窗口编号：6")&&text.contains("418 ms"));
    check("Window diagnostics label historical readings and separate website timings",text.contains("历史记录")&&text.contains("不是 ChatGPT 请求的分项"));
    check("Window diagnostics exclude subscription and credential values",!text.contains(ENTRY_URL)&&!text.contains("synthetic")&&!text.contains("127.0.0.1"));
    NetworkCatalog.put(runtime,"exitId","changed-exit");
    text=ConnectionTrace.windowDiagnostics(this,new WindowNetworkState(this,row,initial,runtime,true,now));
    check("Window diagnostics do not reuse readings from another exit",text.contains("尚无匹配的分项记录")&&!text.contains("418 ms"));
  }
  void unchanged()throws Exception{check("Window encrypted settings unchanged at "+stage,Arrays.equals(originalSettings,vault.get("network")));check("Chat draft unchanged at "+stage,"unchanged synthetic chat draft".equals(profile.getSharedPreferences("chat",0).getString("draft","")));}
  JSONObject window(){for(int i=0;i<ui.windows.length();i++){JSONObject item=ui.windows.optJSONObject(i);if(item.optJSONObject("row").optInt("slot")==6)return item;}throw new IllegalStateException("Synthetic window missing");}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);if(!ready||finished)return;try{command(intent.getStringExtra("command"));}catch(Throwable failed){fail(failed);}}
  void command(String command)throws Exception{
    if(command==null)return;NetworkCatalog c=new NetworkCatalog(this);ui.catalog=c;ui.windows=WindowNetworkState.windows(this);NetworkWorkspaceUi.readUiMetadata(this,ui.windows);stage=command;
    switch(command){
      case "window-tab":ui.select(0);break;
      case "entry-tab":ui.select(1);break;
      case "exit-tab":ui.select(2);break;
      case "open-editor":
        editor=ui.editInternal(window());parentBefore=parent();check("Network editor is an actual centered Dialog",editor.dialog.isShowing()&&editor.dialog.getWindow().getAttributes().gravity==Gravity.CENTER);break;
      case "assert-legacy-prepared":{
        JSONObject row=c.subscription(NetworkCatalog.ENTRY,entryId);check("Opening legacy editor reparses existing raw cache without a download",row.optJSONArray("nodeDetails").length()==1&&Arrays.equals(entryRaw,c.cache(row)));
        check("Cached migration retains the legacy manual entry mode","manual".equals(editor.draft.mode));
        check("Cached migration retains the selected entrance and allowed pool","Entry|Entry A".equals(editor.draft.entry)&&editor.draft.pool.equals(new LinkedHashSet<>(Collections.singletonList("Entry|Entry A"))));
        check("Cached migration binds the real native entrance identity",NetworkSourceSelection.fingerprint(row,"Entry|Entry A").equals(editor.draft.entryNodeKey)&&editor.draft.entryNodeKey.matches("[0-9a-f]{64}"));unchanged();break;
      }
      case "assert-unselected":
        check("Unsupported exit cannot change the parent draft",parent().toString().equals(parentBefore.toString()));unchanged();break;
      case "assert-cancelled-picker":
        check("Cancelling a supported exit choice leaves the parent draft unchanged",parent().toString().equals(parentBefore.toString()));unchanged();break;
      case "assert-selected-alias":
        check("Confirming the fixed-exit picker changes only the candidate",editor.draft.exitId.isEmpty()&&exitId.equals(editor.draft.exitSubscriptionId)&&"Exit|Tokyo Alias".equals(editor.draft.exitNodeName));
        check("Selected alias uses the native configuration fingerprint",NetworkSourceSelection.fingerprint(c.subscription(NetworkCatalog.EXIT,exitId),"Exit|Tokyo Alias").equals(editor.draft.exitNodeKey));unchanged();break;
      case "assert-editor-cancelled":check("Cancel closes the actual editor",editor!=null&&!editor.dialog.isShowing());unchanged();break;
      case "assert-entry-added":case "assert-exit-added":{
        String role=command.equals("assert-entry-added")?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,name=command.equals("assert-entry-added")?"AddedEntry":"AddedExit";JSONObject found=findSource(c,role,name);
        check("Touch form saves the new "+role+" source",found!=null&&!found.optString("id").isEmpty());check("New "+role+" source does not appear in the other library",findSource(c,role.equals(NetworkCatalog.ENTRY)?NetworkCatalog.EXIT:NetworkCatalog.ENTRY,name)==null);unchanged();break;
      }
      case "open-entry-edit":ui.subscriptionForm(NetworkCatalog.ENTRY,c.subscription(NetworkCatalog.ENTRY,entryId),null);break;
      case "open-exit-edit":ui.subscriptionForm(NetworkCatalog.EXIT,c.subscription(NetworkCatalog.EXIT,exitId),null);break;
      case "assert-entry-edited":case "assert-exit-edited":{
        boolean entry=command.equals("assert-entry-edited");String role=entry?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,id=entry?entryId:exitId;JSONObject row=c.subscription(role,id);
        check("Touch edit retains the "+role+" source identity",row!=null&&id.equals(row.optString("id")));
        check("Touch edit changes the "+role+" address independently",(entry?EDITED_ENTRY_URL:EDITED_EXIT_URL).equals(row.optString("url"))&&(entry?"EntryEdited":"ExitEdited").equals(row.optString("name")));
        check("Edited "+role+" address is stale until a successful refresh",row.optBoolean("stale")&&c.cache(row)==null);
        check("Editing "+role+" keeps the previous encrypted source bytes",Arrays.equals(entry?entryRaw:exitRaw,c.lastGoodCache(row)));unchanged();break;
      }
      case "assert-entry-failed":case "assert-exit-failed":{
        boolean entry=command.equals("assert-entry-failed");String role=entry?NetworkCatalog.ENTRY:NetworkCatalog.EXIT;JSONObject row=c.subscription(role,entry?entryId:exitId);
        check("Actual refused HTTPS "+role+" update completes with a failure",!row.optBoolean("updating")&&!row.optString("lastError").isEmpty()&&row.optLong("lastFailureAt")>0);
        check("Failed "+role+" refresh retains all last successful nodes",NetworkSourceSelection.names(row).size()==(entry?1:3));
        check("Failed "+role+" refresh retains the last successful timestamp",row.optLong("lastSuccessAt")== (entry?entrySuccessAt:exitSuccessAt));
        check("Failed "+role+" refresh retains the last successful bytes",Arrays.equals(entry?entryRaw:exitRaw,c.lastGoodCache(row)));
        check("Failed "+role+" source is visibly labelled as old address data",ui.sourceSummary(row,role).contains("地址已修改")&&row.optBoolean("stale"));unchanged();break;
      }
      case "open-manual-detail":ui.exitDetail(c.exit(manualId));break;
      case "assert-manual-edited":{
        JSONObject row=c.exit(manualId);check("Touch manual edit retains its library identity",row!=null&&manualId.equals(row.optString("id")));
        check("Touch manual edit saves the changed name and port","ManualEdited".equals(row.optString("name"))&&row.optInt("port")==19121);
        check("Old endpoint alias still resolves to the edited library row",c.exit(NetworkCatalog.exitId(initial))!=null&&manualId.equals(c.exit(NetworkCatalog.exitId(initial)).optString("id")));unchanged();break;
      }
      case "open-entry-detail":ui.subscriptionDetail(c.subscription(NetworkCatalog.ENTRY,entryId));break;
      case "open-exit-detail":ui.subscriptionDetail(c.subscription(NetworkCatalog.EXIT,exitId));break;
      case "assert-entry-deleted":case "assert-exit-deleted":{
        boolean entry=command.equals("assert-entry-deleted");String role=entry?NetworkCatalog.ENTRY:NetworkCatalog.EXIT;
        check("Touch delete removes the "+role+" source",c.subscription(role,entry?entryId:exitId)==null);
        check("Deleting "+role+" preserves the separately added source",findSource(c,role,entry?"AddedEntry":"AddedExit")!=null);unchanged();break;
      }
      case "assert-manual-deleted":check("Touch delete removes the manual exit",c.exit(manualId)==null);unchanged();break;
      case "finish":
        check("No native global default exit is introduced",!c.data.has("defaultExit"));check("UI metadata does not create a ChatGPT account session",ChatSession.peek()==null);unchanged();report(true,"");return;
      default:throw new IllegalArgumentException("Unknown synthetic UI command");
    }publish();
  }
  JSONObject findSource(NetworkCatalog c,String role,String name){JSONArray all=c.subscriptions(role);for(int i=0;i<all.length();i++){JSONObject row=all.optJSONObject(i);if(name.equals(row.optString("name")))return row;}return null;}
  JSONObject sourceState(JSONObject source){return source==null?new JSONObject():J.obj("id",source.optString("id"),"name",source.optString("name"),"url",source.optString("url"),"updating",source.optBoolean("updating"),"stale",source.optBoolean("stale"),"lastError",source.optString("lastError"),"nodeCount",NetworkSourceSelection.names(source).size());}
  void publish(){
    if(finished)return;try{NetworkCatalog c=new NetworkCatalog(this);JSONArray entries=new JSONArray(),exits=new JSONArray();for(int i=0;i<c.subscriptions(NetworkCatalog.ENTRY).length();i++)entries.put(sourceState(c.subscriptions(NetworkCatalog.ENTRY).optJSONObject(i)));for(int i=0;i<c.subscriptions(NetworkCatalog.EXIT).length();i++)exits.put(sourceState(c.subscriptions(NetworkCatalog.EXIT).optJSONObject(i)));
      JSONObject manual=c.exit(manualId);JSONObject value=J.obj("stage",stage,"ready",ready,"entries",entries,"exits",exits,"manual",manual==null?new JSONObject():J.obj("id",manual.optString("id"),"name",manual.optString("name"),"port",manual.optInt("port")),"parent",parent(),"checkCount",checks.length(),"checks",checks);J.write(new File(getFilesDir(),"network-source-ui-state.json"),value.toString());
    }catch(Throwable failed){fail(failed);}
  }
  final Runnable tick=new Runnable(){public void run(){if(finished||isDestroyed())return;publish();handler.postDelayed(this,350);}};
  void fail(Throwable failure){if(Looper.myLooper()!=Looper.getMainLooper()){handler.post(()->fail(failure));return;}if(finished)return;android.util.Log.e("PocketNetworkSourceUi","Synthetic UI scenario failed",failure);report(false,failure.getClass().getSimpleName()+": "+failure.getMessage());}
  void report(boolean ok,String failure){
    if(finished)return;finished=true;JSONObject value=J.obj("status",ok?"passed":"failed","checkCount",checks.length(),"checks",checks,"actualAndroidExecution",true,"actualNativeExecution",nativeEntry&&nativeExit,"actualKeystoreEncryption",vault!=null&&originalSettings!=null,"actualRouteApplication",false,"stage",stage,"failure",failure,"scope","Actual native provider parsing, Android Keystore source library, and ADB touch-operated central dialogs. Loopback HTTPS refusal tests failed refresh. No public proxy, account login or WAN speed is claimed.");try{J.write(new File(getFilesDir(),"network-source-ui-results.json"),value.toString(2));}catch(Throwable failed){android.util.Log.e("PocketNetworkSourceUi","Result save failed",failed);}
  }
  @Override public void onDestroy(){if(ui!=null)ui.close();handler.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}
}
