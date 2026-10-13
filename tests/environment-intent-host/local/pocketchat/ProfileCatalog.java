package local.pocketchat;
import android.content.Context;import org.json.*;import java.nio.file.*;import java.util.UUID;
/** UUID/catalog fixture only. The Android fixture exercises SQLiteOpenHelper. */
final class ProfileCatalog {
  final Context context;private ProfileCatalog(Context context){this.context=context;}static ProfileCatalog get(Context c){return new ProfileCatalog(c);}
  JSONArray list(){try{return new JSONArray(Files.readString(context.root.toPath().resolve("profiles.json")));}catch(Exception ignored){return new JSONArray();}}
  EnvironmentSpec.Identity identity(int slot)throws Exception{JSONArray rows=list();for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(row.getInt("slot")==slot){if(!row.optBoolean("created")||row.optBoolean("deleting"))throw new java.io.IOException("Environment deleted");return new EnvironmentSpec.Identity(slot,row.getInt("generation"),row.getString("environmentId"));}}throw new java.io.IOException("Environment absent");}
  static void create(Context c,int generation)throws Exception{Files.writeString(c.root.toPath().resolve("profiles.json"),J.arr(J.obj("slot",c.slot,"generation",generation,"created",true,"environmentId",UUID.randomUUID().toString())).toString());}
}
