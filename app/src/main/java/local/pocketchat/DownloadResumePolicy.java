package local.pocketchat;

import org.json.JSONObject;

/** Describe only an operation the retained bytes and source can actually support. */
final class DownloadResumePolicy {
  static final String SAVE="继续保存",RESUME="继续下载",RESTART="重新下载";
  private DownloadResumePolicy(){}
  static String action(JSONObject row,boolean partial,boolean requestAvailable){
    if(!row.optString("pendingDestination").isEmpty()||row.optBoolean("complete")&&partial)return SAVE;
    String kind=row.optString("transferKind");
    if(!"gecko-response".equals(kind)&&!"blob".equals(kind)&&partial&&requestAvailable&&!row.optString("validator").isEmpty()&&!row.optString("resource").isEmpty())return RESUME;
    return RESTART;
  }
  static boolean incomplete(JSONObject row){
    if(row==null||!(row.opt("complete") instanceof Boolean)||row.optBoolean("complete")||!row.optString("pendingDestination").isEmpty()||!row.optString("uri").isEmpty())return false;
    String state=row.optString("state");return "paused".equals(state)||"failed".equals(state)||"cancelled".equals(state);
  }
  static String paused(JSONObject row,boolean partial,boolean requestAvailable){
    String action=action(row,partial,requestAvailable);
    return SAVE.equals(action)?"文件已下载，可继续保存":RESUME.equals(action)?"下载已暂停，可继续下载":"下载已暂停，此文件需要重新下载";
  }
}
