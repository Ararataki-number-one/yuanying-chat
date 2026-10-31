package local.pocketchat;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import org.json.*;

// Only the immutable data carrier is supplied. No policy behavior is stubbed.
final class BackgroundReplyPolicy {
  static final class Snapshot {
    final boolean known,enabled;final long revision;final int legacyPendingMask;
    Snapshot(boolean known,boolean enabled,long revision,int legacyPendingMask){this.known=known;this.enabled=enabled;this.revision=revision;this.legacyPendingMask=legacyPendingMask;}
    static Snapshot unknown(){return new Snapshot(false,false,0,255);}
  }
}
final class ProfileCatalog {
  static volatile ProfileCatalog instance;
  final Context root=new Context();final SQLiteDatabase db=new SQLiteDatabase();
  static ProfileCatalog get(Context ignored){if(instance==null)throw new AssertionError("No catalog fixture");return instance;}
  SQLiteDatabase getReadableDatabase(){return db;}
  SQLiteDatabase getWritableDatabase(){return db;}
  JSONObject item(int ignored){return new JSONObject();}
  JSONArray list(){return new JSONArray();}
}
final class Profiles {static final int MAX=8;}
final class UiPerfStats {static void catalogRead(){}}
final class DesignUi {static final class Stars {static void setting(boolean ignored){}}}
final class QuietNotifications {static void clearCompletions(Context ignored){}}
final class J {
  static JSONObject obj(Object... values){JSONObject result=new JSONObject();try{for(int i=0;i<values.length;i+=2)result.put((String)values[i],values[i+1]);}catch(JSONException failure){throw new IllegalStateException(failure);}return result;}
}
