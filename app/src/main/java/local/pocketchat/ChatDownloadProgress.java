package local.pocketchat;

import org.json.JSONObject;

/** A read-only projection of the current environment's actual download task. */
final class ChatDownloadProgress {
  final String id,name,state,reason;final long received,total;final boolean determinate,busy,finished;final int progress;
  boolean sameDisplay(ChatDownloadProgress other){return other!=null&&id.equals(other.id)&&name.equals(other.name)&&state.equals(other.state)&&reason.equals(other.reason)&&received==other.received&&total==other.total&&determinate==other.determinate&&busy==other.busy&&finished==other.finished&&progress==other.progress;}
  private ChatDownloadProgress(JSONObject task){
    id=task.optString("id");name=task.optString("name","文件");state=task.optString("state");reason=task.optString("reason");received=Math.max(0,task.optLong("received"));long expected=task.optLong("total",-1);total=expected>0?expected:"saved".equals(state)?received:expected;
    determinate=total>0||"saved".equals(state);progress=total>0?(int)Math.max(0,Math.min(1000,received/(double)total*1000)):"saved".equals(state)?1000:0;
    busy="preparing".equals(state)||"downloading".equals(state)||"saving".equals(state)||"choosing".equals(state);
    finished="saved".equals(state)||"failed".equals(state)||"cancelled".equals(state);
  }
  static ChatDownloadProgress read(JSONObject task,int slot,String environmentId,int generation){
    if(task==null||environmentId==null||environmentId.isEmpty()||task.optString("id").isEmpty()||task.optInt("slot",-1)!=slot||!environmentId.equals(task.optString("environmentId"))||task.optInt("environmentGeneration",-1)!=generation)return null;
    String state=task.optString("state");if(!("preparing".equals(state)||"downloading".equals(state)||"saving".equals(state)||"choosing".equals(state)||"paused".equals(state)||"saved".equals(state)||"failed".equals(state)||"cancelled".equals(state)))return null;
    return new ChatDownloadProgress(task);
  }
}
