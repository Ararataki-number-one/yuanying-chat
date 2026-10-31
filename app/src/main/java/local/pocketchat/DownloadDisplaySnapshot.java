package local.pocketchat;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import org.json.*;
import java.util.*;

/** A display batch, never a saved-file authorization or durability receipt. */
final class DownloadDisplaySnapshot {
  // A single read statement shares one SQLite snapshot without reserving a write lock.
  static final String SQL="SELECT 0 AS kind,row,NULL AS uri,time,rowid AS position FROM files UNION ALL SELECT 1,NULL,uri,time,rowid FROM deleted_files UNION ALL SELECT 2,row,NULL,time,rowid FROM tasks ORDER BY kind,time ASC,position DESC";
  static JSONArray read(Context context){
    DownloadLibrary library=DownloadLibrary.get(context);library.migrate();library.migrateTasks();
    SQLiteDatabase db=library.getReadableDatabase();JSONArray files=new JSONArray(),tasks=new JSONArray();
    Map<String,JSONObject> latest=new HashMap<>();Map<String,Long> deleted=new HashMap<>();
    try(Cursor cursor=db.rawQuery(SQL,null)){
      while(cursor.moveToNext()){
        int kind=cursor.getInt(0);
        if(kind==1){deleted.put(cursor.getString(2),cursor.getLong(3));continue;}
        JSONObject row=J.parse(cursor.getString(1));
        if(kind==2){tasks.put(row);continue;}
        if(kind!=0)throw new IllegalStateException("下载列表读取类型无效");
        files.put(row);
        // Keep the schema4 time-DESC index's existing ASC/last tie behaviour explicitly.
        latest.put(row.optString("uri"),row);
      }
    }
    JSONArray kept=new JSONArray();
    for(int i=0;i<tasks.length();i++){
      JSONObject row=tasks.optJSONObject(i);String uri=row.optString("uri");Long cutoff=deleted.get(uri);JSONObject last=latest.get(uri);
      if((cutoff==null||row.optLong("time")>cutoff)&&(last==null||row.optLong("time")>last.optLong("time")||row.optLong("time")==last.optLong("time")&&row.optString("id").equals(last.optString("id"))))kept.put(row);
    }
    return DownloadListPolicy.ordered(files,kept);
  }
  static Map<Integer,String> names(Context context,JSONArray rows,int filter){
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&DownloadListPolicy.matches(row,filter))return ProfileCatalog.get(context).names();}
    return Collections.emptyMap();
  }
  /** Read ownership and names together once on the display worker, without private drafts/notes. */
  static Map<Integer,DownloadOwnerLabels.Owner> owners(Context context){
    UiPerfStats.catalogRead();Map<Integer,DownloadOwnerLabels.Owner> owners=new HashMap<>();
    try(Cursor cursor=ProfileCatalog.get(context).getReadableDatabase().query("environments",new String[]{"slot","name","environment_id","generation","created","deleting","resetting"},null,null,null,null,null)){
      while(cursor.moveToNext()){int slot=cursor.getInt(0);owners.put(slot,new DownloadOwnerLabels.Owner(slot,cursor.getString(1),cursor.getString(2),cursor.getInt(3),cursor.getInt(4)!=0,cursor.getInt(5)!=0,cursor.getInt(6)!=0));}
    }return owners;
  }
}
