package local.pocketchat;
import android.content.*;import android.database.*;import android.database.sqlite.*;

/** Global UI options in the shared catalog, never copied into account or network settings. */
final class AppSettings {
  static String get(Context c,String key,String fallback){try(Cursor row=ProfileCatalog.get(c).getReadableDatabase().query("app_settings",new String[]{"value"},"name=?",new String[]{key},null,null,null)){return row.moveToFirst()?row.getString(0):fallback;}}
  static void put(Context c,String key,String value){ContentValues row=new ContentValues();row.put("name",key);row.put("value",value);ProfileCatalog.get(c).getWritableDatabase().insertWithOnConflict("app_settings",null,row,SQLiteDatabase.CONFLICT_REPLACE);}
  static boolean bool(Context c,String key,boolean fallback){return Boolean.parseBoolean(get(c,key,String.valueOf(fallback)));}
  static int defaultSlot(Context c){int id=0;try{id=Integer.parseInt(get(c,"defaultSlot","0"));}catch(Exception ignored){}if(id<0||id>=Profiles.MAX||android.os.Build.VERSION.SDK_INT<28&&id>0||!ProfileCatalog.get(c).item(id).optBoolean("created"))return 0;return id;}
  static boolean defaultSlot(Context c,int id){if(id<0||id>=Profiles.MAX||!ProfileCatalog.get(c).item(id).optBoolean("created"))return false;put(c,"defaultSlot",String.valueOf(id));return true;}
}
