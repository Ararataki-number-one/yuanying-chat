package local.pocketchat;
import android.os.Bundle;
import android.content.Intent;
import org.json.*;
import java.io.File;

public class NotificationTargetTestActivity extends ContinuityFixtureActivity {
  String expected;
  @Override public void onCreate(Bundle b){expected=getIntent().getStringExtra("openConversation");if(getIntent().getBooleanExtra("cold",false))getSharedPreferences("chat",0).edit().putString("conversation",ORIGIN+"c/two").putString("url",ORIGIN+"c/two").commit();super.onCreate(b);observe(0);}
  @Override protected void onNewIntent(Intent i){expected=i.getStringExtra("openConversation");super.onNewIntent(i);observe(0);}
  void observe(int count){if(MainActivity.chatUrl(expected)&&WebReplyObserver.same(expected,remote.getUrl())&&!session.navigating){JSONArray checks=J.arr(J.obj("name","Notification opens requested conversation","pass",WebReplyObserver.same(expected,session.conversation)),J.obj("name","Notification target contains actual requested messages","pass",session.entries.length()==2&&session.entries.optJSONObject(0).optString("text").contains(android.net.Uri.parse(expected).getLastPathSegment())));try{J.write(new File(getFilesDir(),"notification-target-results.json"),J.obj("checks",checks).toString(2));}catch(Exception ignored){}return;}if(count<80)handler.postDelayed(()->observe(count+1),100);else try{J.write(new File(getFilesDir(),"notification-target-results.json"),J.obj("error","notification target timeout").toString());}catch(Exception ignored){}}
}
