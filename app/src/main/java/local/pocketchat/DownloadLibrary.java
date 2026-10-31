package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import org.json.*;

/** Shared file index only: no cookies, chat content or signed source URLs. */
final class DownloadLibrary extends SQLiteOpenHelper {
  static DownloadLibrary instance;final Context root;
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
  void add(Context c,JSONObject row){
    if(row==null)return;String uri=row.optString("uri");if(uri.isEmpty()||!"saved".equals(row.optString("state","saved")))return;
    SQLiteDatabase db=getWritableDatabase();boolean changed=false;JSONObject published=null;db.beginTransaction();
    try{
      if(removed(db,row)||conflicting(db,row)){db.setTransactionSuccessful();return;}
      JSONObject current=newest(db,uri);long time=DownloadListPolicy.preservedTime(row,current);
      JSONObject safe=J.obj("slot",Profiles.slot(c),"id",row.optString("id"),"name",row.optString("name","文件"),"mime",row.optString("mime","application/octet-stream"),"uri",uri,"state","saved","location",row.optString("location","原先选择的保存位置"),"time",time);
      DownloadMetadataValues.copy(row,safe);DownloadMetadataValues.merge(safe,current);
      // A history scan must not manufacture a newer download or rewrite an unchanged file.
      if(current!=null&&sameFile(safe,current)){db.setTransactionSuccessful();return;}
      ContentValues values=new ContentValues();values.put("slot",Profiles.slot(c));values.put("uri",uri);values.put("row",safe.toString());values.put("time",time);
      if(current!=null&&time>current.optLong("time"))db.delete("files","uri=?",new String[]{uri});
      db.insertWithOnConflict("files",null,values,SQLiteDatabase.CONFLICT_REPLACE);if(current==null||time>current.optLong("time"))retireTasks(db,safe);changed=true;published=safe;db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    if(changed){changed(root);SavedDownloadMetadata.added(root,published);}
  }
  static boolean sameFile(JSONObject a,JSONObject b){return a.optInt("slot")==b.optInt("slot")&&a.optLong("time")==b.optLong("time")&&same(a,b,"id","name","mime","uri","state","location")&&DownloadMetadataValues.same(a,b);}
  static boolean same(JSONObject a,JSONObject b,String... fields){for(String name:fields)if(!a.optString(name).equals(b.optString(name)))return false;return true;}
  void sync(Context c,JSONArray rows){
    SQLiteDatabase db=getWritableDatabase();int slot=Profiles.slot(c);boolean changed=false;db.beginTransaction();
    try{
      java.util.Map<String,JSONObject> current=new java.util.HashMap<>();
      try(Cursor prior=db.query("tasks",new String[]{"id","row"},"slot=?",new String[]{String.valueOf(slot)},null,null,null)){while(prior.moveToNext())current.put(prior.getString(0),J.parse(prior.getString(1)));}
      for(int i=0;i<rows.length();i++){
        JSONObject r=rows.optJSONObject(i);if(r==null||r.optString("id").isEmpty()||removed(db,r)||conflicting(db,r))continue;
        JSONObject safe=J.obj("slot",slot,"id",r.optString("id"),"name",r.optString("name","文件"),"mime",r.optString("mime","application/octet-stream"),"uri",r.optString("uri"),"state",r.optString("state"),"reason",r.optString("reason"),"location",r.optString("location"),"time",r.optLong("time"),"received",r.optLong("received"),"total",r.optLong("total",-1));
        DownloadMetadataValues.copy(r,safe);JSONObject old=current.get(r.optString("id"));DownloadMetadataValues.merge(safe,old);if(old!=null&&sameFile(safe,old)&&same(safe,old,"reason")&&safe.optLong("received")==old.optLong("received")&&safe.optLong("total",-1)==old.optLong("total",-1))continue;
        DownloadTasks.put(safe,"updated",System.currentTimeMillis());ContentValues v=new ContentValues();v.put("slot",slot);v.put("id",r.optString("id"));v.put("row",safe.toString());v.put("time",r.optLong("time"));db.insertWithOnConflict("tasks",null,v,SQLiteDatabase.CONFLICT_REPLACE);changed=true;
      }
      db.setTransactionSuccessful();
    }finally{db.endTransaction();}
    if(changed)changed(root);
  }
  JSONArray tasks(){migrate();migrateTasks();JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().query("tasks",new String[]{"row"},null,null,null,null,"time DESC")){while(c.moveToNext())rows.put(J.parse(c.getString(0)));}return prune(rows);}
  void migrate(){SharedPreferences migration=root.getSharedPreferences("download-library-migration",0);for(int id=0;id<Profiles.MAX;id++){if(migration.getBoolean("slot"+id,false))continue;Context c=Profiles.context(root,id);JSONArray old=J.parse(c.getSharedPreferences("chat",0).getString("downloadHistory","{}")).optJSONArray("files");if(old!=null)for(int i=0;i<old.length();i++)add(c,old.optJSONObject(i));try{JSONArray tasks=new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]"));for(int i=0;i<tasks.length();i++)if(tasks.optJSONObject(i).optString("state").equals("saved"))add(c,tasks.optJSONObject(i));}catch(Exception ignored){}migration.edit().putBoolean("slot"+id,true).commit();}}
  void migrateTasks(){SharedPreferences migration=root.getSharedPreferences("download-library-migration",0);for(int id=0;id<Profiles.MAX;id++){if(migration.getBoolean("tasksSlot"+id,false))continue;Context c=Profiles.context(root,id);try{sync(c,new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]")));}catch(Exception ignored){}migration.edit().putBoolean("tasksSlot"+id,true).commit();}}
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
