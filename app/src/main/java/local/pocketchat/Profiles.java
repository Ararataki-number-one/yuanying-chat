package local.pocketchat;

import android.app.Application;
import android.content.*;
import android.os.Build;
import org.json.*;

final class Profiles {
  static final int MAX=8;
  static int processSlot(){if(Build.VERSION.SDK_INT<28)return 0;String process=Application.getProcessName();if(process!=null)for(int id=1;id<MAX;id++)if(process.endsWith(":profile"+id))return id;return 0;}
  static int slot(Context c){Context app=c instanceof ProfileContext?c:c.getApplicationContext();return app instanceof ProfileContext?((ProfileContext)app).slot:processSlot();}
  static Context global(Context c){Context app=c.getApplicationContext();while(app instanceof ProfileContext)app=((ProfileContext)app).getBaseContext();return app;}
  static Context context(Context c,int id){Context root=global(c);return root instanceof PocketApplication?((PocketApplication)root).profile(id):new ProfileContext(root,id);}
  static Class<?> activity(int id){return new Class<?>[]{MainActivity.class,ProfileActivity1.class,ProfileActivity2.class,ProfileActivity3.class,ProfileActivity4.class,ProfileActivity5.class,ProfileActivity6.class,ProfileActivity7.class}[id];}
  static Class<?> preview(Context c){int id=slot(c);return new Class<?>[]{AttachmentPreviewActivity.class,ProfilePreview1.class,ProfilePreview2.class,ProfilePreview3.class,ProfilePreview4.class,ProfilePreview5.class,ProfilePreview6.class,ProfilePreview7.class}[id];}
  static Class<?> service(Context c){int id=slot(c);return new Class<?>[]{ChatService.class,ProfileChatService1.class,ProfileChatService2.class,ProfileChatService3.class,ProfileChatService4.class,ProfileChatService5.class,ProfileChatService6.class,ProfileChatService7.class}[id];}
  static int notification(Context c,int original){return original+slot(c)*100;}
  static String display(Context c,int id){return ProfileCatalog.get(c).name(id);}
  static void rename(Context c,int id,String name){String trimmed=name.trim();if(!trimmed.isEmpty()&&trimmed.length()<=24){ProfileCatalog.get(c).rename(id,trimmed);global(c).getSharedPreferences("browser-environment-names",0).edit().putString("name"+id,trimmed).apply();}}
  static void prepare(Context c,int target,boolean copyNetwork)throws Exception{
    Context dest=context(c,target);android.content.SharedPreferences prefs=dest.getSharedPreferences("chat",0);if(ProfileCatalog.get(c).item(target).optBoolean("deleting"))throw new java.io.IOException("这个环境正在删除，请稍候");if(prefs.getBoolean("environmentInitialized",false)&&ProfileCatalog.get(c).item(target).optBoolean("created"))return;
    if(!ProfileCatalog.get(c).item(target).optBoolean("created")&&!prefs.edit().clear().commit())throw new java.io.IOException("新环境数据无法初始化");
    if(copyNetwork){
      NetworkCopy copy=captureNetwork(c);SecretStore next=new SecretStore(dest);
      NetworkSourceSelection.withActiveSnapshot(next.context,()->{
        java.util.Map<String,byte[]> previous=new java.util.LinkedHashMap<>();for(String record:copy.records.keySet())previous.put(record,next.get(record));
        try{for(java.util.Map.Entry<String,byte[]> record:copy.records.entrySet())next.put(record.getKey(),record.getValue());if(!prefs.edit().putString("networkMode",copy.mode).putString("proxy",copy.proxy).putBoolean("requireExternalVpn",copy.requireVpn).putBoolean("networkConfigured",copy.configured).putString("lastGoodEntry",copy.entry).commit())throw new java.io.IOException("网络配置无法复制");}
        catch(Exception failed){for(java.util.Map.Entry<String,byte[]> record:previous.entrySet())try{NetworkSourceSelection.restore(next,record.getKey(),record.getValue());}catch(Exception restore){failed.addSuppressed(restore);}throw failed;}return null;
      });
    }
    prefs.edit().putBoolean("environmentInitialized",true).putBoolean("pageMode",true).commit();ProfileCatalog.get(c).created(target);
  }
  static final class NetworkCopy {
    final String mode,proxy,entry;final boolean requireVpn,configured;final java.util.Map<String,byte[]> records=new java.util.LinkedHashMap<>();
    NetworkCopy(android.content.SharedPreferences prefs){mode=prefs.getString("networkMode","external");proxy=prefs.getString("proxy","");entry=prefs.getString("lastGoodEntry","");requireVpn=prefs.getBoolean("requireExternalVpn",true);configured=prefs.getBoolean("networkConfigured",false);}
  }
  static NetworkCopy captureNetwork(Context c)throws Exception{
    SecretStore source=new SecretStore(c);
    return NetworkSourceSelection.withActiveSnapshot(source.context,()->{
      NetworkCopy copy=new NetworkCopy(source.context.getSharedPreferences("chat",0));JSONObject settings=source.settings();
      if(!"internal".equals(copy.mode)||settings.length()==0)return copy;NativeNetwork.validate(settings);
      for(String role:new String[]{NetworkCatalog.ENTRY,NetworkCatalog.EXIT}){
        boolean entry=NetworkCatalog.ENTRY.equals(role);if(!entry&&!NativeNetwork.subscribedExit(settings))continue;String slot=entry?"subscription":"exit-subscription";byte[] bytes=source.get(slot),meta=source.get(slot+"-meta");JSONObject receipt=meta==null?new JSONObject():J.parse(new String(meta,java.nio.charset.StandardCharsets.UTF_8));boolean identified=!settings.optString(entry?"entrySubscriptionId":"exitSubscriptionId").isEmpty();
        if(!NativeNetwork.sourceCacheMatches(settings,role,receipt,bytes)){if(!entry||identified)throw new java.io.IOException("所选订阅缓存无法复制，请先重新保存网络");continue;}
        copy.records.put(slot,bytes);copy.records.put(slot+"-meta",meta);byte[] ui=source.get(slot+"-ui");JSONObject display=ui==null?new JSONObject():J.parse(new String(ui,java.nio.charset.StandardCharsets.UTF_8));boolean validUi=NativeNetwork.sourceCacheMatches(settings,role,display,bytes);
        if(identified){if(!validUi)throw new java.io.IOException("订阅快照正在变化，请重新保存网络后复制");NativeNetwork.validateSnapshotSelection(settings,role,display);}
        if(validUi)copy.records.put(slot+"-ui",ui);
      }
      byte[] baseline=source.get("exit-baseline");if(baseline!=null)copy.records.put("exit-baseline",baseline);copy.records.put("network",settings.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));return copy;
    });
  }
  static void open(MainActivity a,int id){if(!ProfileCatalog.get(a).item(id).optBoolean("created"))return;if(id==slot(a))return;if(Build.VERSION.SDK_INT<28){a.status("独立登录环境需要 Android 9 或更新版本");return;}a.startActivity(new Intent(a,activity(id)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
}
