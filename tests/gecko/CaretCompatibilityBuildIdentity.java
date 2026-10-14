package local.pocketchat;

import android.content.Context;
import java.io.InputStream;
import org.json.JSONObject;

/** Immutable pre-build identity asset; APK byte hashes are verified externally after packaging. */
final class CaretCompatibilityBuildIdentity {
  static final String ASSET="caret-build-identity.json";
  static JSONObject read(Context context)throws Exception{
    JSONObject identity;
    try(InputStream input=context.getAssets().open(ASSET)){identity=J.parse(J.text(input,8192));}
    if(identity.optInt("schema")!=1||!identity.optString("sourceCommit").matches("[0-9a-f]{40}")||!identity.optString("runId").matches("[0-9]+")||!identity.optString("runAttempt").matches("[0-9]+"))throw new IllegalStateException("Missing embedded source/run/attempt build identity");
    for(String key:new String[]{"sdkReceiptSha256","sdkAarSha256","sdkClassJarSha256","sdkEditableClassSha256","sdkManifestSha256"})if(!identity.optString(key).matches("[0-9a-f]{64}"))throw new IllegalStateException("Missing embedded SDK identity: "+key);
    if(!identity.optBoolean("normalMode")||identity.optBoolean("sdkObserverIncluded",true))throw new IllegalStateException("Build identity is not observer-free normal mode");
    return identity;
  }
}
