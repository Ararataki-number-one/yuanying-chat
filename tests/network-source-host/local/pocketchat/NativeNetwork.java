package local.pocketchat;
import java.net.URI;import java.io.IOException;import java.nio.charset.StandardCharsets;import java.security.MessageDigest;import org.json.*;
/** No native core is executed by the host fixture; real provider parsing has a separate Android gate. */
final class NativeNetwork {
  static String hash(String text){try{StringBuilder out=new StringBuilder();for(byte x:MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)))out.append(String.format("%02x",x&255));return out.toString();}catch(Exception e){throw new IllegalArgumentException(e);}}
  static String literalRegex(String text){return java.util.regex.Pattern.quote(text);}
  static void validate(JSONObject value)throws Exception{URI u=new URI(value.optString("subscriptionUrl"));if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null)throw new IOException("HTTPS required");if("subscription".equals(value.optString("exitSource"))){if(value.optString("exitSubscriptionUrl").isEmpty()||value.optString("exitNodeKey").isEmpty())throw new IOException("Missing exit reference");}else if(value.optString("exitHost").isEmpty()||value.optInt("exitPort")<1||value.optInt("exitPort")>65535)throw new IOException("Invalid exit");}
}
