package local.pocketchat;

import android.content.Context;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.*;

/** Real TZDB, filesystem, file locks and processes; native ACK inputs are synthetic. */
public final class GeckoTimeZoneHost {
  static final String ID="00000000-0000-0000-0000-000000000002",OTHER="00000000-0000-0000-0000-000000000003";
  static final List<String> checks=new ArrayList<>();static Path root;
  interface Checked {void run()throws Exception;}
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static void rejects(String name,Checked action)throws Exception{boolean failed=false;try{action.run();}catch(Exception expected){failed=true;}check(name,failed);}
  static TestContext context(String name)throws Exception{return new TestContext(root.resolve(name),new EnvironmentSpec.Identity(2,4,ID));}
  static GeckoTimeZoneStore.Binding binding(){return new GeckoTimeZoneStore.Binding("157.0-real-host-boundary","actual_session_id_0123456789abcdef","session_epoch_0123456789abcdef","123");}
  static JSONObject ack(GeckoTimeZoneStore.Ticket ticket,GeckoTimeZoneSpec spec){return J.obj("schema",1,"status","applied","requestToken",ticket.requestToken,
      "requestedZoneId",spec.zoneId,"nativeZoneId",spec.zoneId,"sessionId",ticket.binding.sessionId,"contextId",ticket.binding.contextId,"nativeSettingReadback",true,"scope","top-browsing-context","workerCoverageVerified",false,"serviceWorkerCoverageVerified",false);}
  static byte[] raw(TestContext c)throws Exception{return new SecretStore(c).get(GeckoTimeZoneStore.STORE);}
  static JSONObject rawObject(TestContext c)throws Exception{return new JSONObject(new String(raw(c),StandardCharsets.UTF_8));}
  static void rawWrite(TestContext c,byte[] value)throws Exception{Files.write(new SecretStore(c).file(GeckoTimeZoneStore.STORE),value);}
  static void unchanged(String name,TestContext c,byte[] before)throws Exception{check(name,Arrays.equals(before,raw(c)));}

