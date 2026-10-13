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
    EnvironmentResetActivity.verifyRoots(c,target);Context dest=context(c,target);ProfileCatalog catalog=ProfileCatalog.get(c);org.json.JSONObject row=catalog.item(target);
    if(row.optBoolean("deleting")||row.optBoolean("resetting"))throw new java.io.IOException("这个环境正在维护，请稍候");
    if(row.optBoolean("created"))return;
    NetworkCopy copy=copyNetwork?captureNetwork(c):null;
    catalog.createNew(target,()->{
      FileCheck.requireUnusedBrowser(dest);android.content.SharedPreferences prefs=dest.getSharedPreferences("chat",0);SecretStore vault=new SecretStore(dest);
      clearConfiguration(vault);
      android.content.SharedPreferences.Editor edit=prefs.edit().clear().putBoolean("environmentInitialized",true).putBoolean("pageMode",true);
      if(copy!=null){for(java.util.Map.Entry<String,byte[]> record:copy.records.entrySet())vault.put(record.getKey(),record.getValue());edit.putString("networkMode",copy.mode).putString("proxy",copy.proxy).putBoolean("requireExternalVpn",copy.requireVpn).putBoolean("networkConfigured",copy.configured).putString("lastGoodEntry",copy.entry);}
      if(!edit.commit())throw new java.io.IOException("新环境配置无法保存");return null;
    });
  }
  static void clearConfiguration(SecretStore vault)throws Exception{for(String record:new String[]{"network","subscription","subscription-meta","subscription-ui","exit-subscription","exit-subscription-meta","exit-subscription-ui","exit-baseline","pending-network",EnvironmentSpecRepository.STORE,EnvironmentSpecRepository.RESET})vault.remove(record);}
  static final class NetworkCopy {
    final String mode,proxy,entry;final boolean requireVpn,configured;final java.util.Map<String,byte[]> records=new java.util.LinkedHashMap<>();
    NetworkCopy(android.content.SharedPreferences prefs){mode=prefs.getString("networkMode","external");proxy=prefs.getString("proxy","");entry=prefs.getString("lastGoodEntry","");requireVpn=prefs.getBoolean("requireExternalVpn",true);configured=prefs.getBoolean("networkConfigured",false);}
  }
  static final class ConfigurationCopy {
    final EnvironmentSpec source;final NetworkCopy network;final JSONObject preferences;final float zoom;final boolean hasZoom;
    ConfigurationCopy(EnvironmentSpec source,NetworkCopy network,JSONObject preferences,android.content.SharedPreferences prefs){this.source=source;this.network=network;this.preferences=preferences;hasZoom=prefs.contains(BrowserReadingPolicy.ZOOM_KEY);zoom=hasZoom?prefs.getFloat(BrowserReadingPolicy.ZOOM_KEY,1f):1f;}
  }
  /** Explicit configuration copy. The creation wizard may still borrow only a
   * network; this separate action copies the template without an implicit display override. */
  static EnvironmentSpec.Identity copyConfiguration(Context source,int target)throws Exception{
    return copyConfiguration(source,target,ProfileCatalog.get(source).identity(slot(source)));
  }
  static EnvironmentSpec.Identity copyConfiguration(Context source,int target,EnvironmentSpec.Identity confirmedSource)throws Exception{
    if(target==slot(source))throw new java.io.IOException("请选择另一个环境槽位");
    EnvironmentResetActivity.verifyRoots(source,target);
    ConfigurationCopy copy=EnvironmentSpecRuntime.withIntent(source,()->{
      ProfileCatalog catalog=ProfileCatalog.get(source);EnvironmentSpec.Identity identity=catalog.identity(slot(source));
      if(!identity.equals(confirmedSource))throw new java.io.IOException("源环境已改变，请重新选择要复制的环境");
      EnvironmentSpecRuntime.reconcileNetwork(source,identity,"");
      if(NetworkChanges.pendingStrict(source).length()>0)throw new java.io.IOException("请先应用或取消待应用的网络设置，再复制环境配置");
      NetworkCopy network=captureNetwork(source);EnvironmentSpec spec=new EnvironmentSpecRepository(source).load();
      EnvironmentSpecRuntime.requireIdentity(source,identity);if(!spec.identity.equals(identity))throw new java.io.IOException("源环境身份已变化");
      BrowserIdentitySpec browser=BrowserIdentitySpec.from(spec.desired().browser());if(!browser.validate().isEmpty())throw new java.io.IOException(browser.validate());
      return new ConfigurationCopy(spec,network,AppPrefs.values(source),source.getSharedPreferences("chat",0));
    });
    Context dest=context(source,target);ProfileCatalog catalog=ProfileCatalog.get(source);
    int first=Math.min(slot(source),target),second=Math.max(slot(source),target);
    synchronized(EnvironmentSpecRepository.GATES[first]){synchronized(EnvironmentSpecRepository.GATES[second]){
    return catalog.createNew(target,()->catalog.withIdentity(copy.source.identity,()->{
      EnvironmentSpec current=new EnvironmentSpecRepository(source).load();EnvironmentSpec.requireRevision(copy.source.desiredRevision,current.desiredRevision);
      FileCheck.requireUnusedBrowser(dest);
      android.content.SharedPreferences prefs=dest.getSharedPreferences("chat",0);SecretStore vault=new SecretStore(dest);
      // Only configuration records are copied/re-encrypted under the destination
      // key. A failed reservation is still uncreated, and can be retried safely.
      clearConfiguration(vault);
      for(java.util.Map.Entry<String,byte[]> record:copy.network.records.entrySet())vault.put(record.getKey(),record.getValue());
      BrowserIdentitySpec browser=BrowserIdentitySpec.from(copy.source.desired().browser());android.content.SharedPreferences.Editor edit=prefs.edit().clear().putString("networkMode",copy.network.mode).putString("proxy",copy.network.proxy).putBoolean("requireExternalVpn",copy.network.requireVpn).putBoolean("networkConfigured",copy.network.configured).putString("lastGoodEntry",copy.network.entry).putInt("privacyLevel",browser.protectionLevel()).putBoolean("environmentInitialized",true).putBoolean("pageMode",true);
      for(String key:AppPrefs.KEYS)edit.putBoolean(key,copy.preferences.optBoolean(key));if(copy.hasZoom)edit.putFloat(BrowserReadingPolicy.ZOOM_KEY,copy.zoom);
      if(!edit.commit())throw new java.io.IOException("环境配置未能复制");catalog.browserDisplay(target,browser.desktop());
      EnvironmentSpec.Identity next=catalog.identity(target);new EnvironmentSpecRepository(dest).initializeCopy(next,copy.source.desired().browser());return next;
    }));
    }}
  }
  static final class FileCheck {
    static void requireUnusedBrowser(Context dest)throws Exception{for(String name:new String[]{"gecko-browser","gecko-session.json","gecko-session.json.bak","gecko-session.json.new"})if(java.nio.file.Files.exists(new java.io.File(dest.getNoBackupFilesDir(),name).toPath(),java.nio.file.LinkOption.NOFOLLOW_LINKS))throw new java.io.IOException("目标槽位仍有网页数据，请先完成清理");}
  }
  static NetworkCopy captureNetwork(Context c)throws Exception{
    SecretStore source=new SecretStore(c);
    return NetworkSourceSelection.withActiveSnapshot(source.context,()->{
      NetworkCopy copy=new NetworkCopy(source.context.getSharedPreferences("chat",0));byte[] saved=source.get("network");JSONObject settings=saved==null?new JSONObject():EnvironmentSpecRepository.strictObject(saved);
      if("internal".equals(copy.mode)&&copy.configured&&settings.length()==0)throw new java.io.IOException("内置网络配置无法读取，原记录保留");
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
  static void open(MainActivity a,int id){if(!ProfileCatalog.get(a).available(id))return;if(id==slot(a))return;if(Build.VERSION.SDK_INT<28){a.status("独立登录环境需要 Android 9 或更新版本");return;}a.startActivity(new Intent(a,activity(id)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));}
}
