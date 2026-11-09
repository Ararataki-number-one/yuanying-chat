package local.pocketchat;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;

/** Integration-only component preview. No configuration, observation or connection is saved. */
public final class ConfiguredNetworkVisualActivity extends Activity {
  static final String BANNER="示例配置 · 非真实连接";
  static final String EXPLANATION="IP、延迟与连接状态均为演示数据";
  NetworkWorkspaceUi workspace;

  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    try{
      String nonce=getIntent().getStringExtra("visualNonce");
      if(!"local.pocketchat.test".equals(getPackageName())||nonce==null||!nonce.matches("[0-9a-f]{32}")
          ||!DownloadLocationLayoutEvidence.cleanSource(this).equals(getIntent().getStringExtra("visualSourceCommit"))
          ||!AppSettings.bool(this,"nativeUiFiveEnvironmentSeedV1",false))
        throw new SecurityException("Source-bound disposable integration fixture required");
      int previewTab=getIntent().getIntExtra("visualNetworkTab",0);
      if(previewTab<0||previewTab>2)throw new SecurityException("Unknown presentation tab");
      if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
      LinearLayout root=DesignUi.column(this);root.setBackgroundColor(DesignUi.BG);
      LinearLayout notice=DesignUi.column(this);notice.setPadding(dp(22),dp(8),dp(22),dp(8));
      notice.addView(NetworkWorkspaceStyle.text(this,BANNER,12,ReferenceUi.ORANGE,true));
      notice.addView(NetworkWorkspaceStyle.text(this,EXPLANATION,11,ReferenceUi.MUTED,false));
      root.addView(notice,new LinearLayout.LayoutParams(-1,-2));
      FrameLayout stage=new FrameLayout(this),host=new FrameLayout(this);
      stage.addView(host,new FrameLayout.LayoutParams(-1,-1));root.addView(stage,new LinearLayout.LayoutParams(-1,0,1));
      LinearLayout dock=ReferenceUi.workspaceNav(this,AppHub.NETWORK,n->{},new Button[5]);
      stage.addView(dock,new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM));
      setContentView(root);ReferenceUi.insets(this,root);
      workspace=new NetworkWorkspaceUi(this,host);
      // This catalogue reads only the already-owned disposable test fixture.
      // Do not call show/fetch: no service IPC or observed snapshot is requested.
      workspace.catalog=new NetworkCatalog(this);
      JSONObject library=libraryPresentation(System.currentTimeMillis());
      for(String key:new String[]{"subscriptions","exitSubscriptions","exits"})NetworkCatalog.put(workspace.catalog.data,key,library.optJSONArray(key));
      workspace.windows=presentation(System.currentTimeMillis());
      workspace.tab=previewTab;workspace.closed=true;workspace.layout();
      dock.addOnLayoutChangeListener((v,l,t,r,b,ol,ot,or,ob)->workspace.setBottomInset(dock.getHeight()));
      dock.post(()->workspace.setBottomInset(dock.getHeight()));
      inertActions(root);AppAppearance.apply(root);
      Log.i("PocketUiVisual","configured-network-synthetic-ready "+nonce);
    }catch(Exception error){Log.e("PocketUiVisual","configured-network preview rejected",error);finish();}
  }

  int dp(int value){return ReferenceUi.dp(this,value);}
  static void inertActions(View view){
    if(view.isClickable())view.setOnClickListener(v->{});
    if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)inertActions(group.getChildAt(i));}
  }

  /** These arrays replace only this Activity's in-memory display catalogue. */
  static JSONObject libraryPresentation(long now){
    JSONArray entries=new JSONArray(),exits=new JSONArray(),manual=new JSONArray();
    entries.put(source(NetworkCatalog.ENTRY,"visual-entry-japan","日本入口（示例）",new String[]{"Entry|日本东京 01（示例）","Entry|日本大阪 03（示例）"},now));
    entries.put(source(NetworkCatalog.ENTRY,"visual-entry-mixed","多地区入口（示例）",new String[]{"Entry|日本 02（示例）","Entry|美国 01（示例）","Entry|未标注节点（示例）"},now));
    exits.put(source(NetworkCatalog.EXIT,"visual-exit-singapore","新加坡出口订阅（示例）",new String[]{"Exit|新加坡 01（示例）"},now));
    // Exercise display-only removal of a duplicate flag; the saved label stays intact.
    exits.put(source(NetworkCatalog.EXIT,"visual-exit-hong-kong","🇭🇰 香港出口订阅（示例）",new String[]{"Exit|🇭🇰 香港 01（示例）"},now));
    manual.put(manualExit("新加坡固定出口（示例）","新加坡","192.0.2.18"));
    manual.put(manualExit("未标注地区出口（示例）","","192.0.2.80"));
    return J.obj("subscriptions",entries,"exitSubscriptions",exits,"exits",manual);
  }

  static JSONObject source(String role,String id,String name,String[] labels,long now){
    JSONArray names=new JSONArray(),details=new JSONArray();
    for(String label:labels){names.put(label);details.put(J.obj("name",label,"type","socks5","server","192.0.2.10",
        "configFingerprint",NativeNetwork.hash(id+"|"+label),"configFingerprintVersion",1));}
    String url="https://network-preview.test/"+id;
    return J.obj("id",id,"role",role,"name",name,"url",url,"urlHash",NativeNetwork.hash(url),"nodes",names,"nodeDetails",details,
        "revision",1,"addressRevision",1,"cacheAddressRevision",1,"stale",false,"updating",false,"lastSuccessAt",now);
  }

  static JSONObject manualExit(String name,String region,String host){
    String id=NetworkCatalog.exitId(J.obj("exitHost",host,"exitPort",1080));
    return J.obj("id",id,"name",name,"region",region,"host",host,"port",1080,"user","","password","","revision",1);
  }

  /** RFC 5737 documentation addresses and local labels; never network evidence. */
  static JSONArray presentation(long now){
    if(now<=0)throw new IllegalArgumentException("A presentation time is required");
    JSONArray rows=new JSONArray();
    for(int slot=0;slot<3;slot++){
      String id="configured-visual-only-"+slot;
      String name=new String[]{"日常会话","长文阅读与文件整理","翻译与写作"}[slot];
      JSONObject row=J.obj("slot",slot,"generation",1,"environmentId",id,"name",name);
      JSONObject config=J.obj("subscriptionUrl","https://network-preview.invalid/entry","subscriptionName","示例入口订阅",
          "entryMode","manual","entry","Entry|日本大阪 03（示例）","exitName","新加坡固定出口（示例）",
          "exitHost","192.0.2.18","exitPort",1080,"exitRegion","示例地区");
      JSONObject running=J.obj("environmentId",id,"generation",1,"mode",slot==1?"external":"internal",
          "entryMode","manual","entry",config.optString("entry"),"subscriptionName","示例入口订阅",
          "exitName",config.optString("exitName"),"exitRegion","示例地区","exitId","visual-exit",
          "subscriptionId","visual-subscription","configurationFingerprint","visual-only-no-core-receipt",
          "verified",true,"scope","synthetic-visual-only","proxy",false);
      JSONObject runtime=J.obj("environmentId",id,"generation",1,"mode",slot==1?"external":"internal",
          "configured",true,"connected",slot<2,"at",now,"ip",slot==0?"192.0.2.18":slot==1?"198.51.100.24":"",
          "entry",config.optString("entry"),"exitId","visual-exit","subscriptionId","visual-subscription",
          "delay",slot==0?128:86,"delayAt",now,"delayEntry",config.optString("entry"),"delayKind","response",
          "route","visual-external-route","delayRoute","visual-external-route","delayHealth",false,
          "syntheticPresentationOnly",true,"actualNetworkEvidence",false);
      if(slot<2)NetworkCatalog.put(runtime,"runningConfiguration",running);
      else{runtime.remove("delayAt");runtime.remove("delay");}
      JSONObject meta=J.obj("available",true,"environmentId",id,"generation",1,"desiredRevision",slot==2?2:1,
          "appliedRevision",1,"pendingReady",true);
      JSONObject item=J.obj("row",row,"config",config,"runtime",runtime,"live",true,"uiMetadata",meta,
          "syntheticPresentationOnly",true,"actualNetworkEvidence",false);
      if(slot==2){
        JSONObject pending=J.obj("entryMode","latency","entry","Entry|日本东京 01（示例）","exitName","香港固定出口（示例）");
        NetworkCatalog.put(item,"pendingNetwork",true);NetworkCatalog.put(item,"pendingAction","apply");NetworkCatalog.put(item,"pendingConfig",pending);
      }
      rows.put(item);
    }
    return rows;
  }

  @Override protected void onDestroy(){if(workspace!=null)workspace.close();super.onDestroy();}
}