  static void specifications()throws Exception{
    GeckoTimeZoneSpec system=GeckoTimeZoneSpec.system(),utc=GeckoTimeZoneSpec.of("UTC");
    check("Legacy system selection is an empty override, not today's resolved phone timezone",system.followsSystem()&&system.json().getString("zoneId").isEmpty());
    check("New IP default is distinct from an explicitly selected system override",GeckoTimeZoneSpec.automatic().followsIp()&&!GeckoTimeZoneSpec.automatic().equals(system));
    check("Schema1 empty choice migrates conservatively as manual system",GeckoTimeZoneSpec.from(J.obj("schema",1,"engine","gecko","zoneId","")).followsSystem());
    check("Schema1 IANA choice stays manual and keeps its original zone",GeckoTimeZoneSpec.from(J.obj("schema",1,"engine","gecko","zoneId","Asia/Kathmandu")).equals(GeckoTimeZoneSpec.of("Asia/Kathmandu")));
    check("Only system default can continue without native override capability",GeckoTimeZonePolicy.legacySystemMayContinue(system)&&!GeckoTimeZonePolicy.legacySystemMayContinue(utc));
    check("UTC is an explicit named zero-offset setting",utc.offsetAt(Instant.parse("2026-07-01T12:00:00Z")).getTotalSeconds()==0&&!utc.followsSystem());
    GeckoTimeZoneSpec ny=GeckoTimeZoneSpec.of("America/New_York"),howe=GeckoTimeZoneSpec.of("Australia/Lord_Howe"),kathmandu=GeckoTimeZoneSpec.of("Asia/Kathmandu");
    check("IANA timezone keeps real winter and summer DST rules",ny.offsetAt(Instant.parse("2026-01-01T12:00:00Z")).getTotalSeconds()==-18000&&ny.offsetAt(Instant.parse("2026-07-01T12:00:00Z")).getTotalSeconds()==-14400);
    check("Half-hour DST is preserved instead of a whole-hour spoof",howe.offsetAt(Instant.parse("2026-01-01T12:00:00Z")).getTotalSeconds()==39600&&howe.offsetAt(Instant.parse("2026-07-01T12:00:00Z")).getTotalSeconds()==37800);
    check("Quarter-hour timezone is preserved",kathmandu.offsetAt(Instant.parse("2026-07-01T12:00:00Z")).getTotalSeconds()==20700);
    check("Historical IANA rule transitions are retained",GeckoTimeZoneSpec.of("Europe/Moscow").offsetAt(Instant.parse("2012-01-01T12:00:00Z")).getTotalSeconds()==14400&&GeckoTimeZoneSpec.of("Europe/Moscow").offsetAt(Instant.parse("2026-01-01T12:00:00Z")).getTotalSeconds()==10800);
    check("RFP custom-zone conflict never silently weakens protection",GeckoTimeZonePolicy.protectionConflict(2,ny)&&GeckoTimeZonePolicy.protectionConflict(2,utc)&&!GeckoTimeZonePolicy.protectionConflict(2,system)&&!GeckoTimeZonePolicy.protectionConflict(1,ny));
    for(String invalid:new String[]{null," UTC","UTC ","UTC+08:00","+08:00","GMT+08:00","Asia/shanghai","Missing/City","Europe/../London","Asia/Shanghai\0"})rejects("Invalid or synthetic timezone rejected "+String.valueOf(invalid),()->GeckoTimeZoneSpec.of(invalid));
    check("Spec round trip is immutable and exact",GeckoTimeZoneSpec.from(ny.json()).equals(ny));
    JSONObject modified=ny.json();modified.put("zoneId","UTC");check("Caller JSON cannot mutate saved spec",ny.zoneId.equals("America/New_York"));
    for(JSONObject invalid:new JSONObject[]{J.obj("schema",2,"engine","gecko","zoneId","UTC"),J.obj("schema",true,"engine","gecko","zoneId","UTC"),J.obj("schema",1,"engine","chromium","zoneId","UTC"),J.obj("schema",1,"engine","gecko","zoneId",0),J.obj("schema",1,"engine","gecko","zoneId","UTC","appliedRevision",99)})rejects("Unknown/old/mixed schema is not accepted as timezone configuration",()->GeckoTimeZoneSpec.from(invalid));
    for(String bad:new String[]{"0","01","-1","1234567890123456789012345","abc"})rejects("Native context binding rejects invalid decimal ID "+bad,()->new GeckoTimeZoneStore.Binding("157","actual_session_id_001","session_epoch_0123456789",bad));
    check("Native context IDs stay strings without double rounding",GeckoTimeZonePolicy.validContext("18446744073709551615"));
  }

