package local.pocketchat;

import android.app.Activity;
import android.content.Intent;
import android.os.*;
import android.util.Log;
import android.widget.*;
import org.json.*;

/** Test-only: actual production screens and components, with local synthetic records. */
public final class UiVisualIntegrationActivity extends Activity {
  NetworkWorkspaceUi workspace;
  SavedFileActions savedActions;
  final Handler handler=new Handler(Looper.getMainLooper());
  @Override public void onCreate(Bundle state){
    super.onCreate(state);String action=getIntent().getStringExtra("visualAction");
    try{seed();}catch(Exception e){Log.e("PocketUiVisual","fixture setup failed",e);finish();return;}
    if("environment-picker".equals(action)||"templates".equals(action)||"zoom".equals(action)||"audit".equals(action)){startActivity(new Intent(this,UiDetailsIntegrationActivity.class).putExtra("detailScene",action));finish();return;}
    if("update".equals(action)){startActivity(new Intent(this,AppUpdateActivity.class));finish();return;}
    if("file-preview".equals(action)){startActivity(new Intent(this,AttachmentPreviewActivity.class).putExtra("uri","content://local.pocketchat.test.upload/image").putExtra("mime","image/png").putExtra("name","界面预览图片.png"));finish();return;}
    if("brand".equals(action)){startActivity(new Intent(this,BrandLaunchActivity.class).putExtra("previewBrand",true));finish();return;}
    if("import".equals(action)){startActivity(new Intent(this,NetworkImportActivity.class));finish();return;}
    if("settings".equals(action)||"appearance".equals(action)||"default-entry".equals(action)||"feedback".equals(action)||"downloads".equals(action)||"delete-file".equals(action)||"share-preview".equals(action)){
      LinearLayout root=DesignUi.screen(this),box=DesignUi.body(this,root,"应用设置",null);
      if("downloads".equals(action)){
        savedActions=new SavedFileActions(this);DesignDownloads.Controller controller=new DesignDownloads.Controller(this,box,0,n->{},savedActions);
        long now=System.currentTimeMillis();JSONArray data=J.arr(
          J.obj("id","visual-active","slot",0,"name","项目资料与界面设计说明.pdf","state","downloading","received",1200000,"total",5000000,"time",now,"updated",now),
          J.obj("id","visual-paused","slot",1,"name","稍后继续的文件.zip","state","paused","received",900000,"total",3000000,"time",now-1000),
          J.obj("id","visual-failed","slot",0,"name","等待重试的文件.pdf","state","failed","reason","连接中断，可检查网络后重试。","time",now-2000),
          J.obj("id","visual-saved","slot",0,"name","已保存的笔记.pdf","state","saved","time",now-3000,"location","Download/元婴期院士/"));controller.apply(data,0,now);
      }else DesignSettingsUi.render(this,box,()->{});
      root.addView(ReferenceUi.nav(this,4,n->{},new Button[5]));setContentView(root);AppAppearance.apply(root);
      if("appearance".equals(action))DesignSettingsUi.appearance(this,()->{});
      if("default-entry".equals(action))DesignSettingsUi.defaultEntry(this,()->{});
      if("feedback".equals(action))FeedbackUi.open(this);
      if("delete-file".equals(action)){savedActions=new SavedFileActions(this);savedActions.confirmDelete(J.obj("name","准备清理的文件.pdf","slot",0));}
      if("share-preview".equals(action))NetworkShareUi.show(this,new NetworkShareCodec.Bundle("布局测试线路",J.obj("name","测试入口","type","socks5","server","127.0.0.1","port",1080),J.obj("name","固定测试出口","type","socks5","server","127.0.0.1","port",1081)));
      return;
    }
    if("environments".equals(action)){startActivity(new Intent(this,WindowHomeActivity.class));finish();return;}
    if("browser".equals(action)||"preferences".equals(action)||"chat".equals(action)){
      Intent target=new Intent(this,MainActivity.class).putExtra("openWindowAction","chat".equals(action)?"native-smoke":"edit");
      startActivity(target);finish();return;
    }
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    LinearLayout root=DesignUi.screen(this);FrameLayout host=new FrameLayout(this);
    root.addView(host,new LinearLayout.LayoutParams(-1,0,1));
    root.addView(ReferenceUi.nav(this,3,n->{if(n==1)startActivity(new Intent(this,WindowHomeActivity.class));},new Button[5]));
    setContentView(root);ReferenceUi.insets(this,root);
    workspace=new NetworkWorkspaceUi(this,host);workspace.show(0);
    workspace.afterRead=()->{
      if("network".equals(action)&&workspace.windows.length()>0){
        JSONObject item=workspace.windows.optJSONObject(0);
        NetworkCatalog.put(item,"config",J.obj("subscriptionUrl","https://example.test/ui-only-subscription","entryMode","manual","entry","Entry|日本大阪 03","exitName","固定测试出口","exitHost","127.0.0.1","exitPort",1080));
        NetworkCatalog.put(item,"runtime",J.obj("mode","internal","configured",true,"connected",false,"at",System.currentTimeMillis()));
        workspace.lastRendered="";workspace.render();
      }
      if("network-menu".equals(action))workspace.networkMore();
      if("subscription-form".equals(action))workspace.subscriptionForm(NetworkCatalog.ENTRY,null,null);
      if("exit-form".equals(action))workspace.exitForm(null);
      if("route-editor".equals(action)&&workspace.windows.length()>0)workspace.editInternal(workspace.windows.optJSONObject(0));
      if("exit-password".equals(action))workspace.exitForm(J.obj("id","synthetic-exit","name","测试出口","host","127.0.0.1","port",1080,"user","fixture","password","Synthetic-exit-7!"),null);
      if("proxy".equals(action))workspace.external(0,true);
      if("entries".equals(action))try{
        JSONObject sub=workspace.catalog.subscriptions().getJSONObject(0);
        JSONArray nodes=sub.getJSONArray("nodes");
        NetworkDraft draft=new NetworkDraft(0,J.obj("subscriptionUrl",sub.getString("url"),"entryMode","random","entryPool",nodes,"entry",nodes.getString(0)),workspace.catalog);
        if("latency".equals(getIntent().getStringExtra("entryMode")))draft.mode="latency";
        workspace.selectEntry(draft,()->{});
      }catch(Exception e){Log.e("PocketUiVisual","entry presentation failed",e);}
      Log.i("PocketUiVisual","ready "+action);
    };
  }
  void seed()throws Exception{
    if(!getPackageName().endsWith(".test"))throw new SecurityException();
    String[] names={"日常会话","资料整理","开发调试","长文阅读与文件整理","翻译与写作","个人收藏","备用环境","项目讨论"};
    ProfileCatalog catalog=ProfileCatalog.get(this);
    for(int slot=0;slot<names.length;slot++){
      catalog.created(slot);Profiles.rename(this,slot,names[slot]);catalog.details(slot,slot<4?"工作":"个人","");
      catalog.favorite(slot,slot==0||slot==4);catalog.browserDisplay(slot,slot==0||slot==3);
      Profiles.context(this,slot).getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external").putBoolean("networkConfigured",false).putBoolean("pageMode",true).putBoolean("environmentInitialized",true).commit();
    }
    android.os.Bundle updateOptions=new android.os.Bundle();updateOptions.putBoolean("autoCheck",false);AppUpdates.call(this,"settings",updateOptions);
    AppSettings.defaultSlot(this,0);AppSettings.put(this,"brandSeen","true");AppSettings.put(this,"updateAutoCheck","false");
    NetworkCatalog library=new NetworkCatalog(this);
    if(library.subscriptions().length()==0){
      JSONObject sub=library.addSubscription("日常线路","https://example.test/ui-only-subscription");
      String fixture="proxies:\n  - {name: '日本大阪 03', type: socks5, server: 127.0.0.1, port: 1080}\n  - {name: '日本东京 01', type: socks5, server: 127.0.0.1, port: 1081}\n  - {name: '香港入口', type: socks5, server: 127.0.0.1, port: 1082}\n";
      library.parsed(sub.getString("id"),J.arr("Entry|日本大阪 03","Entry|日本东京 01","Entry|香港入口"),fixture.getBytes(java.nio.charset.StandardCharsets.UTF_8),System.currentTimeMillis());
    }
  }
  @Override protected void onDestroy(){if(workspace!=null)workspace.close();if(savedActions!=null)savedActions.close();handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
