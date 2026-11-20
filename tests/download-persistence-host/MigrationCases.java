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
    // Preflight can be run while the environment is still active. It doesn't
    // index records or acknowledge migration, even with a healthy source.
    long filesBeforePreflight=count(db,"files");
    library.preflightRemoval(0);
    check("healthy preflight leaves both sources and the global index alone",
        count(db,"files")==filesBeforePreflight&&!marks.getBoolean("slot0",false)
        &&J.parse(root.getSharedPreferences("chat",0).getString("downloadHistory","")).has("files"));
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
  private static void restart(Context root,DownloadLibrary library)throws Exception{
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
    try{library.migrateBeforeRemoval(1);}catch(DownloadLibrary.LegacyHistoryUnreadable expected){failed=true;}
    check("targeted retirement rejects corruption and keeps the legacy source",
        failed&&!marks.getBoolean("slot1",false)
        &&"[".equals(Profiles.context(root,1).getSharedPreferences("download-tasks",0).getString("rows","")));
    library.migrate();
    library.migrateTasks();
    check("repeated calls do not duplicate saved or task records",count(db,"files")==6&&count(db,"tasks")==6);
    Context damaged=Profiles.context(root,1);
    check("old boot marker can coexist with a damaged latest input",
        marks.edit().putBoolean("slot1",true).commit());
    long filesBefore=count(db,"files");
    boolean unreadable=false;
    try{library.preflightRemoval(1);}catch(DownloadLibrary.LegacyHistoryUnreadable expected){unreadable=true;}
    check("permanent preflight error remains distinct even with an old completion marker",
        unreadable&&count(db,"files")==filesBefore
        &&"[".equals(damaged.getSharedPreferences("download-tasks",0).getString("rows","")));
    library.preflightRemoval(2);
    check("other healthy slots remain usable while the damaged slot is blocked",
        content(db,"files",2,PREFIX+"later").has("id"));
    SharedPreferences badHistory=damaged.getSharedPreferences("chat",0);
    String originalHistory=badHistory.getString("downloadHistory","");
    check("a wrong-shaped history can be injected independently",
        badHistory.edit().putString("downloadHistory","{\"files\":{}}").commit()
        &&damaged.getSharedPreferences("download-tasks",0).edit().putString("rows","[]").commit());
    boolean badHistoryBlocked=false;
    try{library.preflightRemoval(1);}catch(DownloadLibrary.LegacyHistoryUnreadable expected){badHistoryBlocked=true;}
    check("a wrong-shaped history is preserved and blocks preflight with a readable task source",
        badHistoryBlocked&&count(db,"files")==filesBefore
        &&"{\"files\":{}}".equals(badHistory.getString("downloadHistory","")));
    check("synthetic recovery of the original history was committed",
        badHistory.edit().putString("downloadHistory",originalHistory).commit());
    JSONArray repaired=new JSONArray().put(file("late-owner","late-owner",40,"Late saved document"))
        .put(file("deleted","deleted",5,"Deleted"));
    check("synthetic repair restores a readable pending source",
        damaged.getSharedPreferences("download-tasks",0).edit().putString("rows",repaired.toString()).commit());
    library.preflightRemoval(1);
    check("repaired targeted source passes read-only preflight after the old marker",
        count(db,"files")==filesBefore);
    db.failureKey=PREFIX+"late-owner";
    boolean temporary=false;
    try{library.migrateBeforeRemoval(1);}
    catch(DownloadLibrary.LegacyHistoryUnreadable wrong){throw new AssertionError("write was reported as corruption",wrong);}
    catch(IllegalStateException expected){temporary=true;}
    check("targeted reindex reports a write failure separately and leaves saved source intact",
        temporary&&!content(db,"files",1,PREFIX+"late-owner").has("id")
        &&"late-owner".equals(new JSONArray(damaged.getSharedPreferences("download-tasks",0).getString("rows","")).getJSONObject(0).optString("id")));
    library.migrateBeforeRemoval(1);
    library.migrateBeforeRemoval(1);
    check("targeted retry preserves recent saved records despite the old marker without resurrecting deleted files",
        "Late saved document".equals(content(db,"files",1,PREFIX+"late-owner").optString("name"))
        &&!content(db,"files",1,PREFIX+"deleted").has("id")&&count(db,"files")==filesBefore+1);
  }
  private static JSONObject owned(Context root,int slot,JSONObject row)throws Exception{
    EnvironmentSpec.Identity owner=ProfileCatalog.get(root).identity(slot);
    DownloadTasks.put(row,"slot",slot,"environmentId",owner.environmentId,"environmentGeneration",owner.generation);
    return row;
  }
  private static void history(Context root,int slot,JSONArray rows){
    check("synthetic legacy file index committed",Profiles.context(root,slot).getSharedPreferences("chat",0)
        .edit().putString("downloadHistory",J.obj("files",rows).toString()).commit());
  }
  private static void completedMarkerReplay(Context root,DownloadLibrary library)throws Exception{
    int slot=3;
    library.list(); // Settle older fixtures before injecting this slot's marker failure.
    Context profile=Profiles.context(root,slot);
    SharedPreferences marks=root.getSharedPreferences("download-library-migration",0);
    SQLiteDatabase db=library.getWritableDatabase();
    check("simulated old completion markers committed",marks.edit().putBoolean("slot3",true)
        .putBoolean("tasksSlot3",true).commit());
    history(root,slot,new JSONArray().put(owned(root,slot,file("backfill","backfill",100,"Recoverable")))
        .put(owned(root,slot,file("stale","latest",Long.MAX_VALUE,"Reject duplicate URI")))
        .put(owned(root,slot,file("removed","deleted",Long.MAX_VALUE,"Reject tombstoned URI")))
        .put(file("unknown","unknown",100,"Unproven history")));
    library.sync(profile,new JSONArray().put(owned(root,slot,task("keep-current",101,52))));
    JSONObject deleted=file("deleted-task","deleted",Long.MAX_VALUE,"Reject resurrected task");
    JSONObject stale=file("stale-file-task","latest",Long.MAX_VALUE,"Reject newer-looking task");
    legacyTasks(root,slot,new JSONArray().put(owned(root,slot,task("backfill-task",100,7)))
        .put(owned(root,slot,task("keep-current",110,2))).put(owned(root,slot,deleted))
        .put(owned(root,slot,stale)).put(task("unknown-task",100,5)));

    marks.failAfterMemoryBeforeDisk=true;
    library.list();
    check("old true file marker cannot hide a missing file with the current owner",
        content(db,"files",slot,PREFIX+"backfill").has("id"));
    check("failed confirmation cannot complete replay in memory or on disk",
        marks.getBoolean("slot3",false)&&!marks.getBoolean("slot3Reconciled",false)
        &&"false".equals(marks.diskString("slot3Reconciled","false")));
    db.failureKey="backfill-task";
    library.migrateTasks();
    check("failed task replay is pending despite its old true marker",!marks.getBoolean("tasksSlot3Reconciled",false));
    library.list();
    library.migrateTasks();
    check("retry adds only the missing owned task",indexedTask(db,slot,"backfill-task").optLong("received")==7
        &&indexedTask(db,slot,"keep-current").optLong("received")==52&&!indexedTask(db,slot,"unknown-task").has("id"));
    check("retry preserves indexed URI, strictly respects tombstones and never admits ambiguous old history",
        "Newer saved data".equals(saved(db,"latest").optString("name"))
        &&!content(db,"files",slot,PREFIX+"latest").has("id")&&!content(db,"files",slot,PREFIX+"deleted").has("id")
        &&!content(db,"files",slot,PREFIX+"unknown").has("id")&&!indexedTask(db,slot,"deleted-task").has("id")
        &&!indexedTask(db,slot,"stale-file-task").has("id"));
    long files=count(db,"files"),tasks=count(db,"tasks");
    library.list();
    library.migrateTasks();
    check("a successful repair is durable and cannot duplicate records",
        "true".equals(marks.diskString("slot3Reconciled","false"))
        &&"true".equals(marks.diskString("tasksSlot3Reconciled","false"))
        &&files==count(db,"files")&&tasks==count(db,"tasks"));
  }
  private static void resetMigration(Context root,DownloadLibrary library)throws Exception{
    int slot=4;
    ProfileCatalog catalog=ProfileCatalog.get(root);
    SharedPreferences marks=root.getSharedPreferences("download-library-migration",0);
    SQLiteDatabase db=library.getWritableDatabase();
    JSONObject retired=owned(root,slot,task("retired",10,8));
    history(root,slot,new JSONArray().put(file("early-history","early-history",3,"Preserved historical file"))
        .put(file("unbound", "new-saved",12,"Pre-owner conflict")));
    catalog.generation[slot]=1;
    catalog.resetting[slot]=true;
    legacyTasks(root,slot,new JSONArray().put(retired));
    library.migrateTasks();
    check("first migration cannot write or acknowledge old tasks during reset",
        !indexedTask(db,slot,"retired").has("id")&&!marks.getBoolean("tasksSlot4",false));
    catalog.resetting[slot]=false;
    legacyTasks(root,slot,new JSONArray().put(retired).put(task("unknown-owner",10,6))
        .put(owned(root,slot,task("active",11,7))).put(owned(root,slot,file("owned-saved","new-saved",12,"Verified owner"))));
    library.list();
    library.migrateTasks();
    JSONObject early=content(db,"files",slot,PREFIX+"early-history");
    check("first migration preserves pre-owner saved history with unknown ownership",
        "early-history".equals(early.optString("id"))&&early.optString("environmentId").isEmpty());
    check("verified history takes priority over unbound history at the same URI and timestamp",
        "owned-saved".equals(content(db,"files",slot,PREFIX+"new-saved").optString("id")));
    check("first migration after reset admits only the current generation of live tasks",
        !indexedTask(db,slot,"retired").has("id")&&!indexedTask(db,slot,"unknown-owner").has("id")
        &&indexedTask(db,slot,"active").has("id"));
  }
  public static void main(String[] args)throws Exception{
    Context context=new Context(Paths.get(args[0]),0);
    try(DownloadLibrary library=new DownloadLibrary(context)){
      if("fail".equals(args[1]))fail(context,library);else{
        restart(context,library);
        completedMarkerReplay(context,library);
        resetMigration(context,library);
      }
    }
    System.out.println(args[1]+": "+checks+" migration checks passed (host SQLite, no Android execution)");
  }
}

final class Profiles {
  static final int MAX=5;
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

final class EnvironmentSpec {
  static final class Identity {
    final int slot,generation;
    final String environmentId;
    Identity(int slot,int generation,String environmentId){
      this.slot=slot;this.generation=generation;this.environmentId=environmentId;
    }
  }
}
final class ProfileCatalog {
  private static final ProfileCatalog INSTANCE=new ProfileCatalog();
  final int[] generation=new int[Profiles.MAX];
  final boolean[] resetting=new boolean[Profiles.MAX];
  static ProfileCatalog get(Context context){return INSTANCE;}
  EnvironmentSpec.Identity identity(int slot)throws java.io.IOException{
    if(resetting[slot])throw new java.io.IOException("Simulated environment reset");
    return new EnvironmentSpec.Identity(slot,generation[slot],String.format("00000000-0000-0000-0000-%012d",slot+1));
  }
  interface IdentityAction<T>{T run()throws Exception;}
  synchronized <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{
    EnvironmentSpec.Identity live=identity(expected.slot);
    if(live.generation!=expected.generation||!live.environmentId.equals(expected.environmentId))
      throw new java.io.IOException("Simulated environment change");
    return action.run();
  }
}
