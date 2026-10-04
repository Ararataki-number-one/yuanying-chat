package local.pocketchat;

import java.io.IOException;
import org.json.*;

final class AppUpdateInfo {
  final String version,url,sha,notes;final long code,bytes;final int minSdk;
  AppUpdateInfo(JSONObject j)throws IOException {
    if(j.optInt("schema")!=1)throw new IOException("更新信息版本暂不支持");
    version=j.optString("version");code=j.optLong("versionCode");bytes=j.optLong("bytes");sha=j.optString("sha256");url=j.optString("downloadUrl");minSdk=j.optInt("minSdk");notes=j.optString("notes");
    AppUpdatePolicy.validate(version,code,bytes,sha,j.optString("signerSha256"),url,j.optString("package"),j.optString("abi"),minSdk);
    if(notes.length()>12000)throw new IOException("更新说明过长");
  }
}
