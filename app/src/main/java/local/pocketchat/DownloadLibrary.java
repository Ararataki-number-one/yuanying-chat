package local.pocketchat;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import org.json.*;

/** Shared file index only: no cookies, chat content or signed source URLs. */
final class DownloadLibrary extends SQLiteOpenHelper {
  static DownloadLibrary instance;final Context root;
  static synchronized DownloadLibrary get(Context c){if(instance==null)instance=new DownloadLibrary(Profiles.global(c));return instance;}
  DownloadLibrary(Context c){super(c,"saved-download-library.db",null,1);root=c;}
  public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE files (slot INTEGER NOT NULL,uri TEXT NOT NULL,row TEXT NOT NULL,time INTEGER NOT NULL,PRIMARY KEY(slot,uri))");}
  public void onUpgrade(SQLiteDatabase db,int old,int next){}
  void add(Context c,JSONObject row){String uri=row.optString("uri");if(uri.isEmpty()||!"saved".equals(row.optString("state","saved")))return;JSONObject safe=J.obj("slot",Profiles.slot(c),"id",row.optString("id"),"name",row.optString("name","文件"),"mime",row.optString("mime","application/octet-stream"),"uri",uri,"state","saved","location",row.optString("location","原先选择的保存位置"),"time",row.optLong("time",System.currentTimeMillis()));ContentValues values=new ContentValues();values.put("slot",Profiles.slot(c));values.put("uri",uri);values.put("row",safe.toString());values.put("time",safe.optLong("time"));getWritableDatabase().insertWithOnConflict("files",null,values,SQLiteDatabase.CONFLICT_REPLACE);}
  void migrate(){SharedPreferences migration=root.getSharedPreferences("download-library-migration",0);for(int id=0;id<Profiles.MAX;id++){if(migration.getBoolean("slot"+id,false))continue;Context c=Profiles.context(root,id);JSONArray old=J.parse(c.getSharedPreferences("chat",0).getString("downloadHistory","{}")).optJSONArray("files");if(old!=null)for(int i=0;i<old.length();i++)add(c,old.optJSONObject(i));try{JSONArray tasks=new JSONArray(c.getSharedPreferences("download-tasks",0).getString("rows","[]"));for(int i=0;i<tasks.length();i++)if(tasks.optJSONObject(i).optString("state").equals("saved"))add(c,tasks.optJSONObject(i));}catch(Exception ignored){}migration.edit().putBoolean("slot"+id,true).commit();}}
  JSONArray list(){migrate();JSONArray rows=new JSONArray();try(Cursor c=getReadableDatabase().query("files",new String[]{"row"},null,null,null,null,"time DESC")){while(c.moveToNext())rows.put(J.parse(c.getString(0)));}return rows;}
}
