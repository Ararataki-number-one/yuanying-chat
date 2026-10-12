package local.pocketchat;
import java.net.URI;import java.io.IOException;import java.nio.charset.StandardCharsets;import java.security.MessageDigest;import org.json.*;
final class NativeNetwork {
  static String hash(String text){try{StringBuilder out=new StringBuilder();for(byte x:MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)))out.append(String.format("%02x",x&255));return out.toString();}catch(Exception e){throw new IllegalArgumentException(e);}}
  static void validate(JSONObject value)throws Exception{URI u=new URI(value.optString("subscriptionUrl"));if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null)throw new IOException("HTTPS required");if(value.optString("exitHost").isEmpty()||value.optInt("exitPort")<1||value.optInt("exitPort")>65535)throw new IOException("Invalid exit");}
}