  static void policy()throws Exception{
    TestContext c=context("policy");GeckoTimeZoneStore.State fresh=GeckoTimeZoneStore.load(c),state=GeckoTimeZoneStore.save(c,fresh.identity,fresh.revision,GeckoTimeZoneSpec.system());GeckoTimeZoneStore.Ticket ticket=GeckoTimeZoneStore.activate(c,state.identity,state.revision,binding());
    JSONObject nativeAck=ack(ticket,state.spec);
    check("Exact synthetic native readback retains separate observation scope",GeckoTimeZonePolicy.nativeReadback(nativeAck.toString(),state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId).getBoolean("nativeSettingReadback"));
    JSONObject read=new JSONObject(nativeAck.toString());read.put("status","read");check("Read-only native setting ACK can confirm exact current value",GeckoTimeZonePolicy.nativeReadback(read.toString(),state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId).getString("status").equals("read"));
    JSONObject previousZone=new JSONObject(read.toString());previousZone.put("requestedZoneId","Asia/Tokyo").put("nativeZoneId","Asia/Tokyo");
    check("Bootstrap read only identifies actual session context, never invents desired-zone readiness",GeckoTimeZonePolicy.contextReadback(previousZone.toString(),ticket.requestToken,ticket.binding.sessionId).getString("contextId").equals("123"));
    rejects("Bootstrap existing value cannot replace exact desired apply acknowledgement",()->GeckoTimeZonePolicy.nativeReadback(previousZone.toString(),state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId));
    Object[][] changes={{"schema",2},{"schema",true},{"status","unsupported"},{"status","failed"},{"status","page-observed"},{"requestToken",new String(new char[64]).replace('\0','f')},{"requestedZoneId","UTC"},{"nativeZoneId","UTC"},{"sessionId","foreign_native_session"},{"contextId","124"},{"contextId",123},{"nativeSettingReadback",false},{"scope","all-workers"},{"workerCoverageVerified",true},{"serviceWorkerCoverageVerified",true}};
    for(Object[] change:changes){JSONObject copy=new JSONObject(nativeAck.toString());copy.put((String)change[0],change[1]);rejects("Foreign/unsupported/overclaimed native ACK rejected: "+change[0]+"="+change[1],()->GeckoTimeZonePolicy.nativeReadback(copy.toString(),state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId));}
    for(String field:new String[]{"requestToken","sessionId","contextId","workerCoverageVerified","serviceWorkerCoverageVerified"}){JSONObject copy=new JSONObject(nativeAck.toString());copy.remove(field);rejects("Missing native ACK field rejected: "+field,()->GeckoTimeZonePolicy.nativeReadback(copy.toString(),state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId));}
    String duplicate="{\"schema\":1,"+nativeAck.toString().substring(1);
    rejects("Duplicate raw ACK key rejected with both JSON libraries",()->GeckoTimeZonePolicy.nativeReadback(duplicate,state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId));
    rejects("Oversize raw ACK rejected before encoding/parsing",()->GeckoTimeZonePolicy.nativeReadback(new String(new char[GeckoTimeZonePolicy.ACK_BYTES+1]),state.spec,ticket.requestToken,ticket.binding.sessionId,ticket.binding.contextId));
    rejects("Invalid UTF8 record rejected",()->GeckoTimeZonePolicy.object(new byte[]{(byte)255},100));
  }

