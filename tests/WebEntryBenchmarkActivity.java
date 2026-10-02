package local.pocketchat;

import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Local fixture: essential composer appears before one irrelevant image finishes. */
public class WebEntryBenchmarkActivity extends MainActivity {
  long started=SystemClock.elapsedRealtime(),firstVisible=0,finished=0,domReady=0;int attempt=0;boolean written=false;
  @Override void startNetwork(){session.offline=false;session.networkReady=true;session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.guard.setBlocked(false);session.navigate(ORIGIN+"c/entry-fixture","正在加载测试页面…");}
  @Override WebViewClient remoteClient(){WebViewClient real=super.remoteClient();return new WebViewClient(){
    @Override public void onPageStarted(WebView v,String u,android.graphics.Bitmap i){real.onPageStarted(v,u,i);}
    @Override public void onPageCommitVisible(WebView v,String u){firstVisible=SystemClock.elapsedRealtime();real.onPageCommitVisible(v,u);}
    @Override public void onPageFinished(WebView v,String u){finished=SystemClock.elapsedRealtime();real.onPageFinished(v,u);}
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{
      if(r.getUrl().getPath().endsWith("slow.png")){Thread.sleep(6000);return new WebResourceResponse("image/png",null,new ByteArrayInputStream(new byte[0]));}
      Thread.sleep(350);String html=asset("fixture.html");
      String content="<div id=\"turns\"><article data-message-author-role=\"user\" data-message-id=\"entry-user\">local startup fixture</article></div>";
      html=html.replace("<div id=\"turns\"></div>",content);
      if(getIntent().getBooleanExtra("modernMessages",false))html=html.replace("data-message-author-role=\"user\"","data-turn=\"user\"");
      html+="<img style=\"display:none\" src=\"https://chatgpt.com/slow.png\"><script>const input=document.querySelector('textarea');input.style.display='none';setTimeout(()=>{input.style.display='';window.fixtureDomReady=performance.now();},"+getIntent().getIntExtra("composerDelay",900)+");</script>";
      return new WebResourceResponse("text/html","UTF-8",new ByteArrayInputStream(html.getBytes(StandardCharsets.UTF_8)));
    }catch(Exception e){return blocked();}}
  };}
  @Override public void onCreate(Bundle b){if(!getPackageName().endsWith(".test"))throw new IllegalStateException("Isolated fixture required");getSharedPreferences("chat",0).edit().clear().putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).commit();super.onCreate(b);handler.postDelayed(()->awaitReady(),80);}
  void awaitReady(){if(!session.navigating&&session.entries.length()==1&&session.state.optBoolean("composer")){long usable=SystemClock.elapsedRealtime();written=true;remote.evaluateJavascript("({domReady:window.fixtureDomReady||0,now:performance.now(),sends:window.sendCount||0})",r->{JSONObject p=J.parse(r);JSONArray checks=J.arr(
      J.obj("name","Composer and conversation both ready","pass",session.state.optBoolean("composer")&&session.entries.length()==1),
      J.obj("name","Entry never sends a message","pass",p.optInt("sends")==0),
      J.obj("name","Page is usable before unrelated image finishes","pass",finished==0),
      J.obj("name","Entry fixture completes","pass",usable-started<8000));
      try{J.write(new File(getFilesDir(),"web-entry-benchmark.json"),J.obj("variant",getIntent().getStringExtra("variant"),"appToUsableMs",usable-started,"firstVisibleMs",firstVisible==0?-1:firstVisible-started,"postComposerWaitMs",Math.max(0,p.optDouble("now")-p.optDouble("domReady")),"fullLoadFinished",finished>0,"entries",session.entries.length(),"checks",checks).toString(2));}catch(Exception ignored){}
    });return;}
    if(attempt++<200)handler.postDelayed(()->awaitReady(),80);else try{J.write(new File(getFilesDir(),"web-entry-benchmark.json"),J.obj("error","entry timed out","status",session.status,"navigating",session.navigating,"state",session.state,"entries",session.entries.length(),"url",session.web.getUrl(),"inFlight",session.inFlight,"offline",session.offline,"networkReady",session.networkReady).toString(2));}catch(Exception ignored){}
  }
}
