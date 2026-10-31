package local.pocketchat;
import java.net.URI;import java.io.IOException;import java.nio.charset.StandardCharsets;import java.security.MessageDigest;import org.json.*;
/** No core execution or WAN claims: stable synthetic digest binding only. */
final class NativeNetwork {
  static NativeNetwork peek(){throw new AssertionError("Actual core proof is outside the intent transaction host scope");}
  static String hash(String text){try{StringBuilder out=new StringBuilder();for(byte x:MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)))out.append(String.format("%02x",x&255));return out.toString();}catch(Exception e){throw new IllegalArgumentException(e);}}
  static String literalRegex(String text){return java.util.regex.Pattern.quote(text);}
  static void validate(JSONObject value)throws Exception{URI u=new URI(value.optString("subscriptionUrl"));if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null)throw new IOException("HTTPS required");if(subscribedExit(value)){if(value.optString("exitSubscriptionUrl").isEmpty()||value.optString("exitNodeKey").isEmpty())throw new IOException("Missing exit reference");}else if(value.optString("exitHost").isEmpty()||value.optInt("exitPort")<1||value.optInt("exitPort")>65535)throw new IOException("Invalid exit");}
  static boolean subscribedExit(JSONObject value){return "subscription".equals(value.optString("exitSource"));}
  static String exitIdentity(JSONObject value){return hash(value.optString("exitHost")+":"+value.optInt("exitPort")+":"+value.optString("exitUser")+":"+value.optString("exitPassword"));}
  static String transportFingerprint(JSONObject value){return hash(value.toString());}
}