  static void independentSessions()throws Exception{
    TestContext c=context("independent-sessions");GeckoTimeZoneStore.State freshDefault=GeckoTimeZoneStore.load(c),state=GeckoTimeZoneStore.save(c,freshDefault.identity,freshDefault.revision,GeckoTimeZoneSpec.system());
    GeckoTimeZoneStore.Ticket primary=GeckoTimeZoneStore.activate(c,state.identity,state.revision,binding());GeckoTimeZoneStore.record(c,primary,ack(primary,state.spec).toString());
    GeckoTimeZoneStore.Binding auxBinding=new GeckoTimeZoneStore.Binding("157","aux_native_session","aux_open_epoch","456");
    GeckoTimeZoneStore.Ticket aux=GeckoTimeZoneStore.activate(c,state.identity,state.revision,auxBinding);
    check("A second native session has no borrowed primary receipt",GeckoTimeZoneStore.lastReceipt(c,aux).length()==0&&GeckoTimeZoneStore.lastReceipt(c,primary).length()>0);
    GeckoTimeZoneStore.record(c,aux,ack(aux,state.spec).toString());
    check("Independent native sessions retain their own exact receipts",GeckoTimeZoneStore.lastReceipt(c,primary).getJSONObject("binding").getString("sessionId").equals(binding().sessionId)&&GeckoTimeZoneStore.lastReceipt(c,aux).getJSONObject("binding").getString("sessionId").equals(auxBinding.sessionId));
    GeckoTimeZoneStore.Ticket reopened=GeckoTimeZoneStore.activate(c,state.identity,state.revision,new GeckoTimeZoneStore.Binding("157",binding().sessionId,"reopened_epoch","789"));
    check("Reopening one session retires its acknowledgement without retiring unrelated session",GeckoTimeZoneStore.lastReceipt(c,primary).length()==0&&GeckoTimeZoneStore.lastReceipt(c,reopened).length()==0&&GeckoTimeZoneStore.lastReceipt(c,aux).length()>0);
    rejects("Late ACK from same-ID previous native open is rejected",()->GeckoTimeZoneStore.record(c,primary,ack(primary,state.spec).toString()));
    GeckoTimeZoneStore.retire(c,primary);GeckoTimeZoneStore.record(c,reopened,ack(reopened,state.spec).toString());
    check("Late old-open retirement cannot revoke new-open receipt",GeckoTimeZoneStore.lastReceipt(c,reopened).length()>0);
    GeckoTimeZoneStore.retire(c,aux);check("Closing auxiliary context leaves primary verified",GeckoTimeZoneStore.lastReceipt(c,reopened).length()>0&&GeckoTimeZoneStore.lastReceipt(c,aux).length()==0);
    for(int i=0;i<31;i++)GeckoTimeZoneStore.activate(c,state.identity,state.revision,new GeckoTimeZoneStore.Binding("157","bounded_session_"+i,"bounded_epoch_"+i,String.valueOf(i+1)));
    rejects("Live session ticket map has an explicit bound",()->GeckoTimeZoneStore.activate(c,state.identity,state.revision,new GeckoTimeZoneStore.Binding("157","overflow_session","overflow_epoch","999")));
    GeckoTimeZoneStore.Ticket replacement=GeckoTimeZoneStore.activate(c,state.identity,state.revision,new GeckoTimeZoneStore.Binding("157",binding().sessionId,"last_reopen","790"));
    check("Replacing own session at capacity remains possible without stale receipt",GeckoTimeZoneStore.lastReceipt(c,replacement).length()==0);
    GeckoTimeZoneStore.State changed=GeckoTimeZoneStore.save(c,state.identity,state.revision,GeckoTimeZoneSpec.of("UTC"));
    rejects("New desired revision revokes every old live session token",()->GeckoTimeZoneStore.record(c,replacement,ack(replacement,state.spec).toString()));
    GeckoTimeZoneStore.Ticket fresh=GeckoTimeZoneStore.activate(c,changed.identity,changed.revision,new GeckoTimeZoneStore.Binding("157","fresh_session","fresh_epoch","800"));
    check("Revision change releases bounded session registry",GeckoTimeZoneStore.lastReceipt(c,fresh).length()==0);
  }

