package local.pocketchat;

import android.content.*;
import org.json.*;
import java.nio.charset.StandardCharsets;

/** Encrypted desired route; writing this record never changes a running route. */
final class NetworkChanges {
  static String hash(Context c){SharedPreferences p=c.getSharedPreferences("chat",0);return NativeNetwork.hash(new SecretStore(c).settings()+"|"+p.getString("networkMode","external")+"|"+p.getString("proxy","")+"|"+p.getBoolean("requireExternalVpn",true));}
  static JSONObject pending(Context c){try{byte[] value=new SecretStore(c).get("pending-network");return value==null?new JSONObject():J.parse(new String(value,StandardCharsets.UTF_8));}catch(Exception e){return new JSONObject();}}
  static void save(Context c,String action,JSONObject config,String baseline)throws Exception{new SecretStore(c).put("pending-network",J.obj("action",action,"config",config,"baseline",baseline,"savedAt",System.currentTimeMillis()).toString().getBytes(StandardCharsets.UTF_8));}
  static void clear(Context c){new android.util.AtomicFile(new SecretStore(c).file("pending-network")).delete();}
  static void validate(Context c,String action,JSONObject value)throws Exception{
    if("external".equals(action)){String proxy=value.optString("proxy");if(!proxy.isEmpty()&&!MainActivity.validProxy(proxy))throw new java.io.IOException("代理地址无效");return;}
    NativeNetwork.validate(value);NetworkCatalog catalog=new NetworkCatalog(c);JSONObject sub=catalog.subscription(NativeNetwork.hash(value.optString("subscriptionUrl")));
    if(sub==null)throw new java.io.IOException("订阅已变化，请重新选择");EntrySelection.validate(value,EntrySelection.strings(sub.optJSONArray("nodes")));if(catalog.cache(sub)==null)throw new java.io.IOException("请先读取所选订阅的入口，再保存");
  }
}
