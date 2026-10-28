package local.pocketchat;

import org.json.*;

/** Display only: observed fields are neither a protection score nor an attestation. */
final class FingerprintAuditSummary {
  static String summary(JSONObject report,boolean current,boolean running,String error,String storageIssue){
    StringBuilder text=new StringBuilder();
    if(running)text.append("正在检查…");
    else if(report==null||report.length()==0)text.append("尚未检查。点按本机检查后，在这里查看已观察、发现差异和尚未覆盖的项目。");
    else if(!current||!Boolean.TRUE.equals(report.opt("fresh")))text.append("历史结果，当前页面或配置尚未核对。请重新检查后再看本次摘要。");
    else{
      JSONArray rows=report.optJSONArray("rows");
      if(rows==null||rows.length()==0)text.append("结果尚不完整，尚无可汇总的观测。");
      else{
        int observed=0,different=0,uncovered=0,failed=0;
        for(int i=0;i<rows.length();i++){
          JSONObject row=rows.optJSONObject(i);String state=row==null?"":row.optString("state");
          if("issue".equals(state)){observed++;different++;}
          else if("verified".equals(state)||"available".equals(state)||"restricted".equals(state))observed++;
          else{uncovered++;if("failed".equals(state))failed++;}
        }
        text.append("已观察 ").append(observed).append(" 项\n发现差异 ").append(different).append(" 项\n尚未覆盖 ").append(uncovered).append(" 项");
        if(failed>0)text.append("（含 ").append(failed).append(" 项操作失败）");
        text.append("\n观测与差异只描述本次字段或有限操作，不代表全部保护通过或发生泄漏。");
      }
    }
    if(error!=null&&!error.isEmpty())text.append("\n\n").append(error);
    if(storageIssue!=null&&!storageIssue.isEmpty())text.append("\n\n").append(storageIssue);
    return text.toString();
  }
}
