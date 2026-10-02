package local.pocketchat;
import android.app.*;
import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;

public class HistoryTestActivity extends Activity {
  WebView web;String script;JSONArray checks=new JSONArray();ConversationStore store;interface Result{void done(JSONObject o);}
  void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));}
  @Override public void onCreate(Bundle b){super.onCreate(b);try(InputStream in=getAssets().open("history-driver.js")){script=J.text(in,512*1024);}catch(Exception e){throw new RuntimeException(e);}store=new ConversationStore(this);web=new WebView(this);web.getSettings().setJavaScriptEnabled(true);web.setWebViewClient(new WebViewClient(){boolean started=false;@Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture-history.html"));}catch(Exception e){return MainActivity.blocked();}}@Override public void onPageFinished(WebView v,String u){if(!started){started=true;new Handler().postDelayed(()->begin(),200);}}});setContentView(web);web.loadUrl("https://chatgpt.com/");}
  void call(String action,JSONObject args,Result cb){String key="testResult";String code=script.replace("__ACTION__",JSONObject.quote(action)).replace("__ARG__",args.toString());web.evaluateJavascript("window."+key+"=null;void(Promise.resolve("+code+").then(v=>window."+key+"=v))",r->poll(key,cb,0));}
  void poll(String key,Result cb,int attempts){new Handler().postDelayed(()->web.evaluateJavascript("window."+key,r->{if("null".equals(r)&&attempts<600)poll(key,cb,attempts+1);else cb.done(J.parse(r));}),150);}
  void begin(){call("history-sync",new JSONObject(),r->{JSONArray rows=r.optJSONArray("chats");check("Full pagination reaches 110 conversations",r.optBoolean("complete")&&rows!=null&&rows.length()==110);if(rows!=null)store.merge(rows,true);check("Database has no old 80-item limit",store.list().length()==110);rename();});}
  void rename(){String url="https://chatgpt.com/c/fixture-3";call("history-rename",J.obj("url",url,"title","Renamed by native client"),r->{check("Rename confirmed by web UI",r.optBoolean("ok"));if(r.optBoolean("ok"))store.rename(url,"Renamed by native client");check("Renamed title stored",store.list().toString().contains("Renamed by native client"));call("history-delete",J.obj("url",url,"confirmed",false),denied->{check("Delete requires explicit confirmation",!denied.optBoolean("ok"));call("history-delete",J.obj("url",url,"confirmed",true),deleted->{check("Confirmed delete reaches web UI",deleted.optBoolean("ok"));if(deleted.optBoolean("ok"))store.remove(url);check("Deleted conversation removed locally",store.list().length()==109);call("history-sync",new JSONObject(),again->{check("Sync starts from top after previous scan",again.optBoolean("complete")&&again.optJSONArray("chats")!=null&&again.optJSONArray("chats").length()==109);finishResults();});});});});}
  void finishResults(){try{J.write(new File(getFilesDir(),"history-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}android.widget.TextView v=new android.widget.TextView(this);v.setText(checks.toString());setContentView(v);}
  @Override protected void onDestroy(){web.destroy();super.onDestroy();}
}
