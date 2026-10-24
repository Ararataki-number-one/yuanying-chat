package local.pocketchat;

import android.content.Context;
import org.json.*;

/** Controls app-owned unsent draft copies, never the live editor or delivery journal. */
final class LocalDraftPolicy {
  static boolean enabled(Context context){return AppPrefs.enabled(context,"saveDraft");}
  static long revision(Context context){return context.getSharedPreferences("chat",0).getLong("localDraftPolicyRevision",0);}
  static boolean mayRestore(Context context,JSONObject snapshot){return enabled(context)&&snapshot.optLong("localDraftPolicyRevision",-1)==revision(context);}
  static JSONObject snapshot(Context context,JSONObject value){return snapshot(context,value,revision(context));}
  static JSONObject snapshot(Context context,JSONObject value,long capturedRevision){
    JSONObject copy=J.parse(value.toString());
    try{
      copy.put("localDraftPolicyRevision",revision(context));
      if(!enabled(context)||capturedRevision!=revision(context)){copy.put("draft",JSONObject.NULL).put("draftComplete",false).put("draftOmittedReason","local-saving-disabled");copy.remove("selectionStart");copy.remove("selectionEnd");}
    }catch(JSONException ignored){}
    return copy;
  }
  /** Gecko 157 SessionState serializes history, scrolldata and formdata separately. */
  static String checkpoint(String value,boolean keepDrafts){
    if(value==null||keepDrafts)return value;
    try{JSONObject state=new JSONObject(value);state.remove("formdata");return state.toString();}catch(JSONException invalid){return null;}
  }
  static String unavailable(Context context){return enabled(context)?"草稿暂存未完成，请稍后重试":"本机草稿保存已关闭，请先手动保留输入";}
}
