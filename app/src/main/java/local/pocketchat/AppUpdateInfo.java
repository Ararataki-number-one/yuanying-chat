package local.pocketchat;

import java.io.IOException;
import org.json.*;

final class AppUpdateInfo {
  final String version,url,sha,notes,technicalDetails,publishedAt,channel,tag;final long code,bytes;final int minSdk,candidateNumber;final boolean userNotes;
  AppUpdateInfo(JSONObject j)throws IOException {
    if(j.optInt("schema")!=1)throw new IOException("更新信息版本暂不支持");
    version=j.optString("version");code=j.optLong("versionCode");bytes=j.optLong("bytes");sha=j.optString("sha256");url=j.optString("downloadUrl");minSdk=j.optInt("minSdk");notes=j.optString("notes");
    channel=j.optString("channel",AppUpdatePolicy.versionChannel(version));candidateNumber=j.optInt("candidateNumber",0);tag=AppUpdatePolicy.tag(version,channel,candidateNumber);
    Object sequence=j.opt("candidateNumber");if("candidate".equals(channel)&&(!(sequence instanceof Number)||((Number)sequence).doubleValue()!=candidateNumber))throw new IOException("候选版序号不完整");
    AppUpdatePolicy.validate(version,code,bytes,sha,j.optString("signerSha256"),url,j.optString("package"),j.optString("abi"),minSdk,channel,candidateNumber);
    if(j.has("releaseTag")&&!tag.equals(j.optString("releaseTag")))throw new IOException("更新版本与发布地址不符");
    if(notes.length()>12000)throw new IOException("更新说明过长");
    userNotes="user".equals(j.optString("notesRole",""));publishedAt=j.optString("publishedAt","").length()<=40?j.optString("publishedAt",""):"";
    String technical=j.optString("technicalDetails","");technicalDetails=technical.length()<=12000&&(notes+technical).getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=49152?technical:"技术说明较长，请查看此版本的官方发布页。";
  }
  String display(){return AppUpdatePolicy.display(version,channel,candidateNumber);}
}
