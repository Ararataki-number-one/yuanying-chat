package local.pocketchat;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

/** Pure migration of the existing settings, without moving a directory or key.
 * BrowserPolicyAdapter must later acknowledge what the real runtime accepted. */
final class EnvironmentSpecMigration {
  static EnvironmentSpec fromLegacy(EnvironmentSpec.Identity identity,boolean desktop,int privacy,String networkMode,JSONObject network,String externalProxy){
    if(privacy<0||privacy>2)throw new IllegalArgumentException("Invalid legacy privacy level");
    if(network==null)network=new JSONObject();
    String protection=privacy==0?"compatibility":privacy==2?"native-rfp":"standard";
    String template=privacy==0?(desktop?"compatibility-desktop":"compatibility-mobile"):privacy==2?(desktop?"native-rfp-desktop-experimental":"native-rfp-experimental"):(desktop?"standard-desktop":"standard-mobile");
    JSONObject browser=J.obj("schema",1,"templateId",template,"display",desktop?"desktop":"mobile","privacy",protection,"locales",new JSONArray(),"timezoneStrategy",privacy==2?"native-standardized":"system");
    String url=network.optString("subscriptionUrl"),entry=network.optString("entry");
    String entrySource=network.optString("entrySourceId",url.isEmpty()?"":"entry-source-"+hash(url));
    String entryNode=network.optString("entryNodeId",entry.isEmpty()?"":"legacy-entry-"+hash(entry));
    String exitFingerprint=network.optString("exitHost").isEmpty()?"":hash(network.optString("exitHost")+":"+network.optInt("exitPort")+":"+network.optString("exitUser")+":"+network.optString("exitPassword"));
    String exitSource=network.optString("exitSourceId","");
    String exitNode=network.optString("exitNodeId",exitFingerprint);
    String selection=network.optString("entryMode","random");
    if(!"manual".equals(selection)&&!"latency".equals(selection)&&!"random".equals(selection))throw new IllegalArgumentException("Invalid legacy entry selection");
    // Hash the credential-bearing old proxy string rather than copying it.
    String credentialRevision=network.optString("exitCredentialRevision",network.optString("credentialRevision","internal".equals(networkMode)?exitFingerprint:externalProxy==null||externalProxy.isEmpty()?"":hash(externalProxy)));
    EnvironmentSpec.NetworkBinding route=new EnvironmentSpec.NetworkBinding(networkMode,entrySource,entryNode,exitSource,exitNode,selection,credentialRevision,network.optString("entryConfigRevision"),network.optString("exitConfigRevision",exitFingerprint));
    return EnvironmentSpec.initial(identity,new EnvironmentSpec.Configuration(browser,route));
  }
  private static String hash(String text){try{byte[] value=MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte b:value)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}}
}
