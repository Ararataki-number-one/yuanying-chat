package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.nio.file.Paths;
import org.json.JSONArray;
import org.json.JSONObject;

/** Separate JVM launches with real host SQLite and file-backed preference doubles. */
public final class MigrationCases {
  private static final String PREFIX="content://migration/";
  private static int checks;
  private static void check(String name,boolean passed){if(!passed)throw new AssertionError(name);checks++;}
  private static JSONObject task(String id,long time,long received){
    return J.obj("id",id,"uri","","time",time,"state","paused","received",received);
  }
  private static JSONObject file(String id,String uri,long time,String name){
    return J.obj("id",id,"uri",PREFIX+uri,"time",time,"state","saved","name",name);
  }
  private static JSONObject content(SQLiteDatabase db,String table,int slot,String key){
    String field=table.equals("files")?"uri":"id";
    try(Cursor row=db.query(table,new String[]{"row"},"slot=? AND "+field+"=?",new String[]{String.valueOf(slot),key},null,null,null)){
      return row.moveToFirst()?J.parse(row.getString(0)):new JSONObject();
    }
  }
  private static JSONObject saved(SQLiteDatabase db,String uri){return content(db,"files",0,PREFIX+uri);}
  private static JSONObject indexedTask(SQLiteDatabase db,int slot,String id){return content(db,"tasks",slot,id);}
  private static long count(SQLiteDatabase db,String table){
    try(Cursor row=db.rawQuery("SELECT count(*) FROM "+table,null)){if(!row.moveToFirst())throw new AssertionError();return row.getLong(0);}
  }
  private static void legacyTasks(Context root,int slot,JSONArray tasks){
    check("legacy task preferences persisted",Profiles.context(root,slot).getSharedPreferences("download-tasks",0)
        .edit().putString("rows",tasks.toString()).commit());
  }
  private static void fail(Context root,DownloadLibrary library){
    SQLiteDatabase db=library.getWritableDatabase();
    SharedPreferences marks=root.getSharedPreferences("download-library-migration",0);
    check("existing completion marker persisted",marks.edit().putBoolean("tasksSlot2",true).commit());
    JSONObject deleted=file("deleted","deleted",5,"Deleted");
    library.add(root,deleted);
    library.removeSaved(deleted);
    library.add(root,file("current","latest",10,"Newer saved data"));
    library.add(root,file("same-file","same",10,"Current same-timestamp saved data"));
    library.sync(root,new JSONArray().put(task("existing",10,92))
        .put(J.obj("id","keep-task","uri",PREFIX+"saved-task","time",1,"state","paused")));
    JSONArray history=new JSONArray().put(file("history-only","first",1,"Legacy history"))
        .put(file("history-older","latest",2,"Stale saved data"))
        .put(file("same-file","same",10,"Stale same-timestamp data")).put(deleted);
    check("legacy history persisted",root.getSharedPreferences("chat",0).edit()
        .putString("downloadHistory",J.obj("files",history).toString()).commit());
    legacyTasks(root,0,new JSONArray().put(task("existing",1,3)).put(task("fresh-task",4,7))
        .put(task("failure-task",5,9)).put(task("fresh-task",2,1)).put(JSONObject.NULL)
        .put(file("from-task","saved-task",12,"Saved task")).put(deleted));
    legacyTasks(root,1,new JSONArray().put(task("other",20,3)));
    legacyTasks(root,2,new JSONArray().put(task("old-completed",21,3)));
    check("legacy saved record in a later slot persisted",Profiles.context(root,2).getSharedPreferences("chat",0)
        .edit().putString("downloadHistory",J.obj("files",new JSONArray().put(file("later","later",30,"Later slot"))).toString()).commit());
    db.failureKey=PREFIX+"saved-task";
    boolean failed=false;
    try{library.migrateBeforeRemoval(0);}catch(IllegalStateException expected){failed=true;}
    check("saved write failure does not mark the slot complete",!marks.getBoolean("slot0",false));
    check("saved migration signals failure to callers that clear legacy data",failed);
    check("saved replay can restart after earlier writes committed",saved(db,"first").has("id")&&!saved(db,"saved-task").has("id"));

    db.failureKey="failure-task";
    library.migrateTasks();
    check("sync exception leaves the slot pending",!marks.getBoolean("tasksSlot0",false));
    check("the task transaction rolled back with existing data intact",
        !indexedTask(db,0,"fresh-task").has("id")&&indexedTask(db,0,"existing").optLong("received")==92);
    check("other slots can complete during a task failure",marks.getBoolean("tasksSlot1",false)&&indexedTask(db,1,"other").has("id"));

    db.failureKey="failure-task";
    db.reportFailure=true;
    library.migrateTasks();
    check("an unsuccessful SQLite insert also leaves the task slot pending and atomic",
        !marks.getBoolean("tasksSlot0",false)&&!indexedTask(db,0,"fresh-task").has("id"));
    Context damaged=Profiles.context(root,1);
    JSONArray retained=new JSONArray().put(file("intact-history","intact",25,"Intact saved history"));
    check("valid history and corrupt task source persist in the same slot",
        damaged.getSharedPreferences("chat",0).edit().putString("downloadHistory",J.obj("files",retained).toString()).commit()
        &&damaged.getSharedPreferences("download-tasks",0).edit().putString("rows","[").commit());
  }
  private static void restart(Context root,DownloadLibrary library){
    SQLiteDatabase db=library.getWritableDatabase();
    SharedPreferences marks=root.getSharedPreferences("download-library-migration",0);
    check("new process reads durable partial saved state and pending flags",saved(db,"first").has("id")
        &&!marks.getBoolean("slot0",false)&&!marks.getBoolean("tasksSlot0",false));
    library.add(root,file("history-only","first",1,"Updated after failure"));
    JSONArray listed=library.list();
    library.migrateTasks();
    check("completed writes set both durable flags",
        "true".equals(marks.diskString("slot0","false"))&&"true".equals(marks.diskString("tasksSlot0","false")));
    check("retry reaches both legacy inputs",saved(db,"saved-task").has("id")&&indexedTask(db,0,"failure-task").has("id"));
    check("retry preserves a later edit and newer and equal-timestamp indexed records",
        "Updated after failure".equals(saved(db,"first").optString("name"))
        &&"Newer saved data".equals(saved(db,"latest").optString("name"))
        &&"Current same-timestamp saved data".equals(saved(db,"same").optString("name")));
    check("migration keeps existing tasks and ignores duplicate older task rows",
        indexedTask(db,0,"existing").optLong("received")==92&&indexedTask(db,0,"keep-task").has("id")
        &&indexedTask(db,0,"fresh-task").optLong("received")==7);
    check("deleted files and tasks remain removed with the original tombstone",
        !saved(db,"deleted").has("id")&&!indexedTask(db,0,"deleted").has("id")&&count(db,"deleted_files")==1);
    check("historical completed flags stay authoritative",marks.getBoolean("tasksSlot2",false)
        &&!indexedTask(db,2,"old-completed").has("id"));
    check("browsing leaves a corrupt unrelated slot pending and imports later healthy slots",
        !marks.getBoolean("slot1",false)&&marks.getBoolean("slot2",false)
        &&content(db,"files",2,PREFIX+"later").has("id"));
    JSONObject intact=DownloadTaskRevisions.find(listed,"intact-history");
    check("the damaged slot's readable saved history is visible even when its task source is corrupt",
        intact!=null&&intact.optInt("slot",-1)==1&&intact.optString("uri").equals(PREFIX+"intact"));
    boolean failed=false;
    try{library.migrateBeforeRemoval(1);}catch(IllegalStateException expected){failed=true;}
    check("targeted retirement rejects corruption and keeps the legacy source",
        failed&&!marks.getBoolean("slot1",false)
        &&"[".equals(Profiles.context(root,1).getSharedPreferences("download-tasks",0).getString("rows","")));
    library.migrate();
    library.migrateTasks();
    check("repeated calls do not duplicate saved or task records",count(db,"files")==6&&count(db,"tasks")==6);
  }
  public static void main(String[] args){
    Context context=new Context(Paths.get(args[0]),0);
    try(DownloadLibrary library=new DownloadLibrary(context)){
      if("fail".equals(args[1]))fail(context,library);else restart(context,library);
    }
    System.out.println(args[1]+": "+checks+" migration checks passed (host SQLite, no Android execution)");
  }
}

final class Profiles {
  static final int MAX=3;
  static Context global(Context c){return c;}
  static Context context(Context c,int slot){return slot==c.slot?c:new Context(c.root,slot);}
  static int slot(Context c){return c.slot;}
}
final class DownloadTasks {
  static void put(JSONObject row,Object... fields){
    try{for(int i=0;i<fields.length;i+=2)row.put((String)fields[i],fields[i+1]);}
    catch(org.json.JSONException error){throw new IllegalStateException(error);}
  }
}
final class DownloadLibraryChanges {static void changed(Context context){}}
final class SavedDownloadMetadata {static void added(Context context,JSONObject row){}}
