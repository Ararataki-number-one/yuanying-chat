package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import org.json.*;

/** Shared file index only: no cookies, chat content or signed source URLs. */
final class DownloadLibrary extends SQLiteOpenHelper {
  private enum IndexWrite { CURRENT, LEGACY, REPAIR, DURABLE_SAVE }
  static DownloadLibrary instance;final Context root;
  private final java.util.Map<Integer,String> replayedTaskDigests=new java.util.concurrent.ConcurrentHashMap<>();
  static synchronized DownloadLibrary get(Context c){if(instance==null)instance=new DownloadLibrary(Profiles.global(c));return instance;}
  DownloadLibrary(Context c){super(c,"saved-download-library.db",null,4);root=c;}
  public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE files (slot INTEGER NOT NULL,uri TEXT NOT NULL,row TEXT NOT NULL,time INTEGER NOT NULL,PRIMARY KEY(slot,uri))");createTasks(db);createDeleted(db);createIndexes(db);}
  static void createTasks(SQLiteDatabase db){db.execSQL("CREATE TABLE tasks(slot INTEGER NOT NULL,id TEXT NOT NULL,row TEXT NOT NULL,time INTEGER NOT NULL,PRIMARY KEY(slot,id))");}
  static void createDeleted(SQLiteDatabase db){db.execSQL("CREATE TABLE deleted_files(uri TEXT PRIMARY KEY NOT NULL,time INTEGER NOT NULL)");}
  static void createIndexes(SQLiteDatabase db){db.execSQL("CREATE INDEX files_uri_time ON files(uri,time DESC)");db.execSQL("CREATE INDEX files_time ON files(time DESC)");db.execSQL("CREATE INDEX tasks_time ON tasks(time DESC)");}
  public void onUpgrade(SQLiteDatabase db,int old,int next){if(old<2)createTasks(db);if(old<3)createDeleted(db);if(old<4)createIndexes(db);}
  static void changed(Context context){DownloadLibraryChanges.changed(context);}
  boolean isRemoved(JSONObject row){return removed(getReadableDatabase(),row);}
  long publicationTime(android.net.Uri uri){long time=System.currentTimeMillis();SQLiteDatabase db=getReadableDatabase();try(Cursor c=db.query("deleted_files",new String[]{"time"},"uri=?",new String[]{uri.toString()},null,null,null)){if(c.moveToFirst())time=Math.max(time,c.getLong(0)+1);}JSONObject current=newest(db,uri.toString());if(current!=null)time=Math.max(time,current.optLong("time")+1);return time;}
  boolean indexed(android.net.Uri uri){try(Cursor c=getReadableDatabase().query("files",new String[]{"uri"},"uri=?",new String[]{uri.toString()},null,null,null)){return c.moveToFirst();}}
  static JSONObject newest(SQLiteDatabase db,String uri){try(Cursor c=db.query("files",new String[]{"row"},"uri=?",new String[]{uri},null,null,"time DESC","1")){return c.moveToFirst()?J.parse(c.getString(0)):null;}}
  static boolean removed(SQLiteDatabase db,JSONObject row){
    if(row==null||row.optString("uri").isEmpty())return false;
    try(Cursor c=db.query("deleted_files",new String[]{"time"},"uri=?",new String[]{row.optString("uri")},null,null,null)){if(c.moveToFirst()&&row.optLong("time")<=c.getLong(0))return true;}
    JSONObject current=newest(db,row.optString("uri"));return current!=null&&(row.optLong("time")<current.optLong("time"));
  }
  static boolean conflicting(SQLiteDatabase db,JSONObject row){if(row.optString("uri").isEmpty())return false;JSONObject current=newest(db,row.optString("uri"));return current!=null&&row.optLong("time")==current.optLong("time")&&!row.optString("id").equals(current.optString("id"));}
  JSONObject saved(JSONObject row){if(removed(getReadableDatabase(),row)||conflicting(getReadableDatabase(),row))return null;try(Cursor c=getReadableDatabase().query("files",new String[]{"row"},"slot=? AND uri=?",new String[]{String.valueOf(row.optInt("slot")),row.optString("uri")},null,null,null)){if(!c.moveToFirst())return null;JSONObject current=J.parse(c.getString(0));return current.optString("id").equals(row.optString("id"))&&current.optLong("time")==row.optLong("time")?current:null;}}
  void removeSaved(JSONObject row){
    SQLiteDatabase db=getWritableDatabase();String uri=row.optString("uri");db.beginTransaction();
    try{
      long cutoff=Math.max(System.currentTimeMillis(),row.optLong("time"));
      try(Cursor old=db.query("deleted_files",new String[]{"time"},"uri=?",new String[]{uri},null,null,null)){if(old.moveToFirst())cutoff=Math.max(cutoff,old.getLong(0));}
      ContentValues v=new ContentValues();v.put("uri",uri);v.put("time",cutoff);db.insertWithOnConflict("deleted_files",null,v,SQLiteDatabase.CONFLICT_REPLACE);
      db.delete("files","uri=?",new String[]{uri});
      java.util.List<String[]> keys=new java.util.ArrayList<>();
      try(Cursor tasks=db.query("tasks",new String[]{"slot","id","row"},null,null,null,null,null)){while(tasks.moveToNext())if(uri.equals(J.parse(tasks.getString(2)).optString("uri")))keys.add(new String[]{tasks.getString(0),tasks.getString(1)});}
      for(String[] key:keys)db.delete("tasks","slot=? AND id=?",key);
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    changed(root);
  }
  JSONArray prune(JSONArray rows){
    java.util.Map<String,Long> deleted=new java.util.HashMap<>();
    try(Cursor c=getReadableDatabase().query("deleted_files",new String[]{"uri","time"},null,null,null,null,null)){while(c.moveToNext())deleted.put(c.getString(0),c.getLong(1));}
    java.util.Map<String,JSONObject> current=new java.util.HashMap<>();
    try(Cursor c=getReadableDatabase().query("files",new String[]{"row"},null,null,null,null,"time ASC")){while(c.moveToNext()){JSONObject row=J.parse(c.getString(0));current.put(row.optString("uri"),row);}}
    JSONArray kept=new JSONArray();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null)continue;String uri=row.optString("uri");Long cutoff=deleted.get(uri);JSONObject last=current.get(uri);if((cutoff==null||row.optLong("time")>cutoff)&&(last==null||row.optLong("time")>last.optLong("time")||row.optLong("time")==last.optLong("time")&&row.optString("id").equals(last.optString("id"))))kept.put(row);}return kept;
  }
  static void retireTasks(SQLiteDatabase db,JSONObject current){
    java.util.List<String[]> keys=new java.util.ArrayList<>();
    try(Cursor tasks=db.query("tasks",new String[]{"slot","id","row"},null,null,null,null,null)){
      while(tasks.moveToNext()){
        JSONObject row=J.parse(tasks.getString(2));
        if(current.optString("uri").equals(row.optString("uri"))&&(row.optLong("time")<current.optLong("time")||row.optLong("time")==current.optLong("time")&&!row.optString("id").equals(current.optString("id"))))keys.add(new String[]{tasks.getString(0),tasks.getString(1)});
      }
    }
    for(String[] key:keys)db.delete("tasks","slot=? AND id=?",key);
  }
  void add(Context c,JSONObject row){add(c,row,IndexWrite.CURRENT);}
  private void add(Context c,JSONObject row,IndexWrite write){
    if(row==null)return;String uri=row.optString("uri");if(uri.isEmpty()||!"saved".equals(row.optString("state","saved")))return;
    int slot=Profiles.slot(c);
    SQLiteDatabase db=getWritableDatabase();boolean changed=false;JSONObject published=null;db.beginTransaction();
    try{
      if(removed(db,row)||conflicting(db,row)){db.setTransactionSuccessful();return;}
      JSONObject current=newest(db,uri);long time=DownloadListPolicy.preservedTime(row,current);
      boolean staleTask=false;
      if(write==IndexWrite.REPAIR||write==IndexWrite.DURABLE_SAVE){
        if(current!=null||tombstoned(db,uri)){db.setTransactionSuccessful();return;}
        JSONObject task=indexedTask(db,slot,row.optString("id"));
        staleTask=write==IndexWrite.DURABLE_SAVE&&olderOwnedTask(row,task);
        if(task!=null&&!staleTask&&(!"saved".equals(task.optString("state"))||!sameOwnedPublication(row,task))){db.setTransactionSuccessful();return;}
      }
      if(write==IndexWrite.LEGACY&&current!=null&&time<=current.optLong("time")){db.setTransactionSuccessful();return;}
      JSONObject safe=J.obj("slot",slot,"id",row.optString("id"),"name",row.optString("name","文件"),"mime",row.optString("mime","application/octet-stream"),"uri",uri,"state","saved","location",row.optString("location","原先选择的保存位置"),"time",time);
      DownloadMetadataValues.copy(row,safe);DownloadMetadataValues.merge(safe,current);
      // A history scan must not manufacture a newer download or rewrite an unchanged file.
      if(current!=null&&sameFile(safe,current)){db.setTransactionSuccessful();return;}
      ContentValues values=new ContentValues();values.put("slot",slot);values.put("uri",uri);values.put("row",safe.toString());values.put("time",time);
      if(current!=null&&time>current.optLong("time"))db.delete("files","uri=?",new String[]{uri});
      if(db.insertWithOnConflict("files",null,values,SQLiteDatabase.CONFLICT_REPLACE)<0)throw new IllegalStateException("Saved download was not indexed");
      if(write==IndexWrite.CURRENT&&(current==null||time>current.optLong("time")))retireTasks(db,safe);
      if(staleTask)db.delete("tasks","slot=? AND id=?",new String[]{String.valueOf(slot),row.optString("id")});
      changed=true;published=safe;db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    if(changed){changed(root);SavedDownloadMetadata.added(root,published);}
  }
  static boolean sameFile(JSONObject a,JSONObject b){return a.optInt("slot")==b.optInt("slot")&&a.optLong("time")==b.optLong("time")&&same(a,b,"id","name","mime","uri","state","location")&&DownloadMetadataValues.same(a,b);}
  static boolean same(JSONObject a,JSONObject b,String... fields){for(String name:fields)if(!a.optString(name).equals(b.optString(name)))return false;return true;}
  void sync(Context c,JSONArray rows){sync(c,rows,IndexWrite.CURRENT);}
  private void sync(Context c,JSONArray rows,IndexWrite write){
    SQLiteDatabase db=getWritableDatabase();int slot=Profiles.slot(c);boolean changed=false;db.beginTransaction();
    try{
      java.util.Map<String,JSONObject> current=new java.util.HashMap<>();
      try(Cursor prior=db.query("tasks",new String[]{"id","row"},"slot=?",new String[]{String.valueOf(slot)},null,null,null)){while(prior.moveToNext())current.put(prior.getString(0),J.parse(prior.getString(1)));}
      for(int i=0;i<rows.length();i++){
        JSONObject r=rows.optJSONObject(i);if(r==null||r.optString("id").isEmpty()||removed(db,r)||conflicting(db,r))continue;
        JSONObject safe=J.obj("slot",slot,"id",r.optString("id"),"name",r.optString("name","文件"),"mime",r.optString("mime","application/octet-stream"),"uri",r.optString("uri"),"state",r.optString("state"),"reason",r.optString("reason"),"location",r.optString("location"),"time",r.optLong("time"),"received",r.optLong("received"),"total",r.optLong("total",-1));
        String id=r.optString("id");JSONObject old=current.get(id);
        if(write!=IndexWrite.CURRENT&&old!=null)continue;
        if(write==IndexWrite.REPAIR&&coveredByOtherPublication(db,r))continue;
        DownloadMetadataValues.copy(r,safe);DownloadMetadataValues.merge(safe,old);
        if(old!=null&&sameFile(safe,old)&&same(safe,old,"reason")&&safe.optLong("received")==old.optLong("received")&&safe.optLong("total",-1)==old.optLong("total",-1))continue;
        DownloadTasks.put(safe,"updated",System.currentTimeMillis());ContentValues v=new ContentValues();v.put("slot",slot);v.put("id",id);v.put("row",safe.toString());v.put("time",r.optLong("time"));
        if(db.insertWithOnConflict("tasks",null,v,SQLiteDatabase.CONFLICT_REPLACE)<0)throw new IllegalStateException("Download task was not indexed");
        if(write!=IndexWrite.CURRENT)current.put(id,safe);
        changed=true;
      }
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    if(changed)changed(root);
  }
  JSONArray tasks(){migrate();migrateTasks();JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().query("tasks",new String[]{"row"},null,null,null,null,"time DESC")){while(c.moveToNext())rows.put(J.parse(c.getString(0)));}return prune(rows);}
  void migrate(){migrate(false);replayDurableSavedTasks();}
  private void replayDurableSavedTasks(){
    for(int slot=0;slot<Profiles.MAX;slot++){
      try{
        Context context=Profiles.context(root,slot);
        String durable=DownloadTasks.durableRows(context);
        String digest=Base64.getEncoder().encodeToString(
            MessageDigest.getInstance("SHA-256").digest(durable.getBytes(StandardCharsets.UTF_8)));
        if(digest.equals(replayedTaskDigests.get(slot)))continue;
        JSONArray rows=new JSONArray(durable);
        if(rows.length()>0){
          ProfileCatalog catalog=ProfileCatalog.get(root);
          EnvironmentSpec.Identity owner=catalog.identity(slot);
          catalog.withIdentity(owner,()->{
            JSONArray owned=ownedRows(rows,owner,IndexWrite.REPAIR);
            for(int i=0;i<owned.length();i++){
              JSONObject row=owned.optJSONObject(i);
              if("saved".equals(row.optString("state"))&&row.optLong("time")>0
                  &&row.optString("uri").startsWith("content://"))add(context,row,IndexWrite.DURABLE_SAVE);
            }
            return null;
          });
        }
        replayedTaskDigests.put(slot,digest);
      }catch(Exception failure){/* Keep this snapshot retryable when the index or owner cannot be read. */}
    }
  }
  private void migrate(boolean taskIndex){
    SharedPreferences migration=root.getSharedPreferences("download-library-migration",0);
    for(int slot=0;slot<Profiles.MAX;slot++){
      try{migrateSlot(migration,slot,taskIndex);}
      catch(Exception failure){/* Keep pending so a later read can retry this slot. */}
    }
  }
  static final class LegacyHistoryUnreadable extends IllegalStateException {
    LegacyHistoryUnreadable(Exception cause){super("旧下载记录无法读取",cause);}
  }
  void preflightRemoval(int slot){
    Context context=Profiles.context(root,slot);
    legacyHistory(context);
    legacyTasks(context);
  }
  void migrateBeforeRemoval(int slot){
    // New records can exist after the one-time migration marker. Re-read both
    // sources after stopping the target writers, before clearing private data.
    Context context=Profiles.context(root,slot);
    JSONArray history=legacyHistory(context),tasks=legacyTasks(context);
    addLegacySaved(context,history,false,IndexWrite.LEGACY);
    addLegacySaved(context,tasks,true,IndexWrite.LEGACY);
  }
  private void migrateSlot(SharedPreferences migration,int slot,boolean taskIndex)throws Exception{
    String key=(taskIndex?"tasksSlot":"slot")+slot;
    String reconciled=key+"Reconciled";
    if(migration.getBoolean(reconciled,false))return;
    Context context=Profiles.context(root,slot);
    if((taskIndex||legacyHistory(context).length()==0)&&legacyTasks(context).length()==0)return;
    ProfileCatalog catalog=ProfileCatalog.get(root);
    EnvironmentSpec.Identity owner=catalog.identity(slot);
    // Reset/delete cannot run between validating the owner and writing its legacy rows.
    catalog.withIdentity(owner,()->{
      if(migration.getBoolean(reconciled,false))return null;
      boolean previouslyMarked=migration.getBoolean(key,false);
      IndexWrite write=previouslyMarked?IndexWrite.REPAIR:IndexWrite.LEGACY;
      migrateLegacy(context,taskIndex,owner,write);
      if(!migration.edit().putBoolean(key,true).putBoolean(reconciled,true).commit()){
        // commit(false) can still change memory. Leave the flags retryable.
        migration.edit().putBoolean(key,previouslyMarked).putBoolean(reconciled,false).commit();
        throw new IllegalStateException("Download migration marker was not persisted");
      }
      return null;
    });
  }
  private void migrateLegacy(Context context,boolean taskIndex,EnvironmentSpec.Identity owner,IndexWrite write){
    if(taskIndex){sync(context,ownedRows(legacyTasks(context),owner,write),write);return;}
    // A malformed task source must not block independently readable owned history.
    JSONArray history=legacyHistory(context);
    addLegacySaved(context,ownedRows(history,owner,write),false,write);
    addLegacySaved(context,ownedRows(legacyTasks(context),owner,write),true,write);
    if(write==IndexWrite.LEGACY)addPreOwnerHistory(context,history,owner);
  }
  private static JSONArray ownedRows(JSONArray rows,EnvironmentSpec.Identity owner,IndexWrite write){
    JSONArray owned=new JSONArray();
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(row==null)continue;
      boolean exact=matchesInteger(row.opt("slot"),owner.slot)&&matchesInteger(row.opt("environmentGeneration"),owner.generation)
          &&owner.environmentId.equals(row.opt("environmentId"));
      // Retain first-import compatibility for genuinely old data from an untouched slot.
      boolean unbound=write==IndexWrite.LEGACY&&owner.generation==0&&savedInSlot(row,owner.slot)
          &&withoutEnvironmentId(row)&&!row.has("environmentGeneration");
      if(unbound||(exact&&(write!=IndexWrite.REPAIR||!row.optString("id").isEmpty())))owned.put(row);
    }
    return owned;
  }
  private void addPreOwnerHistory(Context context,JSONArray history,EnvironmentSpec.Identity owner){
    // Login reset keeps saved history. Index pre-owner files without assigning
    // them to the new generation; never revive their old active tasks.
    for(int i=0;i<history.length();i++){
      JSONObject row=history.optJSONObject(i);
      if(row==null||!savedInSlot(row,owner.slot)||!withoutEnvironmentId(row))continue;
      Object generation=row.opt("environmentGeneration");
      boolean preOwner=row.has("environmentGeneration")
          ?isInteger(generation)&&row.optLong("environmentGeneration")>=0&&row.optLong("environmentGeneration")<=owner.generation
          :owner.generation>0;
      if(preOwner)add(context,row,IndexWrite.REPAIR);
    }
  }
  private static boolean isInteger(Object value){return value instanceof Integer||value instanceof Long;}
  private static boolean matchesInteger(Object value,int expected){return isInteger(value)&&((Number)value).longValue()==expected;}
  private static boolean savedInSlot(JSONObject row,int slot){return !row.has("slot")||matchesInteger(row.opt("slot"),slot);}
  private static boolean withoutEnvironmentId(JSONObject row){return row.isNull("environmentId")||"".equals(row.opt("environmentId"));}
  private static boolean tombstoned(SQLiteDatabase db,String uri){
    try(Cursor cursor=db.query("deleted_files",new String[]{"uri"},"uri=?",new String[]{uri},null,null,null)){
      return cursor.moveToFirst();
    }
  }
  private static JSONObject indexedTask(SQLiteDatabase db,int slot,String id){
    try(Cursor prior=db.query("tasks",new String[]{"row"},"slot=? AND id=?",
        new String[]{String.valueOf(slot),id},null,null,null)){
      return prior.moveToFirst()?J.parse(prior.getString(0)):null;
    }
  }
  private static boolean olderOwnedTask(JSONObject row,JSONObject indexed){
    return indexed!=null&&indexed.optLong("time")<row.optLong("time")
        &&!"saved".equals(indexed.optString("state"))&&indexed.optString("uri").isEmpty()
        &&java.util.Objects.equals(row.opt("environmentId"),indexed.opt("environmentId"))
        &&java.util.Objects.equals(row.opt("environmentGeneration"),indexed.opt("environmentGeneration"));
  }
  private static boolean coveredByOtherPublication(SQLiteDatabase db,JSONObject row){
    String uri=row.optString("uri");
    if(uri.isEmpty())return false;
    if(tombstoned(db,uri))return true;
    JSONObject existing=newest(db,uri);
    return existing!=null&&(!"saved".equals(row.optString("state"))||!sameOwnedPublication(row,existing));
  }
  private static boolean sameOwnedPublication(JSONObject row,JSONObject existing){
    return DownloadMetadataValues.identity(row,existing)
        &&java.util.Objects.equals(row.opt("environmentId"),existing.opt("environmentId"))
        &&java.util.Objects.equals(row.opt("environmentGeneration"),existing.opt("environmentGeneration"));
  }
  private static JSONArray legacyHistory(Context context){
    try{
      JSONObject history=new JSONObject(context.getSharedPreferences("chat",0).getString("downloadHistory","{}"));
      return history.has("files")?history.getJSONArray("files"):new JSONArray();
    }catch(JSONException|ClassCastException failure){throw new LegacyHistoryUnreadable(failure);}
  }
  private void addLegacySaved(Context context,JSONArray rows,boolean tasks,IndexWrite write){
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(row!=null&&(!tasks||"saved".equals(row.optString("state"))))add(context,row,write);
    }
  }
  void migrateTasks(){migrate(true);}
  private static JSONArray legacyTasks(Context context){
    try{return new JSONArray(context.getSharedPreferences("download-tasks",0).getString("rows","[]"));}
    catch(JSONException|ClassCastException failure){throw new LegacyHistoryUnreadable(failure);}
  }
  void removeEnvironmentTasks(int slot){if(getWritableDatabase().delete("tasks","slot=?",new String[]{String.valueOf(slot)})>0)changed(root);}
  // Metadata queries and compare-and-set writes run only on a worker holding the URI lease.
  JSONArray metadataPage(long afterRowId,int limit){JSONArray rows=new JSONArray();try(Cursor cursor=getReadableDatabase().rawQuery("SELECT row,rowid FROM files WHERE rowid>? ORDER BY rowid LIMIT ?",new String[]{String.valueOf(afterRowId),String.valueOf(limit)})){while(cursor.moveToNext()){JSONObject row=J.parse(cursor.getString(0));DownloadTasks.put(row,"metadataRowId",cursor.getLong(1));rows.put(row);}}return rows;}
  boolean metadataUpdate(JSONObject expected,JSONObject result){
    SQLiteDatabase db=getWritableDatabase();boolean updated=false;db.beginTransaction();try{
      if(removed(db,expected)||conflicting(db,expected)){db.setTransactionSuccessful();return false;}
      try(Cursor cursor=db.query("files",new String[]{"row"},"slot=? AND uri=?",new String[]{String.valueOf(expected.optInt("slot")),expected.optString("uri")},null,null,null)){
        if(!cursor.moveToFirst())return false;String before=cursor.getString(0);JSONObject current=J.parse(before);
        if(!DownloadTaskRevisions.value(current).equals(DownloadTaskRevisions.value(expected)))return false;
        ContentValues values=new ContentValues();values.put("row",result.toString());updated=db.update("files",values,"slot=? AND uri=? AND row=?",new String[]{String.valueOf(expected.optInt("slot")),expected.optString("uri"),before})==1;
      }db.setTransactionSuccessful();
    }finally{db.endTransaction();}return updated;
  }
  JSONArray list(){migrate();JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().query("files",new String[]{"row"},null,null,null,null,"time DESC")){while(c.moveToNext())rows.put(J.parse(c.getString(0)));}return rows;}
}
