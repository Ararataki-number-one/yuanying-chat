package local.pocketchat;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.LinkedHashSet;
import java.util.Set;
import org.json.JSONArray;
import org.json.JSONObject;

/** Pure migration of the existing settings, without moving a directory or key.
 * BrowserPolicyAdapter must later acknowledge what the real runtime accepted. */
final class EnvironmentSpecMigration {
  static EnvironmentSpec fromLegacy(EnvironmentSpec.Identity identity,boolean desktop,int privacy,String networkMode,JSONObject network,String externalProxy){
    if(privacy<0||privacy>2)throw new IllegalArgumentException("Invalid legacy privacy level");
    // Dormant internal settings must not become the identity of an external
    // route after a user switches modes.
    if(network==null||!"internal".equals(networkMode))network=new JSONObject();
    String protection=privacy==0?"compatibility":privacy==2?"native-rfp":"standard";
    String template=privacy==0?(desktop?"compatibility-desktop":"compatibility-mobile"):privacy==2?(desktop?"native-rfp-desktop-experimental":"native-rfp-experimental"):(desktop?"standard-desktop":"standard-mobile");
    JSONObject browser=J.obj("schema",1,"templateId",template,"display",desktop?"desktop":"mobile","privacy",protection,"locales",new JSONArray(),"timezoneStrategy",privacy==2?"native-standardized":"system");
    String url=network.optString("subscriptionUrl"),entry=network.optString("entry");
    String entrySource=network.optString("entrySubscriptionId",network.optString("entrySourceId",url.isEmpty()?"":"entry-source-"+hash(url)));
    String entryNode=network.optString("entryNodeKey",network.optString("entryNodeId",entry.isEmpty()?"":"legacy-entry-"+hash(entry)));
    String exitFingerprint=network.optString("exitHost").isEmpty()?"":hash(network.optString("exitHost")+":"+network.optInt("exitPort")+":"+network.optString("exitUser")+":"+network.optString("exitPassword"));
    boolean subscribed="subscription".equals(network.optString("exitSource"));
    String exitSource=subscribed?network.optString("exitSubscriptionId"):network.optString("exitLibraryId",network.optString("exitSourceId",""));
    String exitNode=subscribed?network.optString("exitNodeKey"):network.optString("exitNodeId",exitFingerprint);
    String selection=network.optString("entryMode");
    if(!selection.isEmpty()&&!"manual".equals(selection)&&!"latency".equals(selection)&&!"random".equals(selection))throw new IllegalArgumentException("Invalid legacy entry selection");
    // Hash the credential-bearing old proxy string rather than copying it.
    String subscribedIdentity=subscribed&&!exitNode.isEmpty()?hash("subscription|"+exitSource+"|"+exitNode):exitFingerprint;
    String credentialRevision=network.optString("exitCredentialRevision",network.optString("credentialRevision","internal".equals(networkMode)?subscribedIdentity:externalProxy==null||externalProxy.isEmpty()?"":hash(externalProxy)));
    String entryRevision=network.optString("entryConfigRevision",sourceRevision(network,"entry",true));
    String exitRevision=network.optString("exitConfigRevision",subscribed?sourceRevision(network,"exit",false):exitFingerprint);
    EnvironmentSpec.NetworkBinding route=new EnvironmentSpec.NetworkBinding(networkMode,entrySource,entryNode,exitSource,exitNode,selection,credentialRevision,entryRevision,exitRevision);
    return EnvironmentSpec.initial(identity,new EnvironmentSpec.Configuration(browser,route));
  }
  /** New source references carry credential-bearing connection digests rather
   * than node labels. Pool identity is independent of ordering and renames. */
  private static String sourceRevision(JSONObject network,String side,boolean includePool){
    String addressKey=side+"SubscriptionAddressRevision";
    Set<String> uniqueKeys=new LinkedHashSet<>();
    if(includePool){JSONArray pool=network.optJSONArray("entryPoolKeys");if(pool!=null)for(int i=0;i<pool.length();i++){String key=pool.optString(i);if(!key.isEmpty())uniqueKeys.add(key);}}
    List<String> keys=new ArrayList<>(uniqueKeys);Collections.sort(keys);
    if(!network.has(addressKey)&&keys.isEmpty())return "";
    JSONObject value=J.obj("addressRevision",network.optLong(addressKey),"nodeKeys",new JSONArray(keys));
    return hash(value.toString());
  }
  private static String hash(String text){return Sha256.hash(text);}
}
