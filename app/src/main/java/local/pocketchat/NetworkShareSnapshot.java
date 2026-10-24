package local.pocketchat;

import org.json.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Encrypted-library sidecar: candidate connection bytes never enter public node details.
 * Candidates are bound to their exact source and native identity, and require a fresh
 * native fingerprint check before sharing. This is not a native validation receipt. */
final class NetworkShareSnapshot {
  static final int VERSION=2,LIMIT=16*1024*1024;
  static String hash(byte[] bytes){try{byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder out=new StringBuilder();for(byte b:digest)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();}catch(Exception impossible){throw new IllegalStateException(impossible);}}
  static final class Parts {final JSONArray details;final byte[] index;Parts(JSONArray details,byte[] index){this.details=details;this.index=index;}}
  static Parts split(JSONArray input,byte[] source)throws Exception {
    JSONArray details=new JSONArray();JSONObject nodes=new JSONObject();String hash=hash(source);
    for(int i=0;i<input.length();i++){JSONObject original=input.optJSONObject(i);if(original==null)continue;JSONObject row=(JSONObject)NetworkShareJson.copy(original);Object raw=row.remove("shareCandidate");String bound=row.optString("shareSourceHash");int version=row.optInt("shareVersion");row.remove("shareSourceHash");row.remove("shareVersion");
      if(raw instanceof JSONObject&&version==VERSION&&hash.equals(bound)&&row.optString("configFingerprint").matches("[0-9a-f]{64}")&&row.optInt("configFingerprintVersion")==1){nodes.put(row.optString("name"),J.obj("fingerprint",row.optString("configFingerprint"),"node",raw));row.put("shareAvailability","candidate");}
      else if(raw!=null)row.put("shareAvailability","unavailable");details.put(row);
    }
    byte[] encoded=null;boolean budgetExceeded=false;
    if(nodes.length()>0)try{encoded=NetworkShareJson.encode(J.obj("version",VERSION,"sourceHash",hash,"nodes",nodes),LIMIT).getBytes(StandardCharsets.UTF_8);}catch(IOException optionalLimit){budgetExceeded=true;}
    if(budgetExceeded){for(int i=0;i<details.length();i++)details.getJSONObject(i).put("shareAvailability","budget");}
    return new Parts(details,encoded);
  }
  static JSONObject select(byte[] encoded,byte[] source,String name,String fingerprint)throws Exception {
    if(encoded==null||encoded.length>LIMIT||source==null||fingerprint==null||!fingerprint.matches("[0-9a-f]{64}"))return null;
    JSONObject index=(JSONObject)NetworkShareJson.decode(new String(encoded,StandardCharsets.UTF_8),LIMIT);if(index.optInt("version")!=VERSION||!hash(source).equals(index.optString("sourceHash")))return null;
    JSONObject nodes=index.optJSONObject("nodes"),candidate=nodes==null?null:nodes.optJSONObject(name);if(candidate==null||!fingerprint.equals(candidate.optString("fingerprint")))return null;
    JSONObject node=candidate.optJSONObject("node");return node==null?null:(JSONObject)NetworkShareJson.copy(node);
  }
}
