package local.pocketchat;

import android.os.*;
import android.view.*;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.util.function.*;

abstract class WebReplyFixtureActivity extends MainActivity {
  final JSONArray checks=new JSONArray();
  void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));}
  void write(String name,JSONObject data){try{J.write(new File(getFilesDir(),name),data.toString(2));}catch(Exception e){throw new RuntimeException(e);}}
  void report(String name){write(name,J.obj("checks",checks));}
  @Override void startNetwork(){session.networkReady=true;session.offline=false;session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.guard.setBlocked(false);String url=session.pending==null?ORIGIN:session.resumeUrl();remote.loadUrl(url);}
  @Override WebViewClient remoteClient(){WebViewClient real=super.remoteClient();return new WebViewClient(){
    @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{if(!MainActivity.chatUrl(r.getUrl().toString()))return blocked();return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture-web-reply.html"));}catch(Exception e){return blocked();}}
    @Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap icon){real.onPageStarted(v,url,icon);}
    @Override public void onPageFinished(WebView v,String url){real.onPageFinished(v,url);}
  };}
  @Override public void onCreate(Bundle b){
    if(!getPackageName().endsWith(".test"))throw new IllegalStateException("Isolated test package required");
    if(!getIntent().getBooleanExtra("restore",false)){
      getSharedPreferences("chat",0).edit().clear().putBoolean("networkConfigured",true).putString("networkMode","external").putBoolean("requireExternalVpn",false).putBoolean("pageMode",true).putBoolean("webNotificationAsked",true).commit();
      getSystemService(android.app.NotificationManager.class).cancelAll();
    }
    super.onCreate(b);handler.postDelayed(()->awaitReady(0),700);
  }
  void awaitReady(int count){remote.evaluateJavascript("!!window.fixture&&!!window.__pocketWebReplyObserver",r->{if("true".equals(r)){check("Origin-scoped observer installed on Android WebView",session.webObserver.supported);begin();}else if(count<30)handler.postDelayed(()->awaitReady(count+1),200);else{check("Observer installation timed out",false);report("web-reply-results.json");}});}
  abstract void begin();
  void js(String code,Runnable next){remote.evaluateJavascript(code,r->handler.postDelayed(next,80));}
  void waitFor(String name,BooleanSupplier condition,int remaining,Runnable next){if(condition.getAsBoolean()){check(name,true);next.run();}else if(remaining>0)handler.postDelayed(()->waitFor(name,condition,remaining-1,next),200);else{check(name,false);next.run();}}
  void tap(String selector,Runnable next){remote.evaluateJavascript("(()=>{const e=document.querySelector("+JSONObject.quote(selector)+");if(!e)return {};e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2,width:innerWidth};})()",raw->{JSONObject p=J.parse(raw);if(!p.has("width")){check("Tap target exists: "+selector,false);next.run();return;}float scale=remote.getWidth()/(float)p.optDouble("width"),x=(float)p.optDouble("x")*scale,y=(float)p.optDouble("y")*scale;long time=SystemClock.uptimeMillis();MotionEvent down=MotionEvent.obtain(time,time,MotionEvent.ACTION_DOWN,x,y,0);remote.dispatchTouchEvent(down);down.recycle();handler.postDelayed(()->{MotionEvent up=MotionEvent.obtain(time,SystemClock.uptimeMillis(),MotionEvent.ACTION_UP,x,y,0);remote.dispatchTouchEvent(up);up.recycle();handler.postDelayed(next,200);},60);});}
  void compose(String text,Runnable next){js("document.querySelector('textarea').value="+JSONObject.quote(text),next);}
  long completionPost(){for(android.service.notification.StatusBarNotification n:getSystemService(android.app.NotificationManager.class).getActiveNotifications())if(n.getId()==4102)return n.getPostTime();return 0;}
  void noResend(String name,int expected,Runnable next){remote.evaluateJavascript("window.sendCount",r->{check(name,Integer.toString(expected).equals(r));next.run();});}
  void reset(String options,Runnable next){if(session.pending!=null)session.abandonWait();js("fixture.reset("+options+")",next);}
}
