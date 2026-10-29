package local.pocketchat;

import org.json.*;
import java.util.*;

/** Read-only template guidance. A setting receipt or user checklist is never a
 * proof of fingerprint protection, site compatibility, or physical-phone testing. */
final class ProtectionTemplateAssessment {
  static final int SCHEMA=1;
  private static final String[] MANUAL={"login","input","attachment","drawing","recovery","restart","background"};
  private static final String[] REQUIRED_GROUP={"engineVersion","appVersion","appVersionCode","configurationRevision"};

  private static JSONObject object(JSONObject value,String key){JSONObject out=value==null?null:value.optJSONObject(key);return out==null?new JSONObject():out;}
  private static void put(JSONObject value,String key,Object item){try{value.put(key,item);}catch(JSONException invalid){throw new IllegalArgumentException(invalid);}}
  private static boolean integer(Object value,long min,long max){return value instanceof Number&&Double.isFinite(((Number)value).doubleValue())&&((Number)value).doubleValue()==((Number)value).longValue()&&((Number)value).longValue()>=min&&((Number)value).longValue()<=max;}
  private static boolean same(Object first,Object second){return FingerprintObservationHistory.same(first,second);}

  static JSONObject assess(BrowserIdentitySpec requested,JSONObject runtime,JSONObject savedComparison){
    JSONObject out=J.obj("schema",SCHEMA,"kind","native-template-assessment","suggestedTemplateId",BrowserIdentitySpec.MOBILE,
        "automaticTemplateChange",false,"protectionEffectivenessVerified",false,"physicalPhoneAcceptance",false,
        "fullDesktopIdentityVerified",false,"capabilities",capabilities(),"manualEvidenceSource","user-entered-not-independent-verification");
    if(requested==null||!requested.validate().isEmpty()){
      put(out,"state","invalid-template");put(out,"compatibility",unavailable("invalid-template"));return out;
    }
    if(runtime==null)runtime=new JSONObject();
    int level=requested.protectionLevel();boolean applied=Boolean.TRUE.equals(runtime.opt("templateApplied"));
    JSONObject receipt=object(runtime,"nativeProtection");
    boolean confirmed=applied&&confirmed(receipt,level);
    String state=!applied?"pending-application":confirmed?"confirmed":
        "failed".equals(receipt.optString("state"))?"confirmation-failed":"pending-confirmation";
    put(out,"state",state);put(out,"templateId",requested.templateId);put(out,"display",requested.display);
    put(out,"privacy",requested.privacy);put(out,"experimental",level>=2);put(out,"nativeReadbackConfirmed",confirmed);
    put(out,"nativeProtectionRequested",level>=2);put(out,"strictNewRequestAdmission",level>=2);
    put(out,"timezoneStrategy",requested.timezoneStrategy);
    put(out,"compatibility",compatibility(requested,runtime,savedComparison,applied));
    return out;
  }

  private static boolean confirmed(JSONObject receipt,int level){
    return "native-setting-new-request-admission".equals(receipt.optString("scope"))
        &&Boolean.FALSE.equals(receipt.opt("fullApiProtectionAttested"))
        &&"confirmed".equals(receipt.optString("state"))
        &&integer(receipt.opt("desiredLevel"),level,level)&&integer(receipt.opt("level"),level,level)
        &&integer(receipt.opt("generation"),1,9007199254740991L)&&integer(receipt.opt("token"),1,9007199254740991L)
        &&Boolean.TRUE.equals(receipt.opt("received"))&&Boolean.TRUE.equals(receipt.opt("settingsReadbackConfirmed"))
        &&Boolean.valueOf(level>=2).equals(receipt.opt("observedFingerprinting"))
        &&(level<2||Boolean.FALSE.equals(receipt.opt("newRequestsBlocked")));
  }

  private static JSONObject unavailable(String reason){return J.obj("state","unavailable","reason",reason,
      "recordedCount",0,"untestedCount",MANUAL.length,"failureCount",0,"notApplicableCount",0,
      "allManuallyRecordedNormal",false,"independentVerification",false,"physicalPhoneAcceptance",false);}

