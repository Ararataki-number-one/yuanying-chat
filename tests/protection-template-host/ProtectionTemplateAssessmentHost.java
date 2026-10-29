package local.pocketchat;

import org.json.*;

/** Contract checks on production assessment code; SDK, receipts and phone results are synthetic. */
public final class ProtectionTemplateAssessmentHost {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean ok){checks.put(J.obj("name",name,"pass",ok));if(!ok)throw new AssertionError(name);}
  static JSONObject copy(JSONObject input){return FingerprintObservationHistory.copy(input);}
  static JSONObject runtime(String slot)throws Exception{
    long revision="enhanced".equals(slot)?8:7;
    JSONObject value=FingerprintReportComparisonHost.metadata(slot,revision);
    value.put("sourceOrigin","https://chatgpt.com/c/current?secret=never-exported");
    value.put("templateApplied",true).put("nativeProtection",FingerprintReportComparisonHost.nativeSettings(slot));return value;
  }
  static JSONObject assess(String slot,JSONObject runtime,JSONObject pair){return ProtectionTemplateAssessment.assess(BrowserIdentitySpec.preset("enhanced".equals(slot)?BrowserIdentitySpec.RFP:BrowserIdentitySpec.MOBILE),runtime,pair);}
  static JSONObject compatibility(JSONObject value){return value.optJSONObject("compatibility");}
  public static void main(String[] args)throws Exception{
    JSONObject pair=FingerprintReportComparisonHost.pair(),base=runtime("standard"),standard=assess("standard",base,pair);
    check("A matching standard readback is a setting confirmation",standard.getString("state").equals("confirmed")&&standard.getBoolean("nativeReadbackConfirmed")&&!standard.getBoolean("nativeProtectionRequested"));
    check("A confirmed setting never attests API protection or phone acceptance",!standard.getBoolean("protectionEffectivenessVerified")&&!standard.getBoolean("physicalPhoneAcceptance")&&!standard.getBoolean("fullDesktopIdentityVerified"));
    check("Default mobile guidance does not change a template",standard.getString("suggestedTemplateId").equals(BrowserIdentitySpec.MOBILE)&&!standard.getBoolean("automaticTemplateChange"));
    check("A default follow-system template can use the actual SDK language observation",compatibility(standard).getString("state").equals("partially-recorded")&&compatibility(standard).getInt("untestedCount")==7);
    check("An enhanced exact readback remains experimental",assess("enhanced",runtime("enhanced"),pair).getBoolean("experimental")&&assess("enhanced",runtime("enhanced"),pair).getBoolean("nativeReadbackConfirmed"));
    check("Enhanced summary does not advertise independently verified compatibility",ProtectionTemplateAssessment.summary(assess("enhanced",runtime("enhanced"),pair)).contains("仍为实验模式"));
    JSONObject pending=copy(base).put("templateApplied",false);
    check("A saved but unapplied template cannot inherit a confirmed receipt",assess("standard",pending,pair).getString("state").equals("pending-application")&&!assess("standard",pending,pair).getBoolean("nativeReadbackConfirmed"));
    check("An unapplied template has no current compatibility evidence",compatibility(assess("standard",pending,pair)).getString("reason").equals("template-not-applied"));
    JSONObject failed=runtime("enhanced");failed.getJSONObject("nativeProtection").put("state","failed").put("settingsReadbackConfirmed",false).put("newRequestsBlocked",true);
    check("A failed strict request is not a protection confirmation",assess("enhanced",failed,pair).getString("state").equals("confirmation-failed")&&!assess("enhanced",failed,pair).getBoolean("nativeReadbackConfirmed"));
    for(String field:new String[]{"received","settingsReadbackConfirmed"}){
      JSONObject invalid=runtime("enhanced");invalid.getJSONObject("nativeProtection").put(field,"true");
      check("A string boolean cannot confirm "+field,!assess("enhanced",invalid,pair).getBoolean("nativeReadbackConfirmed"));
    }
    for(String field:new String[]{"desiredLevel","level","generation","token"}){
      JSONObject invalid=runtime("enhanced");invalid.getJSONObject("nativeProtection").put(field,field.endsWith("Level")||field.equals("level")?1:0);
      check("A mismatching or zero native receipt field is not confirmed "+field,!assess("enhanced",invalid,pair).getBoolean("nativeReadbackConfirmed"));
    }
    JSONObject off=runtime("enhanced");off.getJSONObject("nativeProtection").put("observedFingerprinting",false);
    check("An enhanced label cannot confirm a disabled underlying setting",!assess("enhanced",off,pair).getBoolean("nativeReadbackConfirmed"));
    JSONObject contradictory=runtime("enhanced");contradictory.getJSONObject("nativeProtection").put("newRequestsBlocked",true);
    check("A contradictory blocked strict receipt stays unconfirmed",!assess("enhanced",contradictory,pair).getBoolean("nativeReadbackConfirmed"));
    JSONObject alienScope=runtime("enhanced");alienScope.getJSONObject("nativeProtection").put("scope","all-apis-protected");
    check("An unrelated receipt scope is not a native setting confirmation",!assess("enhanced",alienScope,pair).getBoolean("nativeReadbackConfirmed"));
    for(String field:new String[]{"configurationRevision","appVersionCode","appVersion","engineVersion"}){
      JSONObject changed=copy(base);changed.put(field,field.endsWith("Revision")||field.endsWith("Code")?99:"different");
      check("Historical mode records do not attest the current "+field,compatibility(assess("standard",changed,pair)).getString("reason").equals("observation-context-differs"));
    }
    JSONObject origin=copy(base).put("sourceOrigin","https://other.example");
    check("Records from another current origin are not reused",compatibility(assess("standard",origin,pair)).getString("reason").equals("observation-source-differs"));
    JSONObject noOrigin=copy(base);noOrigin.remove("sourceOrigin");
    check("An unavailable source cannot become current evidence",compatibility(assess("standard",noOrigin,pair)).getString("state").equals("unavailable"));
    JSONObject language=copy(base).put("requestedLocales",new JSONArray().put("ja-JP"));
    check("Actual SDK language changes retire current compatibility",compatibility(assess("standard",language,pair)).getString("reason").equals("language-request-differs"));
    JSONObject noLanguage=copy(base);noLanguage.remove("expectedLocales");
    check("Missing actual language arrays are not synthesized",compatibility(assess("standard",noLanguage,pair)).getString("reason").equals("current-language-unavailable"));
    JSONObject foreign=copy(base).put("environmentId",FingerprintDeepBaselineHost.OTHER);
    check("A foreign environment cannot inherit compatibility records",compatibility(assess("standard",foreign,pair)).getString("state").equals("unavailable"));
    JSONObject generation=copy(base).put("environmentGeneration",2);
    check("A new environment generation cannot inherit old records",compatibility(assess("standard",generation,pair)).getString("state").equals("unavailable"));
    JSONObject full=copy(pair);
    for(String key:FingerprintReportComparison.MANUAL_KEYS)full=FingerprintReportComparison.manual(full,"standard",key,"pass",FingerprintDeepBaselineHost.ENV,1,6000);
    JSONObject human=assess("standard",base,full);
    check("Complete positive checklists remain explicitly user-reported",compatibility(human).getBoolean("allManuallyRecordedNormal")&&compatibility(human).getString("state").equals("user-recorded-normal")&&!compatibility(human).getBoolean("independentVerification"));
    check("Positive manual records never upgrade physical-phone acceptance",!human.getBoolean("physicalPhoneAcceptance")&&!compatibility(human).getBoolean("physicalPhoneAcceptance")&&!human.getBoolean("protectionEffectivenessVerified"));
    JSONObject issue=FingerprintReportComparison.manual(full,"standard","input","fail",FingerprintDeepBaselineHost.ENV,1,6100);
    check("One manual issue is visible without a security verdict",compatibility(assess("standard",base,issue)).getString("state").equals("user-reported-issue")&&compatibility(assess("standard",base,issue)).getInt("failureCount")==1);
    JSONObject excluded=FingerprintReportComparison.manual(full,"standard","input","not-applicable",FingerprintDeepBaselineHost.ENV,1,6100);
    check("Not-applicable is not silently counted as normal",compatibility(assess("standard",base,excluded)).getString("state").equals("recorded-with-exclusions")&&!compatibility(assess("standard",base,excluded)).getBoolean("allManuallyRecordedNormal"));
    check("Missing mode observations stay unknown",compatibility(assess("standard",base,new JSONObject())).getString("reason").equals("no-mode-observation"));
    JSONObject compatible=ProtectionTemplateAssessment.assess(BrowserIdentitySpec.preset(BrowserIdentitySpec.COMPATIBLE),base,pair);
    check("A compatibility-mode template does not borrow a standard-mode record",compatibility(compatible).getString("reason").equals("no-compatible-mode-slot"));
    check("Compatibility guidance does not advertise the standard tracking policy",ProtectionTemplateAssessment.summary(compatible).contains("兼容模板未请求现有追踪器列表拦截"));
    check("Invalid templates have no positive or automatic action",ProtectionTemplateAssessment.assess(null,base,pair).getString("state").equals("invalid-template")&&!ProtectionTemplateAssessment.assess(null,base,pair).getBoolean("automaticTemplateChange"));
    JSONObject secret=copy(base).put("token","private-token").put("proxy","socks://private-user:secret@example").put("password","never-return");
    String encoded=assess("standard",secret,pair).toString();
    check("Assessment output never copies raw runtime secrets or document URLs",!encoded.contains("private-token")&&!encoded.contains("private-user")&&!encoded.contains("never-return")&&!encoded.contains("never-exported"));
    JSONObject caps=standard.getJSONObject("capabilities");
    check("Capability identity is pinned to the shipped SDK",caps.getString("sdkCoordinate").equals(NativeCapabilityManifest.SDK_COORDINATE)&&caps.getString("runtimeCoordinate").equals(NativeCapabilityManifest.SDK_RUNTIME_COORDINATE));
    check("Observation capabilities are not control enablement",caps.getBoolean("observationsDoNotEnableControls")&&!caps.getBoolean("apiProtectionAttested"));
    JSONArray unsupported=caps.getJSONArray("unavailableControls");boolean custom=true,fpp=false;
    for(int i=0;i<unsupported.length();i++){JSONObject row=unsupported.getJSONObject(i);if(row.getString("id").equals("independent-fpp"))fpp=row.getString("status").equals("not-verified-for-pinned-sdk");else custom&=row.getString("status").equals("unsupported");}
    check("Unsupported native custom controls remain unavailable",custom&&unsupported.length()==7);
    check("A separate FPP API is not invented from current online docs",fpp);
    check("Caller-owned mode records are never mutated",FingerprintObservationHistory.same(pair,FingerprintReportComparisonHost.pair()));
    System.out.println(J.obj("status","passed","total",checks.length(),"passed",checks.length(),"checks",checks,
        "actualAndroidExecution",false,"actualGeckoExecution",false,"physicalPhoneAcceptance",false,"protectionEffectivenessAcceptance",false));
  }
}