  static void storage()throws Exception{
    TestContext c=context("storage");Files.write(c.directory.resolve("environment-spec.host-vault"),new byte[]{9,8,7});
    GeckoTimeZoneStore.State initial=GeckoTimeZoneStore.load(c);check("Missing sidecar defaults to exit-IP policy/revision1",initial.revision==1&&initial.spec.followsIp()&&initial.identity.equals(c.catalog.current));
    check("Independent timezone sidecar does not rewrite existing environment schema",Arrays.equals(Files.readAllBytes(c.directory.resolve("environment-spec.host-vault")),new byte[]{9,8,7}));
    long writes=c.vault.writes;GeckoTimeZoneStore.State same=GeckoTimeZoneStore.save(c,initial.identity,initial.revision,initial.spec);check("Unchanged save is stable without a new revision or write",same.revision==1&&c.vault.writes==writes);
    GeckoTimeZoneStore.State tokyo=GeckoTimeZoneStore.save(c,initial.identity,1,GeckoTimeZoneSpec.of("Asia/Tokyo"));check("Desired timezone save has independent monotonic revision",tokyo.revision==2&&tokyo.spec.zoneId.equals("Asia/Tokyo")&&rawObject(c).getJSONObject("receipt").length()==0);
    rejects("Stale revision cannot overwrite a newer zone",()->GeckoTimeZoneStore.save(c,initial.identity,1,GeckoTimeZoneSpec.of("UTC")));
    GeckoTimeZoneStore.Ticket first=GeckoTimeZoneStore.activate(c,tokyo.identity,2,binding());check("Native activation alone never invents a receipt",GeckoTimeZoneStore.lastReceipt(c,first).length()==0);
    JSONObject receipt=GeckoTimeZoneStore.record(c,first,ack(first,tokyo.spec).toString());
    check("Native acknowledgement binds identity/revision/session/context/token",receipt.getJSONObject("identity").getString("environmentId").equals(ID)&&receipt.getLong("desiredRevision")==2&&receipt.getJSONObject("binding").getString("contextId").equals("123")&&receipt.getString("requestToken").equals(first.requestToken));
    check("Native setting acknowledgement cannot attest page or worker coverage",receipt.getBoolean("nativeSettingReadback")&&!receipt.getBoolean("pageObservationVerified")&&!receipt.getBoolean("workerCoverageVerified")&&!receipt.getBoolean("serviceWorkerCoverageVerified"));
    receipt.getJSONObject("nativeReceipt").put("nativeZoneId","UTC");check("Returned receipt cannot mutate durable/current state",GeckoTimeZoneStore.lastReceipt(c,first).getJSONObject("nativeReceipt").getString("nativeZoneId").equals("Asia/Tokyo"));
    GeckoTimeZoneStore.Ticket second=GeckoTimeZoneStore.activate(c,tokyo.identity,2,binding());check("Identical session reactivation revokes previous native token",!second.requestToken.equals(first.requestToken)&&GeckoTimeZoneStore.lastReceipt(c,second).length()==0);
    rejects("Late previous ACK cannot become current",()->GeckoTimeZoneStore.record(c,first,ack(first,tokyo.spec).toString()));
    GeckoTimeZoneStore.retire(c,first);GeckoTimeZoneStore.record(c,second,ack(second,tokyo.spec).toString());check("Retiring old request cannot revoke newer owner",GeckoTimeZoneStore.lastReceipt(c,second).length()>0);
    byte[] before=raw(c);c.vault.failPut=true;
    rejects("Failed desired save surfaces its publication failure",()->GeckoTimeZoneStore.save(c,tokyo.identity,2,GeckoTimeZoneSpec.of("UTC")));unchanged("Failed save preserves exact durable zone/receipt",c,before);check("Failed save does not revoke currently accepted setting",GeckoTimeZoneStore.lastReceipt(c,second).length()>0);
    GeckoTimeZoneStore.State utc=GeckoTimeZoneStore.save(c,tokyo.identity,2,GeckoTimeZoneSpec.of("UTC"));check("Changed desired configuration clears old durable receipt",utc.revision==3&&rawObject(c).getJSONObject("receipt").length()==0);
    rejects("Old-revision ACK cannot satisfy newly saved timezone",()->GeckoTimeZoneStore.record(c,second,ack(second,tokyo.spec).toString()));
    GeckoTimeZoneStore.Ticket current=GeckoTimeZoneStore.activate(c,utc.identity,3,new GeckoTimeZoneStore.Binding("157","different_native_session_001","different_session_epoch_001","124"));
    before=raw(c);c.vault.failPut=true;rejects("Failed native receipt publication is not current",()->GeckoTimeZoneStore.record(c,current,ack(current,utc.spec).toString()));unchanged("Receipt publication failure preserves old bytes",c,before);check("No unpersisted native ACK is reported current",GeckoTimeZoneStore.lastReceipt(c,current).length()==0);
    GeckoTimeZoneStore.record(c,current,ack(current,utc.spec).toString());GeckoTimeZoneStore.retire(c,current);
    check("Closing native context retires its acknowledgement",GeckoTimeZoneStore.lastReceipt(c,current).length()==0);rejects("Retired native callback cannot recreate acknowledgement",()->GeckoTimeZoneStore.record(c,current,ack(current,utc.spec).toString()));
    before=raw(c);c.vault.failRead=true;rejects("Read/decrypt failure does not silently reset to system",()->GeckoTimeZoneStore.load(c));c.vault.failRead=false;unchanged("Read failure retains original sealed boundary bytes",c,before);
  }