  private static JSONObject compatibility(BrowserIdentitySpec requested,JSONObject runtime,JSONObject saved,boolean applied){
    if(!applied)return unavailable("template-not-applied");
    if("compatibility".equals(requested.privacy))return unavailable("no-compatible-mode-slot");
    String id=runtime.optString("environmentId");Object generation=runtime.opt("environmentGeneration");
    if(!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")||!integer(generation,0,Integer.MAX_VALUE))return unavailable("environment-unavailable");
    JSONObject restored=FingerprintReportComparison.restore(saved,id,((Number)generation).intValue());
    String slot="native-rfp".equals(requested.privacy)?"enhanced":"standard";
    JSONObject snapshot=object(object(restored,"slots"),slot);if(snapshot.length()==0)return unavailable("no-mode-observation");
    JSONObject template=object(snapshot,"template"),group=object(snapshot,"group");
    if(!requested.templateId.equals(template.optString("templateId")))return unavailable("template-differs");
    if(!(runtime.opt("requestedLocales") instanceof JSONArray)||!(runtime.opt("expectedLocales") instanceof JSONArray))return unavailable("current-language-unavailable");
    if(!same(template.opt("requestedLocales"),runtime.opt("requestedLocales"))||!same(template.opt("expectedLocales"),runtime.opt("expectedLocales")))return unavailable("language-request-differs");
    for(String key:REQUIRED_GROUP){
      Object current=runtime.opt(key);boolean present="engineVersion".equals(key)||"appVersion".equals(key)
          ?current instanceof String&&!((String)current).isEmpty():integer(current,1,Long.MAX_VALUE);
      if(!present)return unavailable("current-version-unavailable");
      if(!same(current,group.opt(key)))return unavailable("observation-context-differs");
    }
    String origin=FingerprintObservationHistory.origin(runtime.opt("sourceOrigin"));
    if(origin.isEmpty()||!origin.equals(group.optString("sourceOrigin")))return unavailable("observation-source-differs");
    JSONObject manual=object(snapshot,"compatibility");int recorded=0,untested=0,failures=0,notApplicable=0;
    for(String key:MANUAL){String state=manual.optString(key,"not-tested");if("pass".equals(state))recorded++;else if("fail".equals(state)){recorded++;failures++;}else if("not-applicable".equals(state))notApplicable++;else untested++;}
    return J.obj("state",failures>0?"user-reported-issue":untested>0?"partially-recorded":notApplicable>0?"recorded-with-exclusions":"user-recorded-normal",
        "reason","manual-record-only","recordedCount",recorded,"untestedCount",untested,"failureCount",failures,"notApplicableCount",notApplicable,
        "allManuallyRecordedNormal",recorded==MANUAL.length&&failures==0&&untested==0&&notApplicable==0,
        "independentVerification",false,"physicalPhoneAcceptance",false);
  }

  static JSONObject capabilities(){
    JSONArray supported=J.arr(
        capability("session-mobile-desktop-ua","Firefox 手机版／电脑版显示","native-setting-observation-required"),
        capability("locales","语言请求","native-setting-observation-required"),
        capability("anti-tracking","现有原生追踪器拦截策略","native-setting-observation-required"),
        capability("native-rfp","Firefox 原生抗指纹","native-setting-readback-only"));
    JSONArray unavailable=J.arr(
        capability("independent-timezone","独立时区","unsupported"),
        capability("custom-canvas","自定义 Canvas 输出控制","unsupported"),
        capability("custom-webgl","自定义 WebGL／GPU 身份","unsupported"),
        capability("custom-audio","自定义音频身份","unsupported"),
        capability("custom-fonts","自定义字体身份","unsupported"),
        capability("custom-hardware","自定义硬件身份","unsupported"),
        capability("independent-fpp","独立 FPP 策略接口","not-verified-for-pinned-sdk"));
    return J.obj("sdkCoordinate",NativeCapabilityManifest.SDK_COORDINATE,"runtimeCoordinate",NativeCapabilityManifest.SDK_RUNTIME_COORDINATE,
        "buildKind",NativeCapabilityManifest.SDK_BUILD_KIND,"controls",supported,"unavailableControls",unavailable,
        "apiProtectionAttested",false,"observationsDoNotEnableControls",true);
  }
  private static JSONObject capability(String id,String label,String status){return J.obj("id",id,"label",label,"status",status);}

  static String summary(JSONObject assessment){
    if(assessment==null||assessment.optInt("schema")!=SCHEMA)return "模板保护信息尚未读取。";
    String state=assessment.optString("state"),text="confirmed".equals(state)?"原生设置回读已确认":
        "confirmation-failed".equals(state)?"原生设置确认失败，请查看保护状态并有限重试":
        "pending-application".equals(state)?"模板已保存，尚待当前浏览器应用":
        "invalid-template".equals(state)?"模板信息无效，原配置未由此评估改变":"原生设置尚待确认";
    StringBuilder out=new StringBuilder(text);
    if("compatibility".equals(assessment.optString("privacy")))out.append("\n兼容模板未请求现有追踪器列表拦截或原生抗指纹；可以按需主动选择其他模板。");
    else if(assessment.optBoolean("experimental"))out.append("\n强化模板仍为实验模式；设置确认不等于具体 API 保护或 GPT 兼容性已验证。");
    else out.append("\n标准手机版是日常使用的起始模板；不会自动切换当前配置，也不代表已完成真机验收。");
    if("desktop".equals(assessment.optString("display")))out.append("\n电脑版显示保留手机布局；页面与 Worker 的 HTTP UA 不保证完整一致。");
    JSONObject compatibility=object(assessment,"compatibility");
    if("unavailable".equals(compatibility.optString("state")))out.append("\n尚无与当前模板、来源及版本相符的人工兼容记录。");
    else out.append("\n当前样本人工记录：").append(compatibility.optInt("recordedCount")).append(" 项已记录，")
        .append(compatibility.optInt("untestedCount")).append(" 项未测试，").append(compatibility.optInt("failureCount")).append(" 项异常，")
        .append(compatibility.optInt("notApplicableCount")).append(" 项不适用。仅为用户自行记录。");
    return out.append("\n当前 SDK 未开放独立时区、GPU、Canvas、音频、字体或硬件身份自定义；按需观测不会开启这些能力。").toString();
  }
}
