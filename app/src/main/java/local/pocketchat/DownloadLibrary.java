package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import org.json.*;

/** Shared file index only: no cookies, chat content or signed source URLs. */
final class DownloadLibrary extends SQLiteOpenHelper {
  static DownloadLibrary instance;final Context root;
  static synchronized DownloadLibrary get(Context c){if(instance==null)instance=new DownloadLibrary(Profiles.global(c));return instance;}
  DownloadLibrary(Context c){super(c,"saved-download-library.db",null,2);root=c;}
  public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE files (slot INTEGER NOT NULL,uri TEXT NOT NULL,row TEXT NOT NULL,time INTEGER NOT NULL,PRIMARY KEY(slot,uri))");createTasks(db);}
  static void createTasks(SQLiteDatabase db){db.execSQL("CREATE TABLE tasks(slot INTEGER NOT NULL,id TEXT NOT NULL,row TEXT NOT NULL,time INTEGER NOT NULL,PRIMARY KEY(slot,id))");}
  public void onUpgrade(SQLiteDatabase db,int old,int next){if(old<2)createTasks(db);}
  void add(Context c,JSONObject row){String uri=row.optString("uri");if(uri.isEmpty()||!"saved".equals(row.optString("state","saved")))return;JSONObject safe=J.obj("slot",Profiles.slot(c),"id",row.optString("id"),"name",row.optString("name","文件"),"mime",row.optString("mime","application/octet-stream"),"uri",uri,"state","saved","location",row.optString("location","原先选择的保存位置"),"time",row.optLong("time",System.currentTimeMillis()));ContentValues values=new ContentValues();values.put("slot",Profiles.slot(c));values.put("uri",uri);values.put("row",safe.toString());values.put("time",safe.optLong("time"));getWritableDatabase().insertWithOnConflict("files",null,values,SQLiteDatabase.CONFLICT_REPLACE);}
  void sync(Context c,JSONArray rows){SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(r==null||r.optString("id").isEmpty())continue;JSONObject safe=J.obj("slot",Profiles.slot(c),"id",r.optString("id"),"name",r.optString("name","文件"),"mime",r.optString("mime","application/octet-stream"),"uri",r.optString("uri"),"state",r.optString("state"),"reason",r.optString("reason"),"location",r.optString("location"),"time",r.optLong("time"),"received",r.optLong("received"),"total",r.optLong("total",-1),"updated",System.currentTimeMillis());ContentValues v=new ContentValues();v.put("slot",Profiles.slot(c));v.put("id",r.optString("id"));v.put("row",safe.toString());v.put("time",r.optLong("time"));db.insertWithOnConflict("tasks",null,v,SQLiteDatabase.CONFLICT_REPLACE);}db.setTransactionSuccessful();}finally{db.endTransaction();}}
  JSONArray tasks(){migrate();migrateTasks();JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().query("tasks",new String[]{"row"},null,null,null,null,"time DESC")){while(c.moveToNext())rows.put(J.parse(c.getString(0)));}return rows;}
  void migrate(){SharedPreferences migration=root.getSharedPreferences("download-library-migration",0);for(int id=0;id<Profiles.MAX;id++){if(migration.getBoolean("slot"+id,false))continue;Context c=Profiles.context(root,id);JSONArray old=J.parse(c.getSharedPreferences("chat",0).getString("downloadHistory","{}")).optJSONArray("files");if(old!=null)for(int i=0;i<old.length();i++)add(c,old.optJSONObject(i));try{JSONArray tasks=new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]"));for(int i=0;i<tasks.length();i++)if(tasks.optJSONObject(i).optString("state").equals("saved"))add(c,tasks.optJSONObject(i));}catch(Exception ignored){}migration.edit().putBoolean("slot"+id,true).commit();}}
  void migrateTasks(){SharedPreferences migration=root.getSharedPreferences("download-library-migration",0);for(int id=0;id<Profiles.MAX;id++){if(migration.getBoolean("tasksSlot"+id,false))continue;Context c=Profiles.context(root,id);try{sync(c,new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]")));}catch(Exception ignored){}migration.edit().putBoolean("tasksSlot"+id,true).commit();}}
  JSONArray list(){migrate();JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().query("files",new String[]{"row"},null,null,null,null,"time DESC")){while(c.moveToNext())rows.put(J.parse(c.getString(0)));}return rows;}
}
