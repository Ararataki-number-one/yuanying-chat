package local.pocketchat;

import android.content.Context;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** Reads build provenance, not runtime repair or native-capability acceptance. */
final class NormalCaretSdkReceipt {
  static final String ASSET="pocketchat-sdk-build.json";
  static final String RECEIPT_ASSET="pocketchat-sdk-build-receipt.json";
  static final String INPUT_COORDINATE="org.mozilla.geckoview:geckoview:157.0.20261005135250";
  static final String RUNTIME_COORDINATE="local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket1";
  static final String INPUT_AAR_SHA256="15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268";
  static final String EDITABLE_SHA256="787e56f101767671ba0fe9a275eb6a0b87939ec5596edd78a74ffedad8b43585";
  static final String UPSTREAM_REVISION="737ec77d798755890b062aab541a90d6c75afd19";
  static final String BUILD_KIND="source-derived-java";
  static final String[] SDK_FIELDS={"sdkBuildKind","sdkCoordinate","sdkInputCoordinate","sdkRuntimeCoordinate",
      "sdkInputAarSha256","sdkAarSha256","sdkClassesJarSha256","sdkGeckoEditableClassSha256",
      "sdkManifestSha256","sdkBuildReceiptSha256","sdkBuildSource"};
  private NormalCaretSdkReceipt() {}

  static JSONObject read(Context context) throws Exception {
    byte[] asset,receipt;
    try(InputStream in=context.getAssets().open(ASSET)){asset=bytes(in,131072);}
    try(InputStream in=context.getAssets().open(RECEIPT_ASSET)){receipt=bytes(in,4194304);}
    return read(asset,receipt);
  }

  // Package-private entry point permits JVM rejection tests without an Android claim.
  static JSONObject read(byte[] assetBytes,byte[] receiptBytes) throws Exception {
    if(assetBytes.length==0||assetBytes.length>131072||receiptBytes.length==0||receiptBytes.length>4194304)
      throw new IOException("Bounded nonempty SDK provenance assets required");
    JSONObject asset=new JSONObject(new String(assetBytes,StandardCharsets.UTF_8));
    JSONObject receipt=new JSONObject(new String(receiptBytes,StandardCharsets.UTF_8));
    integer(asset,"schema",1);integer(receipt,"schema",1);
    for(JSONObject value:new JSONObject[]{asset,receipt}){
      exact(value,"sdkBuildKind",BUILD_KIND);exact(value,"sdkCoordinate",INPUT_COORDINATE);
      exact(value,"sdkInputCoordinate",INPUT_COORDINATE);exact(value,"sdkRuntimeCoordinate",RUNTIME_COORDINATE);
      exact(value,"sdkInputAarSha256",INPUT_AAR_SHA256);exact(value,"sdkGeckoEditableClassSha256",EDITABLE_SHA256);
      hash(value,"sdkAarSha256");hash(value,"sdkClassesJarSha256");hash(value,"sdkManifestSha256");
      if(INPUT_AAR_SHA256.equals(value.getString("sdkAarSha256")))throw new IOException("Derived SDK cannot reuse upstream AAR identity");
      revision(value,"sourceCommit");revision(value,"sourceTree");
      digits(value,"runId");digits(value,"runAttempt");
    }
    exact(receipt,"upstreamRevision",UPSTREAM_REVISION);positive(receipt,"sdkAarBytes");
    java.util.Set<String> allowed=new java.util.HashSet<>(java.util.Arrays.asList(SDK_FIELDS));
    allowed.addAll(java.util.Arrays.asList("schema","sourceCommit","sourceTree","runId","runAttempt"));
    java.util.Set<String> keys=new java.util.HashSet<>();java.util.Iterator<String> iter=asset.keys();while(iter.hasNext())keys.add(iter.next());
    if(!keys.equals(allowed))throw new IOException("Exact SDK asset fields required");
    hash(asset,"sdkBuildReceiptSha256");exact(asset,"sdkBuildReceiptSha256",sha256(receiptBytes));
    exact(asset,"sdkBuildSource",asset.getString("sourceCommit"));
    for(String key:new String[]{"sourceCommit","sourceTree","runId","runAttempt","sdkBuildKind","sdkCoordinate",
        "sdkInputCoordinate","sdkRuntimeCoordinate","sdkInputAarSha256","sdkAarSha256",
        "sdkClassesJarSha256","sdkGeckoEditableClassSha256","sdkManifestSha256"})
      if(!asset.get(key).equals(receipt.get(key)))throw new IOException("SDK receipt/asset identity differs: "+key);
    for(String key:new String[]{"sdkAarModified","sdkClassTransformApplied","sourceCompileApplied",
        "allOtherClassEntriesUnchanged","allNativeAndResourceEntriesUnchanged"})flag(receipt,key,true);
    for(String key:new String[]{"asmTransformApplied","observerIncluded","actualAndroidExecution",
        "releaseAcceptance","physicalDeviceAcceptance"})flag(receipt,key,false);
    exact(receipt,"patchMethod","source-compiled-class-replacement");
    JSONArray changed=receipt.getJSONArray("changedClassEntries");
    if(changed.length()!=1||!"org/mozilla/geckoview/GeckoEditable.class".equals(changed.get(0)))
      throw new IOException("Only the reviewed GeckoEditable class may change");
    artifact(receipt.getJSONObject("sourcePatch"));artifact(receipt.getJSONObject("sourceRecipe"));
    return asset;
  }

