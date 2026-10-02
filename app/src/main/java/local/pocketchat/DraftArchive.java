package local.pocketchat;
import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import org.json.*;

/** Local recovery copies are committed before an existing draft is replaced. */
final class DraftArchive extends SQLiteOpenHelper {
 private static DraftArchive instance;static synchronized DraftArchive get(Context c){if(instance==null)instance=new DraftArchive(c);return instance;}
 DraftArchive(Context c){super(c.getApplicationContext(),"draft-archive.db",null,1);}
 public void onCreate(SQLiteDatabase db){db.execSQL("CREATE TABLE drafts(id INTEGER PRIMARY KEY AUTOINCREMENT,url TEXT NOT NULL,body TEXT NOT NULL,origin TEXT NOT NULL,created INTEGER NOT NULL)");}
 public void onUpgrade(SQLiteDatabase db,int old,int next){}
 synchronized boolean save(String url,String body,String origin){if(body==null||body.isEmpty())return true;try{SQLiteDatabase db=getWritableDatabase();try(Cursor c=db.query("drafts",new String[]{"id"},"url=? AND body=?",new String[]{url,body},null,null,null,"1")){if(c.moveToFirst())return true;}ContentValues v=new ContentValues();v.put("url",url);v.put("body",body);v.put("origin",origin);v.put("created",System.currentTimeMillis());return db.insertOrThrow("drafts",null,v)>0;}catch(Exception e){return false;}}
 JSONArray list(String url){JSONArray out=new JSONArray();try(Cursor c=getReadableDatabase().query("drafts",new String[]{"body","origin","created"},"url=?",new String[]{url},null,null,"created DESC")){while(c.moveToNext())out.put(J.obj("body",c.getString(0),"origin",c.getString(1),"created",c.getLong(2)));}return out;}
}
