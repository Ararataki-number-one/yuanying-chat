package local.pocketchat;
import android.os.*;
import android.webkit.*;
import org.json.*;
import java.io.*;

public class BackgroundTestActivity extends MainActivity {
  boolean armed=false,reported=false,sawScreenOff=false,wasServiceRunning=false;long deadline;
  final ChatSession.Observer watcher=()->{if(armed&&session.pending==null&&!reported){reported=true;handler.postDelayed(()->report(),1200);}};
  @Override void startNetwork(){networkReady=true;session.networkReady=true;session.prefs.edit().putBoolean("requireExternalVpn",false).commit();session.guard.setBlocked(false);remote.loadUrl(ORIGIN);}
  @Override WebViewClient remoteClient(){return new WebViewClient(){@Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){try{return new WebResourceResponse("text/html","UTF-8",getAssets().open("fixture.html"));}catch(Exception e){return blocked();}}};}
  @Override public void onCreate(Bundle b){if(!getPackageName().endsWith(".test"))throw new IllegalStateException("Test package required");getSharedPreferences("chat",0).edit().clear().putLong("testStartedAt",System.currentTimeMillis()).commit();getSystemService(android.app.NotificationManager.class).cancelAll();super.onCreate(b);session.add(watcher);handler.postDelayed(()->beginBackground(),1800);}
  void write(String file,JSONObject data){try{J.write(new File(getFilesDir(),file),data.toString(2));}catch(Exception ignored){}}
  void beginBackground(){runDriver("inspect",new JSONObject(),s->{if(!s.optBoolean("composer")){handler.postDelayed(()->beginBackground(),500);return;}remote.evaluateJavascript("window.replyDelay=18000",r->{input.setText("Background notification test");sendPrompt();deadline=System.currentTimeMillis()+12000;waitForService();});});}
  void waitForService(){if(session.pending!=null&&ChatService.running){armed=true;wasServiceRunning=true;write("background-stage.json",J.obj("stage","waiting","foregroundService",true,"destroyActivity",getIntent().getBooleanExtra("destroy",false)));if(getIntent().getBooleanExtra("destroy",false)){finish();return;}moveTaskToBack(true);watchScreen();handler.postDelayed(()->{if(!reported){reported=true;report();}},35000);return;}if(System.currentTimeMillis()<deadline)handler.postDelayed(()->waitForService(),100);else write("background-result.json",J.obj("pass",false,"reason","Service did not start"));}
  void watchScreen(){if(!((PowerManager)getSystemService(POWER_SERVICE)).isInteractive())sawScreenOff=true;if(session.pending!=null)handler.postDelayed(()->watchScreen(),300);}
  void report(){boolean notification=false;for(android.service.notification.StatusBarNotification n:getSystemService(android.app.NotificationManager.class).getActiveNotifications())if(n.getId()==4102&&n.getPostTime()>=prefs.getLong("testStartedAt",0))notification=true;final boolean notified=notification;remote.evaluateJavascript("window.sendCount",r->{JSONObject result=J.obj("pass",wasServiceRunning&&!session.uiVisible&&session.pending==null&&notified&&"1".equals(r),"serviceStarted",wasServiceRunning,"screenOffObserved",sawScreenOff,"activityInBackground",!session.uiVisible,"pendingCleared",session.pending==null,"completionNotification",notified,"serviceStopped",!ChatService.running,"submittedOnce","1".equals(r),"replyPersisted",prefs.getString("transcript","").contains("安卓运行测试成功"));write("background-result.json",result);});}
}
