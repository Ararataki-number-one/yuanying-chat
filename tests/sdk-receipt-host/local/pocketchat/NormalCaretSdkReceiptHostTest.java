package local.pocketchat;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.JSONArray;
import org.json.JSONObject;

/** Counterfeit metadata rejection controls only; no Android or SDK repair claim. */
public final class NormalCaretSdkReceiptHostTest {
  static int checks;
  interface Edit {void run(JSONObject value)throws Exception;}
  static void check(boolean value){checks++;if(!value)throw new AssertionError("SDK receipt rejection control failed");}
  static byte[] raw(JSONObject value){return value.toString().getBytes(StandardCharsets.UTF_8);}
  static String sha(byte[] raw)throws Exception{StringBuilder value=new StringBuilder();for(byte part:MessageDigest.getInstance("SHA-256").digest(raw))value.append(String.format(java.util.Locale.ROOT,"%02x",part&255));return value.toString();}
  static JSONObject receipt()throws Exception{
    JSONObject value=new JSONObject();value.put("schema",1);value.put("sdkBuildKind",NormalCaretSdkReceipt.BUILD_KIND);
    value.put("sdkCoordinate",NormalCaretSdkReceipt.INPUT_COORDINATE);value.put("sdkInputCoordinate",NormalCaretSdkReceipt.INPUT_COORDINATE);
    value.put("sdkRuntimeCoordinate",NormalCaretSdkReceipt.RUNTIME_COORDINATE);value.put("sdkInputAarSha256",NormalCaretSdkReceipt.INPUT_AAR_SHA256);
    value.put("sdkAarSha256","a".repeat(64));value.put("sdkAarBytes",123);value.put("sdkClassesJarSha256","b".repeat(64));
    value.put("sdkGeckoEditableClassSha256",NormalCaretSdkReceipt.EDITABLE_SHA256);value.put("upstreamRevision",NormalCaretSdkReceipt.UPSTREAM_REVISION);
    value.put("sdkManifestSha256","c".repeat(64));value.put("sourceCommit","d".repeat(40));value.put("sourceTree","e".repeat(40));
    value.put("runId","123");value.put("runAttempt","1");value.put("changedClassEntries",new JSONArray().put("org/mozilla/geckoview/GeckoEditable.class"));
    for(String key:new String[]{"sdkAarModified","sdkClassTransformApplied","sourceCompileApplied","allOtherClassEntriesUnchanged","allNativeAndResourceEntriesUnchanged"})value.put(key,true);
    for(String key:new String[]{"asmTransformApplied","observerIncluded","actualAndroidExecution","releaseAcceptance","physicalDeviceAcceptance"})value.put(key,false);
    value.put("patchMethod","source-compiled-class-replacement");
    for(String key:new String[]{"sourcePatch","sourceRecipe"})value.put(key,new JSONObject().put("path","third-party/patches/"+key).put("bytes",12).put("sha256","f".repeat(64)));
    return value;
  }
  static JSONObject asset(JSONObject receipt)throws Exception{
    JSONObject value=new JSONObject();for(String key:NormalCaretSdkReceipt.SDK_FIELDS)if(receipt.has(key))value.put(key,receipt.get(key));
    for(String key:new String[]{"schema","sourceCommit","sourceTree","runId","runAttempt"})value.put(key,receipt.get(key));
    value.put("sdkBuildSource",receipt.get("sourceCommit"));value.put("sdkBuildReceiptSha256",sha(raw(receipt)));return value;
  }
  static void rejectAsset(Edit edit)throws Exception{
    JSONObject receipt=receipt(),asset=asset(receipt);edit.run(asset);boolean rejected=false;
    try{NormalCaretSdkReceipt.read(raw(asset),raw(receipt));}catch(Exception expected){rejected=true;}check(rejected);
  }
  static void rejectReceipt(Edit edit,boolean mirror)throws Exception{
    JSONObject receipt=receipt(),asset=asset(receipt);edit.run(receipt);if(mirror)asset=asset(receipt);
    else asset.put("sdkBuildReceiptSha256",sha(raw(receipt)));
    boolean rejected=false;try{NormalCaretSdkReceipt.read(raw(asset),raw(receipt));}catch(Exception expected){rejected=true;}check(rejected);
  }
  public static void main(String[] arguments)throws Exception{
    JSONObject receipt=receipt(),asset=asset(receipt);check(NormalCaretSdkReceipt.read(raw(asset),raw(receipt)).toString().equals(asset.toString()));
    for(String key:NormalCaretSdkReceipt.SDK_FIELDS){rejectAsset(value->value.remove(key));rejectAsset(value->value.put(key,"wrong"));}
    for(String key:new String[]{"sourceCommit","sourceTree","runId","runAttempt"}){
      rejectAsset(value->value.remove(key));rejectAsset(value->value.put(key,"wrong"));rejectAsset(value->value.put(key,1));
    }
    rejectAsset(value->value.put("extra",true));rejectAsset(value->value.put("schema",true));rejectAsset(value->value.put("sdkBuildKind","official"));
    rejectAsset(value->value.put("sdkAarSha256",NormalCaretSdkReceipt.INPUT_AAR_SHA256));
    for(String key:new String[]{"sourceCommit","sourceTree","runId","runAttempt","sdkManifestSha256","sdkAarSha256","sdkClassesJarSha256"})rejectReceipt(value->value.put(key,"1".repeat(key.contains("Sha256")?64:40)),false);
    for(String key:new String[]{"sdkAarModified","sdkClassTransformApplied","sourceCompileApplied","allOtherClassEntriesUnchanged","allNativeAndResourceEntriesUnchanged"}){
      rejectReceipt(value->value.put(key,false),false);rejectReceipt(value->value.put(key,"true"),false);
    }
    for(String key:new String[]{"asmTransformApplied","observerIncluded","actualAndroidExecution","releaseAcceptance","physicalDeviceAcceptance"})rejectReceipt(value->value.put(key,true),false);
    rejectReceipt(value->value.put("sdkGeckoEditableClassSha256","1".repeat(64)),true);
    rejectReceipt(value->value.put("sdkRuntimeCoordinate",NormalCaretSdkReceipt.INPUT_COORDINATE),true);
    rejectReceipt(value->value.put("sdkAarSha256",NormalCaretSdkReceipt.INPUT_AAR_SHA256),true);
    rejectReceipt(value->value.put("sdkAarBytes",-1),false);rejectReceipt(value->value.put("sdkAarBytes","123"),false);
    rejectReceipt(value->value.getJSONArray("changedClassEntries").put("org/mozilla/geckoview/GeckoEditable$Action.class"),false);
    rejectReceipt(value->value.put("changedClassEntries",new JSONArray()),false);
    for(String path:new String[]{"../patch","/tmp/patch","third-party/../patch","bad\\path"})rejectReceipt(value->value.getJSONObject("sourcePatch").put("path",path),false);
    rejectReceipt(value->value.getJSONObject("sourceRecipe").put("sha256","wrong"),false);
    JSONObject installed=new JSONObject().put("sourceCommit",asset.get("sourceCommit")).put("sourceTree",asset.get("sourceTree")).put("dirtySource",false);
    NormalCaretSdkReceipt.copySdkFields(asset,installed);installed.put("sdkBuildIdentity",new JSONObject(asset.toString()));
    NormalCaretSdkReceipt.requireInstalled(asset,installed);check(true);
    installed.getJSONObject("sdkBuildIdentity").put("sdkAarSha256","0".repeat(64));boolean rejected=false;
    try{NormalCaretSdkReceipt.requireInstalled(asset,installed);}catch(Exception expected){rejected=true;}check(rejected);
    installed.put("sdkBuildIdentity",new JSONObject(asset.toString()));installed.put("dirtySource",true);rejected=false;
    try{NormalCaretSdkReceipt.requireInstalled(asset,installed);}catch(Exception expected){rejected=true;}check(rejected);
    NativeCapabilityManifest inventory=NativeCapabilityManifest.officialGecko();check(!inventory.usesOfficialSdk());
    for(NativeCapabilityManifest.Capability capability:NativeCapabilityManifest.Capability.values())check(!inventory.supports(capability)&&inventory.status(capability)==NativeCapabilityManifest.Status.UNSUPPORTED);
    check(inventory.unsupportedSummary().contains("输入同步修正"));
    System.out.println(new JSONObject().put("status","passed").put("checks",checks).put("actualAndroidExecution",false).put("releaseAcceptance",false).put("physicalDeviceAcceptance",false).put("synthetic",true).put("scope","JVM counterfeit SDK asset/receipt rejection controls; no actual AAR or native correction acceptance"));
  }
}
