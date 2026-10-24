package local.pocketchat;
import android.content.*;import android.database.*;import android.database.sqlite.*;

/** Global UI options in the shared catalog, never copied into account or network settings. */
final class AppSettings {
  static String get(Context c,String key,String fallback){UiPerfStats.catalogRead();try(Cursor row=ProfileCatalog.get(c).getReadableDatabase().query("app_settings",new String[]{"value"},"name=?",new String[]{key},null,null,null)){return row.moveToFirst()?row.getString(0):fallback;}}
  static void put(Context c,String key,String value){ContentValues row=new ContentValues();row.put("name",key);row.put("value",value);ProfileCatalog.get(c).getWritableDatabase().insertWithOnConflict("app_settings",null,row,SQLiteDatabase.CONFLICT_REPLACE);if("starBackground".equals(key))DesignUi.Stars.setting(Boolean.parseBoolean(value));if("backgroundCompletionNotice".equals(key)&&!Boolean.parseBoolean(value))QuietNotifications.clearCompletions(c);}
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
