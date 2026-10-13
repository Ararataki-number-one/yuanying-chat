package local.pocketchat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;

/** Runs the production immutable model/migration. Android persistence is tested
 * separately: this suite makes no claim about Gecko, WAN or Keystore behavior. */
public final class EnvironmentSpecTest {
  static int checks;
  interface Work{void run()throws Exception;}
  static void check(String message,boolean ok){if(!ok)throw new AssertionError(message);checks++;}
  static void rejects(String message,Work operation)throws Exception{boolean rejected=false;try{operation.run();}catch(IOException|IllegalArgumentException expected){rejected=true;}check(message,rejected);}
  static EnvironmentSpec.Identity id(int slot,int generation){return new EnvironmentSpec.Identity(slot,generation,UUID.randomUUID().toString());}
  static EnvironmentSpec.Configuration change(EnvironmentSpec spec,String key,Object value)throws Exception{JSONObject browser=spec.desired().browser();browser.put(key,value);return new EnvironmentSpec.Configuration(browser,spec.desired().network);}
  static byte[] bytes(JSONObject json){return json.toString().getBytes(StandardCharsets.UTF_8);}
  public static void main(String[] args)throws Exception{
    EnvironmentSpec.Identity identity=id(2,4);
    JSONObject network=J.obj("subscriptionUrl","https://provider.example/sub?token=private-provider-token","exitHost","fixed.example","exitPort",1080,"exitUser","private-user","exitPassword","private-password","entryMode","manual","entry","Tokyo 01");
    EnvironmentSpec initial=EnvironmentSpecMigration.fromLegacy(identity,true,2,"internal",network,"");
    check("Migration retains the stable UUID and generation",initial.identity.equals(identity));
    check("Legacy desktop + strong privacy remains desktop + RFP",initial.desired().browser().optString("display").equals("desktop")&&initial.desired().browser().optString("privacy").equals("native-rfp"));
    check("Migration does not claim runtime application or webpage observation",initial.desiredRevision==1&&initial.appliedRevision==0&&initial.observedRevision==0&&initial.pending());
    check("Manual selection and fixed exit are retained",initial.desired().network.selectionMode.equals("manual")&&!initial.desired().network.exitNodeId.isEmpty());
    String encoded=new String(initial.bytes(),StandardCharsets.UTF_8);
    check("Credential values and token-bearing URLs never enter migrated spec",!encoded.contains("private-user")&&!encoded.contains("private-password")&&!encoded.contains("private-provider-token")&&!encoded.contains("fixed.example"));
    EnvironmentSpec roundtrip=EnvironmentSpec.read(initial.bytes());
    check("Roundtrip retains identity and desired values",roundtrip.identity.equals(identity)&&roundtrip.desired().equals(initial.desired()));
    JSONObject browser=initial.desired().browser();browser.put("display","mobile");
    check("Mutating returned browser JSON cannot mutate a snapshot",initial.desired().browser().optString("display").equals("desktop"));
    JSONObject input=initial.desired().browser();EnvironmentSpec.Configuration immutable=new EnvironmentSpec.Configuration(input,initial.desired().network);input.put("display","mobile");
    check("Mutating input JSON cannot mutate a configuration",immutable.browser().optString("display").equals("desktop"));
    JSONObject reordered=new JSONObject();java.util.List<String> keys=new java.util.ArrayList<>();java.util.Iterator<String> iterator=initial.desired().browser().keys();while(iterator.hasNext())keys.add(iterator.next());java.util.Collections.reverse(keys);for(String key:keys)reordered.put(key,initial.desired().browser().get(key));
    check("JSONObject key order does not create a new desired revision",initial.withDesired(1,new EnvironmentSpec.Configuration(reordered,initial.desired().network))==initial);
    EnvironmentSpec applied=initial.withApplied(1,"GeckoView 157 fixture",100);
    check("Application acknowledgement changes only applied state",applied.appliedRevision==1&&applied.observedRevision==0&&!applied.pending());
    JSONObject observation=J.obj("context","main-world","language","zh-CN");
    EnvironmentSpec observed=applied.withObservation(1,observation,200);observation.put("language","mutated");
    check("Observations are defensive snapshots",observed.observations().optString("language").equals("zh-CN"));
    JSONObject returned=observed.observations();returned.put("language","changed-again");
    check("Returned observations are defensive",observed.observations().optString("language").equals("zh-CN"));
    EnvironmentSpec desired=observed.withDesired(1,change(observed,"display","mobile"));
    check("Saving desired preserves the prior actual applied snapshot",desired.desiredRevision==2&&desired.appliedRevision==1&&desired.applied().browser().optString("display").equals("desktop"));
    check("Prior observations remain clearly associated with applied revision",desired.observedRevision==1&&desired.pending());
    rejects("Stale desired edits fail CAS",()->desired.withDesired(1,change(desired,"display","desktop")));
    rejects("Late application ack cannot claim a newer desired configuration",()->desired.withApplied(1,"GeckoView 157",300));
    EnvironmentSpec applied2=desired.withApplied(2,"GeckoView 157 fixture",300);
    check("Applying a new revision invalidates prior observations",applied2.observedRevision==0&&applied2.observations().length()==0);
    rejects("Old async observation rejected after new apply",()->applied2.withObservation(1,J.obj("late",true),400));
    rejects("Unapplied settings cannot be observed",()->initial.withObservation(0,J.obj("fake",true),400));
    rejects("Empty engine version cannot acknowledge application",()->initial.withApplied(1,"",400));
    rejects("Future schemas rejected",()->{JSONObject bad=initial.json();bad.put("schema",2);EnvironmentSpec.read(bytes(bad));});
    rejects("Revision strings rejected rather than coerced",()->{JSONObject bad=initial.json();bad.put("desiredRevision","1");EnvironmentSpec.read(bytes(bad));});
    rejects("Applied revision newer than desired rejected",()->{JSONObject bad=applied.json();bad.put("appliedRevision",2);EnvironmentSpec.read(bytes(bad));});
    rejects("Observed revision without actual application rejected",()->{JSONObject bad=initial.json();bad.put("observedRevision",1);EnvironmentSpec.read(bytes(bad));});
    rejects("Unapplied state cannot carry engine proof",()->{JSONObject bad=initial.json();bad.put("engineVersion","pretend-applied");EnvironmentSpec.read(bytes(bad));});
    rejects("Unexpected applied JSON rejected",()->{JSONObject bad=initial.json();bad.put("applied",initial.desired().json());EnvironmentSpec.read(bytes(bad));});
    rejects("Applied state without engine acknowledgement rejected",()->{JSONObject bad=applied.json();bad.put("engineVersion","");EnvironmentSpec.read(bytes(bad));});
    rejects("Equal revisions with different configurations rejected",()->{JSONObject bad=applied.json();bad.getJSONObject("applied").getJSONObject("browser").put("display","mobile");EnvironmentSpec.read(bytes(bad));});
    rejects("Cyclic browser input rejected without recursion overflow",()->{JSONObject cyclic=new JSONObject();cyclic.put("cycle",cyclic);new EnvironmentSpec.Configuration(cyclic,initial.desired().network);});
    rejects("Corrupt JSON rejected",()->EnvironmentSpec.read("{bad".getBytes(StandardCharsets.UTF_8)));
    rejects("Malformed UTF-8 rejected rather than replaced",()->EnvironmentSpec.read(new byte[]{'{','"','x','"',':','"',(byte)0xc3,'"','}'}));
    rejects("Trailing garbage rejected",()->EnvironmentSpec.read((encoded+"garbage").getBytes(StandardCharsets.UTF_8)));
    rejects("Oversized file rejected",()->EnvironmentSpec.read(new byte[EnvironmentSpec.MAX_BYTES+1]));
    rejects("Invalid UUID rejected",()->new EnvironmentSpec.Identity(2,4,"not-an-id"));
    rejects("Negative generation rejected",()->new EnvironmentSpec.Identity(2,-1,UUID.randomUUID().toString()));
    rejects("Out of range slot rejected",()->new EnvironmentSpec.Identity(8,0,UUID.randomUUID().toString()));
    for(int slot=0;slot<8;slot++)for(int privacy=0;privacy<3;privacy++){
      EnvironmentSpec migrated=EnvironmentSpecMigration.fromLegacy(id(slot,9),slot%2==0,privacy,"external",new JSONObject(),"socks5://external-user:external-password@host:1080");
      check("Slot/legacy privacy migration "+slot+"/"+privacy,migrated.identity.slot==slot&&migrated.desired().browser().optString("privacy").equals(privacy==0?"compatibility":privacy==1?"standard":"native-rfp"));
      check("External proxy credentials remain outside spec "+slot+"/"+privacy,!new String(migrated.bytes(),StandardCharsets.UTF_8).contains("external-password"));
    }
    network.put("entrySourceId","entry-source-new");network.put("entryNodeId","entry-node-new");network.put("exitSourceId","exit-source-new");network.put("exitNodeId","exit-node-new");network.put("entryConfigRevision","entry-revision-2");network.put("exitConfigRevision","exit-revision-2");network.put("exitCredentialRevision","credential-revision-2");
    EnvironmentSpec linked=EnvironmentSpecMigration.fromLegacy(identity,false,1,"internal",network,"");
    check("Explicit subscribed source/node IDs supersede legacy hashes",linked.desired().network.exitSourceId.equals("exit-source-new")&&linked.desired().network.entryNodeId.equals("entry-node-new"));
    check("Configuration and credential revisions migrate independently",linked.desired().network.entryConfigRevision.equals("entry-revision-2")&&linked.desired().network.exitConfigRevision.equals("exit-revision-2")&&linked.desired().network.credentialRevision.equals("credential-revision-2"));
    check("Same generation with another UUID is a different environment",!identity.equals(new EnvironmentSpec.Identity(identity.slot,identity.generation,UUID.randomUUID().toString())));
    check("Same UUID with another generation is stale",!identity.equals(new EnvironmentSpec.Identity(identity.slot,identity.generation+1,identity.environmentId)));
    System.out.println("{\"passed\":"+checks+",\"scope\":\"production immutable environment model and legacy-settings migration on JVM; Android DB/Keystore/Gecko not covered\"}");
  }
}
