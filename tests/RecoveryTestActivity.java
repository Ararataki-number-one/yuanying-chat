package local.pocketchat;
import android.content.*;
import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;

public class RecoveryTestActivity extends MainActivity {
 JSONArray checks=new JSONArray();FakeNetwork fake;int callbacks=0;
 static class FakeNetwork extends NativeNetwork {
   volatile int starts=0;volatile boolean alive=false,fail=false;volatile long delay=150;
   FakeNetwork(Context c){super(c);}
   @Override boolean coreAlive(){return alive;}
   @Override void startNow()throws Exception{starts++;Thread.sleep(delay);if(fail)throw new IOException("Fixture proxy failure");alive=true;ready=true;message="Fixture proxy ready";}
   @Override void stopNow(){alive=false;ready=false;}
   @Override void health(){}
   @Override int probe(String name){return alive?25:-1;}
   @Override String verifyExit(){return "fixture-fixed-exit";}
   @Override String proxy(){return "http://127.0.0.1:9";}
 }
 void check(String n,boolean value){checks.put(J.obj("name",n,"pass",value));}
 @Override public void onCreate(Bundle b){getSharedPreferences("chat",0).edit().clear().putBoolean("networkConfigured",true).putString("networkMode","internal").commit();fake=new FakeNetwork(this);try{java.lang.reflect.Field f=NativeNetwork.class.getDeclaredField("instance");f.setAccessible(true);f.set(null,fake);}catch(Exception e){throw new RuntimeException(e);}super.onCreate(b);setRequestedOrientation(1);handler.postDelayed(()->begin(),3500);}
 @Override WebViewClient remoteClient(){return new WebViewClient(){@Override public void onPageStarted(WebView v,String u,android.graphics.Bitmap icon){session.client().onPageStarted(v,u,icon);}@Override public void onPageFinished(WebView v,String u){session.client().onPageFinished(v,u);}@Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture.html"));}catch(Exception e){return blocked();}}};}
 void begin(){check("Initial proxy handshake completes",session.networkReady&&!session.connecting);input.setText("keep this draft through reconnect");session.attachments.put(J.obj("name","retained.pdf","state","unknown","uri","content://fixture/retained.pdf"));attachments.persist();session.connectivity(false);int starts=fake.starts;check("Offline blocks network loads",remote.getSettings().getBlockNetworkLoads()&&!session.networkReady);check("Offline retains draft and file",input.getText().length()>0&&session.attachments.length()==1);fake.stopNow();session.connectivity(true);session.scheduleRecovery();session.scheduleRecovery();handler.postDelayed(()->{check("Duplicate retry requests coalesce",fake.starts==starts+1);check("Core restored before webpage loads",session.networkReady&&!session.connecting&&!remote.getSettings().getBlockNetworkLoads());check("Recovery preserves input and attachment",input.getText().toString().equals("keep this draft through reconnect")&&session.attachments.length()==1);coreFailure();},5500);}
 void coreFailure(){int before=fake.starts;fake.stopNow();session.networkStatus("Fixture core exited",false);handler.postDelayed(()->{check("Core exit automatically reconnects",fake.starts==before+1&&session.networkReady);singleFlight();},5000);}
 void singleFlight(){fake.stopNow();fake.delay=700;int before=fake.starts;NativeNetwork.Callback cb=(ok,m)->{if(ok)callbacks++;};fake.start(cb);fake.start(cb);fake.start(cb);handler.postDelayed(()->{check("Concurrent native starts run once",fake.starts==before+1);check("All start callers receive result",callbacks==3);stale();},1600);}
 void stale(){fake.stopNow();fake.delay=1200;session.networkReady=false;session.openConnection(false,false);handler.postDelayed(()->session.connectivity(false),100);handler.postDelayed(()->{check("Late startup cannot reopen network after disconnect",session.offline&&!session.networkReady&&remote.getSettings().getBlockNetworkLoads());session.connectivity(true);handler.postDelayed(()->guards(),4000);},1700);}
 void guards(){session.recoveryToken++;session.recoveryScheduled=false;session.recoveryAttempt=5;session.scheduleRecovery();check("Automatic retries stop at five",!session.recoveryScheduled&&session.status.contains("自动重连暂未成功"));check("Backoff increases with cap",ChatSession.retryDelay(0)==1000&&ChatSession.retryDelay(1)==2000&&ChatSession.retryDelay(4)==20000&&ChatSession.retryDelay(12)==20000);session.recoveryAttempt=0;session.finishNavigation("Fixture login required",false);check("Login errors do not create reload loops",session.manualAttention&&!session.recoveryScheduled);session.manualAttention=false;fake.recoveryBlocked=true;session.scheduleRecovery();check("Exit mismatch requires attention without route fallback",session.manualAttention&&!session.recoveryScheduled);fake.recoveryBlocked=false;session.manualAttention=false;session.pending=J.obj("expectedUrl",ORIGIN,"confirmedUrl",ORIGIN+"c/confirmed");check("Pending recovery targets confirmed conversation",session.resumeUrl().equals(ORIGIN+"c/confirmed"));session.pending=null;remote.evaluateJavascript("window.sendCount",r->{check("All recovery paths never submit a message","0".equals(r));write();});}
 void write(){try{J.write(new File(getFilesDir(),"recovery-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}}
}
