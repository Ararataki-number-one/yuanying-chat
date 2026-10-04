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
  final Handler handler=new Handler(Looper.getMainLooper());
  @Override public void onCreate(Bundle state){
    super.onCreate(state);String action=getIntent().getStringExtra("visualAction");
    try{seed();}catch(Exception e){Log.e("PocketUiVisual","fixture setup failed",e);finish();return;}
    if("environments".equals(action)){startActivity(new Intent(this,WindowHomeActivity.class));finish();return;}
    if("browser".equals(action)||"chat".equals(action)){
      Intent target=new Intent(this,MainActivity.class).putExtra("openWindowAction","browser".equals(action)?"edit":"native-smoke");
      startActivity(target);finish();return;
    }
    if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
    LinearLayout root=DesignUi.screen(this);FrameLayout host=new FrameLayout(this);
    root.addView(host,new LinearLayout.LayoutParams(-1,0,1));
    root.addView(ReferenceUi.nav(this,3,n->{if(n==1)startActivity(new Intent(this,WindowHomeActivity.class));},new Button[5]));
    setContentView(root);ReferenceUi.insets(this,root);
    workspace=new NetworkWorkspaceUi(this,host);workspace.show(0);
    workspace.afterRead=()->{
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
      Profiles.context(this,slot).getSharedPreferences("chat",0).edit().putString("browserEngine","system").putString("networkMode","external").putBoolean("networkConfigured",false).putBoolean("pageMode",true).putBoolean("environmentInitialized",true).commit();
    }
    AppSettings.defaultSlot(this,0);AppSettings.put(this,"brandSeen","true");AppSettings.put(this,"updateAutoCheck","false");
    NetworkCatalog library=new NetworkCatalog(this);
    if(library.subscriptions().length()==0){
      JSONObject sub=library.addSubscription("日常线路","https://example.test/ui-only-subscription");
      String fixture="proxies:\n  - {name: '日本大阪 03', type: socks5, server: 127.0.0.1, port: 1080}\n  - {name: '日本东京 01', type: socks5, server: 127.0.0.1, port: 1081}\n  - {name: '香港入口', type: socks5, server: 127.0.0.1, port: 1082}\n";
      library.parsed(sub.getString("id"),J.arr("Entry|日本大阪 03","Entry|日本东京 01","Entry|香港入口"),fixture.getBytes(java.nio.charset.StandardCharsets.UTF_8),System.currentTimeMillis());
    }
  }
  @Override protected void onDestroy(){if(workspace!=null)workspace.close();handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