  static void generations()throws Exception{
    TestContext c=context("generations");GeckoTimeZoneStore.State before=GeckoTimeZoneStore.load(c),saved=GeckoTimeZoneStore.save(c,before.identity,1,GeckoTimeZoneSpec.of("Europe/London"));GeckoTimeZoneStore.Ticket old=GeckoTimeZoneStore.activate(c,saved.identity,saved.revision,binding());GeckoTimeZoneStore.record(c,old,ack(old,saved.spec).toString());
    c.catalog.current=new EnvironmentSpec.Identity(2,5,ID);GeckoTimeZoneStore.State rebound=GeckoTimeZoneStore.load(c);
    check("Reset generation keeps desired named timezone but never old native ACK",rebound.identity.generation==5&&rebound.spec.equals(saved.spec)&&rebound.revision==saved.revision&&rawObject(c).getJSONObject("receipt").length()==0);
    rejects("Old environment generation cannot save or record",()->GeckoTimeZoneStore.record(c,old,ack(old,saved.spec).toString()));
    c.catalog.current=new EnvironmentSpec.Identity(2,0,OTHER);GeckoTimeZoneStore.State reused=GeckoTimeZoneStore.load(c);
    check("Slot reuse never copies a deleted owner's timezone",reused.identity.environmentId.equals(OTHER)&&reused.revision==1&&reused.spec.followsIp());
    rejects("Old UUID cannot save into reused slot",()->GeckoTimeZoneStore.save(c,saved.identity,saved.revision,GeckoTimeZoneSpec.of("UTC")));
    JSONObject future=rawObject(c);future.getJSONObject("identity").put("generation",99);rawWrite(c,future.toString().getBytes(StandardCharsets.UTF_8));byte[] raw=raw(c);
    rejects("Future-generation record is preserved instead of migrated backwards",()->GeckoTimeZoneStore.load(c));unchanged("Future generation bytes unchanged",c,raw);
  }

