package local.pocketchat;
import android.content.*;import android.net.Uri;import android.os.*;import org.json.*;import java.util.concurrent.*;import java.util.concurrent.atomic.AtomicBoolean;import java.util.function.Consumer;

/** Work is dispatched without changing the visible window or constructing a browser. */
final class NetworkBridge {
  interface Result{void done(boolean ok,String message,JSONObject state);}
  interface Decision{void required(JSONObject choice,Consumer<String> select);}
  interface ShareResult{void done(NetworkSharePreparation.Frozen frozen,NetworkSharePreparation.Failure failure);}
  static final ExecutorService worker=Executors.newCachedThreadPool();static final Handler main=new Handler(Looper.getMainLooper());
  static Uri uri(Context c,int slot){if(slot<0||slot>=Profiles.MAX)throw new IllegalArgumentException();if(slot>0&&Build.VERSION.SDK_INT<28)throw new IllegalStateException("独立窗口需要 Android 9 或更新版本");return Uri.parse("content://"+c.getPackageName()+".network-ui"+slot);}
  static void run(Context c,int slot,String action,JSONObject candidate,String baseline,Result cb){run(c,slot,action,candidate,baseline,null,null,cb);}
  static void run(Context c,int slot,String action,JSONObject candidate,String baseline,EnvironmentSpec.Identity expected,Result cb){run(c,slot,action,candidate,baseline,expected,null,cb);}
  static void run(Context c,int slot,String action,JSONObject candidate,String baseline,EnvironmentSpec.Identity expected,Decision decision,Result cb){
    if(expected!=null&&expected.slot!=slot){main.post(()->cb.done(false,"此环境已改变，请重新打开网络设置",new JSONObject()));return;}
    if(slot>0&&Build.VERSION.SDK_INT<28){main.post(()->cb.done(false,"独立窗口需要 Android 9 或更新版本",new JSONObject()));return;}
    final String configuration=candidate==null?"{}":candidate.toString();Context root=Profiles.global(c);
    worker.execute(()->{boolean ok=false;String message="此窗口暂时无法完成操作，请稍后再试";JSONObject state=new JSONObject(),outcome=null;
      try{
        Bundle args=new Bundle();args.putString("action",action);args.putString("config",configuration);args.putString("baseline",baseline==null?"":baseline);if(expected!=null)args.putString("expectedIdentity",expected.json().toString());
        Bundle start=root.getContentResolver().call(uri(c,slot),"start",null,args);if(start==null)throw new IllegalStateException();
        if(start.containsKey("json")){JSONObject rejected=J.parse(start.getString("json","{}"));main.post(()->cb.done(false,rejected.optString("message"),rejected));return;}
        String id=start.getString("id"),offered="";long deadline=SystemClock.elapsedRealtime()+160000;boolean awaitingChoice=false;
        while(SystemClock.elapsedRealtime()<deadline){
          Bundle result=root.getContentResolver().call(uri(c,slot),"job",id,null);JSONObject status=J.parse(result==null?"{}":result.getString("json","{}"));
          if(status.optBoolean("done")){ok=status.optBoolean("ok");message=status.optString("message");JSONObject completed=status.optJSONObject("operationResult");outcome=completed==null?null:J.parse(completed.toString());break;}
          if("choice-required".equals(status.optString("phase"))){
            JSONObject choice=status.optJSONObject("choice");if(choice==null)throw new IllegalStateException();
            if(decision==null){ok=true;message="设置已保存，等待选择应用方式";outcome=J.obj("saveState","saved","applicationState","pending","scope","core","environmentId",choice.optString("environmentId"),"generation",choice.optInt("generation"),"candidateId",choice.optString("candidateId"),"savedRevision",choice.optLong("savedRevision"),"appliedRevision",0,"message",message);NetworkCatalog.put(state,"applicationChoice",choice);break;}
            if(!offered.equals(choice.optString("token"))){offered=choice.optString("token");awaitingChoice=true;deadline=SystemClock.elapsedRealtime()+300000;JSONObject frozen=J.parse(choice.toString());AtomicBoolean selected=new AtomicBoolean();
              main.post(()->decision.required(frozen,value->{if(!NetworkApplyCoordinator.IMMEDIATE.equals(value)&&!NetworkApplyCoordinator.DEFER.equals(value)||!selected.compareAndSet(false,true))return;worker.execute(()->{Bundle selection=new Bundle();selection.putString("token",frozen.optString("token"));selection.putString("policy",value);try{root.getContentResolver().call(uri(c,slot),"decide",id,selection);}catch(Exception ignored){}});}));
            }
          }else if(awaitingChoice){awaitingChoice=false;deadline=SystemClock.elapsedRealtime()+160000;}
          Thread.sleep(600);
        }
        Bundle current=root.getContentResolver().call(uri(c,slot),"state",null,null);if(current!=null){JSONObject fresh=J.parse(current.getString("json","{}"));if(state.has("applicationChoice"))NetworkCatalog.put(fresh,"applicationChoice",state.optJSONObject("applicationChoice"));state=fresh;}
      }catch(Exception ignored){}
      state.remove("operationResult");if(outcome!=null)NetworkCatalog.put(state,"operationResult",outcome);boolean success=ok;String text=message;JSONObject snapshot=state;main.post(()->cb.done(success,text,snapshot));
    });
  }
  /** Scope is frozen before reads. SAVED avoids even a cold provider bind. */
  static void shareSnapshot(Context context,NetworkSharePreparation.Request request,ShareResult callback){
    worker.execute(()->{NetworkSharePreparation.Frozen frozen=null;NetworkSharePreparation.Failure failure=null;try{
      Context profile=Profiles.context(context,request.owner.slot);
      if("saved".equals(request.source)){
        frozen=NetworkShareSelection.capture(profile,request);if(!NetworkShareSelection.current(profile,request))throw NetworkSharePreparation.fail("CONFIG_READ","VERSION_CHANGED","");
      }else{
        Bundle args=new Bundle();args.putString("request",request.json().toString());Bundle response=Profiles.global(context).getContentResolver().call(uri(context,request.owner.slot),"shareSnapshot",null,args);
        if(response==null)throw NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","");
        if(response.containsKey("failure"))throw NetworkSharePreparation.Failure.read(new JSONObject(response.getString("failure")));
        ParcelFileDescriptor descriptor=response.getParcelable("snapshot");if(descriptor==null)throw NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","");
        frozen=NetworkShareTransfer.read(descriptor,request);
      }
    }catch(NetworkSharePreparation.Failure typed){failure=typed;}catch(Exception unavailable){failure=NetworkSharePreparation.fail("CONFIG_READ","UNREADABLE","");}
      NetworkSharePreparation.Frozen result=frozen;NetworkSharePreparation.Failure problem=failure;main.post(()->callback.done(problem==null?result:null,problem));
    });
  }
}
