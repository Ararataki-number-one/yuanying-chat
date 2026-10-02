package local.pocketchat;
import android.os.*;
import android.webkit.*;
import android.view.View;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class LoadingTestActivity extends MainActivity {
  JSONArray checks=new JSONArray();
  void check(String title,boolean ok){checks.put(J.obj("name",title,"pass",ok));}
  @Override void startNetwork(){networkReady=true;session.networkReady=true;session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.guard.setBlocked(false);session.navigate(ORIGIN,"正在准备新对话…");}
  @Override WebViewClient remoteClient(){WebViewClient original=session.client();return new WebViewClient(){
    @Override public void onPageStarted(WebView v,String u,android.graphics.Bitmap i){original.onPageStarted(v,u,i);}
    @Override public void onPageFinished(WebView v,String u){original.onPageFinished(v,u);}
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{String path=r.getUrl().getPath();if(path.contains("slow"))Thread.sleep(4000);else if(path.contains("target"))Thread.sleep(1200);String html=asset("fixture.html");if(path.contains("/c/"))html=html.replace("<div id=\"turns\"></div>","<div id=\"turns\"><article data-message-author-role=\"user\" data-message-id=\"target-user\">"+path+"</article></div>");return new WebResourceResponse("text/html","UTF-8",new ByteArrayInputStream(html.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){return blocked();}}
  };}
  @Override public void onCreate(Bundle b){getSharedPreferences("chat",0).edit().clear().commit();super.onCreate(b);handler.postDelayed(()->begin(),5000);}
  void begin(){check("Initial loading clears when ready",!session.navigating);switchConversation(ORIGIN+"c/slow");check("Conversation tap immediately starts animation",session.navigating&&loading.cover.getVisibility()==View.VISIBLE);check("Draft editable but send disabled while switching",input.isEnabled()&&!send.isEnabled());handler.postDelayed(()->{switchConversation(ORIGIN+"c/target");handler.postDelayed(()->loaded(),7500);},250);}
  void loaded(){android.util.Log.i("PocketLoadingTest",session.conversation+" "+session.entries);check("Newest conversation wins after rapid switches",session.conversation.endsWith("/c/target")&&session.entries.length()>0&&session.entries.optJSONObject(0).optString("text").contains("/c/target"));check("Animation ends after target content",!session.navigating&&loading.cover.getVisibility()==View.GONE);check("Composer accepts draft while empty send is disabled",input.isEnabled()&&!send.isEnabled());loading.task("正在同步历史对话…");check("Async operations show spinner dialog",loading.taskDialog!=null&&loading.taskDialog.isShowing());loading.dismissTask();check("Completed operation dismisses dialog",loading.taskDialog==null);session.beginNavigation(ORIGIN,"正在加载…");session.finishNavigation("连接失败，请重试");check("Failure stops spinner and offers retry",!session.navigating&&session.navigationFailed&&loading.wheel.getVisibility()==View.GONE&&loading.retry.getVisibility()==View.VISIBLE);session.navigate(ORIGIN,"正在重新加载…");handler.postDelayed(()->{check("Retry recovers and dismisses error",!session.navigating&&!session.navigationFailed&&loading.cover.getVisibility()==View.GONE);try{J.write(new File(getFilesDir(),"loading-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}},5000);}
}

