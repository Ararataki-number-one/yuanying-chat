package local.pocketchat;
import android.app.*;
import android.os.*;
import android.content.*;
import org.json.*;
import java.io.*;

/** Debug/test-only fault injection, excluded from production manifests and sources. */
public class NetworkFaultActivity extends Activity {
 @Override public void onCreate(Bundle b){super.onCreate(b);if((getApplicationInfo().flags&android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)==0){finish();return;}ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(this);String action=getIntent().getStringExtra("action");if("crash".equals(action)&&s!=null&&s.pending==null&&n.process!=null){n.process.destroy();n.worker.execute(()->n.health());}else if("inspect".equals(action)){JSONObject data=J.obj("sessionExists",s!=null,"networkReady",s!=null&&s.networkReady,"offline",s!=null&&s.offline,"connecting",s!=null&&s.connecting,"retryScheduled",s!=null&&s.recoveryScheduled,"retryAttempt",s==null?-1:s.recoveryAttempt,"stage",s==null?"":s.connectionStage,"coreAlive",n.coreAlive(),"coreReady",n.ready,"pending",s!=null&&s.pending!=null,"draftLength",getSharedPreferences("chat",0).getString("draft","").length(),"exitVerified",n.lastVerified>0);try{J.write(new File(getFilesDir(),"network-fault-state.json"),data.toString(2));}catch(Exception ignored){}}finish();}
}
