package local.pocketchat;

import java.util.*;
import org.json.*;

/** Host-only counterfeit callback packets exercise the actual integration protocol. */
public final class TrustStateHost {
  static int checks;static final long UTC=1800000000000L;
  interface Action {void run()throws Exception;}
  static void check(boolean value,String name){checks++;if(!value)throw new AssertionError(name);}
  static void rejected(String name,Action action)throws Exception{try{action.run();throw new AssertionError("Accepted "+name);}catch(java.io.IOException expected){check(expected.getMessage().startsWith("FixtureTrust:"),name);}}
  static JSONObject obj(Object... value){return GeckoTlsFixtureTrustState.obj(value);}
  static String hex(char c,int n){char[] a=new char[n];Arrays.fill(a,c);return new String(a);}
  static final class Fixture {
    long time=1000,until=121000;boolean owner=true;GeckoTlsFixtureTrustState state;
    Fixture()throws Exception{
      JSONObject input=obj("caPemSha256",hex('1',64),"caDerSha256",hex('2',64),"leafDerSha256",hex('3',64),"caNotBeforeMs",UTC-10000,"caNotAfterMs",UTC+10000,"leafNotBeforeMs",UTC-10000,"leafNotAfterMs",UTC+10000,"hostUtcMs",UTC);
      JSONObject binding=obj("sourceCommit",hex('a',40),"sourceTree",hex('b',40),"runNonce",hex('c',32),"caseNonce",hex('d',32),"bootCaseNonce",hex('d',32),"runtimeNonce",hex('e',32),"processNonce",hex('f',32),"challengeNonce",hex('4',32),"expectedCaDerSha256",hex('2',64),"pid",12345,"slot",1);
      state=new GeckoTlsFixtureTrustState(binding,input,()->time,()->until,()->owner);
    }
    JSONObject armed(){return obj("schema",1,"binding",GeckoTlsFixtureTrustState.copy(state.binding),"observerRegistered",true,"nativeEffective",false,"nativeHasUserValue",false,"importEventCount",0);}
    JSONObject proof(){return obj("schema",1,"binding",GeckoTlsFixtureTrustState.copy(state.binding),"importEventCount",1,"importedEventObserved",true,"importTopic","psm:enterprise-certs-imported","importedAtUtcMs",UTC,"nativeEffective",true,"nativeHasUserValue",false,"nativeGetEnterpriseRoots",true,"rootMatches",1,"caDerSha256",hex('2',64),"caNotBeforeMs",UTC-10000,"caNotAfterMs",UTC+10000,"nativeReadUtcMs",UTC+1);}
    void waiting()throws Exception{state.connected();state.armed(armed());time++;state.enabling();time++;}
    void complete()throws Exception{waiting();state.ready(proof());}
  }
  public static void main(String[] args)throws Exception{
    Fixture good=new Fixture();check(!good.state.bootReady(),"no admission before connection");good.state.connected();check(!good.state.bootReady(),"no admission from native port");good.state.armed(good.armed());check(!good.state.bootReady(),"observer and false pref are not trust");good.state.enabling();check(!good.state.bootReady(),"setter return is not trust");good.state.ready(good.proof());check(good.state.bootReady()&&good.state.caseReady(hex('d',32)),"matching completed native import admits owned case");
    rejected("duplicate armed",()->good.state.armed(good.armed()));rejected("duplicate enable",good.state::enabling);rejected("duplicate ACK",()->good.state.ready(good.proof()));
    for(String key:Arrays.asList("sourceCommit","sourceTree","runNonce","caseNonce","bootCaseNonce","runtimeNonce","processNonce","challengeNonce","expectedCaDerSha256")){
      Fixture f=new Fixture();f.waiting();JSONObject p=f.proof();p.getJSONObject("binding").put(key,hex('0',key.startsWith("source")?40:key.equals("expectedCaDerSha256")?64:32));rejected("foreign "+key,()->f.state.ready(p));check(!f.state.bootReady(),"foreign callback cannot open "+key);
    }
    for(String key:Arrays.asList("importedEventObserved","nativeEffective","nativeGetEnterpriseRoots")){
      Fixture f=new Fixture();f.waiting();JSONObject p=f.proof();p.put(key,false);rejected("missing native "+key,()->f.state.ready(p));check(!f.state.bootReady(),"missing proof cannot open "+key);
    }
    for(String key:Arrays.asList("nativeHasUserValue","importEventCount","rootMatches","caDerSha256","importTopic","caNotBeforeMs","caNotAfterMs")){
      Fixture f=new Fixture();f.waiting();JSONObject p=f.proof();p.put(key,key.equals("nativeHasUserValue")?true:key.equals("caDerSha256")?hex('0',64):key.equals("importTopic")?"unrelated-native-topic":2);rejected("invalid "+key,()->f.state.ready(p));check(!f.state.bootReady(),"invalid proof cannot open "+key);
    }
    for(long time:new long[]{121000,121001}){Fixture f=new Fixture();f.waiting();f.time=time;rejected("expired ACK "+time,()->f.state.ready(f.proof()));check(!f.state.bootReady(),"expired cannot open");}
    Fixture owner=new Fixture();owner.waiting();owner.owner=false;rejected("retired runtime/host",()->owner.state.ready(owner.proof()));check(!owner.state.bootReady(),"host swap cannot open");
    Fixture closed=new Fixture();closed.waiting();closed.state.close();rejected("destroyed Activity",()->closed.state.ready(closed.proof()));check(!closed.state.bootReady(),"destroyed cannot open");
    Fixture crossed=new Fixture();crossed.waiting();JSONObject slow=new JSONObject(crossed.proof().toString()){
      @Override public String toString(){String value=super.toString();crossed.time=crossed.until;return value;}
    };rejected("deadline crossed while normalizing receipt",()->crossed.state.ready(slow));check(!crossed.state.bootReady(),"last active check before admission");
    Fixture doubles=new Fixture();doubles.waiting();JSONObject js=doubles.proof();for(String key:Arrays.asList("schema","importEventCount","importedAtUtcMs","rootMatches","caNotBeforeMs","caNotAfterMs","nativeReadUtcMs"))js.put(key,((Number)js.get(key)).doubleValue());js.getJSONObject("binding").put("pid",12345.0).put("slot",1.0);doubles.state.ready(js);check(doubles.state.caseReady(hex('d',32)),"GeckoBundle safe integral Doubles accepted exactly");check(doubles.state.evidence().getJSONObject("nativeReceipt").get("nativeReadUtcMs") instanceof Long,"native integer normalized without truncation");
    for(double number:new double[]{1.5,9007199254740992d,-9007199254740992d,Double.NaN,Double.POSITIVE_INFINITY,Double.NEGATIVE_INFINITY})rejected("unsafe native numeric "+number,()->GeckoTlsFixtureTrustState.numeric(number));
    Fixture live=new Fixture();live.complete();String oldCase=live.state.binding.getString("caseNonce");JSONObject old=live.proof();live.time=2000;live.until=122000;JSONObject request=live.state.resample(hex('5',32));check(live.state.bootReady()&&!live.state.caseReady(hex('5',32)),"resample retains boot trust while withholding its original dispatch");check(request.getString("kind").equals("read")&&live.state.enableCalls==1,"resample never re-enables trust");rejected("old case ACK after rebinding",()->live.state.ready(old));live.state.ready(live.proof());check(live.state.caseReady(hex('5',32))&&!live.state.caseReady(oldCase),"fresh original case challenge admitted");check(live.state.evidence().getLong("importAckAtElapsed")==1002&&live.state.enableCalls==1,"same actual boot event retained");
    live.time=live.until;check(!live.state.caseReady(hex('5',32)),"late pending UI callback cannot dispatch after original deadline");check(live.state.bootReady(),"case deadline does not retire resident runtime trust");
    Fixture failed=new Fixture();failed.waiting();failed.state.fail();rejected("failure cannot recover by another ACK",()->failed.state.ready(failed.proof()));check(!failed.state.bootReady(),"failed stays closed");
    System.out.println(obj("status","passed","checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"scope","Actual integration protocol with counterfeit native callbacks, monotonic clock and owner fault injection only").toString());
  }
}
