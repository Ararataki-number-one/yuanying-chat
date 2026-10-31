package local.pocketchat;

import java.io.IOException;
import org.json.JSONObject;

/** Live, exact core proof. Persisted JSON is an event receipt, never admission. */
final class NetworkCoreApplication {
  private static volatile NetworkCoreApplication observed;
  static NetworkCoreApplication observed(NativeNetwork network){NetworkCoreApplication value=observed;return value!=null&&value.current(network)?value:null;}
  /** Called by actual startup/verification, never by a share request. */
  static void observeRunning(NativeNetwork n){try{
    EnvironmentSpec model=new EnvironmentSpecRepository(n.context).load();EnvironmentSpec.NetworkBinding actual=EnvironmentSpecRuntime.binding(model.identity,"internal",n.settings,"");
    NetworkCoreApplication previous=observed;long revision=NetworkApplicationReceipt.sameNetwork(model.desired().network,actual)?model.desiredRevision:model.applied()!=null&&NetworkApplicationReceipt.sameNetwork(model.applied().network,actual)?model.appliedRevision:previous!=null&&model.identity.equals(previous.identity)&&NetworkApplicationReceipt.sameNetwork(previous.network,actual)?previous.savedRevision:-1;
    if(revision<0)return;NetworkCoreApplication proof=captureRoute(model.identity,"",revision,NetworkChanges.hash(n.context),n);
    NetworkShareSelection.runningApplied(n.context,proof);
  }catch(Exception unavailable){/* Missing proof stays unknown, never synthesized. */}finally{NetworkUiProvider.sessionAvailable();}}
  final EnvironmentSpec.Identity identity;
  final String candidateId,activeHash,configuration;
  final long savedRevision,verifiedAt;
  final EnvironmentSpec.NetworkBinding network;
  final NativeNetwork.ExitRouteReceipt route;
  private final NativeNetwork nativeNetwork;
  private NetworkCoreApplication(EnvironmentSpec.Identity identity,String candidateId,long revision,String activeHash,NativeNetwork n,EnvironmentSpec.NetworkBinding network,NativeNetwork.ExitRouteReceipt route){
    this.identity=identity;this.candidateId=candidateId;savedRevision=revision;this.activeHash=activeHash;nativeNetwork=n;this.network=network;this.route=route;configuration=route.configuration;verifiedAt=n.lastVerified;
  }
  /** Worker only: actual service IPC must succeed before the proof is created. */
  static NetworkCoreApplication capture(EnvironmentSpec.Identity owner,String candidateId,long revision,String activeHash,NativeNetwork n)throws Exception{
    if(revision<1)throw new IOException("网络核心尚未取得应用回执");return captureRoute(owner,candidateId,revision,activeHash,n);
  }
  static NetworkCoreApplication captureRollback(EnvironmentSpec.Identity owner,long originalRevision,String activeHash,NativeNetwork n)throws Exception{return captureRoute(owner,"",Math.max(0,originalRevision),activeHash,n);}
  private static NetworkCoreApplication captureRoute(EnvironmentSpec.Identity owner,String candidateId,long revision,String activeHash,NativeNetwork n)throws Exception{
    if(n==null||n.settings==null)throw new IOException("网络核心尚未取得应用回执");
    EnvironmentSpecRuntime.requireIdentity(n.context,owner);
    JSONObject active=EnvironmentSpecRepository.strictObject(new SecretStore(n.context).get("network"));
    if(!"internal".equals(n.context.getSharedPreferences("chat",0).getString("networkMode","external"))||!NativeNetwork.transportFingerprint(active).equals(NativeNetwork.transportFingerprint(n.settings)))throw new IOException("当前保存来源与运行线路不同，未生成新回执");
    NativeNetwork.ExitRouteReceipt receipt=n.verifiedRoute;
    if(receipt==null||n.settings==null||!n.authoritySourcesCurrent()||!n.verifiedRouteCurrent()||n.connectionAdmission()!=NetworkHealthPolicy.Admission.VERIFIED||n.starting||n.recoveryBlocked||!receipt.configuration.equals(NativeNetwork.transportFingerprint(n.settings))||!activeHash.equals(NetworkChanges.hash(n.context)))throw new IOException("网络核心的当前线路尚未核验");
    EnvironmentSpec.NetworkBinding actual=EnvironmentSpecRuntime.binding(owner,"internal",n.settings,"");
    NetworkCoreApplication proof=new NetworkCoreApplication(owner,candidateId,revision,activeHash,n,actual,receipt);
    if(!proof.current(n))throw new IOException("网络核心回执已变化");observed=proof;return proof;
  }
  /** Main-actor/share handoff checks only cached core identifiers. Full config
   * and source bytes were checked during capture, never during a scoped share. */
  boolean current(NativeNetwork n){
    return n==nativeNetwork&&n!=null&&n.ready&&!n.starting&&!n.recoveryBlocked&&n.transport!=null&&n.settings!=null&&route==n.verifiedRoute&&n.connectionAdmission()==NetworkHealthPolicy.Admission.VERIFIED&&!configuration.isEmpty()&&configuration.equals(n.transport.state.optString("configuration"))&&route.matches(n,n.transport.state);
  }
  NetworkApplicationReceipt.CoreProof receipt(){return new NetworkApplicationReceipt.CoreProof(identity,candidateId,savedRevision,network,route.generation,verifiedAt);}
  JSONObject json(){return J.obj("schema",1,"environmentId",identity.environmentId,"generation",identity.generation,"slot",identity.slot,"candidateId",candidateId,"networkAppliedRevision",savedRevision,"activeHash",activeHash,"configurationFingerprint",configuration,"coreGeneration",route.generation,"corePid",route.pid,"servicePid",route.servicePid,"routeSerial",route.serial,"verifiedAt",verifiedAt,"scope","core");}
}
