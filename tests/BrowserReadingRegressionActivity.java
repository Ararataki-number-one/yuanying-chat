package local.pocketchat;

import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;

/** Isolated device fixture. Compiling this activity does not execute these checks. */
public class BrowserReadingRegressionActivity extends MainActivity {
  final JSONArray checks=new JSONArray();int attempts;boolean priorDesktop;
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  @Override public void onCreate(Bundle state){priorDesktop=ProfileCatalog.get(this).item(Profiles.slot(this)).optBoolean("desktopSite");ProfileCatalog.get(this).browserDisplay(Profiles.slot(this),true);getSharedPreferences("chat",0).edit().clear().putString("browserEngine","system").putBoolean("networkConfigured",true).putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).commit();super.onCreate(state);handler.postDelayed(this::begin,200);}
  @Override void startNetwork(){session.networkReady=true;session.guard.setBlocked(false);remote.loadUrl(ORIGIN+"c/reading-fixture");}
  @Override WebViewClient remoteClient(){WebViewClient original=session.client();return new WebViewClient(){
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest request){try{return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture-desktop-reading.html"));}catch(Exception e){return blocked();}}
    @Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap b){original.onPageStarted(v,url,b);}
    @Override public void onPageCommitVisible(WebView v,String url){original.onPageCommitVisible(v,url);}
    @Override public void onPageFinished(WebView v,String url){original.onPageFinished(v,url);}
    @Override public void onScaleChanged(WebView v,float before,float after){original.onScaleChanged(v,before,after);}
  };}
  void begin(){if(!session.reading.ready){if(attempts++<50){handler.postDelayed(this::begin,200);return;}check("Desktop fixture becomes visible",false);write();return;}
    GeckoWebView same=remote;long epoch=session.navigationEpoch;check("New profile uses fit scale",session.reading.choice()==1);session.reading.choose(1.5f);handler.postDelayed(()->{
      check("Zoom uses the same live document and WebView",remote==same&&epoch==session.navigationEpoch);
      check("Zoom choice is profile local",Math.abs(prefs.getFloat(BrowserReadingPolicy.ZOOM_KEY,0)-1.5f)<.01);
      keyboardVisible=true;updateReadingLayout();check("Typing temporarily hides app navigation",hub.bar.getVisibility()==android.view.View.GONE);
      keyboardVisible=false;updateReadingLayout();check("Navigation returns after keyboard closes",hub.bar.getVisibility()==android.view.View.VISIBLE);
      remote.evaluateJavascript("JSON.stringify({draft:document.querySelector('textarea').value,model:document.querySelector('header button').textContent,code:document.querySelector('code').textContent,title:document.title,paragraphs:document.querySelectorAll('#paragraphs p').length})",raw->{JSONObject value=J.parse(raw);try{value=new JSONObject((String)new JSONTokener(raw).nextValue());}catch(Exception ignored){}check("Draft and official style controls are unchanged",value.optString("draft").equals("Unsent draft stays here")&&value.optString("model").equals("Original model")&&value.optString("title").equals("Desktop reading fixture"));check("Long reply and horizontal code remain intact",value.optInt("paragraphs")==40&&value.optString("code").contains("xxx"));session.reading.choose(1);write();});
    },600);
  }
  void write(){try{J.write(new File(getFilesDir(),"browser-reading-regression.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}}
  @Override protected void onDestroy(){ProfileCatalog.get(this).browserDisplay(Profiles.slot(this),priorDesktop);super.onDestroy();}
}
