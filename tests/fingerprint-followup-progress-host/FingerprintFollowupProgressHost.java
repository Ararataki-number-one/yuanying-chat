package local.pocketchat;

import org.json.*;

/** Pure-Java progress and reference fixtures; no device or privacy attestation. */
public final class FingerprintFollowupProgressHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));if(!value)throw new AssertionError(name);}
  static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  static JSONObject manual(JSONObject pair,String slot,String key,String state,long at){return FingerprintReportComparison.manual(pair,slot,key,state,FingerprintDeepBaselineHost.ENV,1,at);}
  public static void main(String[] args)throws Exception{
    String env=FingerprintDeepBaselineHost.ENV;JSONObject pair=FingerprintReportComparisonHost.pair();String original=pair.toString();
    JSONObject progress=FingerprintReportComparison.manualChecklist(pair,"standard",env,1);
    check("A saved sample begins with seven explicitly untested manual operations",progress.getBoolean("saved")&&progress.getInt("recorded")==0&&progress.getInt("notTested")==7&&!progress.getBoolean("allItemsRecorded"));
    check("Listing manual progress does not mutate stored observations",original.equals(pair.toString()));
    check("Unknown slot is never treated as an already tested sample",!FingerprintReportComparison.manualChecklist(pair,"invalid",env,1).getBoolean("saved")&&FingerprintReportComparison.manualState(pair,"invalid","login",env,1).equals("not-tested"));
    check("Foreign environment cannot read the other environment's manual result",!FingerprintReportComparison.manualChecklist(pair,"standard",FingerprintDeepBaselineHost.OTHER,1).getBoolean("saved"));
    check("Retired environment generation does not inherit progress",!FingerprintReportComparison.manualChecklist(pair,"standard",env,2).getBoolean("saved"));
    pair=manual(pair,"standard","login","pass",6000);pair=manual(pair,"standard","input","fail",6001);pair=manual(pair,"standard","drawing","not-applicable",6002);
    progress=FingerprintReportComparison.manualChecklist(pair,"standard",env,1);
    check("Recorded normal abnormal and inapplicable values remain distinct",progress.getInt("recorded")==3&&progress.getInt("reportedFailures")==1&&progress.getInt("notApplicable")==1&&progress.getInt("notTested")==4);
    check("The edit selector can recover the existing abnormal selection",FingerprintReportComparison.manualState(pair,"standard","input",env,1).equals("fail"));
    check("A slot edit cannot change the opposite mode's progress",FingerprintReportComparison.manualChecklist(pair,"enhanced",env,1).getInt("recorded")==0);
    JSONObject visible=FingerprintReportComparison.comparison(pair,env,1).getJSONObject("slots").getJSONObject("standard");
    check("A displayed manual entry retains its own recording time",visible.getJSONObject("compatibilityUpdatedAt").getLong("input")==6001);
    pair=manual(pair,"standard","input","not-tested",7000);progress=FingerprintReportComparison.manualChecklist(pair,"standard",env,1);
    check("Resetting to untested removes both completion and failure progress",progress.getInt("recorded")==2&&progress.getInt("reportedFailures")==0&&FingerprintReportComparison.comparison(pair,env,1).getJSONObject("slots").getJSONObject("standard").getJSONObject("compatibilityUpdatedAt").getLong("input")==0);
    for(String key:FingerprintReportComparison.MANUAL_KEYS)pair=manual(pair,"standard",key,"pass",8000);
    progress=FingerprintReportComparison.manualChecklist(pair,"standard",env,1);
    check("Completing all manual entries is never phone or protection acceptance",progress.getBoolean("allItemsRecorded")&&!progress.getBoolean("physicalPhoneAcceptance")&&!progress.getBoolean("protectionVerified")&&!progress.getBoolean("leakVerdict"));
    check("The progress label explicitly identifies user-recorded findings",FingerprintReportComparison.manualProgress(pair,"standard",env,1).contains("仅自行记录"));
    check("Malformed persisted manual state does not become a success",!FingerprintReportComparison.manualChecklist(copy(pair).put("schema",2),"standard",env,1).getBoolean("saved"));

    JSONObject report=FingerprintContextBaselinesHost.report(1000,FingerprintDeepBaselineHost.A),meta=FingerprintContextBaselinesHost.meta(),saved=new JSONObject();
    JSONObject empty=FingerprintContextBaselines.overview(saved,report,meta);
    check("An overview starts with four unpinned independent contexts",empty.getInt("retainedContexts")==0&&empty.getJSONArray("contexts").length()==4&&empty.getInt("comparableContexts")==0);
    for(String context:FingerprintContextBaselines.CONTEXTS)saved=FingerprintContextBaselines.replace(saved,report,meta,context,2000);
    String savedBefore=saved.toString(),reportBefore=report.toString();
    JSONObject overview=FingerprintContextBaselines.overview(saved,report,meta);
    check("Four valid independent references remain separately comparable",overview.getInt("retainedContexts")==4&&overview.getInt("comparableContexts")==4);
    check("The overview explicitly leaves current-document checks to its owner",overview.getBoolean("callerMustCheckLiveDocument"));
    check("Reference comparison is not a protection leakage or cross-context verdict",!overview.getBoolean("protectionVerified")&&!overview.getBoolean("leakVerdict")&&!overview.getBoolean("crossExecutionContextComparison"));
    JSONObject changedMeta=copy(meta).put("engineVersion","different-engine");
    JSONObject changed=FingerprintContextBaselines.overview(saved,report,changedMeta);
    check("A new engine keeps old references but cannot silently compare them",changed.getInt("retainedContexts")==4&&changed.getInt("comparableContexts")==0);
    check("A different engine is shown as a specific separation reason",FingerprintContextBaselines.overviewSummary(saved,report,changedMeta).contains("内核版本"));
    check("Single-context details explain the changed condition",FingerprintContextBaselines.summary(saved,report,changedMeta,"worker").contains("内核版本"));
    JSONObject ordinary=copy(report);ordinary.getJSONObject("signals").remove("apiChecks");ordinary.getJSONObject("signals").remove("apiContexts");ordinary.remove("requestIdentity");ordinary.put("requestIdentityNetwork",false);
    JSONObject noDeep=FingerprintContextBaselines.overview(saved,ordinary,meta);
    check("A light sample preserves all references without inventing deep comparisons",noDeep.getInt("retainedContexts")==4&&noDeep.getInt("comparableContexts")==0);
    boolean cannotCapture=true;for(int i=0;i<4;i++)cannotCapture&=!noDeep.getJSONArray("contexts").getJSONObject(i).getBoolean("captureEvidenceComplete");
    check("Light samples do not become fixed-reference capture evidence",cannotCapture);
    JSONObject cleared=FingerprintContextBaselines.clear(saved,env,1,"worker");
    check("Clearing one context retains exactly the other three",FingerprintContextBaselines.overview(cleared,report,meta).getInt("retainedContexts")==3&&FingerprintContextBaselines.hasReference(cleared,env,1,"frame")&&!FingerprintContextBaselines.hasReference(cleared,env,1,"worker"));
    check("Overview and detail reads do not modify the report or reference store",savedBefore.equals(saved.toString())&&reportBefore.equals(report.toString()));
    check("Missing live metadata cannot expose retained reference ownership",FingerprintContextBaselines.overview(saved,null,null).getInt("retainedContexts")==0);
    System.out.println(J.obj("status","passed","passed",checks.length(),"total",checks.length(),"checks",checks,
        "actualAndroidExecution",false,"actualGeckoExecution",false,"physicalPhoneAcceptance",false,"protectionEffectivenessAcceptance",false).toString());
  }
}
