package local.pocketchat;

import java.util.*;
import java.util.function.*;
import org.json.*;

/** Integration-only native import protocol. No Android/Gecko action is simulated here. */
final class GeckoTlsFixtureTrustState {
  static final Set<String> BINDING=keys("sourceCommit sourceTree runNonce caseNonce bootCaseNonce runtimeNonce processNonce challengeNonce expectedCaDerSha256 pid slot");
  static final Set<String> INPUT=keys("caPemSha256 caDerSha256 leafDerSha256 caNotBeforeMs caNotAfterMs leafNotBeforeMs leafNotAfterMs hostUtcMs");
  static final Set<String> NATIVE=keys("schema binding importEventCount importedEventObserved importTopic importedAtUtcMs nativeEffective nativeHasUserValue nativeGetEnterpriseRoots rootMatches caDerSha256 caNotBeforeMs caNotAfterMs nativeReadUtcMs");
  final LongSupplier now,deadline;final BooleanSupplier owner;final JSONObject input;
  final Set<String> cases=new HashSet<>();
  JSONObject binding,nativeReceipt=new JSONObject();
  String phase="connecting";boolean bootReady,caseReady,retired;
  int enableCalls;long armedAt,enabledAt,importAckAt,caseAckAt,importedUtc;

  GeckoTlsFixtureTrustState(JSONObject original,JSONObject expected,LongSupplier now,LongSupplier deadline,BooleanSupplier owner)throws Exception{
    this.now=now;this.deadline=deadline;this.owner=owner;binding=copy(original);input=copy(expected);
    exact(binding,BINDING);exact(input,INPUT);
    for(String key:Arrays.asList("sourceCommit","sourceTree"))hex(binding,key,40);
    for(String key:Arrays.asList("runNonce","caseNonce","bootCaseNonce","runtimeNonce","processNonce","challengeNonce"))hex(binding,key,32);
    hex(binding,"expectedCaDerSha256",64);
    for(String key:Arrays.asList("caPemSha256","caDerSha256","leafDerSha256"))hex(input,key,64);
    if(!same(binding.get("caseNonce"),binding.get("bootCaseNonce"))||!same(binding.get("expectedCaDerSha256"),input.get("caDerSha256"))||number(binding,"pid")<1||!Arrays.asList(0L,1L,2L,6L).contains(number(binding,"slot")))reject("binding");
    for(String key:Arrays.asList("caNotBeforeMs","caNotAfterMs","leafNotBeforeMs","leafNotAfterMs","hostUtcMs"))if(number(input,key)<1)reject("validity");
    if(number(input,"caNotBeforeMs")>=number(input,"caNotAfterMs")||number(input,"leafNotBeforeMs")>=number(input,"leafNotAfterMs"))reject("validity");
    cases.add(binding.getString("caseNonce"));active();
  }
  JSONObject connected()throws Exception{active();if(!"connecting".equals(phase))reject("duplicate-connect");phase="arming";return request("arm");}
  void armed(JSONObject value)throws Exception{
    active();if(!"arming".equals(phase))reject("duplicate-arm");
    exact(value,keys("schema binding observerRegistered nativeEffective nativeHasUserValue importEventCount"));bound(value);
    if(number(value,"schema")!=1||!Boolean.TRUE.equals(value.opt("observerRegistered"))||!Boolean.FALSE.equals(value.opt("nativeEffective"))||!Boolean.FALSE.equals(value.opt("nativeHasUserValue"))||number(value,"importEventCount")!=0)reject("arm-proof");
    armedAt=now.getAsLong();phase="armed";
  }
  void enabling()throws Exception{active();if(!"armed".equals(phase)||enableCalls!=0)reject("duplicate-enable");enabledAt=now.getAsLong();enableCalls++;phase="waiting-import";}
  void ready(JSONObject value)throws Exception{
    active();boolean cold="waiting-import".equals(phase),resample="reading".equals(phase);
    if(!cold&&!resample||enableCalls!=1)reject("unexpected-ack");exact(value,NATIVE);bound(value);
    if(number(value,"schema")!=1||number(value,"importEventCount")!=1||!Boolean.TRUE.equals(value.opt("importedEventObserved"))||!"psm:enterprise-certs-imported".equals(value.opt("importTopic"))||!Boolean.TRUE.equals(value.opt("nativeEffective"))||!Boolean.FALSE.equals(value.opt("nativeHasUserValue"))||!Boolean.TRUE.equals(value.opt("nativeGetEnterpriseRoots"))||number(value,"rootMatches")!=1||!same(value.opt("caDerSha256"),input.opt("caDerSha256")))reject("native-proof");
    if(!same(value.opt("caNotBeforeMs"),input.opt("caNotBeforeMs"))||!same(value.opt("caNotAfterMs"),input.opt("caNotAfterMs")))reject("validity");
    long imported=number(value,"importedAtUtcMs"),read=number(value,"nativeReadUtcMs");
    if(imported<1||imported>read||resample&&imported!=importedUtc||read<number(input,"caNotBeforeMs")||read>number(input,"caNotAfterMs")||read<number(input,"leafNotBeforeMs")||read>number(input,"leafNotAfterMs"))reject("clock-or-import");
    JSONObject accepted=copy(value);
    // GeckoBundle carries JS integral values above int32 as Double. Preserve
    // their exact safe-integer values in the original Android JSON report.
    for(String key:Arrays.asList("schema","importEventCount","importedAtUtcMs","rootMatches","caNotBeforeMs","caNotAfterMs","nativeReadUtcMs"))accepted.put(key,number(value,key));
    accepted.put("binding",copy(binding));active();
    if(cold){if(bootReady||armedAt<1||enabledAt<armedAt)reject("import-order");importAckAt=now.getAsLong();importedUtc=imported;bootReady=true;}
    nativeReceipt=accepted;caseAckAt=now.getAsLong();caseReady=true;phase="ready";
  }
  JSONObject resample(String next)throws Exception{
    active();if(!bootReady||!caseReady||!"ready".equals(phase)||next==null||!next.matches("[0-9a-f]{32}")||!cases.add(next)||cases.size()>11)reject("resample-binding");
    binding.put("caseNonce",next);binding.put("challengeNonce",UUID.randomUUID().toString().replace("-",""));caseReady=false;phase="reading";
    return request("read");
  }
  boolean bootReady(){return bootReady&&!retired&&!"failed".equals(phase)&&owner.getAsBoolean();}
  boolean caseReady(String nonce){return bootReady()&&caseReady&&"ready".equals(phase)&&deadline.getAsLong()>0&&now.getAsLong()<deadline.getAsLong()&&nonce.equals(binding.opt("caseNonce"));}
  void fail(){phase="failed";caseReady=false;}
  void close(){retired=true;caseReady=false;}
  void active()throws Exception{if(retired||!owner.getAsBoolean())reject("retired");if(deadline.getAsLong()<=0||now.getAsLong()>=deadline.getAsLong())reject("deadline");if("failed".equals(phase))reject("failed");}
  JSONObject evidence(){return obj("schema",1,"status",phase,"binding",copy(binding),"enableCalls",enableCalls,
    "observerArmedBeforeEnable",armedAt>0&&enabledAt>=armedAt,"bootImportAcknowledged",bootReady,
    "caseReadOnly",!binding.optString("caseNonce").equals(binding.optString("bootCaseNonce")),
    "armedAtElapsed",armedAt,"enabledAtElapsed",enabledAt,"importAckAtElapsed",importAckAt,
    "caseAckAtElapsed",caseAckAt,"deadlineElapsed",deadline.getAsLong(),"nativeReceipt",copy(nativeReceipt));}
  JSONObject request(String kind){return obj("kind",kind,"binding",copy(binding));}
  void bound(JSONObject value)throws Exception{if(!(value.opt("binding") instanceof JSONObject)||!same(value.get("binding"),binding))reject("binding");}
  static JSONObject copy(JSONObject value){try{return new JSONObject(value.toString());}catch(JSONException invalid){throw new IllegalStateException(invalid);}}
  static Set<String> keys(String value){return new HashSet<>(Arrays.asList(value.split(" ")));}
  static void exact(JSONObject value,Set<String> expected)throws Exception{Set<String> actual=new HashSet<>();for(Iterator<String> it=value.keys();it.hasNext();)actual.add(it.next());if(!actual.equals(expected))reject("fields");}
  static long number(JSONObject value,String key)throws Exception{return numeric(value.opt(key));}
  static long numeric(Object value)throws Exception{
    if(!(value instanceof Integer)&&!(value instanceof Long)&&!(value instanceof Double))reject("type");
    double number=((Number)value).doubleValue();
    if(!Double.isFinite(number)||Math.abs(number)>9007199254740991d||number!=Math.rint(number))reject("integer");
    return ((Number)value).longValue();
  }
  static void hex(JSONObject value,String key,int count)throws Exception{Object text=value.opt(key);if(!(text instanceof String)||!((String)text).matches("[0-9a-f]{"+count+"}"))reject("binding");}
  static boolean same(Object left,Object right)throws Exception{
    if(left instanceof JSONObject&&right instanceof JSONObject){JSONObject a=(JSONObject)left,b=(JSONObject)right;Set<String> keys=new HashSet<>();for(Iterator<String> it=b.keys();it.hasNext();)keys.add(it.next());exact(a,keys);for(String key:keys)if(!same(a.get(key),b.get(key)))return false;return true;}
    if(left instanceof Number||right instanceof Number)return numeric(left)==numeric(right);
    return left!=null&&left.getClass()==right.getClass()&&left.equals(right);
  }
  static JSONObject obj(Object... values){JSONObject result=new JSONObject();try{for(int i=0;i<values.length;i+=2)result.put((String)values[i],values[i+1]);return result;}catch(JSONException invalid){throw new IllegalStateException(invalid);}}
  static void reject(String reason)throws java.io.IOException{throw new java.io.IOException("FixtureTrust:"+reason);}
}
