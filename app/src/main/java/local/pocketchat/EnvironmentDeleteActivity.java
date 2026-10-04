package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import org.json.*;

/** A foreground maintenance process owns deletion after all target writers have exited. */
public final class EnvironmentDeleteActivity extends Activity {
  boolean working;int slot;TextView label;
  @Override public void onCreate(Bundle state){super.onCreate(state);slot=getIntent().getIntExtra("slot",-1);if(slot<0||slot>=Profiles.MAX){finish();return;}LinearLayout root=DesignUi.screen(this);LinearLayout body=DesignUi.body(this,root,"删除环境",null);label=DesignUi.text(this,"正在清理环境数据…",16,DesignUi.TEXT);body.addView(label);setContentView(root);run();}
  void run(){if(working)return;working=true;new Thread(()->{String failure="";try{remove(this,slot);}catch(Exception e){failure="清理尚未完成，环境已暂停。请重试，不会清理其他环境。";}String error=failure;runOnUiThread(()->{working=false;if(error.isEmpty()){startActivity(new Intent(this,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));finish();}else{label.setText(error);new AlertDialog.Builder(this).setTitle("删除未完成").setMessage(error).setPositiveButton("重试",(d,w)->run()).setNegativeButton("返回列表",(d,w)->{startActivity(new Intent(this,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));finish();}).show();}});},"environment-delete").start();}
  @Override public void onBackPressed(){if(!working)super.onBackPressed();}
  static void remove(Context c,int slot)throws Exception{
    ProfileCatalog catalog=ProfileCatalog.get(c);JSONObject row=catalog.item(slot);
    if(!row.optBoolean("deleting"))throw new IOException("删除状态已变化");
    Context profile=Profiles.context(c,slot);DownloadLibrary.get(c).migrate();NetworkCatalog library=new NetworkCatalog(c);library.save();
    // A subscription may be cached only in the environment being removed. Keep
    // the user-owned shared subscription library available to all remaining environments.
    for(int i=0;i<library.subscriptions().length();i++){JSONObject sub=library.subscriptions().optJSONObject(i);if(sub.optInt("owner",-1)==slot){byte[] bytes=library.cache(sub);if(bytes!=null)library.parsed(sub.optString("id"),sub.optJSONArray("nodes"),bytes,sub.optLong("updatedAt"));}}
    Bundle stopped=c.getContentResolver().call(NetworkBridge.uri(c,slot),"stopForDelete",null,null);if(stopped==null||!stopped.getBoolean("stopped"))throw new IOException();
    String owner=c.getPackageName()+(slot==0?"":":profile"+slot),children=c.getPackageName()+":gecko_env"+slot+"_";
    ActivityManager manager=c.getSystemService(ActivityManager.class);long deadline=SystemClock.elapsedRealtime()+10000;
    do{boolean alive=false;List<ActivityManager.RunningAppProcessInfo> all=manager.getRunningAppProcesses();if(all!=null)for(ActivityManager.RunningAppProcessInfo p:all)if(p.uid==android.os.Process.myUid()&&(p.processName.equals(owner)||p.processName.startsWith(children))){if(p.pid==android.os.Process.myPid())throw new IOException();android.os.Process.killProcess(p.pid);alive=true;}if(!alive)break;if(SystemClock.elapsedRealtime()>deadline)throw new IOException();Thread.sleep(100);}while(true);
    NotificationManager notices=c.getSystemService(NotificationManager.class);for(int id=4101;id<=4105;id++)notices.cancel(Profiles.notification(profile,id));
    File data=new File(Profiles.global(c).getApplicationInfo().dataDir);
    String prefix=slot==0?"":"env"+slot+"_";
    if(slot>0){File files=new File(data,"files/profiles/env"+slot);File[] personal=files.listFiles();if(personal!=null)for(File f:personal)if(!f.getName().equals("saved-downloads"))erase(f);erase(new File(data,"cache/profiles/env"+slot));erase(new File(data,"no_backup/profiles/env"+slot));}
    else{
      for(String name:new String[]{"gecko-browser","gecko-browser.yaml","gecko-session.json","gecko-session.json.bak","gecko-session.json.new","network-runtime"})erase(new File(profile.getNoBackupFilesDir(),name));
      for(String name:new String[]{"network","network-ui","exit-baseline","exit-region","subscription","subscription-meta","subscription-ui","pending-network"}){android.util.AtomicFile f=new android.util.AtomicFile(new SecretStore(profile).file(name));f.delete();}
      erase(new File(profile.getFilesDir(),"network-import.json"));erase(new File(profile.getCacheDir(),"gecko-uploads"));
      File[] previews=profile.getNoBackupFilesDir().listFiles();if(previews!=null)for(File f:previews)if(f.getName().startsWith("subscription-preview-"))erase(f);
      File[] temporary=profile.getCacheDir().listFiles();if(temporary!=null)for(File f:temporary)if(f.getName().matches("download-.*[.]part")||f.getName().startsWith("subscription-preview-"))erase(f);
    }
    // System WebView data is private to this process suffix, even if Gecko is selected.
    erase(new File(data,slot==0?"app_webview":"app_webview_env"+slot));
    File[] prefs=new File(data,"shared_prefs").listFiles();if(prefs!=null)for(File f:prefs){String name=f.getName();if(slot>0&&name.startsWith(prefix)||slot==0&&(name.matches("(chat|download-tasks|network-journal|environment-audit|browser-reading|web-perf|route-quality|traffic-monitor)[.]xml(\\.bak)?"))){String base=name.replaceFirst("[.]xml(\\.bak)?$","");Profiles.global(c).getSharedPreferences(base,0).edit().clear().commit();if(f.exists()&&!f.delete())throw new IOException();}}
    for(String name:new String[]{"conversations.db","deliveries.db","draft-archive.db"})profile.deleteDatabase(name);
    if(slot>0){File[] dbs=new File(data,"databases").listFiles();if(dbs!=null)for(File f:dbs)if(f.getName().startsWith(prefix))erase(f);}
    // Saved files in Downloads or the user's chosen folder are user-owned and remain accessible.
    Profiles.global(c).getSharedPreferences("browser-environment-names",0).edit().remove("name"+slot).commit();
    DownloadLibrary.get(c).removeEnvironmentTasks(slot);catalog.completeDelete(slot);
  }
  static void erase(File f)throws IOException{if(java.nio.file.Files.isSymbolicLink(f.toPath())){if(!f.delete())throw new IOException("无法清理链接："+f.getName());return;}if(!f.exists())return;if(f.isDirectory()){File[] children=f.listFiles();if(children==null)throw new IOException("无法读取目录："+f.getName());for(File child:children)erase(child);}if(!f.delete())throw new IOException("无法清理文件："+f.getName());}
}
