package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Host-constructed observations exercising production context ownership and persistence rules. */
public final class FingerprintContextBaselinesHost {
  static final String ENV=FingerprintDeepBaselineHost.ENV,OTHER=FingerprintDeepBaselineHost.OTHER;
  static final String A=FingerprintDeepBaselineHost.A,B=FingerprintDeepBaselineHost.B;
  static final String SECOND="https://secondary.example";
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  static JSONObject copy(JSONObject value){return FingerprintObservationHistory.copy(value);}
  static JSONObject meta(){return FingerprintDeepBaselineHost.metadata();}
  static JSONObject raw(JSONObject report,String context)throws Exception{
    if("main".equals(context))return report.getJSONObject("signals").getJSONObject("apiChecks");
    if("crossOriginFrame".equals(context))return report.getJSONObject("requestIdentity").getJSONObject("browser").getJSONObject("crossOriginFrame").getJSONObject("apiChecks");
    return report.getJSONObject("signals").getJSONObject("apiContexts").getJSONObject(context);
  }
  static JSONObject probe(JSONObject report,String context,String api)throws Exception{return raw(report,context).getJSONObject("probes").getJSONObject(api);}
  static JSONObject frame(JSONObject report)throws Exception{return report.getJSONObject("requestIdentity").getJSONObject("browser").getJSONObject("crossOriginFrame");}
  static JSONObject report(long at,String hash)throws Exception{
    JSONObject value=FingerprintDeepBaselineHost.deep(at,hash),signals=value.getJSONObject("signals"),main=signals.getJSONObject("apiChecks");
    JSONObject frame=copy(main);frame.put("source","same-origin-srcdoc");
    JSONObject worker=copy(main);worker.put("source","dedicated-worker").put("status","partial");
    worker.getJSONObject("limits").put("audioFrames",0).put("fontCandidates",0);
    worker.getJSONObject("probes").put("audio",J.obj("state","uncovered","reason","not-applicable-in-worker")).put("fonts",J.obj("state","uncovered","reason","not-applicable-in-worker"));
    worker.getJSONObject("probes").getJSONObject("webgl").put("readbackPixels",256).put("readbackBytes",1024).put("readbackHash",hash).put("readbackHashAlgorithm","sha256");
    signals.put("frame",FingerprintDeepBaselineHost.signal()).put("worker",FingerprintDeepBaselineHost.signal())
        .put("apiContexts",J.obj("schema",1,"requested",true,"frame",frame,"worker",worker));
    JSONObject cross=copy(worker);cross.put("source","controlled-cross-origin-iframe").put("status","completed");cross.remove("durationMs");
    // The production checked cross-origin result intentionally omits extensions and duration.
    cross.getJSONObject("probes").getJSONObject("webgl").remove("extensions");
    JSONObject checkedFrame=J.obj("status","complete","source","controlled-cross-origin-iframe","nonce","host-context-case","origin",SECOND,"apiChecks",cross,"protectionVerified",false);
    JSONObject identity=J.obj("schema",1,"source","controlled-top-level-document","status","observed","nonce","host-context-case","endpoint","https://chatgpt.com/identity","frameEndpoint",SECOND+"/identity","controlSource","extension-background-control","crossOriginFrameRequested",true,"fresh",true,"environmentId",ENV,"environmentGeneration",1,"configurationRevision",7,"executionId","run-1",
        "expected",J.obj("environmentId",ENV,"environmentGeneration",1,"configurationRevision",7),"browser",J.obj("crossOriginFrame",checkedFrame));
    value.put("requestIdentityControlSource","extension-background-control").put("requestIdentityNetwork",true).put("requestIdentity",identity);
    return value;
  }
  static JSONObject pin(JSONObject saved,JSONObject report,JSONObject meta,String context,long at){return FingerprintContextBaselines.replace(saved,report,meta,context,at);}
  static JSONObject compare(JSONObject saved,JSONObject report,JSONObject meta,String context){return FingerprintContextBaselines.comparison(saved,report,meta,context);}
  static boolean rejected(JSONObject value,JSONObject metadata,String context){return !FingerprintContextBaselines.captureIssue(value,metadata,context).isEmpty();}
  static int count(JSONObject value){return FingerprintContextBaselines.count(value,ENV,1);}
  static JSONObject observation(JSONObject value,String context)throws Exception{return value.getJSONObject("refs").getJSONObject(context).getJSONObject("observation");}
  static boolean crossRejectedOnly(JSONObject saved,JSONObject report)throws Exception{
    if(!rejected(report,meta(),"crossOriginFrame")||!"current-unavailable".equals(compare(saved,report,meta(),"crossOriginFrame").optString("state"))
        ||!FingerprintObservationHistory.same(saved,pin(saved,report,meta(),"crossOriginFrame",4000)))return false;
    for(String context:new String[]{"main","worker","frame"})if(rejected(report,meta(),context)||!"comparable".equals(compare(saved,report,meta(),context).optString("state")))return false;
    return true;
  }
  public static void main(String[] args)throws Exception{
    JSONObject first=report(1000,A),saved=new JSONObject();String original=first.toString();
    for(String context:FingerprintContextBaselines.CONTEXTS){
      check("A complete explicitly requested observation can pin its own context "+context,!rejected(first,meta(),context));
      saved=pin(saved,first,meta(),context,2000);
    }
    check("Exactly four execution contexts can be retained",count(saved)==4&&saved.getJSONObject("refs").length()==4);
    check("Each context has a distinct visible label",new HashSet<String>(Arrays.asList(FingerprintContextBaselines.label("main"),FingerprintContextBaselines.label("worker"),FingerprintContextBaselines.label("frame"),FingerprintContextBaselines.label("crossOriginFrame"))).size()==4);
    check("Cross origin retains the actual secondary source and primary embedding origin",observation(saved,"crossOriginFrame").getString("sourceOrigin").equals(SECOND)&&observation(saved,"crossOriginFrame").getString("topLevelOrigin").equals("https://chatgpt.com"));
    check("Same origin iframe keeps its distinct execution source",observation(saved,"frame").getString("source").equals("same-origin-srcdoc")&&!observation(saved,"frame").getString("source").equals(observation(saved,"main").getString("source")));
    check("Only origins are retained instead of private document paths",!saved.toString().contains("private-draft")&&!saved.toString().contains("not-persisted"));
    JSONObject restored=FingerprintContextBaselines.restore(saved,ENV,1);
    check("All four references survive bounded JSON restoration",count(restored)==4&&FingerprintObservationHistory.same(saved,restored));
    check("Another environment cannot restore these references",FingerprintContextBaselines.count(saved,OTHER,1)==0);
    check("A new environment generation cannot restore old references",FingerprintContextBaselines.count(saved,ENV,2)==0);
    JSONObject legacy=FingerprintDeepBaseline.capture(first,meta(),2000),migrated=FingerprintContextBaselines.restore(legacy,ENV,1);
    check("Legacy main reference migrates without acquiring child references",count(migrated)==1&&FingerprintContextBaselines.hasReference(migrated,ENV,1,"main")&&!FingerprintContextBaselines.hasReference(migrated,ENV,1,"worker"));
    check("Migration keeps the original validated main reference unchanged",FingerprintObservationHistory.same(legacy,migrated.getJSONObject("refs").getJSONObject("main")));
    check("Legacy ownership cannot be relabelled during migration",FingerprintContextBaselines.count(legacy,OTHER,1)==0);
    JSONObject restarted=report(3000,A),restartMeta=meta();restarted.put("executionId","run-2");restartMeta.put("executionId","run-2");restarted.getJSONObject("requestIdentity").put("executionId","run-2").put("nonce","host-context-case-2");frame(restarted).put("nonce","host-context-case-2");
    for(String context:FingerprintContextBaselines.CONTEXTS){
      JSONObject result=compare(saved,restarted,restartMeta,context);
      check("A restart compares only the same context and group "+context,"comparable".equals(result.optString("state"))&&result.optInt("hashComparedCount")>0&&result.optInt("hashChangedCount")==0&&!result.optBoolean("crossExecutionContextComparison")&&!result.optBoolean("protectionVerified")&&!result.optBoolean("leakVerdict"));
    }
    JSONObject changed=report(3000,A);probe(changed,"worker","canvas").put("hash",B);
    check("A Worker output change affects only the Worker reference",compare(saved,changed,meta(),"worker").getInt("hashChangedCount")==1&&compare(saved,changed,meta(),"main").getInt("hashChangedCount")==0&&compare(saved,changed,meta(),"frame").getInt("hashChangedCount")==0);
    JSONObject readback=report(3000,A);probe(readback,"worker","webgl").put("readbackHash",B);
    check("Worker readback differences are reported separately from primary hashes",compare(saved,readback,meta(),"worker").optInt("readbackChangedCount")==1&&compare(saved,readback,meta(),"worker").getInt("hashChangedCount")==0);
    JSONObject unequal=report(3000,A);probe(unequal,"frame","canvas").put("hash",B);JSONObject isolated=pin(new JSONObject(),unequal,meta(),"frame",4000);
    check("Different valid main and frame hashes are not compared across contexts",compare(isolated,unequal,meta(),"frame").getInt("hashChangedCount")==0&&compare(isolated,unequal,meta(),"main").getString("state").equals("no-reference"));
    for(String field:new String[]{"configurationRevision","engineVersion","appVersion","appVersionCode","sourceOrigin"}){
      JSONObject now=report(3000,B),metadata=meta();
      if("configurationRevision".equals(field)){metadata.put(field,8);now.put("identityAppliedRevision",8);}else if("appVersionCode".equals(field))metadata.put(field,78);else metadata.put(field,"sourceOrigin".equals(field)?"https://other.example/check":"different");
      JSONObject result=compare(saved,now,metadata,"worker");
      check("Changed grouping field never creates a Worker hash verdict "+field,"separate-context".equals(result.optString("state"))&&result.optInt("hashComparedCount")==0);
    }
    JSONObject newProbe=report(3000,B);raw(newProbe,"worker").put("probeVersion",2);
    check("Different Worker probe versions remain separate",compare(saved,newProbe,meta(),"worker").getString("state").equals("separate-context"));
    JSONObject embedding=report(3000,B),embeddingMeta=meta();embeddingMeta.put("sourceOrigin","https://embedding.example/check");embedding.getJSONObject("requestIdentity").put("endpoint","https://embedding.example/identity");
    check("A changed cross frame embedding origin cannot compare the old reference",compare(saved,embedding,embeddingMeta,"crossOriginFrame").getString("state").equals("separate-context"));
    JSONObject secondary=report(3000,B);frame(secondary).put("origin","https://different-secondary.example");secondary.getJSONObject("requestIdentity").put("frameEndpoint","https://different-secondary.example/identity");
    check("A changed secondary source remains separate from the old frame reference",compare(saved,secondary,meta(),"crossOriginFrame").getString("state").equals("separate-context"));
    JSONObject cleared=FingerprintContextBaselines.clear(saved,ENV,1,"worker");
    check("Clearing one context retains the other three references",count(cleared)==3&&!FingerprintContextBaselines.hasReference(cleared,ENV,1,"worker")&&FingerprintContextBaselines.hasReference(cleared,ENV,1,"main")&&FingerprintContextBaselines.hasReference(cleared,ENV,1,"frame")&&FingerprintContextBaselines.hasReference(cleared,ENV,1,"crossOriginFrame"));
    check("Explicit clear all removes all contexts",count(FingerprintContextBaselines.clear(saved,ENV,1,"all"))==0);
    check("Unknown context cannot clear existing references",FingerprintObservationHistory.same(saved,FingerprintContextBaselines.clear(saved,ENV,1,"invented")));
    check("Unknown context cannot be pinned",rejected(first,meta(),"invented")&&count(pin(saved,first,meta(),"invented",3000))==4);
    check("Unknown context cannot be presented as a covered cross origin source",compare(saved,first,meta(),"invented").getString("source").isEmpty()&&compare(saved,first,meta(),"invented").getString("state").equals("no-reference"));
    JSONObject stale=report(3000,A);stale.put("fresh",false);
    check("Stale current results cannot replace a Worker reference",rejected(stale,meta(),"worker")&&FingerprintObservationHistory.same(saved,pin(saved,stale,meta(),"worker",4000)));
    JSONObject wrongExecution=report(3000,A);wrongExecution.put("executionId","old-run");
    check("Current report execution must match capture metadata",rejected(wrongExecution,meta(),"worker"));
    JSONObject wrongRevision=report(3000,A);wrongRevision.put("identityAppliedRevision",8);
    check("Current report revision cannot be relabelled",rejected(wrongRevision,meta(),"frame"));
    JSONObject foreign=report(3000,A);foreign.getJSONObject("expected").put("environmentId",OTHER);
    check("Current report belongs to the expected environment",rejected(foreign,meta(),"worker"));
    JSONObject fallback=report(3000,A);fallback.getJSONObject("signals").put("provenance","extension-isolated-world-fallback");
    check("An isolated-world fallback cannot substitute Worker evidence",rejected(fallback,meta(),"worker"));
    JSONObject noContexts=report(3000,A);noContexts.getJSONObject("signals").remove("apiContexts");
    check("Ordinary observations cannot silently replace deep child references",rejected(noContexts,meta(),"worker")&&compare(saved,noContexts,meta(),"worker").getString("state").equals("current-unavailable"));
    JSONObject wrongSource=report(3000,A);raw(wrongSource,"worker").put("source","page-main-world");
    check("Wrong execution source cannot be promoted into Worker evidence",rejected(wrongSource,meta(),"worker"));
    JSONObject wrongBudget=report(3000,A);raw(wrongBudget,"worker").getJSONObject("limits").put("audioFrames",2048);
    check("Worker cannot claim a main-page audio operation budget",rejected(wrongBudget,meta(),"worker"));
    JSONObject unsupported=report(3000,A);raw(unsupported,"worker").getJSONObject("probes").put("audio",FingerprintDeepBaselineHost.audio(A));
    check("Worker audio and fonts cannot be promoted from page implementations",rejected(unsupported,meta(),"worker"));
    JSONObject hash=report(3000,A);probe(hash,"worker","canvas").put("hash","not-a-digest");
    check("Malformed child operation hash cannot be pinned",rejected(hash,meta(),"worker"));
    JSONObject pixels=report(3000,A);probe(pixels,"worker","webgl").put("readbackBytes",1025);
    check("Unexpected Worker readback dimensions cannot be pinned",rejected(pixels,meta(),"worker"));
    for(Object renderer:new Object[]{J.obj("unregistered","nested-object"),String.join("",Collections.nCopies(257,"x"))}){
      JSONObject invalid=report(3000,A);probe(invalid,"worker","webgl").put("unmaskedRenderer",renderer);
      check("Optional Worker renderer must be a bounded string "+(renderer instanceof String?"oversized":"object"),rejected(invalid,meta(),"worker"));
    }
    JSONObject hashFlag=report(3000,A);probe(hashFlag,"worker","webgl").put("readbackHashUnavailable",true);
    check("A digest and unavailability claim cannot both verify readback",rejected(hashFlag,meta(),"worker"));
    for(String[] operation:new String[][]{{"frame","webgl"},{"worker","canvas"},{"frame","audio"},{"crossOriginFrame","canvas"}}){
      JSONObject extra=report(3000,A);probe(extra,operation[0],operation[1]).put("readbackPixels",256).put("readbackBytes",1024).put("readbackHash",A).put("readbackHashAlgorithm","sha256");
      check("An unimplemented readback cannot enter an operation reference "+operation[0]+" "+operation[1],rejected(extra,meta(),operation[0]));
    }
    JSONObject mainReadback=report(3000,A);probe(mainReadback,"main","webgl").put("readbackPixels",256).put("readbackBytes",1024).put("readbackHash",A).put("readbackHashAlgorithm","sha256");
    check("Main page comparison snapshots cannot invent an unimplemented WebGL readback",FingerprintContextBaselines.contextSnapshot(mainReadback,meta(),"main").length()==0);
    JSONObject noHash=report(3000,A);JSONObject canvas=probe(noHash,"worker","canvas");canvas.remove("hash");canvas.remove("hashAlgorithm");canvas.put("hashUnavailable",true);
    JSONObject noHashPin=pin(new JSONObject(),noHash,meta(),"worker",4000);
    check("An explicit unavailable digest retains an observed operation without inventing hash comparison",count(noHashPin)==1&&!compare(noHashPin,noHash,meta(),"worker").getJSONObject("apiComparisons").getJSONObject("canvas").getBoolean("compared"));
    JSONObject failed=report(3000,A);for(String name:new String[]{"canvas","webgl"})raw(failed,"worker").getJSONObject("probes").put(name,J.obj("state","failed","reason","host-labelled-failure"));
    check("Entirely failed operations cannot replace a useful Worker reference",rejected(failed,meta(),"worker")&&FingerprintObservationHistory.same(saved,pin(saved,failed,meta(),"worker",4000)));
    check("Failed current operations never appear unchanged",compare(saved,failed,meta(),"worker").optInt("hashComparedCount")==0);
    JSONObject restricted=report(3000,A);for(String name:new String[]{"canvas","webgl"})raw(restricted,"worker").getJSONObject("probes").put(name,J.obj("state","restricted","reason","SecurityError"));
    check("Restricted observations can be retained without a protection verdict",count(pin(new JSONObject(),restricted,meta(),"worker",4000))==1&&compare(saved,restricted,meta(),"worker").optInt("hashComparedCount")==0&&!compare(saved,restricted,meta(),"worker").optBoolean("protectionVerified"));
    JSONObject nonce=report(3000,A);frame(nonce).put("nonce","different-session");
    check("Cross origin result nonce must match the checked audit",rejected(nonce,meta(),"crossOriginFrame"));
    JSONObject noConsent=report(3000,A);noConsent.getJSONObject("requestIdentity").put("crossOriginFrameRequested",false);
    check("Unrequested secondary context cannot be pinned",rejected(noConsent,meta(),"crossOriginFrame"));
    JSONObject wrongControl=report(3000,A);wrongControl.put("requestIdentityControlSource","page-self-report");
    check("Page self report cannot replace independently controlled cross origin evidence",rejected(wrongControl,meta(),"crossOriginFrame"));
    JSONObject sameOrigin=report(3000,A);frame(sameOrigin).put("origin","https://chatgpt.com");
    check("Cross origin slot refuses a same origin replacement",rejected(sameOrigin,meta(),"crossOriginFrame"));
    JSONObject insecure=report(3000,A);frame(insecure).put("origin","http://secondary.example");
    check("Cross origin source must remain a valid secure origin",rejected(insecure,meta(),"crossOriginFrame"));
    JSONObject incomplete=report(3000,A);frame(incomplete).put("status","uncovered");
    check("Missing controlled context cannot be described as a pinned observation",rejected(incomplete,meta(),"crossOriginFrame"));
    JSONObject tampered=copy(saved);observation(tampered,"worker").put("source","page-main-world");
    check("Stored context relabelling is rejected without disturbing other slots",!FingerprintContextBaselines.hasReference(tampered,ENV,1,"worker")&&FingerprintContextBaselines.hasReference(tampered,ENV,1,"main"));
    JSONObject unknown=copy(saved);unknown.getJSONObject("refs").put("invented",copy(unknown.getJSONObject("refs").getJSONObject("worker")));
    check("Unknown stored slots are not restored",count(FingerprintContextBaselines.restore(unknown,ENV,1))==4&&FingerprintContextBaselines.restore(unknown,ENV,1).getJSONObject("refs").length()==4);
    JSONObject forged=copy(saved);forged.getJSONObject("refs").getJSONObject("worker").put("protectionVerified",true);
    check("A forged protection attestation cannot enter stored observations",!FingerprintContextBaselines.hasReference(forged,ENV,1,"worker"));
    JSONObject leaking=report(3000,A);raw(leaking,"worker").getJSONObject("probes").getJSONObject("canvas").put("unregisteredSecret","must-not-persist");
    check("Only registered child operation fields are persisted",!pin(new JSONObject(),leaking,meta(),"worker",4000).toString().contains("must-not-persist"));
    JSONObject huge=copy(saved);huge.put("unregistered",String.join("",Collections.nCopies(70000,"x")));
    check("Oversized saved aggregate cannot bypass the bounded store",count(FingerprintContextBaselines.restore(huge,ENV,1))==0);
    JSONObject oneSnapshot=null;boolean snapshotsOwned=true;
    for(String context:FingerprintContextBaselines.CONTEXTS){
      JSONObject observation=report(3000,A);
      for(String name:new String[]{"canvas","audio","fonts","webgl"})if(!(("worker".equals(context)||"crossOriginFrame".equals(context))&&("audio".equals(name)||"fonts".equals(name))))raw(observation,context).getJSONObject("probes").put(name,J.obj("state","failed","reason","host-labelled-failed-operation"));
      JSONObject snapshot=FingerprintContextBaselines.contextSnapshot(observation,meta(),context);oneSnapshot=snapshot;
      check("A failed observation snapshot preserves status without becoming a useful fixed reference "+context,snapshot.length()>0&&FingerprintContextBaselines.restoreContextSnapshot(snapshot,ENV,1,context).length()>0&&rejected(observation,meta(),context)&&!snapshot.optBoolean("protectionVerified")&&!snapshot.optBoolean("leakVerdict"));
      String other="worker".equals(context)?"frame":"worker";
      snapshotsOwned&=FingerprintContextBaselines.restoreContextSnapshot(snapshot,ENV,1,other).length()==0&&FingerprintContextBaselines.restoreContextSnapshot(snapshot,OTHER,1,context).length()==0&&FingerprintContextBaselines.restoreContextSnapshot(snapshot,ENV,2,context).length()==0;
    }
    check("Snapshots cannot cross execution context environment or generation ownership",oneSnapshot!=null&&snapshotsOwned);
    check("A current ordinary check does not falsely claim unchanged deep outputs",FingerprintContextBaselines.summary(saved,noContexts,meta(),"worker").contains("未")&&!FingerprintContextBaselines.summary(saved,noContexts,meta(),"worker").contains("已比较哈希未变"));
    check("No caller report or original reference is mutated",original.equals(first.toString())&&count(saved)==4);
    // These labelled host faults exercise mixed nested receipts. They do not
    // establish that the real Android session can produce these interleavings.
    String[] nestedFields={"configurationRevision","executionId","environmentId","environmentGeneration","fresh","fresh","configurationRevision"};
    Object[] nestedValues={6,"old-execution",OTHER,0,false,"true","7"};
    String[] nestedLabels={"old revision","old execution","foreign owner","old generation","false freshness","string freshness","string revision"};
    for(int i=0;i<nestedFields.length;i++){
      JSONObject bad=report(3000,A);bad.getJSONObject("requestIdentity").put(nestedFields[i],nestedValues[i]);
      check("Mixed nested cross receipt cannot inherit outer metadata and affects no other context "+nestedLabels[i],crossRejectedOnly(saved,bad));
    }
    String[] expectedFields={"environmentId","environmentGeneration","configurationRevision"};Object[] expectedValues={OTHER,0,6};
    for(int i=0;i<expectedFields.length;i++){
      JSONObject bad=report(3000,A);bad.getJSONObject("requestIdentity").getJSONObject("expected").put(expectedFields[i],expectedValues[i]);
      check("Nested expected cross binding must match the actual outer group "+expectedFields[i],crossRejectedOnly(saved,bad));
    }
    boolean missingReceiptRejected=true;
    for(String field:new String[]{"fresh","environmentId","environmentGeneration","configurationRevision","executionId","expected"}){
      JSONObject bad=report(3000,A);bad.getJSONObject("requestIdentity").remove(field);missingReceiptRejected&=crossRejectedOnly(saved,bad);
    }
    check("Missing nested freshness ownership or execution cannot be supplied by outer metadata",missingReceiptRejected);
    boolean missingExpectedRejected=true;
    for(String field:expectedFields){JSONObject bad=report(3000,A);bad.getJSONObject("requestIdentity").getJSONObject("expected").remove(field);missingExpectedRejected&=crossRejectedOnly(saved,bad);}
    check("Every nested expected owner generation and revision field is required",missingExpectedRejected);
    JSONObject captured=new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])),StandardCharsets.UTF_8)),capturedMeta=captured.getJSONObject("observationMetadata");
    String capturedBefore=captured.toString();JSONObject capturedSnapshot=FingerprintContextBaselines.contextSnapshot(captured,capturedMeta,"crossOriginFrame");
    check("An exact prior AVD Gecko cross origin report retains its actual owner and source without envelope replacement",capturedSnapshot.length()>0
        &&FingerprintContextBaselines.restoreContextSnapshot(capturedSnapshot,capturedMeta.getString("environmentId"),capturedMeta.getInt("environmentGeneration"),"crossOriginFrame").length()>0
        &&capturedSnapshot.getJSONObject("observation").getString("sourceOrigin").equals(frame(captured).getString("origin"))
        &&capturedSnapshot.getJSONObject("observation").getString("topLevelOrigin").equals(FingerprintObservationHistory.origin(capturedMeta.opt("sourceOrigin"))));
    boolean capturedMixedRejected=true;
    for(String field:new String[]{"configurationRevision","executionId"}){
      JSONObject bad=copy(captured);bad.getJSONObject("requestIdentity").put(field,"executionId".equals(field)?"host-injected-old-execution":capturedMeta.getLong("configurationRevision")-1);
      capturedMixedRejected&=FingerprintContextBaselines.contextSnapshot(bad,capturedMeta,"crossOriginFrame").length()==0&&!FingerprintContextBaselines.captureIssue(bad,capturedMeta,"crossOriginFrame").isEmpty();
    }
    check("Mixed nested revision and execution copies of the real old capture are rejected without changing its original",capturedMixedRejected&&capturedBefore.equals(captured.toString()));
    System.out.println(J.obj("schema",1,"status","passed","total",checks.length(),"passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"actualChromiumExecution",false,"usesPreviouslyCapturedActualGeckoInput",true,"protectionEffectivenessAcceptance",false,"scope","Production pure-Java context-reference ownership, bounded persistence and same-context comparison; host-constructed observations plus an exact prior AVD Gecko report, no new browser/native freshness or privacy-effectiveness attestation").toString());
  }
}