  static void requireSource(JSONObject sdk,JSONObject build) throws Exception {
    for(String key:new String[]{"sourceCommit","sourceTree"})
      if(!sdk.get(key).equals(build.get(key)))throw new IOException("SDK build belongs to another "+key);
    if(build.optBoolean("dirtySource",true))throw new IOException("Clean integration source required");
  }
  static void copySdkFields(JSONObject sdk,JSONObject target) throws Exception {
    for(String key:SDK_FIELDS)target.put(key,sdk.get(key));
  }
  static void requireInstalled(JSONObject sdk,JSONObject installed) throws Exception {
    requireSource(sdk,installed);
    JSONObject actual=installed.getJSONObject("sdkBuildIdentity");
    for(String key:SDK_FIELDS)if(!sdk.get(key).equals(actual.get(key))||!sdk.get(key).equals(installed.get(key)))
      throw new IOException("Installed SDK build identity differs: "+key);
    for(String key:new String[]{"sourceCommit","sourceTree","runId","runAttempt"})
      if(!sdk.get(key).equals(actual.get(key)))throw new IOException("Installed SDK build invocation differs: "+key);
  }
  private static byte[] bytes(InputStream in,int limit)throws IOException{
    ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] block=new byte[4096];int count;
    while((count=in.read(block))!=-1){if(out.size()+count>limit)throw new IOException("SDK provenance asset exceeds bound");out.write(block,0,count);}
    return out.toByteArray();
  }
  private static void exact(JSONObject value,String key,String expected)throws Exception{
    if(!(value.get(key) instanceof String)||!expected.equals(value.get(key)))throw new IOException("SDK identity differs: "+key);
  }
  private static void hash(JSONObject value,String key)throws Exception{
    if(!(value.get(key) instanceof String)||!value.getString(key).matches("[0-9a-f]{64}"))throw new IOException("SDK SHA-256 required: "+key);
  }
  private static void revision(JSONObject value,String key)throws Exception{
    if(!(value.get(key) instanceof String)||!value.getString(key).matches("[0-9a-f]{40}"))throw new IOException("SDK source revision required: "+key);
  }
  private static void digits(JSONObject value,String key)throws Exception{
    if(!(value.get(key) instanceof String)||!value.getString(key).matches("[1-9][0-9]{0,19}"))throw new IOException("SDK CI invocation required: "+key);
  }
  private static void integer(JSONObject value,String key,long wanted)throws Exception{
    positive(value,key);if(value.getLong(key)!=wanted)throw new IOException("SDK integer differs: "+key);
  }
  private static void positive(JSONObject value,String key)throws Exception{
    Object number=value.get(key);
    if(!(number instanceof Integer||number instanceof Long)||((Number)number).longValue()<=0)throw new IOException("Positive SDK integer required: "+key);
  }
  private static void flag(JSONObject value,String key,boolean wanted)throws Exception{
    if(!(value.get(key) instanceof Boolean)||!Boolean.valueOf(wanted).equals(value.get(key)))throw new IOException("SDK provenance flag differs: "+key);
  }
  private static void artifact(JSONObject value)throws Exception{
    Object path=value.get("path");
    if(!(path instanceof String)||((String)path).isEmpty()||((String)path).startsWith("/")||((String)path).contains("\\")
        ||((String)path).contains("..")||((String)path).indexOf('\0')>=0)throw new IOException("Repository-relative SDK source artifact required");
    positive(value,"bytes");hash(value,"sha256");
  }
  private static String sha256(byte[] bytes){return Sha256.hash(bytes);}
}
