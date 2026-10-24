package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import org.json.*;
import java.util.*;

/** Shared metadata only. Cookies, chats and sealed settings remain profile-local. */
final class ProfileCatalog extends SQLiteOpenHelper {
  static ProfileCatalog instance;final Context root;
  static synchronized ProfileCatalog get(Context c){if(instance==null)instance=new ProfileCatalog(Profiles.global(c));return instance;}
  static final int SCHEMA=8;
  ProfileCatalog(Context c){super(c,"environment-catalog.db",null,SCHEMA);root=c;setWriteAheadLoggingEnabled(true);}
  public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE environments (slot INTEGER PRIMARY KEY,name TEXT NOT NULL,created INTEGER NOT NULL DEFAULT 0,draft TEXT NOT NULL DEFAULT '',pid INTEGER NOT NULL DEFAULT 0,seen INTEGER NOT NULL DEFAULT 0,connected INTEGER NOT NULL DEFAULT 0,waiting INTEGER NOT NULL DEFAULT 0,mode TEXT NOT NULL DEFAULT '',privacy INTEGER NOT NULL DEFAULT 1,opened INTEGER NOT NULL DEFAULT 0,favorite INTEGER NOT NULL DEFAULT 0,problem TEXT NOT NULL DEFAULT '',page TEXT NOT NULL DEFAULT '原网页',group_name TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',desktop INTEGER NOT NULL DEFAULT 0,generation INTEGER NOT NULL DEFAULT 0,deleting INTEGER NOT NULL DEFAULT 0,environment_id TEXT NOT NULL DEFAULT '',resetting INTEGER NOT NULL DEFAULT 0)");db.execSQL("CREATE TABLE app_settings(name TEXT PRIMARY KEY,value TEXT NOT NULL)");SharedPreferences old=root.getSharedPreferences("browser-environment-names",0);for(int i=0;i<Profiles.MAX;i++){SharedPreferences p=Profiles.context(root,i).getSharedPreferences("chat",0);ContentValues v=new ContentValues();v.put("slot",i);v.put("environment_id",UUID.randomUUID().toString());v.put("name",old.getString("name"+i,i==0?"默认环境":"环境 "+(i+1)));v.put("created",i==0||p.getBoolean("environmentInitialized",false)||p.getBoolean("networkConfigured",false)?1:0);db.insert("environments",null,v);}}
  public void onUpgrade(SQLiteDatabase db,int old,int next){if(old<2){db.execSQL("ALTER TABLE environments ADD COLUMN opened INTEGER NOT NULL DEFAULT 0");db.execSQL("ALTER TABLE environments ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0");}if(old<3){db.execSQL("ALTER TABLE environments ADD COLUMN problem TEXT NOT NULL DEFAULT ''");db.execSQL("ALTER TABLE environments ADD COLUMN page TEXT NOT NULL DEFAULT '原网页'");db.execSQL("CREATE TABLE app_settings(name TEXT PRIMARY KEY,value TEXT NOT NULL)");}if(old<4){db.execSQL("ALTER TABLE environments ADD COLUMN group_name TEXT NOT NULL DEFAULT ''");db.execSQL("ALTER TABLE environments ADD COLUMN notes TEXT NOT NULL DEFAULT ''");}if(old<5)db.execSQL("ALTER TABLE environments ADD COLUMN desktop INTEGER NOT NULL DEFAULT 0");if(old<6){db.execSQL("ALTER TABLE environments ADD COLUMN generation INTEGER NOT NULL DEFAULT 0");db.execSQL("ALTER TABLE environments ADD COLUMN deleting INTEGER NOT NULL DEFAULT 0");}if(old<7){db.execSQL("ALTER TABLE environments ADD COLUMN environment_id TEXT NOT NULL DEFAULT ''");try(Cursor rows=db.query("environments",new String[]{"slot"},null,null,null,null,null)){while(rows.moveToNext()){ContentValues values=new ContentValues();values.put("environment_id",UUID.randomUUID().toString());db.update("environments",values,"slot=?",new String[]{String.valueOf(rows.getInt(0))});}}}if(old<8)db.execSQL("ALTER TABLE environments ADD COLUMN resetting INTEGER NOT NULL DEFAULT 0");}
  JSONObject item(int slot){UiPerfStats.catalogRead();try(Cursor c=getReadableDatabase().query("environments",null,"slot=?",new String[]{String.valueOf(slot)},null,null,null)){return c.moveToFirst()?row(c):new JSONObject();}}
  static JSONObject row(Cursor c){return J.obj("slot",c.getInt(c.getColumnIndexOrThrow("slot")),"name",c.getString(c.getColumnIndexOrThrow("name")),"created",c.getInt(c.getColumnIndexOrThrow("created"))==1,"draft",c.getString(c.getColumnIndexOrThrow("draft")),"pid",c.getInt(c.getColumnIndexOrThrow("pid")),"seen",c.getLong(c.getColumnIndexOrThrow("seen")),"connected",c.getInt(c.getColumnIndexOrThrow("connected"))==1,"waiting",c.getInt(c.getColumnIndexOrThrow("waiting"))==1,"mode",c.getString(c.getColumnIndexOrThrow("mode")),"opened",c.getLong(c.getColumnIndexOrThrow("opened")),"favorite",c.getInt(c.getColumnIndexOrThrow("favorite"))==1,"problem",c.getString(c.getColumnIndexOrThrow("problem")),"page",c.getString(c.getColumnIndexOrThrow("page")),"privacy",c.getInt(c.getColumnIndexOrThrow("privacy")),"group",c.getString(c.getColumnIndexOrThrow("group_name")),"notes",c.getString(c.getColumnIndexOrThrow("notes")),"desktopSite",c.getInt(c.getColumnIndexOrThrow("desktop"))==1,"generation",c.getInt(c.getColumnIndexOrThrow("generation")),"deleting",c.getInt(c.getColumnIndexOrThrow("deleting"))==1,"environmentId",c.getString(c.getColumnIndexOrThrow("environment_id")),"resetting",c.getInt(c.getColumnIndexOrThrow("resetting"))==1);}
  JSONArray list(){JSONArray out=new JSONArray();try(Cursor c=getReadableDatabase().query("environments",null,null,null,null,null,"slot ASC")){while(c.moveToNext())out.put(row(c));}return out;}
  String name(int slot){return item(slot).optString("name",slot==0?"默认环境":"环境 "+(slot+1));}
  void rename(int slot,String name){String text=name.trim();if(text.isEmpty()||text.length()>24)return;ContentValues v=new ContentValues();v.put("name",text);getWritableDatabase().update("environments",v,"slot=?",new String[]{String.valueOf(slot)});}
  void details(int slot,String group,String notes){ContentValues v=new ContentValues();v.put("group_name",group.trim());v.put("notes",notes.trim());getWritableDatabase().update("environments",v,"slot=?",new String[]{String.valueOf(slot)});}
  void browserDisplay(int slot,boolean desktop){ContentValues v=new ContentValues();v.put("desktop",desktop?1:0);getWritableDatabase().update("environments",v,"slot=?",new String[]{String.valueOf(slot)});}
  void created(int slot){
    SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{
      JSONObject current=item(slot);
      if(current.length()==0||(current.optBoolean("deleting")||current.optBoolean("resetting")))throw new IllegalStateException("环境不存在或正在删除");
      ContentValues values=new ContentValues();values.put("created",1);
      if(!current.optBoolean("created")||current.optString("environmentId").isEmpty())values.put("environment_id",UUID.randomUUID().toString());
      db.update("environments",values,"slot=? AND deleting=0 AND resetting=0",new String[]{String.valueOf(slot)});
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
  }
  EnvironmentSpec.Identity identity(int slot)throws java.io.IOException{
    JSONObject current=item(slot);
    if(!current.optBoolean("created")||(current.optBoolean("deleting")||current.optBoolean("resetting")))throw new java.io.IOException("环境已删除或尚未创建");
    try{return new EnvironmentSpec.Identity(slot,current.optInt("generation"),current.getString("environmentId"));}
    catch(Exception invalid){throw new java.io.IOException("环境身份无效",invalid);}
  }
  interface IdentityAction<T>{T run()throws Exception;}
  /** Holds SQLite's cross-process writer transaction while sealed state is read/written.
   * Deletion cannot invalidate this identity halfway through an encrypted write. */
  <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{
    SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{
      if(!identity(expected.slot).equals(expected))throw new java.io.IOException("环境已改变，请重新读取配置");
      T result=action.run();db.setTransactionSuccessful();return result;
    }finally{db.endTransaction();}
  }
  /** Reserve an unused slot while its fresh, non-login configuration is written. */
  <T>T createNew(int slot,IdentityAction<T> action)throws Exception{
    SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{
      JSONObject current=item(slot);if(current.length()==0||current.optBoolean("created")||current.optBoolean("deleting")||current.optBoolean("resetting"))throw new java.io.IOException("目标槽位已变化，请重新复制");
      ContentValues values=new ContentValues();values.put("created",1);values.put("environment_id",UUID.randomUUID().toString());db.update("environments",values,"slot=?",new String[]{String.valueOf(slot)});
      T result=action.run();db.setTransactionSuccessful();return result;
    }finally{db.endTransaction();}
  }
  void beginReset(EnvironmentSpec.Identity expected)throws Exception{
    withIdentity(expected,()->{if(expected.generation==Integer.MAX_VALUE)throw new java.io.IOException("环境代际已达到上限");ContentValues values=new ContentValues();values.put("resetting",1);values.put("generation",expected.generation+1);values.put("connected",0);values.put("waiting",0);getWritableDatabase().update("environments",values,"slot=?",new String[]{String.valueOf(expected.slot)});return null;});
  }
  <T>T withReset(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{
    SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{
      JSONObject row=item(expected.slot);if(!row.optBoolean("created")||row.optBoolean("deleting")||!row.optBoolean("resetting")||row.optInt("generation")!=expected.generation||!row.optString("environmentId").equals(expected.environmentId))throw new java.io.IOException("登录重置身份已变化");
      T result=action.run();db.setTransactionSuccessful();return result;
    }finally{db.endTransaction();}
  }
  void completeReset(EnvironmentSpec.Identity expected,boolean desktop)throws Exception{
    withReset(expected,()->{ContentValues values=new ContentValues();values.put("resetting",0);values.put("draft","");values.put("pid",0);values.put("seen",0);values.put("connected",0);values.put("waiting",0);values.put("problem","");values.put("desktop",desktop?1:0);getWritableDatabase().update("environments",values,"slot=?",new String[]{String.valueOf(expected.slot)});return null;});
  }
  boolean available(int slot){JSONObject row=item(slot);return row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting");}
  void draft(int slot,JSONObject value){ContentValues v=new ContentValues();v.put("draft",value==null?"":value.toString());getWritableDatabase().update("environments",v,"slot=?",new String[]{String.valueOf(slot)});}
  void opened(int slot){ContentValues v=new ContentValues();v.put("opened",System.currentTimeMillis());getWritableDatabase().update("environments",v,"slot=?",new String[]{String.valueOf(slot)});}
  void favorite(int slot,boolean value){ContentValues v=new ContentValues();v.put("favorite",value?1:0);getWritableDatabase().update("environments",v,"slot=?",new String[]{String.valueOf(slot)});}
  int group(Collection<Integer> slots,String value){
    String group=value==null?"":value.trim();
    if(group.length()>12)throw new IllegalArgumentException("分组最多 12 字");
    ContentValues values=new ContentValues();values.put("group_name",group);
    return updateCreated(slots,values);
  }
  int favorites(Collection<Integer> slots,boolean favorite){
    ContentValues values=new ContentValues();values.put("favorite",favorite?1:0);
    return updateCreated(slots,values);
  }
  private int updateCreated(Collection<Integer> slots,ContentValues values){
    if(slots==null||slots.isEmpty())return 0;
    SQLiteDatabase db=getWritableDatabase();int changed=0;
    db.beginTransaction();
    try{
      for(Integer slot:new LinkedHashSet<>(slots)){
        if(slot==null||slot<0||slot>=Profiles.MAX)continue;
        changed+=db.update("environments",values,"slot=? AND created=1",new String[]{String.valueOf(slot)});
      }
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    return changed;
  }
  void beginDelete(int slot)throws java.io.IOException{
    SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{
      JSONObject row=item(slot);if(row.optBoolean("deleting")){db.setTransactionSuccessful();return;}
      if(!row.optBoolean("created")||row.optBoolean("resetting"))throw new java.io.IOException("此环境已删除或正在重置登录");
      int count=0;JSONArray rows=list();for(int i=0;i<rows.length();i++)if(rows.optJSONObject(i).optBoolean("created"))count++;
      if(count<=1)throw new java.io.IOException("请至少保留一个环境，先新建环境后再删除");
      int selectedDefault=AppSettings.defaultSlot(root);if(selectedDefault<0&&AppSettings.firstAvailable(rows,-1)>=0)throw new java.io.IOException("默认环境暂时无法更新，环境尚未删除");int storedDefault=AppSettings.requestedDefault(root);JSONObject defaultRow=item(storedDefault);EnvironmentSpec.Identity previousDefault=!AppSettings.eligibleDefault(defaultRow)?null:new EnvironmentSpec.Identity(storedDefault,defaultRow.optInt("generation"),defaultRow.optString("environmentId"));
      if(row.optInt("generation")==Integer.MAX_VALUE)throw new java.io.IOException("环境代际已达到上限");
      ContentValues v=new ContentValues();v.put("created",0);v.put("deleting",1);v.put("generation",row.optInt("generation")+1);v.put("connected",0);v.put("waiting",0);db.update("environments",v,"slot=?",new String[]{String.valueOf(slot)});
      if(previousDefault!=null&&previousDefault.slot==slot&&!AppSettings.writeDefault(db,AppSettings.firstAvailable(rows,slot)))throw new java.io.IOException("默认环境暂时无法更新，环境尚未删除");
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
  }
  void completeDelete(int slot){ContentValues v=new ContentValues();v.put("environment_id","");v.put("name",slot==0?"默认环境":"环境 "+(slot+1));v.put("created",0);v.put("deleting",0);v.put("resetting",0);v.put("draft","");v.put("pid",0);v.put("seen",0);v.put("connected",0);v.put("waiting",0);v.put("mode","");v.put("privacy",1);v.put("opened",0);v.put("favorite",0);v.put("problem","");v.put("page","原网页");v.put("group_name","");v.put("notes","");v.put("desktop",0);getWritableDatabase().update("environments",v,"slot=? AND deleting=1",new String[]{String.valueOf(slot)});}
  final java.util.concurrent.ExecutorService heartbeatWriter=java.util.concurrent.Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"environment-heartbeat");t.setPriority(Thread.MIN_PRIORITY);return t;});
  final Object heartbeatGate=new Object(),heartbeatIo=new Object();
  final Map<Integer,Long> heartbeatSeen=new HashMap<>(),heartbeatRevisions=new HashMap<>();
  final Map<Integer,String> heartbeatSignatures=new HashMap<>();
  final LinkedHashMap<Integer,Heartbeat> pendingHeartbeats=new LinkedHashMap<>();
  long heartbeatRevision;volatile boolean heartbeatScheduled;
  static final class Heartbeat {
    final int slot,generation;final long revision;final ContentValues values;
    Heartbeat(int slot,int generation,long revision,ContentValues values){this.slot=slot;this.generation=generation;this.revision=revision;this.values=values;}
  }
  void heartbeat(ChatSession s,boolean force){
    String mode=s.internalNetwork()?"内置网络":s.prefs.getString("proxy","").isEmpty()?"手机网络":"应用代理";
    String problem=s.offline?"网络已断开":s.navigationFailed?"网页加载失败":!s.networkIssue.isEmpty()?"连接需处理":"";
    String page="原网页";
    int slot=Profiles.slot(s.context);long now=System.currentTimeMillis();
    String signature=s.environmentGeneration+"|"+s.networkReady+"|"+(s.pending!=null)+"|"+mode+"|"+s.privacy.level()+"|"+problem+"|"+page;
    ContentValues values=new ContentValues();values.put("pid",android.os.Process.myPid());values.put("seen",now);
    values.put("connected",s.networkReady&&!s.offline&&problem.isEmpty()?1:0);values.put("waiting",s.pending==null?0:1);
    values.put("mode",mode);values.put("problem",problem);values.put("page",page);values.put("privacy",s.privacy.level());
    Heartbeat next;
    synchronized(heartbeatGate){
      if(!force&&signature.equals(heartbeatSignatures.get(slot))&&now-heartbeatSeen.getOrDefault(slot,0L)<5000)return;
      heartbeatSeen.put(slot,now);heartbeatSignatures.put(slot,signature);
      long revision=++heartbeatRevision;heartbeatRevisions.put(slot,revision);next=new Heartbeat(slot,s.environmentGeneration,revision,values);
      pendingHeartbeats.remove(slot);
      if(!force){pendingHeartbeats.put(slot,next);if(!heartbeatScheduled){heartbeatScheduled=true;heartbeatWriter.execute(this::drainHeartbeats);}return;}
    }
    writeHeartbeat(next);
  }
  void drainHeartbeats(){
    for(;;){Heartbeat next;
      synchronized(heartbeatGate){if(pendingHeartbeats.isEmpty()){heartbeatScheduled=false;return;}Integer slot=pendingHeartbeats.keySet().iterator().next();next=pendingHeartbeats.remove(slot);}
      try{writeHeartbeat(next);}catch(Exception ignored){}
    }
  }
  void writeHeartbeat(Heartbeat next){
    synchronized(heartbeatIo){
      synchronized(heartbeatGate){if(!Objects.equals(heartbeatRevisions.get(next.slot),next.revision))return;}
      UiPerfStats.heartbeatWrite();
      getWritableDatabase().update("environments",next.values,"slot=? AND generation=? AND created=1 AND deleting=0 AND resetting=0",new String[]{String.valueOf(next.slot),String.valueOf(next.generation)});
    }
  }
}
