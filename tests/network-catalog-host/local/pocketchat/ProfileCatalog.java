package local.pocketchat;
import android.content.Context;import org.json.*;import java.nio.file.*;
final class ProfileCatalog {
  final Context c;private ProfileCatalog(Context c){this.c=c;}static ProfileCatalog get(Context c){return new ProfileCatalog(c);}
  JSONArray list(){try{return new JSONArray(Files.readString(c.root.toPath().resolve("profiles.json")));}catch(Exception ignored){return new JSONArray();}}
}
