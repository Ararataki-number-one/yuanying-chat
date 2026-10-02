package local.pocketchat;
import android.app.*;
import android.os.*;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

public class DevStatusActivity extends Activity {
  @Override public void onCreate(Bundle b){super.onCreate(b);JSONObject data=new JSONObject();try{ChatSession session=ChatSession.peek();String kind=getIntent().getStringExtra("kind");if("network".equals(kind)){NativeNetwork n=NativeNetwork.get(this);byte[] baseline=new SecretStore(this).get("exit-baseline");JSONObject saved=baseline==null?new JSONObject():new JSONObject(new String(baseline,StandardCharsets.UTF_8));data=J.obj("nativeCoreRunning",n.process!=null&&n.process.isAlive(),"networkReady",n.ready,"exitMatchesSavedBaseline",!n.exitIp.isEmpty()&&n.exitIp.equals(saved.optString("ip")),"entryCount",n.totalEntries,"testedCount",n.results.length(),"healthyChains",countHealthy(n.results),"appLoopbackProxy",n.proxy().startsWith("http://127.0.0.1:"),"selectedEntryVerified",!n.currentEntry.isEmpty(),"webSessionReady",session!=null&&session.state.optBoolean("composer"),"conversationCount",new ConversationStore(this).list().length(),"source","android-native-core");}
    else{android.content.SharedPreferences p=getSharedPreferences("chat",0);boolean notified=false;for(android.service.notification.StatusBarNotification n:getSystemService(NotificationManager.class).getActiveNotifications())if(n.getId()==4102&&n.getPostTime()>=p.getLong("testStartedAt",0))notified=true;data=J.obj("pendingCleared",!p.contains("pending"),"replyPersisted",p.getString("transcript","").contains("安卓运行测试成功"),"completionNotification",notified,"serviceStopped",!ChatService.running,"sessionSurvived",session!=null,"mainActivityNotForeground",session!=null&&!session.uiVisible);}
    J.write(new File(getFilesDir(),"probe-"+(kind==null?"background":kind)+".json"),data.toString(2));}catch(Exception e){data=J.obj("error",e.getClass().getSimpleName());}TextView text=new TextView(this);text.setText(data.toString());setContentView(text);}
  int countHealthy(JSONArray values){int n=0;for(int i=0;i<values.length();i++)if(values.optJSONObject(i).optInt("delay")>0)n++;return n;}
}
