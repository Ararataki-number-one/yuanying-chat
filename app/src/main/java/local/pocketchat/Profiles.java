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
    if(copyNetwork){android.content.SharedPreferences source=c.getSharedPreferences("chat",0);String mode=source.getString("networkMode","external");SecretStore old=new SecretStore(c),next=new SecretStore(dest);JSONObject settings=old.settings();
      if("internal".equals(mode)&&settings.length()>0){NativeNetwork.validate(settings);next.save(settings);byte[] meta=old.get("subscription-meta"),provider=old.get("subscription");if(meta!=null&&provider!=null&&J.parse(new String(meta,java.nio.charset.StandardCharsets.UTF_8)).optString("urlHash").equals(NativeNetwork.hash(settings.optString("subscriptionUrl")))){next.put("subscription",provider);next.put("subscription-meta",meta);}byte[] baseline=old.get("exit-baseline");if(baseline!=null)next.put("exit-baseline",baseline);}
      prefs.edit().putString("networkMode",mode).putString("proxy",source.getString("proxy","")).putBoolean("requireExternalVpn",source.getBoolean("requireExternalVpn",true)).putBoolean("networkConfigured",source.getBoolean("networkConfigured",false)).putString("lastGoodEntry",source.getString("lastGoodEntry","")).commit();
    }
    prefs.edit().putBoolean("environmentInitialized",true).putBoolean("pageMode",true).commit();ProfileCatalog.get(c).created(target);
  }
  static void open(MainActivity a,int id){if(!ProfileCatalog.get(a).item(id).optBoolean("created"))return;if(id==slot(a))return;if(Build.VERSION.SDK_INT<28){a.status("独立登录环境需要 Android 9 或更新版本");return;}a.startActivity(new Intent(a,activity(id)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
}
