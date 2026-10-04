package local.pocketchat;

import android.content.*;import android.database.Cursor;import android.net.Uri;import android.os.*;import android.util.AtomicFile;
import org.json.*;import java.util.*;import java.util.concurrent.*;import java.nio.charset.StandardCharsets;

/** Private UI-to-profile bridge. Each provider runs in the existing profile's own process. */
public class NetworkUiProvider extends ContentProvider {
  Context profile;final Handler main=new Handler(Looper.getMainLooper());final Map<String,JSONObject> jobs=new ConcurrentHashMap<>();boolean applying,saving;String activeApply="";final Runnable drain=()->{drainPending();main.postDelayed(this.drain,1000);};final ExecutorService io=Executors.newSingleThreadExecutor();
  public static class Profile1 extends NetworkUiProvider{}public static class Profile2 extends NetworkUiProvider{}public static class Profile3 extends NetworkUiProvider{}public static class Profile4 extends NetworkUiProvider{}public static class Profile5 extends NetworkUiProvider{}public static class Profile6 extends NetworkUiProvider{}public static class Profile7 extends NetworkUiProvider{}
  @Override public boolean onCreate(){profile=Profiles.context(getContext(),Profiles.processSlot());main.post(drain);return true;}
  @Override public Bundle call(String method,String arg,Bundle extras){
    if(Binder.getCallingUid()!=android.os.Process.myUid())throw new SecurityException();Bundle result=new Bundle();
    if("stopForDelete".equals(method)){
      if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("deleting"))throw new IllegalStateException();
      java.util.concurrent.CountDownLatch stopped=new java.util.concurrent.CountDownLatch(1);main.post(()->{ChatSession s=ChatSession.peek();if(s!=null){s.deleted=true;s.handler.removeCallbacks(s.tick);s.guard.setBlocked(true);ChatService.end(profile);s.web.destroy();}NativeNetwork n=NativeNetwork.get(profile);n.cancelMaintenance();n.worker.execute(()->{try{n.stopNow();}finally{stopped.countDown();}});});
      try{if(!stopped.await(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("停止环境超时");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IllegalStateException(e);}if(NativeNetwork.get(profile).coreAlive())throw new IllegalStateException("独立网络尚未停止，请重试删除");result.putBoolean("stopped",true);return result;
    }
    if("state".equals(method)){NativeNetwork n=NativeNetwork.get(profile);JSONObject state=WindowNetworkState.live(ChatSession.peek(),n);NetworkCatalog.put(state,"configurationHash",NetworkChanges.hash(profile));result.putString("json",state.toString());return result;}
    if("job".equals(method)){JSONObject status=jobs.get(arg);result.putString("json",status==null?J.obj("done",true,"ok",false,"message","操作记录已过期").toString():status.toString());return result;}
    if(!"start".equals(method))throw new IllegalArgumentException();String action=extras==null?"":extras.getString("action","");JSONObject candidate=J.parse(extras==null?"{}":extras.getString("config","{}"));String baseline=extras==null?"":extras.getString("baseline","");
    String id=UUID.randomUUID().toString();if(jobs.size()>24)jobs.entrySet().removeIf(x->x.getValue().optBoolean("done"));jobs.put(id,J.obj("done",false));main.post(()->request(id,action,candidate,baseline));result.putString("id",id);return result;
  }
  void finish(String id,boolean ok,String message){if(Looper.myLooper()!=Looper.getMainLooper()){main.post(()->finish(id,ok,message));return;}if(id.equals(activeApply)){applying=false;activeApply="";ChatSession s=ChatSession.peek();if(s!=null){s.operation=false;s.changed();}}WindowNetworkState.save(profile,ChatSession.peek(),NativeNetwork.get(profile));jobs.put(id,J.obj("done",true,"ok",ok,"message",message));}
  boolean busy(ChatSession s,NativeNetwork n){return applying||n.starting||n.measuringLatency||s==null&&J.parse(profile.getSharedPreferences("chat",0).getString("pending","{}")).length()>0||s!=null&&(ProfileUi.working(s)||s.connecting);}
  void request(String id,String action,JSONObject candidate,String baseline){request(id,action,candidate,baseline,false);}
  void request(String id,String action,JSONObject candidate,String baseline,boolean deferred){
    if(!"apply".equals(action)&&!"external".equals(action)){operate(id,action,candidate,baseline);return;}
    saving=true;
    io.execute(()->{
      String error="";try{
        if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("created"))throw new java.io.IOException("此环境已删除");
        if(!baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请重新编辑");
        NetworkChanges.validate(profile,action,candidate);NetworkChanges.save(profile,action,candidate,baseline);
      }catch(Exception e){error=e.getMessage()==null?"配置未能保存":e.getMessage();}
      String failure=error;main.post(()->{
        saving=false;if(!failure.isEmpty()){if(deferred){JSONObject current=NetworkChanges.pending(profile);if(baseline.equals(current.optString("baseline"))&&candidate.toString().equals(String.valueOf(current.optJSONObject("config"))))NetworkChanges.clear(profile);ChatSession waiting=ChatSession.peek();if(waiting!=null)waiting.setStatus("已保存的网络设置需要重新编辑："+failure);}finish(id,false,failure);return;}
        ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
        if(saving||busy(s,n)||s!=null&&(s.navigating||s.state.optBoolean("busy"))){finish(id,true,"网络设置已保存，当前回复和文件操作结束后自动应用");return;}
        NetworkChanges.clear(profile);operate(id,action,candidate,baseline);
      });
    });
  }
  void operate(String id,String action,JSONObject candidate,String baseline){
    ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
    if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("created")){finish(id,false,"此环境已删除");return;}
    if(busy(s,n)){finish(id,false,"当前回复继续进行，网络配置可以先编辑保存");return;}
    if("measure".equals(action)){if(!"internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external"))){finish(id,false,"当前方式没有完整线路测速数据；可在窗口详情检查连接");return;}n.measureLatency((ok,msg)->finish(id,ok,msg));return;}
    if("verify".equals(action)){if(!n.ready){finish(id,false,"请先连接此窗口，再核验出口");return;}applying=true;activeApply=id;if(s!=null)s.operation=true;n.checkExit((ok,msg)->finish(id,ok,msg));return;}
    if("reconnect".equals(action)){if(s!=null){s.reconnect();waitConnection(id,s,n,false,SystemClock.elapsedRealtime());}else if("internal".equals(profile.getSharedPreferences("chat",0).getString("networkMode","external")))n.restart((ok,msg)->finish(id,ok,msg));else finish(id,false,"打开此窗口的会话后可重连手机网络");return;}
    if("external".equals(action)){
      SecretStore vault=new SecretStore(profile);if(!baseline.equals(NetworkChanges.hash(profile))){finish(id,false,"此窗口配置已变化，请重新编辑");return;}String proxy=candidate.optString("proxy");if(!proxy.isEmpty()&&!MainActivity.validProxy(proxy)){finish(id,false,"代理地址无效");return;}
      applying=true;activeApply=id;if(s!=null)s.operation=true;
      boolean written=profile.getSharedPreferences("chat",0).edit().putString("networkMode","external").putBoolean("networkConfigured",true).putString("proxy",proxy).putBoolean("requireExternalVpn",candidate.optBoolean("requireExternalVpn",true)).commit();
      if(!written){finish(id,false,"未能保存网络方式");return;}n.stop();if(s!=null){s.reconnect();waitConnection(id,s,n,true,SystemClock.elapsedRealtime());}else finish(id,true,"已保存，打开会话时应用手机网络");return;
    }
    if(!"apply".equals(action)){finish(id,false,"未知网络操作");return;}
    applying=true;activeApply=id;if(s!=null)s.operation=true;io.execute(()->apply(id,candidate,baseline));
  }
  void drainPending(){
    if(!ProfileCatalog.get(profile).item(Profiles.slot(profile)).optBoolean("created"))return;
    ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
    if(saving||busy(s,n)||s!=null&&(s.navigating||s.recoveryScheduled||s.state.optBoolean("busy")))return;
    JSONObject queued=NetworkChanges.pending(profile);if(queued.length()==0)return;
    String id=UUID.randomUUID().toString();jobs.put(id,J.obj("done",false));
    request(id,queued.optString("action"),queued.optJSONObject("config"),queued.optString("baseline"),true);

  }
  void apply(String id,JSONObject candidate,String baseline){
    ChatSession s=ChatSession.peek();NativeNetwork n=NativeNetwork.get(profile);
    SecretStore vault=new SecretStore(profile);JSONObject old=vault.settings();SharedPreferences prefs=profile.getSharedPreferences("chat",0);String oldMode=prefs.getString("networkMode","external"),oldEntry=prefs.getString("lastGoodEntry","");boolean oldConfigured=prefs.getBoolean("networkConfigured",false);byte[] oldProvider=null,oldMeta=null,oldUi=null,oldNetwork=null;boolean writing=false;
    try{
      if(!baseline.equals(NetworkChanges.hash(profile)))throw new java.io.IOException("此窗口配置已变化，请关闭后重新编辑");
      NativeNetwork.validate(candidate);NetworkCatalog catalog=new NetworkCatalog(profile);JSONObject sub=catalog.subscription(NativeNetwork.hash(candidate.optString("subscriptionUrl")));if(sub==null)throw new java.io.IOException("订阅已变化，请重新选择");EntrySelection.validate(candidate,EntrySelection.strings(sub.optJSONArray("nodes")));
      byte[] provider=catalog.cache(sub);if(provider==null)throw new java.io.IOException("请先读取所选订阅的入口，再保存");
      oldProvider=vault.get("subscription");oldMeta=vault.get("subscription-meta");oldUi=vault.get("subscription-ui");oldNetwork=vault.get("network");writing=true;
      vault.put("subscription",provider);vault.put("subscription-meta",J.obj("urlHash",sub.optString("id"),"updatedAt",sub.optLong("updatedAt")).toString().getBytes(StandardCharsets.UTF_8));vault.put("subscription-ui",J.obj("urlHash",sub.optString("id"),"nodes",sub.optJSONArray("nodes")).toString().getBytes(StandardCharsets.UTF_8));vault.save(candidate);
      if(!prefs.edit().putString("networkMode","internal").putBoolean("networkConfigured",true).putString("lastGoodEntry",candidate.optString("entry").isEmpty()?oldEntry:candidate.optString("entry")).commit())throw new java.io.IOException("网络配置未能保存");
    }catch(Exception error){
      // Restore only if writes began; candidate validation has no observable side effects.
      if(writing)try{restore(vault,"network",oldNetwork);restore(vault,"subscription",oldProvider);restore(vault,"subscription-meta",oldMeta);restore(vault,"subscription-ui",oldUi);prefs.edit().putString("networkMode",oldMode).putBoolean("networkConfigured",oldConfigured).putString("lastGoodEntry",oldEntry).commit();}catch(Exception ignored){}
      finish(id,false,error.getMessage()==null?"保存失败，原连接未切换":error.getMessage());return;
    }
    main.post(()->{if(s!=null){s.reconnect();waitConnection(id,s,n,true,SystemClock.elapsedRealtime());}else n.restart((ok,msg)->finish(id,ok,ok?"配置已保存并应用":"配置已保存，"+msg));});
  }
  static void restore(SecretStore store,String slot,byte[] value)throws Exception{if(value==null)new AtomicFile(store.file(slot)).delete();else store.put(slot,value);}
  void waitConnection(String id,ChatSession s,NativeNetwork n,boolean saved,long began){main.postDelayed(()->{
    if(s.networkReady&&!s.offline&&(!s.internalNetwork()||n.ready&&n.coreAlive())){finish(id,true,saved?"配置已保存并应用":"连接已恢复");}
    else if(!s.connecting&&!n.starting||SystemClock.elapsedRealtime()-began>150000){finish(id,false,(saved?"配置已保存，":"")+(s.networkIssue.isEmpty()?"连接尚未完成，请检查此窗口网络":s.networkIssue));}
    else waitConnection(id,s,n,saved,began);
  },500);}
  @Override public Cursor query(Uri u,String[] p,String s,String[] a,String o){return null;}@Override public String getType(Uri u){return null;}@Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}@Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}@Override public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
