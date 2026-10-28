package local.pocketchat;

import org.json.*;

/** Pure summary controls; no Android view or real protection claim. */
public final class FingerprintAuditSummaryHost {
  static JSONArray checks=new JSONArray();
  static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));if(!value)throw new AssertionError(name);}
  static JSONObject report(Object... states){JSONArray rows=new JSONArray();for(Object state:states)rows.put(J.obj("state",state));return J.obj("fresh",true,"rows",rows);}
  static String show(JSONObject value){return FingerprintAuditSummary.summary(value,true,false,"","");}
  public static void main(String[] args)throws Exception{
    check("No report offers explicit checking without claiming observations",show(new JSONObject()).contains("尚未检查")&&!show(new JSONObject()).contains("已观察 0"));
    JSONObject valid=report("verified","available","restricted","issue","uncovered","failed");String summary=show(valid);
    check("Observed count includes differences as observations without summing them twice",summary.contains("已观察 4 项")&&summary.contains("发现差异 1 项"));
    check("Failed operation remains uncovered and is visible",summary.contains("尚未覆盖 2 项")&&summary.contains("含 1 项操作失败"));
    check("Available or restricted APIs do not become protection attestation",summary.contains("不代表全部保护通过或发生泄漏")&&!summary.contains("全部通过"));
    check("Caller-invalidated current document does not retain success counters",FingerprintAuditSummary.summary(valid,false,false,"","").contains("历史结果")&&!FingerprintAuditSummary.summary(valid,false,false,"","").contains("已观察 4"));
    check("Running check hides previous report counters",FingerprintAuditSummary.summary(valid,true,true,"","").equals("正在检查…"));
    check("Fresh false cannot be overridden by caller flag",show(J.obj("fresh",false,"rows",valid.optJSONArray("rows"))).contains("历史结果"));
    check("String true is not accepted as fresh Boolean",show(J.obj("fresh","true","rows",valid.optJSONArray("rows"))).contains("历史结果"));
    check("Missing row collection remains incomplete",show(J.obj("fresh",true)).contains("尚无可汇总"));
    check("Null and unknown row states remain uncovered",show(J.obj("fresh",true,"rows",J.arr(JSONObject.NULL,J.obj("state","invented"),J.obj("state",true)))).contains("尚未覆盖 3 项"));
    check("Check failure and storage failure stay visible in first-level summary",FingerprintAuditSummary.summary(valid,true,false,"检查未完成","保存失败").contains("检查未完成\n\n保存失败"));
    String before=valid.toString();show(valid);check("Display does not mutate original report",before.equals(valid.toString()));
    System.out.println(J.obj("status","passed","total",checks.length(),"passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualUiExecution",false,"protectionEffectivenessAcceptance",false));
  }
}
