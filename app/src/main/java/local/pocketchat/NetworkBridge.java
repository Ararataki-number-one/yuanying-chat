package local.pocketchat;
import android.content.*;import android.net.Uri;import android.os.*;import org.json.*;import java.util.concurrent.*;

/** Work is dispatched without changing the visible window or instantiating its WebView. */
final class NetworkBridge {
  interface Result{void done(boolean ok,String message,JSONObject state);}
  static final ExecutorService worker=Executors.newCachedThreadPool();static final Handler main=new Handler(Looper.getMainLooper());
  static Uri uri(Context c,int slot){if(slot<0||slot>=Profiles.MAX)throw new IllegalArgumentException();if(slot>0&&Build.VERSION.SDK_INT<28)throw new IllegalStateException("独立窗口需要 Android 9 或更新版本");return Uri.parse("content://"+c.getPackageName()+".network-ui"+slot);}
  static void run(Context c,int slot,String action,JSONObject candidate,String baseline,Result cb){if(slot>0&&Build.VERSION.SDK_INT<28){main.post(()->cb.done(false,"独立窗口需要 Android 9 或更新版本",new JSONObject()));return;}Context root=Profiles.global(c);worker.execute(()->{boolean ok=false;String message="此窗口暂时无法完成操作，请稍后再试";JSONObject state=new JSONObject();try{
    Bundle args=new Bundle();args.putString("action",action);args.putString("config",candidate==null?"{}":candidate.toString());args.putString("baseline",baseline==null?"":baseline);
    Bundle start=root.getContentResolver().call(uri(c,slot),"start",null,args);if(start==null)throw new IllegalStateException();String id=start.getString("id");long deadline=SystemClock.elapsedRealtime()+160000;
    while(SystemClock.elapsedRealtime()<deadline){Bundle result=root.getContentResolver().call(uri(c,slot),"job",id,null);JSONObject status=J.parse(result==null?"{}":result.getString("json","{}"));if(status.optBoolean("done")){ok=status.optBoolean("ok");message=status.optString("message");break;}Thread.sleep(600);}
    Bundle current=root.getContentResolver().call(uri(c,slot),"state",null,null);if(current!=null)state=J.parse(current.getString("json","{}"));
  }catch(Exception ignored){}final boolean success=ok;final String text=message;final JSONObject snapshot=state;main.post(()->cb.done(success,text,snapshot));});}
}
