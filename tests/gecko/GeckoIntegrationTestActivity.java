package local.pocketchat;

import android.app.Activity;
import android.content.*;
import android.os.*;
import android.util.Log;
import android.webkit.WebView;
import android.widget.*;
import org.json.*;

/** Test-only controlled HTTP exception; this class and manifest are absent from release. */
public class GeckoIntegrationTestActivity extends Activity {
  ChatSession session;int slot;long run;String action;
  @Override protected void attachBaseContext(Context context){super.attachBaseContext(new ProfileContext(context,Profiles.processSlot()));}
  static final class FixtureView extends GeckoWebView {
    FixtureView(Context context,ChatSession owner){super(context,owner);}
    @Override protected boolean allowedUrl(String target){
      return target.startsWith("http://127.0.0.1:8765/")||target.startsWith("http://remote-probe.invalid:8765/")||super.allowedUrl(target);
    }
  }
  @Override public void onCreate(Bundle state){
    super.onCreate(state);slot=Profiles.slot(this);
    getSharedPreferences("chat",0).edit().putString("browserEngine","gecko").putString("networkMode","external")
      .putString("proxy",(slot==0?"socks":"http")+"://127.0.0.1:"+(1080+slot)).putBoolean("requireExternalVpn",false)
      .putBoolean("networkConfigured",false).putBoolean("pageMode",true).commit();
    ChatSession.browserFactory=FixtureView::new;session=ChatSession.get(this);
    session.guard.setBlocked(false);session.networkReady=true;session.foreground(true);
    LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setFitsSystemWindows(true);
    TextView label=new TextView(this);label.setText("正式应用内核回归 · 环境 "+(slot+1));label.setTextSize(16);root.addView(label);
    if(session.web.getParent() instanceof android.view.ViewGroup)((android.view.ViewGroup)session.web.getParent()).removeView(session.web);
    root.addView(session.web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);command(getIntent());
  }
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);command(intent);}
  void command(Intent intent){
    action=intent.getStringExtra("fixtureAction");if(action==null)return;long serial=++run;
    waitReady(serial);
  }
  void waitReady(long serial){
    if(serial!=run)return;GeckoWebView web=(GeckoWebView)session.web;
    if(web.failed){event("error",J.obj("error","Gecko startup failed"));return;}
    if("switchGecko".equals(action)&&!web.enabled){web.useEngine(true);action="read";}
    if(!web.ready){session.handler.postDelayed(()->waitReady(serial),200);return;}
    if("switchSystem".equals(action)){web.useEngine(false);event("engineSwitch",J.obj("gecko",web.enabled));return;}
    if("switchGecko".equals(action)){web.useEngine(true);action="read";}
    if("clear".equals(action))web.runtime.getStorageController().clearDataForSessionContext("environment-"+slot);
    if("block".equals(action))session.guard.setBlocked(true);
    if("disableExtension".equals(action)){
      web.runtime.getWebExtensionController().disable(web.extension,1).accept(value->{web.current.loadUri("http://127.0.0.1:8765/fixture?context="+(slot+1)+"&action=read");session.handler.postDelayed(()->event("bootstrapCheck",J.obj("navigationFailed",session.navigationFailed)),5000);},error->event("error",J.obj("error","disable failed")));return;
    }
    String target="http://127.0.0.1:8765/fixture?context="+(slot+1)+"&action="+action;
    if("popup".equals(action))target="http://127.0.0.1:8765/popup-main";
    web.loadUrl(target);session.handler.postDelayed(()->poll(serial),500);
  }
  void poll(long serial){
    if(serial!=run)return;
    if("block".equals(action)){event("blocked",J.obj("guard",session.guard.allowed(),"route",((GeckoWebView)session.web).route("http://127.0.0.1:8765/fixture")));return;}
    session.web.evaluateJavascript("(()=>{const text=document.getElementById('result')?.textContent;if(!text||text==='测试中…')return null;try{return JSON.parse(text)}catch{return null}})()",raw->{
      if(serial!=run)return;JSONObject result=J.parse(raw);
      if(result.length()>0){event("fixture",result);return;}
      if(session.navigationFailed)event("loadError",J.obj("failed",true));
      else session.handler.postDelayed(()->poll(serial),300);
    });
  }
  void event(String kind,JSONObject result){Log.i("PocketGeckoIntegration",J.obj("kind",kind,"result",result,"nativeContext","environment-"+(slot+1),"processSlot",slot).toString());}
  @Override protected void onDestroy(){run++;if(session!=null)session.foreground(false);super.onDestroy();}
}
