package local.pocketchat;

import android.app.*;
import android.content.*;
import android.os.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import org.json.*;

/** Separate maintenance process. Only an explicitly confirmed reset or a
 * persisted reset retry enters this activity. The logical environment is kept. */
public final class EnvironmentResetActivity extends ThemedActivity {
  static final Object[] MAINTENANCE_GATES=new Object[8];static{for(int i=0;i<8;i++)MAINTENANCE_GATES[i]=new Object();}
  boolean working;int slot;TextView label;EnvironmentSpec.Identity confirmed;
  @Override public void onCreate(Bundle state){super.onCreate(state);try{slot=getIntent().getIntExtra("slot",-1);confirmed=new EnvironmentSpec.Identity(slot,getIntent().getIntExtra("confirmedGeneration",-1),getIntent().getStringExtra("confirmedEnvironmentId"));}catch(Exception invalid){finish();return;}LinearLayout root=DesignUi.screen(this);LinearLayout body=DesignUi.body(this,root,"重置登录数据",null);label=DesignUi.text(this,"正在清理此环境的登录与网页数据…",16,DesignUi.TEXT);body.addView(label);setContentView(root);run();}
  void run(){if(working)return;working=true;new Thread(()->{String failure="";boolean expired=false;try{reset(this,confirmed);}catch(Expired e){expired=true;}catch(Exception e){failure="重置尚未完成，请重试。环境配置和其他环境会保留。";}String error=failure;boolean done=expired;runOnUiThread(()->{working=false;if(done||error.isEmpty()){backToList();}else{label.setText(error);AppAppearance.dialog(this).setTitle("登录重置未完成").setMessage(error).setPositiveButton("重试",(d,w)->run()).setNegativeButton("返回列表",(d,w)->backToList()).show();}});},"environment-login-reset").start();}
  void backToList(){startActivity(new Intent(this,WindowHomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));finish();}
  @Override public void onBackPressed(){if(!working)super.onBackPressed();}
  static void verifyRoots(Context c,int slot)throws Exception{
    Context global=Profiles.global(c);EnvironmentBrowserData.root(global.getNoBackupFilesDir(),slot);EnvironmentBrowserData.root(global.getCacheDir(),slot);EnvironmentBrowserData.root(global.getFilesDir(),slot);
  }
  static final class Expired extends IOException{}
  static EnvironmentResetPlan begin(Context c,EnvironmentSpec.Identity confirmed)throws Exception{
    int slot=confirmed.slot;
    verifyRoots(c,slot);Context profile=Profiles.context(c,slot);ProfileCatalog catalog=ProfileCatalog.get(c);EnvironmentSpecRepository repository=new EnvironmentSpecRepository(profile);
    JSONObject row=catalog.item(slot);if(row.optBoolean("resetting")){EnvironmentResetPlan plan=repository.resetPlan(new EnvironmentSpec.Identity(slot,row.optInt("generation"),row.getString("environmentId")));if(!plan.before.identity.equals(confirmed))throw new Expired();return plan;}
    return EnvironmentSpecRuntime.withIntent(profile,()->{EnvironmentSpec.Identity expected=catalog.identity(slot);if(!expected.equals(confirmed))throw new Expired();EnvironmentSpecRuntime.reconcileNetwork(profile,expected,"");return repository.beginLoginReset(expected);});
  }
  static void reset(Context c,EnvironmentSpec.Identity confirmed)throws Exception{
    verifyRoots(c,confirmed.slot);Context profile=Profiles.context(c,confirmed.slot);
    // A dedicated lease spans the whole destructive operation, but never blocks
    // the network-intent lease while asking the old provider to stop its IO.
    synchronized(MAINTENANCE_GATES[confirmed.slot]){
      File lease=new File(profile.getNoBackupFilesDir(),"browser-maintenance.lock");if(java.nio.file.Files.isSymbolicLink(lease.toPath()))throw new IOException("维护锁包含链接，未清理数据");
      try(java.io.RandomAccessFile handle=new java.io.RandomAccessFile(lease,"rw");java.nio.channels.FileLock lock=handle.getChannel().lock()){performReset(c,confirmed);}
    }
  }
  private static void performReset(Context c,EnvironmentSpec.Identity confirmed)throws Exception{
    int slot=confirmed.slot;EnvironmentResetPlan plan=begin(c,confirmed);Context profile=Profiles.context(c,slot);ProfileCatalog catalog=ProfileCatalog.get(c);
    Bundle stopped=c.getContentResolver().call(NetworkBridge.uri(c,slot),"stopForReset",null,null);if(stopped==null||!stopped.getBoolean("stopped"))throw new IOException("此环境尚未停止");
    terminate(c,slot);
    // Writers have exited. Freeze the final committed/candidate route without
    // changing its credentials or private subscription snapshots.
    EnvironmentSpecRepository repository=new EnvironmentSpecRepository(profile);
    if(!plan.frozen()){
      final EnvironmentResetPlan started=plan;
      plan=EnvironmentSpecRuntime.withIntent(profile,()->{
        NetworkChanges.recoverIntent(profile,started.before.identity.json(),()->catalog.withReset(started.next,()->null));
        JSONObject queued=NetworkChanges.pendingStrict(profile);JSONObject candidate=queued.optJSONObject("config");if(queued.length()>0&&(candidate==null||!("apply".equals(queued.optString("action"))||"external".equals(queued.optString("action")))))throw new IOException("待应用网络设置无效，原文件保留");
        android.content.SharedPreferences prefs=profile.getSharedPreferences("chat",0);String mode=queued.length()==0?prefs.getString("networkMode","external"):"external".equals(queued.optString("action"))?"external":"internal";
        byte[] active=new SecretStore(profile).get("network");JSONObject network=queued.length()>0?candidate:active==null?new JSONObject():EnvironmentSpecRepository.strictObject(active);
        String proxy=queued.length()>0&&"external".equals(mode)?candidate.optString("proxy"):prefs.getString("proxy","");
        EnvironmentResetPlan frozen=started.freeze(EnvironmentSpecRuntime.binding(started.next,mode,network,proxy),queued);repository.freezeReset(frozen);return frozen;
      });
    }
    verifyRoots(c,slot);catalog.withReset(plan.next,()->null);
    EnvironmentBrowserData.clear(profile.getNoBackupFilesDir(),profile.getCacheDir());
    // These are login-scoped local recovery copies. Saved downloaded files and
    // every network/template/preference record are deliberately outside this set.
    for(String name:new String[]{"conversations.db","deliveries.db","draft-archive.db",ReplyNoticeLedger.DATABASE}){
      File database=profile.getDatabasePath(name);if(java.nio.file.Files.isSymbolicLink(database.getParentFile().toPath()))throw new IOException("网页数据库目录包含链接");
      profile.deleteDatabase(name);for(String suffix:new String[]{"","-wal","-shm","-journal"})if(java.nio.file.Files.exists(new File(database.getPath()+suffix).toPath(),java.nio.file.LinkOption.NOFOLLOW_LINKS))throw new IOException("本地网页数据库尚未清理");
    }
    android.content.SharedPreferences.Editor preferences=profile.getSharedPreferences("chat",0).edit();
    for(String key:new String[]{"pending","legacyPending","sentAttachments","conversation","url","transcript","lastCompletedId","lastNotifiedId","lastReplyNotifiedId","draft","nativeDraft","webDraft"})preferences.remove(key);
    for(String key:profile.getSharedPreferences("chat",0).getAll().keySet())if(key.startsWith("draftBackup:"))preferences.remove(key);
    if(!preferences.commit()||!profile.getSharedPreferences("environment-audit",0).edit().clear().commit())throw new IOException("本地网页记录尚未清理");
    DownloadLibrary.get(c).migrate();DownloadLibrary.get(c).removeEnvironmentTasks(slot);
    if(!profile.getSharedPreferences("download-tasks",0).edit().clear().commit())throw new IOException("文件任务尚未清理");
    NotificationManager notices=c.getSystemService(NotificationManager.class);for(int id=4101;id<=4105;id++)notices.cancel(Profiles.notification(profile,id));
    repository.finishLoginReset(plan);
  }
  static void terminate(Context c,int slot)throws Exception{
    String owner=c.getPackageName()+(slot==0?"":":profile"+slot),children=c.getPackageName()+":gecko_env"+slot+"_";ActivityManager manager=c.getSystemService(ActivityManager.class);long deadline=SystemClock.elapsedRealtime()+10000;
    do{boolean alive=false;List<ActivityManager.RunningAppProcessInfo> all=manager.getRunningAppProcesses();if(all!=null)for(ActivityManager.RunningAppProcessInfo process:all)if(process.uid==android.os.Process.myUid()&&(process.processName.equals(owner)||process.processName.startsWith(children))){if(process.pid==android.os.Process.myPid())throw new IOException("清理必须在独立进程执行");android.os.Process.killProcess(process.pid);alive=true;}if(!alive)return;if(SystemClock.elapsedRealtime()>deadline)throw new IOException("环境进程尚未退出");Thread.sleep(100);}while(true);
  }
}
