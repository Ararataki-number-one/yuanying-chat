package local.pocketchat;
import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class TestActivity extends MainActivity {
  JSONArray checks=new JSONArray();int attempts=0;
  @Override void startNetwork(){networkReady=true;session.networkReady=true;session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.guard.setBlocked(false);remote.loadUrl(ORIGIN);}
  @Override WebViewClient remoteClient(){return new WebViewClient(){
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{if("chatgpt.com".equals(r.getUrl().getHost()))return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture.html"));}catch(Exception ignored){}return blocked();}
  };}
  @Override public void onCreate(Bundle b){setRequestedOrientation(1);boolean restore=getIntent().getBooleanExtra("restore",false);if(!restore)deleteDatabase("deliveries.db");if(!restore)getSharedPreferences("chat",MODE_PRIVATE).edit().clear().commit();super.onCreate(b);reader.setWebChromeClient(new WebChromeClient(){@Override public boolean onConsoleMessage(ConsoleMessage m){android.util.Log.i("PocketReader",m.message()+" @"+m.sourceId()+":"+m.lineNumber());return true;}});if(restore){check("Transcript restored after process restart",entries.length()==2);check("Draft restored after process restart",input.getText().toString().equals("恢复测试草稿"));check("Pending attempt restored after process restart",pending!=null);handler.postDelayed(()->{remote.evaluateJavascript("window.sendCount",n->{check("Restart never automatically resubmits","0".equals(n));writeResults("restore-results.json");status("重启恢复测试完成");});},2000);}else handler.postDelayed(()->begin(),1800);}
  void writeResults(String path){try{FileOutputStream out=openFileOutput(path,MODE_PRIVATE);out.write(fields("android",Build.VERSION.RELEASE,"checks",checks).toString(2).getBytes(StandardCharsets.UTF_8));out.close();}catch(Exception ignored){}android.util.Log.i("PocketChatTest","DONE "+checks.toString());}
  void check(String name,boolean pass){checks.put(fields("name",name,"pass",pass));android.util.Log.i("PocketChatTest",name+":"+pass);}
  void begin(){runDriver("inspect",new JSONObject(),s->{if(!s.optBoolean("composer")&&attempts++<20){handler.postDelayed(()->begin(),500);return;}
    check("Android WebView loads fixture",s.optBoolean("composer"));check("Reads actual model and effort",s.optString("model").equals("Thinking")&&s.optString("effort").equals("Extra High"));
    check("Rejects lookalike origin",!chatUrl("https://chatgpt.com.attacker.example/"));check("Rejects plaintext origin",!chatUrl("http://chatgpt.com/"));check("Rejects nonstandard port",!chatUrl("https://chatgpt.com:444/"));
    check("Validates app proxy address",validProxy("http://127.0.0.1:17897"));check("Rejects proxy credential in URL",!validProxy("http://user:password@host:80"));
    remote.evaluateJavascript("document.querySelector('textarea').value='网页保留草稿'",r->{input.setText("不能覆盖已有草稿");sendPrompt();handler.postDelayed(()->draftTest(),900);});
  });}
  void draftTest(){remote.evaluateJavascript("JSON.stringify({draft:document.querySelector('textarea').value,sends:window.sendCount})",r->{try{JSONObject v=new JSONObject((String)new JSONTokener(r).nextValue());check("Preserves existing web draft",v.optString("draft").equals("网页保留草稿"));check("Does not submit conflicting draft",v.optInt("sends")==0);}catch(Exception e){check("Draft test decoded",false);}
    remote.evaluateJavascript("document.querySelector('textarea').value=''",unused->{input.setText("中文消息\n\n第二段：x² + y² = 1\n  保留缩进");sendPrompt();sendPrompt();handler.postDelayed(()->finishTest(),7000);});
  });}
  void finishTest(){remote.evaluateJavascript("JSON.stringify({sends:window.sendCount,prompt:document.querySelector('[data-message-author-role=user]')?.textContent,bridge:typeof Android})",r->{try{JSONObject v=new JSONObject((String)new JSONTokener(r).nextValue());check("Double tap submits exactly once",v.optInt("sends")==1);check("Unicode multiline preserved",v.optString("prompt").equals("中文消息\n\n第二段：x² + y² = 1\n  保留缩进"));check("Remote page has no native JS bridge",v.optString("bridge").equals("undefined"));}catch(Exception e){check("Submission test decoded",false);}
    check("Reply completion clears pending",pending==null);check("Local transcript persisted",prefs.getString("transcript","").contains("安卓运行测试成功"));check("Confirmed prompt clears native composer",input.getText().length()==0);
    reader.evaluateJavascript("JSON.stringify(window.chat.debug())",d->{try{JSONObject v=new JSONObject((String)new JSONTokener(d).nextValue());check("Custom reader shows both turns",v.optInt("webCount")==2);check("Formula rendered by KaTeX",v.optInt("math")>=1);check("Code block rendered",v.optInt("code")==1);}catch(Exception e){check("Reader test decoded",false);}
      status("离线自动测试完成 · 不代表账号接入成功");writeResults("test-results.json");
      prefs.edit().putString("draft","恢复测试草稿").putString("pending",fields("prompt","未确认的提问","beforeUserKeys",new JSONArray(),"expectedUrl",ORIGIN,"export",true,"attempted",true).toString()).commit();
    });
  });}
}
