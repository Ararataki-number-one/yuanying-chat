package local.pocketchat;
import org.json.*;import java.io.*;import java.nio.charset.StandardCharsets;
import static local.pocketchat.NetworkShareCodec.*;
/** Prior production receiver method, unchanged in released 5f85a90 and 178b37b.
 * The imported node whitelist is unchanged from that source. This fixture
 * exercises its original JSONTokener and wire-version refusal, not a mock.
 * Method SHA256: aa10dcd2397271862512b494ea2c8495dae87697e47ede8b3038b733b4a5883e */
final class LegacyShareReceiver {
  static Bundle decode(String text)throws Exception{
    if(text==null||text.getBytes(StandardCharsets.UTF_8).length>LIMIT)throw invalid();
    int depth=0;boolean quote=false,escape=false;for(int i=0;i<text.length();i++){char ch=text.charAt(i);if(quote){if(escape)escape=false;else if(ch=='\\')escape=true;else if(ch=='"')quote=false;}else if(ch=='"')quote=true;else if(ch=='{'||ch=='['){if(++depth>12)throw invalid();}else if(ch=='}'||ch==']'){if(--depth<0)throw invalid();}}
    if(depth!=0||quote)throw invalid();JSONTokener tok=new JSONTokener(text);Object raw=tok.nextValue();if(!(raw instanceof JSONObject)||tok.nextClean()!=0)throw invalid();JSONObject o=(JSONObject)raw;
    keys(o,set("format schemaVersion kind name entry exit"));if(!"pocketchat-network".equals(o.optString("format"))||!(o.opt("schemaVersion") instanceof Number)||o.getDouble("schemaVersion")!=1)throw new IOException("此分享版本不支持，请更新应用或重新分享。");
    JSONObject e=o.optJSONObject("entry"),x=o.optJSONObject("exit");if(e==null&&x==null||o.has("entry")&&!o.isNull("entry")&&e==null||o.has("exit")&&!o.isNull("exit")&&x==null)throw invalid();
    Bundle b=new Bundle(string(o,"name",200,true),e==null?null:node(e,false),x==null?null:node(x,true));if(!b.kind.equals(o.optString("kind")))throw invalid();return b;
  }
}