  static void malformed()throws Exception{
    TestContext c=context("malformed");GeckoTimeZoneStore.load(c);byte[] valid=raw(c);
    List<byte[]> invalid=new ArrayList<>();invalid.add(new byte[]{(byte)255});invalid.add("{}{}".getBytes(StandardCharsets.UTF_8));invalid.add(Arrays.copyOf(valid,valid.length-3));invalid.add(("{\"schema\":1,"+new String(valid,StandardCharsets.UTF_8).substring(1)).getBytes(StandardCharsets.UTF_8));
    for(String field:new String[]{"schema","engine","revision","spec","identity","receipt"}){JSONObject value=new JSONObject(new String(valid,StandardCharsets.UTF_8));value.remove(field);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));}
    JSONObject value=new JSONObject(new String(valid,StandardCharsets.UTF_8));value.put("revision",true);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(valid,StandardCharsets.UTF_8));value.put("schema",2);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(valid,StandardCharsets.UTF_8));value.getJSONObject("identity").put("slot",1);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));
    value=new JSONObject(new String(valid,StandardCharsets.UTF_8));value.put("appliedRevision",999);invalid.add(value.toString().getBytes(StandardCharsets.UTF_8));invalid.add(new byte[GeckoTimeZoneStore.MAX_BYTES+1]);
    int i=0;for(byte[] bad:invalid){rawWrite(c,bad);rejects("Malformed sidecar rejected "+i,()->GeckoTimeZoneStore.load(c));unchanged("Malformed sidecar never overwritten "+i,c,bad);i++;}rawWrite(c,valid);
  }

  static void concurrency()throws Exception{
    TestContext c=context("concurrent");GeckoTimeZoneStore.State before=GeckoTimeZoneStore.load(c);AtomicInteger wins=new AtomicInteger(),conflicts=new AtomicInteger();ExecutorService workers=Executors.newFixedThreadPool(2);CountDownLatch start=new CountDownLatch(1);
    try{List<Future<?>> futures=new ArrayList<>();for(String zone:new String[]{"UTC","Asia/Tokyo"})futures.add(workers.submit(()->{try{start.await();GeckoTimeZoneStore.save(c,before.identity,1,GeckoTimeZoneSpec.of(zone));wins.incrementAndGet();}catch(Exception expected){conflicts.incrementAndGet();}}));start.countDown();for(Future<?> future:futures)future.get(5,TimeUnit.SECONDS);}finally{workers.shutdownNow();}
    check("Concurrent same-revision saves have exactly one CAS winner",wins.get()==1&&conflicts.get()==1&&GeckoTimeZoneStore.load(c).revision==2);
    TestContext held=context("catalog-barrier");GeckoTimeZoneStore.State initial=GeckoTimeZoneStore.load(held);CountDownLatch publicationEntered=new CountDownLatch(1),publicationRelease=new CountDownLatch(1);held.vault.entered=publicationEntered;held.vault.release=publicationRelease;CountDownLatch identityAttempted=new CountDownLatch(1),identityChanged=new CountDownLatch(1);ExecutorService race=Executors.newFixedThreadPool(2);
    try{Future<?> save=race.submit(()->{try{GeckoTimeZoneStore.save(held,initial.identity,1,GeckoTimeZoneSpec.of("UTC"));}catch(Exception e){throw new RuntimeException(e);}});check("Actual save reaches controlled vault publication while holding identity gate",publicationEntered.await(3,TimeUnit.SECONDS));
      Future<?> change=race.submit(()->{identityAttempted.countDown();synchronized(held.catalog.gate){held.catalog.current=new EnvironmentSpec.Identity(2,0,OTHER);identityChanged.countDown();}});check("Identity replacement caller actually reached held gate",identityAttempted.await(3,TimeUnit.SECONDS));check("Delete/reuse cannot cross an active protected save",!identityChanged.await(50,TimeUnit.MILLISECONDS));held.vault.release.countDown();save.get(3,TimeUnit.SECONDS);change.get(3,TimeUnit.SECONDS);check("New owner starts the exit-IP default after the old save completes",GeckoTimeZoneStore.load(held).spec.followsIp());
    }finally{held.vault.release.countDown();race.shutdownNow();}
  }

  static void restart(String phase)throws Exception{
    TestContext c=context("restart");
    if(phase.equals("restart-seed")){
      GeckoTimeZoneStore.State initial=GeckoTimeZoneStore.load(c),saved=GeckoTimeZoneStore.save(c,initial.identity,1,GeckoTimeZoneSpec.of("Asia/Tokyo"));GeckoTimeZoneStore.Ticket ticket=GeckoTimeZoneStore.activate(c,saved.identity,saved.revision,binding());JSONObject receipt=GeckoTimeZoneStore.record(c,ticket,ack(ticket,saved.spec).toString());
      Files.write(root.resolve("restart-oracle.json"),J.obj("processNonce",receipt.getString("processNonce"),"requestToken",ticket.requestToken).toString().getBytes(StandardCharsets.UTF_8));check("First JVM stores actual synthetic native-setting receipt",GeckoTimeZoneStore.lastReceipt(c,ticket).length()>0);
    }else{
      JSONObject oracle=new JSONObject(new String(Files.readAllBytes(root.resolve("restart-oracle.json")),StandardCharsets.UTF_8));GeckoTimeZoneStore.State saved=GeckoTimeZoneStore.load(c);check("Fresh JVM keeps desired timezone and revision",saved.revision==2&&saved.spec.zoneId.equals("Asia/Tokyo"));
      GeckoTimeZoneStore.Ticket fresh=GeckoTimeZoneStore.activate(c,saved.identity,saved.revision,binding());check("Same native binding after process restart cannot revive old receipt",GeckoTimeZoneStore.lastReceipt(c,fresh).length()==0&&!fresh.requestToken.equals(oracle.getString("requestToken")));
      JSONObject actual=GeckoTimeZoneStore.record(c,fresh,ack(fresh,saved.spec).toString());check("Fresh process ACK has independent process nonce",!actual.getString("processNonce").equals(oracle.getString("processNonce")));
    }
  }
  static void processRace(String phase,String label)throws Exception{
    TestContext c=context("process-race");
    if(phase.equals("race-seed")){GeckoTimeZoneStore.load(c);check("Cross-process fixture begins at independent revision1",true);}
    else if(phase.equals("race-write")){
      boolean won=false;try{GeckoTimeZoneStore.save(c,new EnvironmentSpec.Identity(2,4,ID),1,GeckoTimeZoneSpec.of(label.equals("A")?"UTC":"Asia/Tokyo"));won=true;}catch(IOException expected){}
      Files.write(root.resolve("race-"+label+".json"),J.obj("won",won).toString().getBytes(StandardCharsets.UTF_8));check("Cross-process caller completed without overwriting newer revision",true);
    }else{
      boolean a=new JSONObject(new String(Files.readAllBytes(root.resolve("race-A.json")),StandardCharsets.UTF_8)).getBoolean("won"),b=new JSONObject(new String(Files.readAllBytes(root.resolve("race-B.json")),StandardCharsets.UTF_8)).getBoolean("won");
      check("Real JVM file lock permits one CAS winner across independent processes",a!=b&&GeckoTimeZoneStore.load(c).revision==2);
    }
  }
  public static void main(String[] args)throws Exception{root=Paths.get(args[1]);Files.createDirectories(root);String phase=args[0];if(phase.equals("main")){specifications();policy();storage();independentSessions();generations();malformed();concurrency();}else if(phase.startsWith("restart"))restart(phase);else processRace(phase,args.length>2?args[2]:"");System.out.println(J.obj("status","passed","phase",phase,"passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks)));}
}

final class TestContext extends Context {
  final Path directory;final ProfileCatalog catalog;final VaultFaults vault=new VaultFaults();
  TestContext(Path directory,EnvironmentSpec.Identity identity)throws Exception{this.directory=directory;Files.createDirectories(directory);catalog=new ProfileCatalog(identity);}
  @Override public Context getApplicationContext(){return this;}@Override public File getNoBackupFilesDir(){return directory.toFile();}
}
final class VaultFaults {boolean failPut,failRead;long writes;CountDownLatch entered,release;}
final class Profiles {static int slot(Context context){return ((TestContext)context).catalog.current.slot;}}
final class ProfileCatalog {
  volatile EnvironmentSpec.Identity current;final Object gate=new Object();ProfileCatalog(EnvironmentSpec.Identity current){this.current=current;}
  static ProfileCatalog get(Context context){return ((TestContext)context).catalog;}
  EnvironmentSpec.Identity identity(int slot)throws IOException{if(current.slot!=slot)throw new IOException("Wrong slot");return current;}
  interface IdentityAction<T>{T run()throws Exception;}
  <T>T withIdentity(EnvironmentSpec.Identity expected,IdentityAction<T> action)throws Exception{synchronized(gate){if(!current.equals(expected))throw new IOException("Identity changed");return action.run();}}
}
final class SecretStore {
  final TestContext context;SecretStore(Context context){this.context=(TestContext)context;}
  Path file(String name){if(!name.matches("[a-z-]+"))throw new IllegalArgumentException();return context.directory.resolve(name+".host-vault");}
  byte[] get(String name)throws IOException{if(context.vault.failRead)throw new IOException("Injected read/decrypt boundary failure");return Files.exists(file(name))?Files.readAllBytes(file(name)):null;}
  void put(String name,byte[] value)throws Exception{
    context.vault.writes++;if(context.vault.failPut){context.vault.failPut=false;throw new IOException("Injected atomic prepublication failure");}
    CountDownLatch entered=context.vault.entered,release=context.vault.release;
    if(entered!=null&&release!=null){context.vault.entered=null;entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("Fixture barrier timed out");}
    Path temp=Files.createTempFile(context.directory,"timezone-vault-",".tmp");try{Files.write(temp,value);Files.move(temp,file(name),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}finally{Files.deleteIfExists(temp);}
  }
}
