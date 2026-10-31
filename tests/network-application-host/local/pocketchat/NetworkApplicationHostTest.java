package local.pocketchat;
import org.json.*;
public final class NetworkApplicationHostTest {
  static final JSONArray checks=new JSONArray();static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  interface Throwing {void run()throws Exception;}
  static boolean rejected(Throwing action){try{action.run();return false;}catch(Exception expected){return true;}}
  static EnvironmentSpec.NetworkBinding route(String entry,String exit){return new EnvironmentSpec.NetworkBinding("internal","source-entry",entry,"source-exit",exit,"manual","credential-hash","entry-hash","exit-hash");}
  public static void main(String[] args)throws Exception{
    EnvironmentSpec.Identity identity=new EnvironmentSpec.Identity(0,3,"11111111-1111-1111-1111-111111111111");
    JSONObject browser=J.obj("schema",1,"desktop",false,"locales",J.arr("en-US"));
    EnvironmentSpec.Configuration first=new EnvironmentSpec.Configuration(browser,route("a","fixed"));
    EnvironmentSpec model=EnvironmentSpec.initial(identity,first);NetworkApplicationReceipt receipt=NetworkApplicationReceipt.saved(identity,"candidate-a",model,first.network);
    check("Durable desired settings alone cannot confirm application",!receipt.matchesApplied(model,browser,first.network)&&rejected(()->receipt.applied(model,browser,first.network,"applied")));
    JSONObject pending=receipt.pending("saved");check("Pending result keeps candidate identity and saved revision separate",pending.optString("candidateId").equals("candidate-a")&&pending.optLong("savedRevision")==1&&pending.optLong("appliedRevision")==0&&pending.optString("applicationState").equals("pending"));
    EnvironmentSpec applied=model.withApplied(1,"actual-gecko",123);JSONObject result=receipt.applied(applied,browser,first.network,"applied");
    check("Exact existing model acknowledgement and actual configuration confirm this save",receipt.matchesApplied(applied,browser,first.network)&&result.optLong("appliedRevision")==1&&result.optString("applicationState").equals("applied"));
    check("A retained different entry cannot confirm the new candidate",!receipt.matchesApplied(applied,browser,route("old","fixed")));
    check("A different fixed exit cannot confirm the candidate",!receipt.matchesApplied(applied,browser,route("a","other")));
    check("Unaccepted browser policy cannot borrow a network acknowledgement",!receipt.matchesApplied(applied,J.obj("schema",1,"desktop",true),first.network));
    EnvironmentSpec newer=applied.withDesired(1,new EnvironmentSpec.Configuration(browser,route("b","fixed")));NetworkApplicationReceipt second=NetworkApplicationReceipt.saved(identity,"candidate-b",newer,newer.desired().network);
    check("A newer desired candidate retires an old save success",!receipt.matchesApplied(newer,browser,first.network));
    check("Old applied revision cannot satisfy a newer candidate",!second.matchesApplied(newer,browser,newer.desired().network));
    EnvironmentSpec newApplied=newer.withApplied(2,"actual-gecko",456);check("Only the new candidate accepts its exact new application revision",second.matchesApplied(newApplied,browser,newer.desired().network)&&!receipt.matchesApplied(newApplied,browser,newer.desired().network));
    EnvironmentSpec.Identity recreated=new EnvironmentSpec.Identity(0,3,"22222222-2222-2222-2222-222222222222");EnvironmentSpec other=EnvironmentSpec.initial(recreated,first).withApplied(1,"actual-gecko",123);
    check("Reused slot with different stable identity cannot borrow a receipt",!receipt.matchesApplied(other,browser,first.network));
    EnvironmentSpec reset=applied.afterLoginReset(new EnvironmentSpec.Identity(0,4,identity.environmentId));check("A new environment generation retires the old acknowledgement",!receipt.matchesApplied(reset,browser,first.network));
    check("Receipt capture rejects mismatched model identity",rejected(()->NetworkApplicationReceipt.saved(recreated,"candidate",model,first.network)));
    check("Receipt capture rejects a model that mirrors a different candidate",rejected(()->NetworkApplicationReceipt.saved(identity,"candidate",model,route("wrong","fixed"))));
    JSONObject core=receipt.unconfirmed("core","core only"),next=receipt.unconfirmed("next-session","next session");check("A core-only or unopened-session result never claims webpage application",core.optString("applicationState").equals("saved-unconfirmed")&&next.optString("applicationState").equals("saved-unconfirmed")&&core.optLong("appliedRevision")==0&&next.optLong("appliedRevision")==0);
    check("Cancelled candidate is never displayed as still pending",receipt.cancelled("cancelled").optString("applicationState").equals("cancelled")&&receipt.cancelled("cancelled").optLong("appliedRevision")==0);
    JSONObject superseded=receipt.superseded("newer");check("A superseded operation preserves its own candidate and version",superseded.optString("candidateId").equals("candidate-a")&&superseded.optLong("savedRevision")==1&&superseded.optString("saveState").equals("superseded"));
    result.put("candidateId","changed");check("Published JSON cannot mutate the frozen operation receipt",receipt.applied(applied,browser,first.network,"again").optString("candidateId").equals("candidate-a"));
    String publicResult=receipt.pending("saved").toString();check("Public result contains no raw configuration or source payload",!publicResult.contains("credential-hash")&&!publicResult.contains("source-entry")&&!publicResult.contains("locales")&&!publicResult.contains("password")&&!publicResult.contains("proxy"));
    JSONObject failed=NetworkApplicationReceipt.failed(identity,"save failed");check("Failed save has no saved or applied revision",failed.optString("saveState").equals("failed")&&failed.optLong("savedRevision")==0&&failed.optLong("appliedRevision")==0);
    JSONObject savedUnknown=NetworkApplicationReceipt.savedUnconfirmed(identity,"candidate-a","version read failed");check("Failure to read the model after durable save never becomes save failed",savedUnknown.optString("saveState").equals("saved")&&savedUnknown.optString("applicationState").equals("saved-unconfirmed")&&savedUnknown.optLong("savedRevision")==0);
    JSONObject uncertain=NetworkApplicationReceipt.uncertain(identity,"storage uncertain");check("Uncertain durable storage is not mislabeled saved or failed",uncertain.optString("saveState").equals("uncertain")&&uncertain.optBoolean("recoveryRequired")&&uncertain.optLong("appliedRevision")==0);
    JSONObject newerUnknown=NetworkApplicationReceipt.supersededUnknown(identity,"newer");check("A superseded save with unavailable version is still distinct from failed",newerUnknown.optString("saveState").equals("superseded")&&newerUnknown.optLong("savedRevision")==0);
    NetworkApplicationReceipt.CoreProof networkProof=new NetworkApplicationReceipt.CoreProof(identity,"candidate-a",1,first.network,"core-generation-a",123);
    JSONObject networkResult=receipt.appliedNetwork(model,networkProof,"network applied");
    check("A strict network proof can acknowledge the route before any browser exists",networkResult.optString("applicationState").equals("applied")&&networkResult.optString("scope").equals("core")&&networkResult.optLong("networkAppliedRevision")==1);
    check("A cold network proof does not fabricate browser or full environment acknowledgement",networkResult.optLong("appliedRevision")==0&&networkResult.optLong("browserAppliedRevision")==0&&model.appliedRevision==0&&model.engineVersion.isEmpty());
    check("Network proof cannot borrow another candidate",!receipt.matchesNetworkApplied(model,new NetworkApplicationReceipt.CoreProof(identity,"candidate-b",1,first.network,"core-generation-a",123)));
    check("Network proof cannot borrow another environment",!receipt.matchesNetworkApplied(model,new NetworkApplicationReceipt.CoreProof(recreated,"candidate-a",1,first.network,"core-generation-a",123)));
    check("Network proof cannot borrow another desired revision",!receipt.matchesNetworkApplied(newer,networkProof));
    check("Network proof retains exact fixed exit and source parameters",!receipt.matchesNetworkApplied(model,new NetworkApplicationReceipt.CoreProof(identity,"candidate-a",1,route("a","other"),"core-generation-a",123)));
    check("Network proof requires an actual core generation and verification time",!receipt.matchesNetworkApplied(model,new NetworkApplicationReceipt.CoreProof(identity,"candidate-a",1,first.network,"",123))&&!receipt.matchesNetworkApplied(model,new NetworkApplicationReceipt.CoreProof(identity,"candidate-a",1,first.network,"core-generation-a",0)));
    JSONObject restored=receipt.applicationFailed("restored","应用失败，仍使用原线路"),unknown=receipt.applicationFailed("unconfirmed","应用失败，原线路恢复待确认");
    check("Application failure preserves saved candidate and offers retry without claiming applied",restored.optString("saveState").equals("saved")&&restored.optString("applicationState").equals("failed")&&restored.optBoolean("retryAvailable")&&restored.optString("candidateId").equals("candidate-a")&&restored.optLong("appliedRevision")==0);
    check("Unconfirmed rollback cannot claim a healthy original route",unknown.optString("rollbackState").equals("unconfirmed")&&!unknown.optString("message").contains("仍使用原线路"));
    System.out.println(J.obj("status","passed","passed",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualCoreVerification",false,"productionModelAndReceipt",true));
  }
}
