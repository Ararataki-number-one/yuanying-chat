package local.pocketchat;

import org.json.*;

/** Production progress over labelled local fixtures; no manual action or device executes. */
public final class FingerprintManualProgressHost {
  static final String ENV=FingerprintDeepBaselineHost.ENV,OTHER=FingerprintDeepBaselineHost.OTHER;
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  static JSONObject progress(JSONObject pair,String slot){return FingerprintReportComparison.manualChecklist(pair,slot,ENV,1);}
  static JSONObject edit(JSONObject pair,String slot,String key,String state,long at){
    JSONObject out=FingerprintReportComparison.manual(pair,slot,key,state,ENV,1,at);
    if(out==null)throw new AssertionError("Fixture edit rejected: "+slot+"/"+key+"/"+state);
    return out;
  }
  static JSONObject item(JSONObject progress,String key)throws Exception{
    JSONArray items=progress.getJSONArray("items");
    for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);if(key.equals(item.getString("key")))return item;}
    throw new AssertionError("Missing manual item: "+key);
  }
  static JSONObject slot(JSONObject pair,String slot)throws Exception{return pair.getJSONObject("slots").getJSONObject(slot);}
  static boolean noAcceptance(JSONObject value)throws Exception{
    return !value.getBoolean("physicalPhoneAcceptance")&&!value.getBoolean("protectionVerified")&&!value.getBoolean("leakVerdict");
  }
  static boolean emptyProgress(JSONObject value)throws Exception{
    return !value.getBoolean("saved")&&value.getInt("total")==7&&value.getInt("recorded")==0
        &&value.getInt("notTested")==7&&value.getInt("reportedFailures")==0&&value.getInt("notApplicable")==0
        &&!value.getBoolean("allItemsRecorded");
  }
  public static void main(String[] args)throws Exception{
    JSONObject pair=FingerprintReportComparisonHost.pair();String original=pair.toString();
    JSONObject first=progress(pair,"standard");
    check("A saved sample begins with seven explicitly untested manual operations",first.getBoolean("saved")&&first.getInt("total")==7&&first.getInt("recorded")==0&&first.getInt("notTested")==7&&!first.getBoolean("allItemsRecorded"));
    check("Untouched operations do not invent failures or inapplicable findings",first.getInt("reportedFailures")==0&&first.getInt("notApplicable")==0);
    check("Progress explicitly identifies user entries without phone or protection acceptance","user-entered-not-independent-verification".equals(first.getString("source"))&&noAcceptance(first));
    check("Listing progress does not mutate either stored report",original.equals(pair.toString()));
    for(String key:FingerprintReportComparison.MANUAL_KEYS){
      JSONObject item=item(first,key);
      check("An untouched item retains untested state and zero timestamp "+key,"not-tested".equals(item.getString("state"))&&item.getLong("recordedAt")==0&&"未测试".equals(item.getString("labelState"))&&!item.getString("label").isEmpty());
    }
    check("No saved report cannot appear as an already tested sample",emptyProgress(progress(new JSONObject(),"standard")));
    check("Null persisted input cannot appear as an already tested sample",emptyProgress(progress(null,"standard")));
    check("Unknown slot cannot inherit another slot's results",emptyProgress(progress(pair,"invalid"))&&"not-tested".equals(FingerprintReportComparison.manualState(pair,"invalid","login",ENV,1)));
    check("Foreign environment cannot read the saved manual progress",emptyProgress(FingerprintReportComparison.manualChecklist(pair,"standard",OTHER,1)));
    check("Retired environment generation does not inherit saved progress",emptyProgress(FingerprintReportComparison.manualChecklist(pair,"standard",ENV,2)));
    check("Invalid caller ownership cannot form a saved report",emptyProgress(FingerprintReportComparison.manualChecklist(pair,"standard","bad-owner",1)));
    check("Unknown operation remains untested instead of aliasing an existing entry","not-tested".equals(FingerprintReportComparison.manualState(pair,"standard","unknown-operation",ENV,1)));
    check("Missing reports have an explicit untested summary",FingerprintReportComparison.manualProgress(new JSONObject(),"standard",ENV,1).equals("尚无报告；人工兼容项目未测试"));

    pair=edit(pair,"standard","login","pass",6000);
    pair=edit(pair,"standard","input","fail",6001);
    pair=edit(pair,"standard","drawing","not-applicable",6002);
    JSONObject mixed=progress(pair,"standard");String mixedBefore=pair.toString();
    check("Recorded normal abnormal and inapplicable findings count separately",mixed.getInt("recorded")==3&&mixed.getInt("notTested")==4&&mixed.getInt("reportedFailures")==1&&mixed.getInt("notApplicable")==1&&!mixed.getBoolean("allItemsRecorded"));
    check("The selector recovers an already recorded abnormal choice","fail".equals(FingerprintReportComparison.manualState(pair,"standard","input",ENV,1)));
    check("The selector recovers an already recorded inapplicable choice","not-applicable".equals(FingerprintReportComparison.manualState(pair,"standard","drawing",ENV,1)));
    check("The untouched opposite slot retains independent progress",progress(pair,"enhanced").getInt("recorded")==0&&"not-tested".equals(FingerprintReportComparison.manualState(pair,"enhanced","input",ENV,1)));
    check("A normal operation keeps its actual user-entry time",item(mixed,"login").getLong("recordedAt")==6000);
    check("An abnormal operation keeps its actual user-entry time",item(mixed,"input").getLong("recordedAt")==6001);
    check("An inapplicable operation keeps its actual user-entry time",item(mixed,"drawing").getLong("recordedAt")==6002);
    check("An untested operation never borrows a neighboring timestamp",item(mixed,"attachment").getLong("recordedAt")==0);
    JSONObject exposed=FingerprintReportComparison.comparison(pair,ENV,1).getJSONObject("slots").getJSONObject("standard");
    check("The displayed slot exposes all original manual timestamps",exposed.getJSONObject("compatibilityUpdatedAt").length()==7&&exposed.getJSONObject("compatibilityUpdatedAt").getLong("input")==6001);
    exposed.getJSONObject("compatibilityUpdatedAt").put("input",42);
    item(mixed,"input").put("state","pass").put("recordedAt",43);
    check("Mutating either displayed projection cannot rewrite persisted findings",mixedBefore.equals(pair.toString())&&slot(pair,"standard").getJSONObject("compatibilityUpdatedAt").getLong("input")==6001);
    String card=FingerprintReportComparison.slotSummary(pair,"standard",ENV,1);
    check("The saved card distinguishes record count failures and inapplicability",card.contains("人工记录 3/7")&&card.contains("未测试 4")&&card.contains("异常 1")&&card.contains("不适用 1")&&card.contains("仅自行记录"));

    pair=edit(pair,"standard","input","not-tested",7000);
    JSONObject reset=progress(pair,"standard");
    check("Resetting to untested removes old completion and failure progress",reset.getInt("recorded")==2&&reset.getInt("notTested")==5&&reset.getInt("reportedFailures")==0&&reset.getInt("notApplicable")==1);
    check("Resetting to untested clears the old timestamp and selector value",item(reset,"input").getLong("recordedAt")==0&&"not-tested".equals(FingerprintReportComparison.manualState(pair,"standard","input",ENV,1)));
    for(String key:FingerprintReportComparison.MANUAL_KEYS)pair=edit(pair,"standard",key,"login".equals(key)?"fail":"drawing".equals(key)?"not-applicable":"pass",8000);
    JSONObject complete=progress(pair,"standard");
    check("All entries recorded can still contain a failure and an inapplicable operation",complete.getBoolean("allItemsRecorded")&&complete.getInt("recorded")==7&&complete.getInt("notTested")==0&&complete.getInt("reportedFailures")==1&&complete.getInt("notApplicable")==1);
    check("Completing every manual entry is never phone protection or leakage acceptance",noAcceptance(complete)&&!complete.has("score")&&!complete.has("protectionScore"));
    JSONObject inapplicable=pair;
    for(String key:FingerprintReportComparison.MANUAL_KEYS)inapplicable=edit(inapplicable,"standard",key,"not-applicable",8100);
    JSONObject allInapplicable=progress(inapplicable,"standard");
    check("All inapplicable entries are records without becoming positive protection results",allInapplicable.getBoolean("allItemsRecorded")&&allInapplicable.getInt("notApplicable")==7&&allInapplicable.getInt("reportedFailures")==0&&noAcceptance(allInapplicable));

    Object[] invalidStates={"verified","",JSONObject.NULL,true,42};
    for(Object state:invalidStates){JSONObject invalid=copy(pair);slot(invalid,"standard").getJSONObject("compatibility").put("input",state);check("Malformed manual state cannot become progress "+String.valueOf(state),emptyProgress(progress(invalid,"standard"))&&progress(invalid,"enhanced").getBoolean("saved"));}
    Object[] invalidTimes={0L,-1L,"8000",1.5,JSONObject.NULL};
    for(Object at:invalidTimes){JSONObject invalid=copy(pair);slot(invalid,"standard").getJSONObject("compatibilityUpdatedAt").put("input",at);check("Malformed recorded timestamp invalidates only the affected slot "+String.valueOf(at),emptyProgress(progress(invalid,"standard"))&&progress(invalid,"enhanced").getBoolean("saved"));}
    JSONObject malformedUntested=copy(pair);slot(malformedUntested,"standard").getJSONObject("compatibility").put("input","not-tested");
    check("An untested persisted entry with an old time cannot be relabelled current",emptyProgress(progress(malformedUntested,"standard")));
    check("An unknown saved schema cannot display completed progress",emptyProgress(progress(copy(pair).put("schema",2),"standard")));
    check("A forged phone-acceptance envelope cannot display completed progress",emptyProgress(progress(copy(pair).put("physicalPhoneAcceptance",true),"standard")));

    pair=edit(pair,"enhanced","attachment","fail",9000);String beforeReplace=pair.toString();
    JSONObject replaced=FingerprintReportComparisonHost.save(pair,"standard",FingerprintReportComparisonHost.report("standard",9,FingerprintDeepBaselineHost.B),FingerprintReportComparisonHost.metadata("standard",9));
    JSONObject replacement=progress(replaced,"standard");
    check("Replacing a report resets every manual result instead of borrowing prior progress",replacement.getBoolean("saved")&&replacement.getInt("recorded")==0&&replacement.getInt("notTested")==7&&!replacement.getBoolean("allItemsRecorded"));
    check("Replacing a report resets every old user-entry timestamp",slot(replaced,"standard").getJSONObject("compatibilityUpdatedAt").getLong("input")==0&&item(replacement,"login").getLong("recordedAt")==0);
    check("Replacing one report preserves the other mode's recorded findings",FingerprintObservationHistory.same(slot(replaced,"enhanced"),slot(pair,"enhanced"))&&progress(replaced,"enhanced").getInt("reportedFailures")==1);
    check("Replacing a report does not mutate the original saved pair",beforeReplace.equals(pair.toString()));
    JSONObject cleared=FingerprintReportComparison.clear(pair,"standard",ENV,1);
    check("Clearing one slot removes its progress and preserves the other slot",emptyProgress(progress(cleared,"standard"))&&progress(cleared,"enhanced").getInt("reportedFailures")==1);
    JSONObject both=FingerprintReportComparison.clear(pair,"",ENV,1);
    check("Clearing both slots leaves both checklists explicitly untested",emptyProgress(progress(both,"standard"))&&emptyProgress(progress(both,"enhanced")));
    check("An invalid persisted result cannot leak through the compact progress label",FingerprintReportComparison.manualProgress(copy(pair).put("schema",2),"standard",ENV,1).equals("尚无报告；人工兼容项目未测试"));
    System.out.println(J.obj("status","passed","versionScope","2.0.28-only","total",checks.length(),"passed",checks.length(),"checks",checks,
        "actualAndroidExecution",false,"actualGeckoExecution",false,"physicalPhoneAcceptance",false,"protectionEffectivenessAcceptance",false,
        "scope","Production manual checklist, state recovery, timestamps and owner-bound progress over synthetic host reports; no UI tap, actual compatibility action, encrypted save or phone acceptance"));
  }
}
