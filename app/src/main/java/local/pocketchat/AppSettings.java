package local.pocketchat;
import android.content.*;import android.database.*;import android.database.sqlite.*;

/** Global UI options in the shared catalog, never copied into account or network settings. */
final class AppSettings {
  static final String REPLY_POLICY_VERSION="backgroundReplyPolicyVersion",REPLY_POLICY_ENABLED="backgroundReplyDetection",REPLY_POLICY_REVISION="backgroundReplyPolicyRevision",REPLY_POLICY_PENDING="backgroundReplyLegacyPendingMask";
  static boolean replyPolicyKey(String key){return REPLY_POLICY_VERSION.equals(key)||REPLY_POLICY_ENABLED.equals(key)||REPLY_POLICY_REVISION.equals(key)||REPLY_POLICY_PENDING.equals(key);}
  static String get(Context c,String key,String fallback){UiPerfStats.catalogRead();try(Cursor row=ProfileCatalog.get(c).getReadableDatabase().query("app_settings",new String[]{"value"},"name=?",new String[]{key},null,null,null)){return row.moveToFirst()?row.getString(0):fallback;}}
  static void put(Context c,String key,String value){if(replyPolicyKey(key))throw new IllegalArgumentException("后台回复检测必须通过全局策略保存");ContentValues row=new ContentValues();row.put("name",key);row.put("value",value);ProfileCatalog.get(c).getWritableDatabase().insertWithOnConflict("app_settings",null,row,SQLiteDatabase.CONFLICT_REPLACE);if("starBackground".equals(key))DesignUi.Stars.setting(Boolean.parseBoolean(value));if("backgroundCompletionNotice".equals(key)&&!Boolean.parseBoolean(value))QuietNotifications.clearCompletions(c);}
  /** A single query observes one WAL snapshot; separate key reads can mix revisions. */
  static BackgroundReplyPolicy.Snapshot readBackgroundReplyPolicy(SQLiteDatabase db){
    java.util.Map<String,String> values=new java.util.HashMap<>();UiPerfStats.catalogRead();
    try(Cursor rows=db.query("app_settings",new String[]{"name","value"},"name IN (?,?,?,?)",new String[]{REPLY_POLICY_VERSION,REPLY_POLICY_ENABLED,REPLY_POLICY_REVISION,REPLY_POLICY_PENDING},null,null,null)){
      while(rows.moveToNext())values.put(rows.getString(0),rows.getString(1));
    }
    try{
      String enabled=values.get(REPLY_POLICY_ENABLED);long revision=Long.parseLong(values.get(REPLY_POLICY_REVISION));int pending=Integer.parseInt(values.get(REPLY_POLICY_PENDING));
      if(!"1".equals(values.get(REPLY_POLICY_VERSION))||!("true".equals(enabled)||"false".equals(enabled))||revision<1||pending<0||pending>255)return BackgroundReplyPolicy.Snapshot.unknown();
      return new BackgroundReplyPolicy.Snapshot(true,"true".equals(enabled),revision,pending);
    }catch(RuntimeException invalid){return BackgroundReplyPolicy.Snapshot.unknown();}
  }
  static void writeReplyPolicy(SQLiteDatabase db,String key,String value){ContentValues row=new ContentValues();row.put("name",key);row.put("value",value);if(db.insertWithOnConflict("app_settings",null,row,SQLiteDatabase.CONFLICT_REPLACE)<0)throw new IllegalStateException("后台回复检测设置未能保存");}
  /** Only an absent marker initializes. A partial/corrupt existing record stays off. */
  static BackgroundReplyPolicy.Snapshot initializeBackgroundReplyPolicy(Context c){
    SQLiteDatabase db=ProfileCatalog.get(c).getWritableDatabase();db.beginTransaction();try{
      boolean initialized;try(Cursor row=db.query("app_settings",new String[]{"value"},"name=?",new String[]{REPLY_POLICY_VERSION},null,null,null)){initialized=row.moveToFirst();}
      if(!initialized){writeReplyPolicy(db,REPLY_POLICY_ENABLED,"false");writeReplyPolicy(db,REPLY_POLICY_REVISION,"1");writeReplyPolicy(db,REPLY_POLICY_PENDING,"255");writeReplyPolicy(db,REPLY_POLICY_VERSION,"1");}
      BackgroundReplyPolicy.Snapshot value=readBackgroundReplyPolicy(db);db.setTransactionSuccessful();return value;
    }finally{db.endTransaction();}
  }
  static BackgroundReplyPolicy.Snapshot readBackgroundReplyPolicy(Context c){return readBackgroundReplyPolicy(ProfileCatalog.get(c).getReadableDatabase());}
  static BackgroundReplyPolicy.Snapshot setBackgroundReplyPolicy(Context c,boolean enabled){
    SQLiteDatabase db=ProfileCatalog.get(c).getWritableDatabase();db.beginTransaction();try{
      BackgroundReplyPolicy.Snapshot previous=initializeBackgroundReplyPolicy(c);if(!previous.known)throw new IllegalStateException("后台回复检测设置无法读取，请重试");
      if(previous.enabled!=enabled){if(previous.revision==Long.MAX_VALUE)throw new IllegalStateException("后台回复检测设置版本已达到上限");writeReplyPolicy(db,REPLY_POLICY_ENABLED,String.valueOf(enabled));writeReplyPolicy(db,REPLY_POLICY_REVISION,String.valueOf(previous.revision+1));}
      BackgroundReplyPolicy.Snapshot value=readBackgroundReplyPolicy(db);db.setTransactionSuccessful();return value;
    }finally{db.endTransaction();}
  }
  static void backgroundReplyLegacyCommitted(Context c,int slot){
    if(slot<0||slot>=Profiles.MAX)throw new IllegalArgumentException("环境槽位无效");SQLiteDatabase db=ProfileCatalog.get(c).getWritableDatabase();db.beginTransaction();try{
      BackgroundReplyPolicy.Snapshot previous=readBackgroundReplyPolicy(db);if(!previous.known)return;writeReplyPolicy(db,REPLY_POLICY_PENDING,String.valueOf(previous.legacyPendingMask&~(1<<slot)));db.setTransactionSuccessful();
    }finally{db.endTransaction();}
  }
  static boolean bool(Context c,String key,boolean fallback){return Boolean.parseBoolean(get(c,key,String.valueOf(fallback)));}
  static boolean backgroundCompletionNotice(Context c){return bool(c,"backgroundCompletionNotice",false);}
  static int requestedDefault(Context c){try{return Integer.parseInt(get(c,"defaultSlot","0"));}catch(Exception invalid){return -1;}}
  static boolean eligibleDefault(org.json.JSONObject row){int slot=row.optInt("slot",-1);return slot>=0&&slot<Profiles.MAX&&(android.os.Build.VERSION.SDK_INT>=28||slot==0)&&row.optBoolean("created")&&!row.optBoolean("deleting");}
  static boolean selectable(org.json.JSONObject row){return eligibleDefault(row)&&!row.optBoolean("resetting");}
  static int firstAvailable(org.json.JSONArray rows,int excluded){for(int i=0;i<rows.length();i++){org.json.JSONObject row=rows.optJSONObject(i);if(row!=null&&row.optInt("slot",-1)!=excluded&&selectable(row))return row.optInt("slot");}return -1;}
  static boolean writeDefault(SQLiteDatabase db,int id){ContentValues row=new ContentValues();row.put("name","defaultSlot");row.put("value",String.valueOf(id));return db.insertWithOnConflict("app_settings",null,row,SQLiteDatabase.CONFLICT_REPLACE)>=0;}
  /** Invalid legacy selections are repaired once, before a deleted slot can be reused. */
  static int defaultSlot(Context c){
    ProfileCatalog catalog=ProfileCatalog.get(c);int requested=requestedDefault(c);
    if(selectable(catalog.item(requested)))return requested;
    SQLiteDatabase db=catalog.getWritableDatabase();db.beginTransaction();try{
      requested=requestedDefault(c);org.json.JSONObject row=catalog.item(requested);int selected=selectable(row)?requested:firstAvailable(catalog.list(),-1);
      boolean transientReset=eligibleDefault(row)&&row.optBoolean("resetting");
      if(selected!=requested&&!transientReset&&!writeDefault(db,selected))return -1;
      db.setTransactionSuccessful();return selected;
    }finally{db.endTransaction();}
  }
  static boolean defaultSlot(Context c,int id){
    ProfileCatalog catalog=ProfileCatalog.get(c);SQLiteDatabase db=catalog.getWritableDatabase();db.beginTransaction();try{
      if(!selectable(catalog.item(id))||!writeDefault(db,id))return false;
      db.setTransactionSuccessful();return true;
    }finally{db.endTransaction();}
  }
  static int recentSlot(Context c){int selected=defaultSlot(c);long latest=0;org.json.JSONArray rows=ProfileCatalog.get(c).list();for(int i=0;i<rows.length();i++){org.json.JSONObject row=rows.optJSONObject(i);if(selectable(row)&&row.optLong("opened")>latest){selected=row.optInt("slot");latest=row.optLong("opened");}}return selected;}


}
