package local.pocketchat;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.os.Build;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.JSONObject;

/** Integration-only byte and source identity; no runtime production endpoint. */
final class IntegrationBuildIdentity {
  private IntegrationBuildIdentity() {}
  static JSONObject read(Context context) throws Exception {
    if (!"local.pocketchat.test".equals(context.getPackageName()))
      throw new SecurityException("Synthetic integration package required");
    byte[] stamp;
    try (InputStream in=context.getAssets().open("pocketchat-integration-build.json")) {
      String text=J.text(in,8192);stamp=text.getBytes(StandardCharsets.UTF_8);
    }
    JSONObject value=new JSONObject(new String(stamp,StandardCharsets.UTF_8));
    if (value.optInt("schema")!=1 || !value.optString("sourceCommit").matches("[0-9a-f]{40}")
        || !value.optString("sourceTree").matches("[0-9a-f]{40}") || value.optBoolean("dirtySource",true))
      throw new IllegalStateException("Clean build source stamp required");
    PackageInfo info=context.getPackageManager().getPackageInfo(context.getPackageName(),0);
    long code=Build.VERSION.SDK_INT>=28?info.getLongVersionCode():info.versionCode;
    if (code!=value.optLong("versionCode") || !info.versionName.equals(value.optString("version")))
      throw new IllegalStateException("Installed package differs from source stamp");
    JSONObject sdk=NormalCaretSdkReceipt.read(context);
    NormalCaretSdkReceipt.requireSource(sdk,value);
    NormalCaretSdkReceipt.copySdkFields(sdk,value);
    value.put("sdkBuildIdentity",sdk);
    File apk=new File(context.getApplicationInfo().sourceDir);
    MessageDigest digest=MessageDigest.getInstance("SHA-256");
    try (InputStream in=new FileInputStream(apk)) {
      byte[] block=new byte[65536];int count;
      while ((count=in.read(block))!=-1) digest.update(block,0,count);
    }
    value.put("package",context.getPackageName());value.put("apkBytes",apk.length());
    value.put("apkSha256",hex(digest.digest()));
    value.put("buildStampSha256",hex(MessageDigest.getInstance("SHA-256").digest(stamp)));
    value.put("scope","Installed synthetic integration APK bytes and embedded source stamp only");
    return value;
  }
  private static String hex(byte[] bytes) {
    StringBuilder result=new StringBuilder();
    for (byte value:bytes)result.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
    return result.toString();
  }
}
