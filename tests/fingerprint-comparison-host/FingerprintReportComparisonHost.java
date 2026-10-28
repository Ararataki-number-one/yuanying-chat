package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Host observations are constructed test input, never a physical-phone acceptance report. */
public final class FingerprintReportComparisonHost {
  static final String ENV=FingerprintDeepBaselineHost.ENV,OTHER=FingerprintDeepBaselineHost.OTHER;
  static final String A=FingerprintDeepBaselineHost.A,B=FingerprintDeepBaselineHost.B;
  static final JSONArray checks=new JSONArray();
  static void check(String label,boolean pass){checks.put(J.obj("name",label,"pass",pass));if(!pass)throw new AssertionError(label);}
  static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  static JSONObject metadata(String slot,long revision)throws Exception{
    boolean enhanced="enhanced".equals(slot);JSONObject value=FingerprintDeepBaselineHost.metadata();
    return value.put("configurationRevision",revision).put("executionId",enhanced?"enhanced-execution":"standard-execution")
        .put("templateId",enhanced?"native-rfp-experimental":"standard-mobile").put("display","mobile")
        .put("requestedLocales",new JSONArray().put("en-US")).put("expectedLocales",new JSONArray().put("en-US"));
  }
  static JSONObject nativeSettings(String slot){int level="enhanced".equals(slot)?2:1;return J.obj("state","confirmed","desiredLevel",level,"level",level,"generation",1,"token",1,"attempt",1,"maxAttempts",3,"reason","","received",true,"settingsReadbackConfirmed",true,"observedFingerprinting",level==2,"newRequestsBlocked",false,"scope","native-setting-new-request-admission","fullApiProtectionAttested",false);}
  static JSONObject report(String slot,long revision,String hash)throws Exception{
    JSONObject value=FingerprintContextBaselinesHost.report("enhanced".equals(slot)?3000:1000,hash),meta=metadata(slot,revision);
    value.put("observationMetadata",copy(meta)).put("identityAppliedRevision",revision).put("executionId",meta.getString("executionId"))
        .put("nativeProtection",nativeSettings(slot)).put("route",A).put("apiProtectionVerified",false);
    value.getJSONObject("expected").put("level","enhanced".equals(slot)?2:1).put("requestedLocales",meta.getJSONArray("requestedLocales")).put("expectedSdkLocales",meta.getJSONArray("expectedLocales"));
    JSONObject request=value.getJSONObject("requestIdentity");request.put("configurationRevision",revision).put("executionId",meta.getString("executionId"));request.getJSONObject("expected").put("configurationRevision",revision);
    return value;
  }
  static JSONObject save(JSONObject pair,String slot,JSONObject report,JSONObject meta){return FingerprintReportComparison.record(pair,slot,report,meta,5000);}
  static JSONObject pair()throws Exception{JSONObject standard=save(new JSONObject(),"standard",report("standard",7,A),metadata("standard",7));return save(standard,"enhanced",report("enhanced",8,B),metadata("enhanced",8));}
  static JSONObject slots(JSONObject pair)throws Exception{return pair.getJSONObject("slots");}
  static JSONObject slot(JSONObject pair,String slot)throws Exception{return slots(pair).getJSONObject(slot);}
  static JSONObject comparison(JSONObject pair){return FingerprintReportComparison.comparison(pair,ENV,1);}
  static JSONObject probe(JSONObject comparison,String context,String api)throws Exception{return comparison.getJSONObject("contexts").getJSONObject(context).getJSONObject("probes").getJSONObject(api);}
  static boolean rejected(JSONObject report,JSONObject metadata,String slot){return !FingerprintReportComparison.captureIssue(report,metadata,slot).isEmpty()&&save(new JSONObject(),slot,report,metadata)==null;}
  static JSONObject changedMetadataReport(String key,Object value,String slot,long revision)throws Exception{
    JSONObject report=report(slot,revision,B);report.getJSONObject("observationMetadata").put(key,value);return report;
  }
  public static void main(String[] args)throws Exception{
    JSONObject first=report("standard",7,A),firstMeta=metadata("standard",7),only=save(new JSONObject(),"standard",first,firstMeta),saved=pair();
    check("An explicitly selected actual standard report can fill its own slot",only!=null&&slots(only).length()==1&&slot(only,"standard").getString("slot").equals("standard"));
    check("A second explicit enhanced observation fills exactly two slots",saved!=null&&slots(saved).length()==2&&slot(saved,"enhanced").getJSONObject("template").getString("templateId").equals("native-rfp-experimental"));
    check("Observation and user-save timestamps remain distinct",slot(saved,"standard").getLong("savedAt")==5000&&slot(saved,"standard").getJSONObject("group").getLong("configurationRevision")==7);
    JSONObject restored=FingerprintReportComparison.restore(saved,ENV,1);
    check("Owned JSON round trip retains both sanitized observations",FingerprintObservationHistory.same(restored,saved));
    check("Changing mode revisions and runtime IDs does not prevent a controlled pair",comparison(saved).getString("state").equals("comparable")&&comparison(saved).getJSONArray("conditionsChanged").toString().contains("configurationRevision")&&comparison(saved).getJSONArray("conditionsChanged").toString().contains("templateId"));
    for(String context:FingerprintReportComparison.CONTEXTS){JSONObject result=probe(comparison(saved),context,"canvas");check("Only matching execution contexts compare hashes "+context,result.getBoolean("hashCompared")&&result.getBoolean("hashChanged")&&!comparison(saved).getJSONObject("contexts").getJSONObject(context).getBoolean("crossExecutionContextComparison"));}
    check("Worker readback hashes are compared independently",probe(comparison(saved),"worker","webgl").getBoolean("readbackHashCompared")&&probe(comparison(saved),"worker","webgl").getBoolean("readbackHashChanged"));
    check("Unsupported Worker audio is never compared as a successful API",probe(comparison(saved),"worker","audio").getString("enhancedState").equals("uncovered")&&!probe(comparison(saved),"worker","audio").getBoolean("hashCompared"));
    JSONObject equalEnhanced=report("enhanced",8,A),equal=save(only,"enhanced",equalEnhanced,metadata("enhanced",8));
    check("Equal output is scoped to the explicitly compared operation",probe(comparison(equal),"main","canvas").getBoolean("hashCompared")&&!probe(comparison(equal),"main","canvas").getBoolean("hashChanged"));
    check("No output equality or difference becomes a score or protection verdict",!comparison(saved).getBoolean("protectionVerified")&&!comparison(saved).getBoolean("leakVerdict")&&!comparison(saved).has("score")&&!comparison(saved).has("protectionScore"));
    check("No host result claims physical-phone acceptance",!saved.getBoolean("physicalPhoneAcceptance")&&!comparison(saved).getBoolean("physicalPhoneAcceptance")&&!slot(saved,"standard").getBoolean("samePhysicalPhoneVerified"));
    for(String mode:FingerprintReportComparison.SLOTS)for(String key:FingerprintReportComparison.MANUAL_KEYS)check("Manual compatibility is never automatically passed "+mode+"/"+key,slot(saved,mode).getJSONObject("compatibility").getString(key).equals("not-tested")&&slot(saved,mode).getJSONObject("compatibilityUpdatedAt").getLong(key)==0);
    JSONObject manual=FingerprintReportComparison.manual(saved,"standard","input","pass",ENV,1,6000);
    check("One user-entered result changes only its chosen slot and item",slot(manual,"standard").getJSONObject("compatibility").getString("input").equals("pass")&&slot(manual,"enhanced").getJSONObject("compatibility").getString("input").equals("not-tested")&&slot(manual,"standard").getJSONObject("compatibility").getString("attachment").equals("not-tested"));
    check("Manual pass records its user-entry time without becoming an independent attestation",slot(manual,"standard").getJSONObject("compatibilityUpdatedAt").getLong("input")==6000&&slot(manual,"standard").getString("compatibilitySource").equals("user-entered-not-independent-verification")&&!comparison(manual).getBoolean("physicalPhoneAcceptance"));
    check("Manual update is detached from the saved input object",slot(saved,"standard").getJSONObject("compatibility").getString("input").equals("not-tested"));
    JSONObject unknown=FingerprintReportComparison.manual(manual,"standard","input","not-tested",ENV,1,7000);
    check("Returning an item to unknown clears its old manual timestamp",slot(unknown,"standard").getJSONObject("compatibility").getString("input").equals("not-tested")&&slot(unknown,"standard").getJSONObject("compatibilityUpdatedAt").getLong("input")==0);
    for(String value:new String[]{"fail","not-applicable"})check("Explicit remaining manual state is retained "+value,slot(FingerprintReportComparison.manual(saved,"enhanced","attachment",value,ENV,1,7000),"enhanced").getJSONObject("compatibility").getString("attachment").equals(value));
    for(String[] fields:new String[][]{{"unknown","input","pass"},{"standard","password","pass"},{"standard","input","verified"}})check("Unknown manual slot key or state is rejected "+Arrays.toString(fields),FingerprintReportComparison.manual(saved,fields[0],fields[1],fields[2],ENV,1,6000)==null);
    check("A missing report cannot receive a manual pass",FingerprintReportComparison.manual(only,"enhanced","input","pass",ENV,1,6000)==null);
    check("Foreign and retired generations cannot receive manual results",FingerprintReportComparison.manual(saved,"standard","input","pass",OTHER,1,6000)==null&&FingerprintReportComparison.manual(saved,"standard","input","pass",ENV,2,6000)==null);
    check("A malformed manual timestamp is rejected",FingerprintReportComparison.manual(saved,"standard","input","pass",ENV,1,0)==null);
    JSONObject replaced=save(manual,"standard",report("standard",9,B),metadata("standard",9));
    check("Replacing one captured report resets its old manual findings",slot(replaced,"standard").getJSONObject("compatibility").getString("input").equals("not-tested")&&slot(replaced,"standard").getJSONObject("group").getLong("configurationRevision")==9);
    check("Replacing standard does not replace the other saved observation",FingerprintObservationHistory.same(slot(replaced,"enhanced"),slot(saved,"enhanced")));
    check("Clearing one slot preserves the other",slots(FingerprintReportComparison.clear(saved,"standard",ENV,1)).length()==1&&slots(FingerprintReportComparison.clear(saved,"standard",ENV,1)).has("enhanced"));
    check("Explicit clearing of both slots remains owner scoped",slots(FingerprintReportComparison.clear(saved,"",ENV,1)).length()==0&&FingerprintReportComparison.clear(saved,"",ENV,1).getString("environmentId").equals(ENV));
    check("An unknown clear target does not silently clear records",FingerprintReportComparison.clear(saved,"other",ENV,1)==null);
    check("Different environments cannot restore saved observations",slots(FingerprintReportComparison.restore(saved,OTHER,1)).length()==0);
    check("A recreated environment cannot inherit prior observations",slots(FingerprintReportComparison.restore(saved,ENV,2)).length()==0);
    check("Invalid caller environment does not form a saved envelope",FingerprintReportComparison.restore(saved,"bad-id",1).length()==0);
    check("A foreign envelope cannot be silently relabelled while recording",save(FingerprintReportComparison.empty(OTHER,1),"standard",first,firstMeta)==null);
    check("A numeric string schema is not accepted",slots(FingerprintReportComparison.restore(copy(saved).put("schema","1"),ENV,1)).length()==0);
    check("A future unknown schema is not silently migrated",slots(FingerprintReportComparison.restore(copy(saved).put("schema",2),ENV,1)).length()==0);
    JSONObject third=copy(saved);slots(third).put("third",slot(saved,"standard"));check("A third hidden report slot is rejected",slots(FingerprintReportComparison.restore(third,ENV,1)).length()==0);
    check("Only origins are stored instead of private conversation paths",!saved.toString().contains("private-draft")&&!saved.toString().contains("not-persisted"));
    JSONObject nestedOld=report("standard",7,A);nestedOld.getJSONObject("requestIdentity").put("configurationRevision",6);JSONObject partial=save(new JSONObject(),"standard",nestedOld,firstMeta);
    check("A stale nested cross-origin response cannot be relabelled by the current mode",partial!=null&&!slot(partial,"standard").getJSONObject("contexts").has("crossOriginFrame")&&slot(partial,"standard").getJSONObject("contexts").has("main")&&slot(partial,"standard").getJSONObject("contexts").has("worker"));
    JSONObject sensitive=report("standard",7,A);sensitive.put("cookie","private-cookie").put("draft","private-message").put("password","private-password");sensitive.getJSONObject("nativeProtection").put("cookie","private-cookie");sensitive.getJSONObject("observationMetadata").put("token","private-subscription-token");
    JSONObject sanitized=save(new JSONObject(),"standard",sensitive,metadata("standard",7));
    check("Only approved observation fields are retained",sanitized!=null&&!sanitized.toString().contains("private-cookie")&&!sanitized.toString().contains("private-message")&&!sanitized.toString().contains("private-password")&&!sanitized.toString().contains("private-subscription-token"));
    check("An unrelated saved field is stripped on restore",!FingerprintReportComparison.restore(copy(saved).put("cookie","private-cookie"),ENV,1).toString().contains("private-cookie"));
    JSONObject oversized=copy(saved).put("unrelated",String.join("",Collections.nCopies(FingerprintReportComparison.MAX_BYTES,"x")));
    check("Oversized saved input is rejected before any field sanitization",slots(FingerprintReportComparison.restore(oversized,ENV,1)).length()==0);
    JSONObject unicode=copy(saved).put("unrelated",String.join("",Collections.nCopies(22000,"中")));
    check("Saved capacity is measured in UTF8 bytes",unicode.toString().length()<FingerprintReportComparison.MAX_BYTES&&slots(FingerprintReportComparison.restore(unicode,ENV,1)).length()==0);
    check("An unknown actual mode cannot be relabelled as standard",rejected(report("enhanced",8,B),metadata("enhanced",8),"standard"));
    check("A standard observation cannot be relabelled as enhanced",rejected(first,firstMeta,"enhanced"));
    check("An unknown slot is rejected before capture",rejected(first,firstMeta,"compatibility"));
    JSONObject compatible=copy(first);compatible.getJSONObject("expected").put("level",0);
    check("Compatibility level is not silently treated as standard",rejected(compatible,firstMeta,"standard"));
    JSONObject mismatch=copy(first);mismatch.getJSONObject("nativeProtection").put("desiredLevel",2);
    check("A mismatched native desired mode cannot enter a labelled slot",rejected(mismatch,firstMeta,"standard"));
    JSONObject unconfirmed=report("enhanced",8,B);unconfirmed.getJSONObject("nativeProtection").put("state","pending").put("reason","awaiting-setting").put("received",false).put("settingsReadbackConfirmed",false).put("observedFingerprinting",false).put("newRequestsBlocked",true);
    JSONObject pending=save(only,"enhanced",unconfirmed,metadata("enhanced",8));
    check("An unconfirmed setting remains an explicit local observation",pending!=null&&slot(pending,"enhanced").getJSONObject("nativeSettings").getString("state").equals("pending"));
    check("Unconfirmed enhanced settings cannot become an effect comparison",comparison(pending).getString("state").equals("settings-unconfirmed")&&!probe(comparison(pending),"main","canvas").getBoolean("hashCompared"));
    check("A pending comparison warns rather than saying protection is effective",FingerprintReportComparison.summary(pending,ENV,1).contains("不能作为已生效模式的效果对照"));
    JSONObject failed=copy(unconfirmed);failed.getJSONObject("nativeProtection").put("state","failed").put("reason","setting-timeout");JSONObject failure=save(only,"enhanced",failed,metadata("enhanced",8));
    check("Failed native setting confirmation remains visible without a pass",failure!=null&&comparison(failure).getString("state").equals("settings-unconfirmed")&&FingerprintReportComparison.slotSummary(failure,"enhanced",ENV,1).contains("失败"));
    for(String key:new String[]{"received","settingsReadbackConfirmed","observedFingerprinting"}){JSONObject invalid=report("enhanced",8,B);invalid.getJSONObject("nativeProtection").put(key,false);check("A contradictory confirmed setting is rejected "+key,rejected(invalid,metadata("enhanced",8),"enhanced"));}
    JSONObject fake=copy(first);fake.getJSONObject("nativeProtection").put("fullApiProtectionAttested",true);check("Native confirmation cannot claim complete API protection",rejected(fake,firstMeta,"standard"));
    JSONObject phone=copy(first);phone.put("physicalPhoneAcceptance",true);check("A claimed physical phone result cannot be imported as model acceptance",rejected(phone,firstMeta,"standard"));
    JSONObject nativeType=copy(first);nativeType.getJSONObject("nativeProtection").put("settingsReadbackConfirmed","true");check("String booleans cannot confirm a setting",rejected(nativeType,firstMeta,"standard"));
    JSONObject stale=copy(first);stale.put("fresh",false);check("A stale report is rejected",rejected(stale,firstMeta,"standard"));
    JSONObject revision=copy(first);revision.put("identityAppliedRevision",6);check("An old applied revision cannot be assigned to current metadata",rejected(revision,firstMeta,"standard"));
    JSONObject epoch=copy(first);epoch.put("executionId","old-execution");check("A prior execution cannot be relabelled by metadata",rejected(epoch,firstMeta,"standard"));
    JSONObject originalMetadata=copy(first);originalMetadata.getJSONObject("observationMetadata").put("configurationRevision",6);check("Capture compares supplied metadata with the report's original metadata",rejected(originalMetadata,firstMeta,"standard"));
    JSONObject missingMetadata=copy(first);missingMetadata.remove("observationMetadata");check("A detached report without its original metadata is rejected",rejected(missingMetadata,firstMeta,"standard"));
    JSONObject wrongTemplate=copy(firstMeta).put("templateId","native-rfp-experimental");check("Template identity must describe the actual saved mode",rejected(first,wrongTemplate,"standard"));
    JSONObject localeTypes=copy(firstMeta).put("requestedLocales",new JSONArray().put(1));check("Locale request values must be typed bounded language tags",rejected(first,localeTypes,"standard"));
    JSONObject initialLanguage=copy(first);initialLanguage.getJSONObject("expected").put("requestedLocales",new JSONArray().put("ja-JP"));check("An initial language request cannot be relabelled at capture time",rejected(initialLanguage,firstMeta,"standard"));
    JSONObject initialSdkLanguage=copy(first);initialSdkLanguage.getJSONObject("expected").put("expectedSdkLocales",new JSONArray().put("ja-JP"));check("An initial SDK language prediction stays distinct from later metadata",rejected(initialSdkLanguage,firstMeta,"standard"));
    JSONObject missingOperation=copy(first);FingerprintContextBaselinesHost.probe(missingOperation,"main","canvas").remove("pixels");check("Available API output requires its operation evidence",rejected(missingOperation,firstMeta,"standard"));
    JSONObject allFailed=report("enhanced",8,B);
    for(String context:FingerprintReportComparison.CONTEXTS){JSONObject raw=FingerprintContextBaselinesHost.raw(allFailed,context);for(String api:FingerprintObservationHistory.APIS){JSONObject op=raw.getJSONObject("probes").getJSONObject(api);boolean na=(context.equals("worker")||context.equals("crossOriginFrame"))&&(api.equals("audio")||api.equals("fonts"));op.put("state",na?"uncovered":"failed");for(String field:new String[]{"hash","hashAlgorithm","readbackHash","readbackHashAlgorithm"})op.remove(field);}raw.put("status",context.equals("worker")?"partial":"completed");}
    JSONObject unavailable=save(only,"enhanced",allFailed,metadata("enhanced",8));
    check("All-failed operations can be retained as an observation rather than a fixed usable baseline",unavailable!=null&&probe(comparison(unavailable),"main","canvas").getString("enhancedState").equals("failed"));
    check("Unavailable operation hashes are never counted as equal or different",!probe(comparison(unavailable),"main","canvas").getBoolean("hashCompared")&&!probe(comparison(unavailable),"main","canvas").has("hashChanged"));
    check("All-failed observation does not become a reference through the old pin API",FingerprintDeepBaseline.capture(allFailed,metadata("enhanced",8),5000).length()==0);
    for(String field:new String[]{"sourceOrigin","engineVersion","appVersion","appVersionCode"}){
      Object value=field.equals("appVersionCode")?78:field.equals("sourceOrigin")?"https://other.example/path":"different";
      JSONObject meta=metadata("enhanced",8).put(field,value),r=changedMetadataReport(field,value,"enhanced",8),different=save(only,"enhanced",r,meta);
      check("Changed comparison condition blocks direct hashes "+field,different!=null&&comparison(different).getString("state").equals("separate-conditions")&&!probe(comparison(different),"main","canvas").getBoolean("hashCompared")&&!probe(comparison(different),"main","canvas").getBoolean("operationStateCompared"));
    }
    JSONObject localeMeta=metadata("enhanced",8).put("requestedLocales",new JSONArray().put("ja-JP")),localeReport=report("enhanced",8,B);localeReport.put("observationMetadata",copy(localeMeta));localeReport.getJSONObject("expected").put("requestedLocales",localeMeta.getJSONArray("requestedLocales"));JSONObject localePair=save(only,"enhanced",localeReport,localeMeta);
    check("Changed requested language is not a silent mode-only comparison",comparison(localePair).getString("state").equals("separate-conditions"));
    JSONObject desktopMeta=metadata("enhanced",8).put("templateId","native-rfp-desktop-experimental").put("display","desktop"),desktopReport=report("enhanced",8,B);desktopReport.put("observationMetadata",copy(desktopMeta));JSONObject desktopPair=save(only,"enhanced",desktopReport,desktopMeta);
    check("Different desktop display stays separate from a mobile comparison",comparison(desktopPair).getString("state").equals("separate-conditions"));
    JSONObject networkReport=report("enhanced",8,B);networkReport.put("route",B);JSONObject networkPair=save(only,"enhanced",networkReport,metadata("enhanced",8));String networkSummary=FingerprintReportComparison.summary(networkPair,ENV,1);check("A changed observed route is not silently treated as a fixed network",comparison(networkPair).getString("state").equals("separate-conditions")&&networkSummary.contains("线路记录")&&networkSummary.contains("线路记录变化不直接证明配置或出口改变")&&!networkSummary.contains("网络配置"));
    JSONObject probeReport=report("enhanced",8,B);FingerprintContextBaselinesHost.raw(probeReport,"main").put("probeVersion",2);check("Main probe versions cannot silently compare old hashes",comparison(save(only,"enhanced",probeReport,metadata("enhanced",8))).getString("state").equals("separate-conditions"));
    JSONObject workerVersion=report("enhanced",8,B);FingerprintContextBaselinesHost.raw(workerVersion,"worker").put("probeVersion",2);JSONObject perContext=save(only,"enhanced",workerVersion,metadata("enhanced",8));check("A changed Worker probe disables only Worker hash comparison",!probe(comparison(perContext),"worker","canvas").getBoolean("hashCompared")&&probe(comparison(perContext),"main","canvas").getBoolean("hashCompared"));
    JSONObject tampered=copy(saved);slot(tampered,"enhanced").getJSONObject("group").put("configurationRevision",99);check("Saved grouping must match the retained operation context",slots(FingerprintReportComparison.restore(tampered,ENV,1)).length()==1);
    JSONObject nativeTampered=copy(saved);slot(nativeTampered,"standard").getJSONObject("nativeSettings").put("desiredLevel",2);check("Saved native mode cannot be relabelled during restore",slots(FingerprintReportComparison.restore(nativeTampered,ENV,1)).length()==1);
    JSONObject manualTampered=copy(saved);slot(manualTampered,"standard").getJSONObject("compatibility").put("input","pass");check("A saved manual pass requires its explicit entry timestamp",slots(FingerprintReportComparison.restore(manualTampered,ENV,1)).length()==1);
    JSONObject claimed=copy(saved);claimed.put("physicalPhoneAcceptance",true);check("A saved physical-phone attestation is rejected",slots(FingerprintReportComparison.restore(claimed,ENV,1)).length()==0);
    JSONObject alias=copy(saved);slot(alias,"standard").put("slot","enhanced");check("A snapshot cannot move between named mode slots",slots(FingerprintReportComparison.restore(alias,ENV,1)).length()==1);
    JSONObject mixed=copy(saved);slot(mixed,"enhanced").getJSONObject("contexts").getJSONObject("worker").getJSONObject("observation").put("configurationRevision",7);check("Child context operations cannot be mixed from another mode revision",slots(FingerprintReportComparison.restore(mixed,ENV,1)).length()==1);
    String original=saved.toString();JSONObject detached=FingerprintReportComparison.restore(saved,ENV,1);slot(detached,"standard").getJSONObject("nativeSettings").put("state","tampered");check("Restoration owns detached copies of all nested evidence",original.equals(saved.toString()));
    String summary=FingerprintReportComparison.summary(manual,ENV,1),card=FingerprintReportComparison.slotSummary(saved,"standard",ENV,1);
    check("Compact cards do not dump long hashes",!card.contains(A)&&!card.contains(B)&&card.contains("配置 7")&&card.contains("Gecko"));
    check("Summary keeps native setting and manual compatibility evidence separate",summary.contains("人工兼容记录")&&summary.contains("用户填写")&&summary.contains("输入法")&&summary.contains("设置回读已确认"));
    check("Summary never presents output changes as a safety score",summary.contains("输出变化不代表保护有效或泄漏")&&summary.contains("不同执行环境不要求哈希相同")&&!summary.contains("保护分数"));
    JSONObject exported=new JSONObject(FingerprintReportComparison.export(manual,ENV,1));
    check("Export preserves observations and comparison without pretending to be current",exported.getJSONObject("observations").getJSONObject("slots").length()==2&&!exported.getBoolean("currentDocumentVerified")&&!exported.getBoolean("physicalPhoneAcceptance")&&!exported.getBoolean("protectionVerified"));
    check("Foreign export contains no saved observations",new JSONObject(FingerprintReportComparison.export(saved,OTHER,1)).getJSONObject("observations").getJSONObject("slots").length()==0);
    check("The two-record capacity remains bounded",saved.toString().getBytes(StandardCharsets.UTF_8).length<=FingerprintReportComparison.MAX_BYTES&&slots(saved).length()==2);
    System.out.println(J.obj("status","passed","total",checks.length(),"passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"physicalPhoneAcceptance",false,"protectionEffectivenessAcceptance",false).toString());
  }
}
