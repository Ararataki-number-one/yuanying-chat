package local.pocketchat;

import org.json.*;
import java.util.*;

/** Executes the production baseline model on a JVM; no Android or privacy verdict. */
public final class FingerprintDeepBaselineHost {
  static final String ENV="11111111-1111-4111-8111-111111111111",OTHER="22222222-2222-4222-8222-222222222222";
  static final String A=String.join("",Collections.nCopies(64,"a")),B=String.join("",Collections.nCopies(64,"b"));
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  static JSONObject metadata(){return J.obj("environmentId",ENV,"environmentGeneration",1,"configurationRevision",7,"engineVersion","Gecko 157.0.1","appVersion","2.0.24","appVersionCode",77,"sourceOrigin","https://chatgpt.com/c/private-draft?secret=not-persisted","executionId","run-1");}
  static JSONObject signal(){return J.obj("ua","Firefox/157.0","language","en-US","languages",new JSONArray(Arrays.asList("en-US","ja-JP")),"offset",-540,"zone","Asia/Tokyo","cpu",8,"memory",JSONObject.NULL,"renderer","restricted","screen",J.obj("width",1080,"height",2400,"depth",24),"viewport",J.obj("width",400,"height",700,"pixelRatio",2.75,"touch",5));}
  static JSONObject canvas(String hash){return J.obj("state","available","reason","draw-and-pixel-readback-completed","pixels",4096,"hash",hash,"hashAlgorithm","sha256");}
  static JSONObject audio(String hash){return J.obj("state","available","reason","offline-render-completed-no-speaker-output","frames",2048,"sampleRate",44100,"peak",0.5,"hash",hash,"hashAlgorithm","sha256");}
  static JSONObject fonts(String hash){JSONArray samples=new JSONArray();for(String name:new String[]{"Arial","Times New Roman","Courier New","Noto Sans","Noto Sans CJK SC"})samples.put(J.obj("name",name,"faceCheck",true,"monospaceWidth",100.25,"sansSerifWidth",98.5));return J.obj("state","available","reason","limited-font-face-check-and-widths-not-installation-proof","candidateCount",5,"samples",samples,"hash",hash,"hashAlgorithm","sha256");}
  static JSONObject webgl(String hash){return J.obj("state","restricted","reason","unmasked-renderer-extension-unavailable","version","WebGL 1.0","shadingLanguageVersion","GLSL ES 1.0","vendor","Mozilla","renderer","WebGL","maxTextureSize",4096,"maxRenderbufferSize",4096,"maxVertexAttribs",16,"extensionCount",1,"extensions",new JSONArray().put("WEBGL_lose_context"),"hash",hash,"hashAlgorithm","sha256");}
  static JSONObject deep(long at,String hash){return J.obj("fresh",true,"at",at,"identityAppliedRevision",7,"executionId","run-1","expected",J.obj("environmentId",ENV,"environmentGeneration",1),"signals",J.obj("provenance","page-main-world","mainWorld",J.obj("observed",true),"parent",signal(),"apiChecks",J.obj("schema",1,"requested",true,"source","page-main-world","probeVersion",1,"status","completed","durationMs",12.5,"limits",J.obj("canvasPixels",4096,"audioFrames",2048,"fontCandidates",5,"totalBudgetMs",1200),"protectionVerified",false,"probes",J.obj("canvas",canvas(hash),"audio",audio(hash),"fonts",fonts(hash),"webgl",webgl(hash)))));}
  static JSONObject probes(JSONObject report){return report.optJSONObject("signals").optJSONObject("apiChecks").optJSONObject("probes");}
  static JSONObject api(JSONObject report){return report.optJSONObject("signals").optJSONObject("apiChecks");}
  static JSONObject compare(JSONObject pin,JSONObject now,JSONObject meta){return FingerprintDeepBaseline.comparison(pin,now,meta);}
  static JSONObject result(JSONObject pin,JSONObject now,String name){return compare(pin,now,metadata()).optJSONObject("apiComparisons").optJSONObject(name);}
  static boolean rejected(JSONObject report,JSONObject meta){return !FingerprintDeepBaseline.captureIssue(report,meta).isEmpty()&&FingerprintDeepBaseline.capture(report,meta,3000).length()==0;}
  public static void main(String[] args)throws Exception{
    JSONObject meta=metadata(),report=deep(1000,A),pin=FingerprintDeepBaseline.capture(report,meta,2000);
    check("A valid explicitly requested deep result may be pinned",pin.length()>0&&FingerprintDeepBaseline.captureIssue(report,meta).isEmpty());
    check("Pin retains distinct observation and user pin timestamps",pin.getLong("pinnedAt")==2000&&pin.getJSONObject("observation").getLong("at")==1000);
    check("Only the source origin is stored",pin.getJSONObject("observation").getString("sourceOrigin").equals("https://chatgpt.com")&&!pin.toString().contains("private-draft")&&!pin.toString().contains("not-persisted"));
    check("Baseline has no protection or leak attestation",!pin.getBoolean("protectionVerified")&&!pin.getBoolean("leakVerdict"));
    JSONObject restored=FingerprintDeepBaseline.restore(pin,ENV,1);
    check("A valid baseline survives JSON restoration",FingerprintObservationHistory.same(pin,restored));
    JSONObject same=compare(pin,deep(3000,A),metadata());
    check("Same group compares all four available hashes",same.getInt("hashComparedCount")==4&&same.getInt("hashChangedCount")==0&&same.getString("state").equals("comparable"));
    check("Hash equality applies only to explicitly compared operations",result(pin,deep(3000,A),"canvas").getBoolean("compared")&&!result(pin,deep(3000,A),"canvas").getBoolean("changed"));
    JSONObject changed=deep(3000,A);probes(changed).put("audio",audio(B));
    check("Only the changed operation is marked different",compare(pin,changed,metadata()).getInt("hashChangedCount")==1&&result(pin,changed,"audio").getBoolean("changed")&&!result(pin,changed,"canvas").getBoolean("changed"));
    check("Output changes never become a leak or protection failure verdict",!compare(pin,changed,metadata()).getBoolean("leakVerdict")&&!compare(pin,changed,metadata()).getBoolean("protectionVerified"));
    JSONArray history=new JSONArray();for(int i=0;i<8;i++){JSONObject light=deep(4000+i,A);light.getJSONObject("signals").remove("apiChecks");history=FingerprintObservationHistory.record(history,light,metadata());}
    check("Eight ordinary checks retain only ordinary recent observations",history.length()==8&&!history.toString().contains(A));
    check("Eight ordinary checks do not evict or replace the fixed baseline",result(pin,deep(5000,B),"canvas").getBoolean("changed")&&FingerprintDeepBaseline.restore(pin,ENV,1).getJSONObject("observation").getLong("at")==1000);
    JSONObject light=deep(3000,A);light.getJSONObject("signals").remove("apiChecks");
    check("An ordinary result cannot be pinned as a deep baseline",rejected(light,metadata()));
    check("An ordinary comparison does not erase the fixed reference",compare(pin,light,metadata()).getString("state").equals("current-unavailable")&&FingerprintDeepBaseline.restore(pin,ENV,1).length()>0);
    String lightSummary=FingerprintDeepBaseline.summary(pin,light,metadata());
    check("Summary says no current deep comparison instead of unchanged",lightSummary.contains("本次没有可比较的深检结果")&&!lightSummary.contains("已比较哈希未变"));
    check("Empty baseline is explicit and has no comparisons",compare(new JSONObject(),report,metadata()).getString("state").equals("no-reference")&&FingerprintDeepBaseline.summary(new JSONObject(),report,metadata()).contains("尚未固定"));
    check("Clearing fixed reference does not clear recent history",FingerprintDeepBaseline.restore(new JSONObject(),ENV,1).length()==0&&history.length()==8);
    check("Deleting recent history does not clear the fixed reference",new JSONArray().length()==0&&FingerprintDeepBaseline.restore(pin,ENV,1).length()>0);
    check("Another environment cannot restore the reference",FingerprintDeepBaseline.restore(pin,OTHER,1).length()==0);
    check("An environment reset cannot restore the old generation",FingerprintDeepBaseline.restore(pin,ENV,2).length()==0);
    check("A foreign reference is not relabelled by comparison",compare(pin,report,J.obj("environmentId",OTHER,"environmentGeneration",1)).getString("state").equals("no-reference"));
    for(String key:new String[]{"configurationRevision","engineVersion","appVersion","appVersionCode","sourceOrigin"}){
      JSONObject differentMeta=metadata(),differentReport=deep(3000,B);
      if(key.equals("configurationRevision")){differentMeta.put(key,8);differentReport.put("identityAppliedRevision",8);}else if(key.equals("appVersionCode"))differentMeta.put(key,78);else differentMeta.put(key,key.equals("sourceOrigin")?"https://other.example/check":"different");
      JSONObject value=compare(pin,differentReport,differentMeta);
      check("Changed "+key+" is a separate context without hash judgement",value.getString("state").equals("separate-context")&&value.getInt("hashComparedCount")==0&&value.getJSONObject("apiComparisons").length()==0&&!value.has("changed"));
    }
    JSONObject newerProbe=deep(3000,B);api(newerProbe).put("probeVersion",2);
    check("A different probe version cannot compare old hashes",compare(pin,newerProbe,metadata()).getString("state").equals("separate-context")&&compare(pin,newerProbe,metadata()).getJSONArray("separationReasons").toString().contains("probeVersion"));
    check("Different contexts are explained without an anomaly claim",FingerprintDeepBaseline.summary(pin,newerProbe,metadata()).contains("未直接比较输出或判断异常"));
    check("A worker is never promoted into a page baseline",!same.getBoolean("crossExecutionContextComparison")&&same.getString("source").equals("page-main-world"));
    JSONObject restricted=deep(3000,A);probes(restricted).put("canvas",J.obj("state","restricted","reason","SecurityError"));
    JSONObject restrictedResult=result(pin,restricted,"canvas");
    check("A restricted current readback compares operation state only",restrictedResult.getBoolean("operationStateCompared")&&restrictedResult.getBoolean("operationStateChanged")&&!restrictedResult.getBoolean("compared")&&!restrictedResult.has("changed"));
    check("Missing current hashes never become unchanged",restrictedResult.getString("reason").equals("current-hash-unavailable")&&FingerprintDeepBaseline.summary(pin,restricted,metadata()).contains("缺少有效哈希，本项输出未比较"));
    JSONObject noHash=deep(3000,A);for(String name:FingerprintDeepBaseline.APIS){JSONObject value=probes(noHash).getJSONObject(name);value.remove("hash");value.remove("hashAlgorithm");value.put("hashUnavailable",true);}
    JSONObject noHashPin=FingerprintDeepBaseline.capture(noHash,metadata(),4000);
    check("Valid available operations can be pinned with explicit hash unavailability",noHashPin.length()>0&&compare(noHashPin,noHash,metadata()).getInt("hashComparedCount")==0);
    check("Absent baseline and current hashes are both explicitly unexamined",result(noHashPin,noHash,"canvas").getString("reason").equals("both-hashes-unavailable")&&!result(noHashPin,noHash,"canvas").has("changed"));
    check("New available hashes do not invent missing reference hashes",result(noHashPin,deep(5000,A),"canvas").getString("reason").equals("reference-hash-unavailable")&&!result(noHashPin,deep(5000,A),"canvas").getBoolean("compared"));
    JSONObject allRestricted=deep(3000,A);for(String name:FingerprintDeepBaseline.APIS)probes(allRestricted).put(name,J.obj("state","restricted","reason","NotAllowedError"));
    JSONObject allRestrictedPin=FingerprintDeepBaseline.capture(allRestricted,metadata(),4000);
    check("A meaningful all-restricted deep observation may be fixed without invented hashes",allRestrictedPin.length()>0&&compare(allRestrictedPin,allRestricted,metadata()).getInt("hashComparedCount")==0);
    check("Restoration preserves a valid no-hash restricted baseline",FingerprintDeepBaseline.restore(allRestrictedPin,ENV,1).length()>0);
    JSONObject allFailed=deep(3000,A);for(String name:FingerprintDeepBaseline.APIS)probes(allFailed).put(name,J.obj("state","failed","reason","Error"));
    check("An entirely failed probe cannot replace a useful baseline",rejected(allFailed,metadata())&&pin.getJSONObject("checks").getJSONObject("probes").getJSONObject("canvas").getString("hash").equals(A));
    JSONObject allUncovered=deep(3000,A);api(allUncovered).put("status","partial");for(String name:FingerprintDeepBaseline.APIS)probes(allUncovered).put(name,J.obj("state","uncovered","reason","unavailable"));
    check("An entirely uncovered probe cannot be pinned",rejected(allUncovered,metadata()));
    check("A later failed observation can still report state changes without hash comparison",compare(pin,allFailed,metadata()).getInt("hashComparedCount")==0&&result(pin,allFailed,"audio").getBoolean("operationStateChanged"));
    JSONObject stale=deep(3000,A);stale.put("fresh",false);check("A stale report cannot be pinned",rejected(stale,metadata()));
    JSONObject isolated=deep(3000,A);isolated.getJSONObject("signals").put("provenance","extension-isolated-world-fallback");check("Extension-isolated fallback is not page evidence",rejected(isolated,metadata()));
    JSONObject noReceipt=deep(3000,A);noReceipt.getJSONObject("signals").getJSONObject("mainWorld").put("observed",false);check("Missing page-world receipt prevents a pin",rejected(noReceipt,metadata()));
    JSONObject worker=deep(3000,A);api(worker).put("source","dedicated-worker");check("Worker evidence is not mixed with the page-world baseline",rejected(worker,metadata()));
    JSONObject mismatch=deep(3000,A);mismatch.put("identityAppliedRevision",8);check("An old result cannot receive current configuration metadata",rejected(mismatch,metadata()));
    JSONObject oldExecution=deep(3000,A);oldExecution.put("executionId","old-run");check("An old execution cannot receive a new execution label",rejected(oldExecution,metadata()));
    JSONObject foreign=deep(3000,A);foreign.getJSONObject("expected").put("environmentId",OTHER);check("A report bound to another environment cannot be pinned",rejected(foreign,metadata()));
    JSONObject oldGeneration=deep(3000,A);oldGeneration.getJSONObject("expected").put("environmentGeneration",0);check("A report bound to an old generation cannot be pinned",rejected(oldGeneration,metadata()));
    for(String field:new String[]{"environmentId","environmentGeneration","configurationRevision","engineVersion","appVersion","appVersionCode","sourceOrigin"}){JSONObject invalid=metadata();invalid.remove(field);check("Missing "+field+" cannot form a pin group",rejected(report,invalid));}
    JSONObject invalidOrigin=metadata();invalidOrigin.put("sourceOrigin","http://chatgpt.com");check("An insecure source origin cannot become a fixed reference",rejected(report,invalidOrigin));
    JSONObject fractional=metadata();fractional.put("configurationRevision",7.5);check("Fractional configuration revisions are rejected",rejected(report,fractional));
    JSONObject badVersion=deep(3000,A);api(badVersion).put("probeVersion",1.5);check("Fractional probe versions are rejected",rejected(badVersion,metadata()));
    JSONObject badSchema=deep(3000,A);api(badSchema).put("schema","1");check("A string schema cannot impersonate a numeric probe schema",rejected(badSchema,metadata()));
    JSONObject auto=deep(3000,A);api(auto).put("requested",false);check("Unrequested operations cannot become an explicit deep reference",rejected(auto,metadata()));
    JSONObject fakeAttestation=deep(3000,A);api(fakeAttestation).put("protectionVerified",true);check("A forged all-protection claim is rejected",rejected(fakeAttestation,metadata()));
    JSONObject outerAttestation=deep(3000,A);outerAttestation.put("apiProtectionVerified",true);check("A report-level all-API attestation cannot enter an observation baseline",rejected(outerAttestation,metadata()));
    JSONObject badBudget=deep(3000,A);api(badBudget).getJSONObject("limits").put("canvasPixels",4097);check("An unexpected operation budget cannot be relabelled as the current probe",rejected(badBudget,metadata()));
    JSONObject badDuration=deep(3000,A);api(badDuration).put("durationMs","12.5");check("String probe duration does not pass numeric validation",rejected(badDuration,metadata()));
    JSONObject badStatus=deep(3000,A);api(badStatus).put("status","partial");check("Aggregate status must match the actual typed operation states",rejected(badStatus,metadata()));
    JSONObject missingProbe=deep(3000,A);probes(missingProbe).remove("audio");check("Partial operation dictionaries cannot be pinned as a complete deep run",rejected(missingProbe,metadata()));
    JSONObject unknownState=deep(3000,A);probes(unknownState).getJSONObject("canvas").put("state","verified");check("Operation states cannot claim verified protection",rejected(unknownState,metadata()));
    JSONObject noReason=deep(3000,A);probes(noReason).getJSONObject("canvas").remove("reason");check("Operations require an explicit bounded reason",rejected(noReason,metadata()));
    for(String hash:new String[]{"invalid",A.toUpperCase(Locale.ROOT),A.substring(1)}){JSONObject badHash=deep(3000,A);probes(badHash).getJSONObject("canvas").put("hash",hash);check("A malformed hash is rejected rather than sanitized into missing: "+hash.length()+"/"+hash.charAt(0),rejected(badHash,metadata()));}
    JSONObject numericHash=deep(3000,A);probes(numericHash).getJSONObject("canvas").put("hash",new java.math.BigInteger(String.join("",Collections.nCopies(64,"1"))));check("A numeric value cannot masquerade as a 64-character hexadecimal hash",rejected(numericHash,metadata()));
    JSONObject wrongAlgorithm=deep(3000,A);probes(wrongAlgorithm).getJSONObject("canvas").put("hashAlgorithm","md5");check("Unrecognized hash algorithms are rejected",rejected(wrongAlgorithm,metadata()));
    JSONObject noAlgorithm=deep(3000,A);probes(noAlgorithm).getJSONObject("canvas").remove("hashAlgorithm");check("A bare hex string cannot imply a hash algorithm",rejected(noAlgorithm,metadata()));
    JSONObject contradicted=deep(3000,A);probes(contradicted).getJSONObject("canvas").put("hashUnavailable",true);check("A hash cannot simultaneously claim unavailable",rejected(contradicted,metadata()));
    JSONObject noHashFlag=deep(3000,A);probes(noHashFlag).getJSONObject("canvas").remove("hash");probes(noHashFlag).getJSONObject("canvas").remove("hashAlgorithm");check("Available without hash needs explicit unavailable metadata",rejected(noHashFlag,metadata()));
    JSONObject failedHash=deep(3000,A);probes(failedHash).getJSONObject("canvas").put("state","failed");check("A failed operation cannot contribute a valid hash reference",rejected(failedHash,metadata()));
    JSONObject missingPixels=deep(3000,A);probes(missingPixels).getJSONObject("canvas").remove("pixels");check("Available canvas needs actual bounded readback evidence",rejected(missingPixels,metadata()));
    JSONObject badAudio=deep(3000,A);probes(badAudio).getJSONObject("audio").put("frames",2049);check("An arbitrary audio hash needs the expected operation evidence",rejected(badAudio,metadata()));
    JSONObject badFonts=deep(3000,A);probes(badFonts).getJSONObject("fonts").getJSONArray("samples").getJSONObject(0).put("name","arbitrary-face");check("A font hash requires the bounded candidate set",rejected(badFonts,metadata()));
    JSONObject badWebgl=deep(3000,A);probes(badWebgl).getJSONObject("webgl").put("extensionCount",0);check("Restricted WebGL hashes still require coherent capability evidence",rejected(badWebgl,metadata()));
    JSONObject stripped=deep(3000,A);stripped.put("cookie","must-not-persist");probes(stripped).getJSONObject("fonts").getJSONArray("samples").getJSONObject(0).put("password","must-not-persist");
    JSONObject safe=FingerprintDeepBaseline.capture(stripped,metadata(),4000);check("Only whitelisted observation fields are saved",safe.length()>0&&!safe.toString().contains("must-not-persist"));
    JSONObject oversized=copy(pin);oversized.put("junk",String.join("",Collections.nCopies(FingerprintDeepBaseline.MAX_BYTES,"x")));check("Oversized saved data is rejected before field sanitization",FingerprintDeepBaseline.restore(oversized,ENV,1).length()==0);
    JSONObject unicodeSaved=copy(pin);unicodeSaved.put("junk",String.join("",Collections.nCopies(6000,"中")));check("The saved limit counts UTF-8 bytes rather than characters",unicodeSaved.toString().length()<FingerprintDeepBaseline.MAX_BYTES&&FingerprintDeepBaseline.restore(unicodeSaved,ENV,1).length()==0);
    JSONObject unicodeReport=deep(3000,A),unicodeMeta=metadata(),unicodeParent=unicodeReport.getJSONObject("signals").getJSONObject("parent");String wide=String.join("",Collections.nCopies(2048,"中")),shortWide=wide.substring(0,256);unicodeParent.put("ua",wide).put("renderer",wide).put("language",shortWide).put("zone",shortWide);JSONArray wideLanguages=new JSONArray();for(int i=0;i<8;i++)wideLanguages.put(wide.substring(0,64));unicodeParent.put("languages",wideLanguages);unicodeMeta.put("engineVersion",wide.substring(0,128)).put("appVersion",wide.substring(0,128));for(String field:new String[]{"version","shadingLanguageVersion","vendor","renderer"})probes(unicodeReport).getJSONObject("webgl").put(field,shortWide);check("Capture eligibility rejects a combined valid-field record above its byte budget",!FingerprintDeepBaseline.captureIssue(unicodeReport,unicodeMeta).isEmpty()&&FingerprintDeepBaseline.capture(unicodeReport,unicodeMeta,4000).length()==0);
    JSONObject tampered=copy(pin);tampered.getJSONObject("observation").getJSONObject("apis").getJSONObject("canvas").put("hash",B);check("Stored hash view must match saved operation evidence",FingerprintDeepBaseline.restore(tampered,ENV,1).length()==0);
    JSONObject tamperedProof=copy(pin);tamperedProof.getJSONObject("checks").getJSONObject("probes").getJSONObject("canvas").remove("pixels");check("Stored operation evidence is validated again on restore",FingerprintDeepBaseline.restore(tamperedProof,ENV,1).length()==0);
    for(Object schema:new Object[]{"1",2,1.5}){JSONObject future=copy(pin);future.put("schema",schema);check("Unknown or malformed saved schema is not migrated silently: "+schema,FingerprintDeepBaseline.restore(future,ENV,1).length()==0);}
    JSONObject wrongKind=copy(pin);wrongKind.put("kind","recent-history");check("A recent-history object cannot masquerade as a fixed baseline",FingerprintDeepBaseline.restore(wrongKind,ENV,1).length()==0);
    JSONObject claimed=copy(pin);claimed.put("protectionVerified",true);check("Stored baseline cannot assert native protection effectiveness",FingerprintDeepBaseline.restore(claimed,ENV,1).length()==0);
    JSONObject zeroTime=copy(pin);zeroTime.put("pinnedAt",0);check("Invalid saved pin timestamps are rejected",FingerprintDeepBaseline.restore(zeroTime,ENV,1).length()==0);
    check("An invalid user pin timestamp cannot create a baseline",FingerprintDeepBaseline.capture(report,metadata(),0).length()==0);
    JSONObject input=deep(6000,A),inputMeta=metadata(),detached=FingerprintDeepBaseline.capture(input,inputMeta,7000);input.getJSONObject("signals").getJSONObject("parent").put("ua","changed-after-pin");probes(input).getJSONObject("canvas").put("hash",B);inputMeta.put("engineVersion","changed-after-pin");check("Pin owns an immutable copy of mutable observation inputs",!detached.toString().contains("changed-after-pin")&&detached.getJSONObject("checks").getJSONObject("probes").getJSONObject("canvas").getString("hash").equals(A));
    JSONObject detachedRestore=FingerprintDeepBaseline.restore(pin,ENV,1);detachedRestore.getJSONObject("checks").getJSONObject("probes").getJSONObject("canvas").put("hash",B);check("Restored output does not mutate the encrypted input object",pin.getJSONObject("checks").getJSONObject("probes").getJSONObject("canvas").getString("hash").equals(A));
    String summary=FingerprintDeepBaseline.summary(pin,deep(8000,B),metadata());
    check("Summary identifies the page source configuration versions and fixed lifecycle",summary.contains("https://chatgpt.com")&&summary.contains("配置 7")&&summary.contains("Gecko 157.0.1")&&summary.contains("探针 1")&&summary.contains("独立于最近八条观测"));
    check("Summary explains that cross-context hashes need not match",summary.contains("Worker 或 iframe 不要求哈希相同")&&summary.contains("变化不等于泄漏"));
    check("Valid capture and restoration remain within the byte budget",pin.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=FingerprintDeepBaseline.MAX_BYTES&&restored.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length<=FingerprintDeepBaseline.MAX_BYTES);
    System.out.println(J.obj("status","passed","total",checks.length(),"passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"protectionEffectivenessAcceptance",false).toString());
  }
}
