package local.pocketchat;

import java.io.IOException;
import org.json.JSONObject;

/** Frozen, credential-free operation result. EnvironmentSpec remains the authority. */
final class NetworkApplicationReceipt {
  final EnvironmentSpec.Identity identity;
  final String candidateId;
  final long savedRevision;
  final EnvironmentSpec.Configuration saved;
  private NetworkApplicationReceipt(EnvironmentSpec.Identity identity,String candidateId,EnvironmentSpec spec){this.identity=identity;this.candidateId=candidateId;savedRevision=spec.desiredRevision;saved=spec.desired();}
  static boolean sameNetwork(EnvironmentSpec.NetworkBinding left,EnvironmentSpec.NetworkBinding right){return left!=null&&right!=null&&new EnvironmentSpec.Configuration(new JSONObject(),left).equals(new EnvironmentSpec.Configuration(new JSONObject(),right));}
  static NetworkApplicationReceipt saved(EnvironmentSpec.Identity expected,String candidateId,EnvironmentSpec spec,EnvironmentSpec.NetworkBinding candidate)throws IOException{
    if(expected==null||spec==null||!expected.equals(spec.identity)||candidateId==null||!candidateId.matches("[a-z0-9:-]{1,96}")||!sameNetwork(spec.desired().network,candidate))throw new IOException("保存结果已变化，请重新读取网络设置");
    return new NetworkApplicationReceipt(expected,candidateId,spec);
  }
  /** Caller supplies a freshly verified route and the accepted Gecko policy;
   * these model comparisons never turn a cached ready flag into admission. */
  boolean matchesApplied(EnvironmentSpec current,JSONObject acceptedBrowser,EnvironmentSpec.NetworkBinding actual){
    return current!=null&&identity.equals(current.identity)&&current.desiredRevision==savedRevision&&current.appliedRevision==savedRevision&&saved.equals(current.desired())&&saved.equals(current.applied())&&acceptedBrowser!=null&&actual!=null&&saved.equals(new EnvironmentSpec.Configuration(acceptedBrowser,actual));
  }
  JSONObject applied(EnvironmentSpec current,JSONObject acceptedBrowser,EnvironmentSpec.NetworkBinding actual,String message)throws IOException{
    if(!matchesApplied(current,acceptedBrowser,actual))throw new IOException("此候选尚未取得对应版本的实际应用回执");
    return result("saved","applied","session",current.appliedRevision,message);
  }
  JSONObject cancelled(String message){return result("saved","cancelled","session",0,message);}
  JSONObject pending(String message){return result("saved","pending","session",0,message);}
  JSONObject unconfirmed(String scope,String message){if(!"session".equals(scope)&&!"core".equals(scope)&&!"next-session".equals(scope))throw new IllegalArgumentException("Invalid application scope");return result("saved","saved-unconfirmed",scope,0,message);}
  JSONObject superseded(String message){return result("superseded","superseded","session",0,message);}
  private JSONObject result(String save,String application,String scope,long applied,String message){return J.obj("environmentId",identity.environmentId,"generation",identity.generation,"candidateId",candidateId,"savedRevision",savedRevision,"appliedRevision",applied,"saveState",save,"applicationState",application,"scope",scope,"message",message);}
  static JSONObject savedUnconfirmed(EnvironmentSpec.Identity identity,String candidateId,String message){return J.obj("environmentId",identity.environmentId,"generation",identity.generation,"candidateId",candidateId,"savedRevision",0,"appliedRevision",0,"saveState","saved","applicationState","saved-unconfirmed","scope","session","message",message);}
  static JSONObject supersededUnknown(EnvironmentSpec.Identity identity,String message){return J.obj("environmentId",identity.environmentId,"generation",identity.generation,"candidateId","","savedRevision",0,"appliedRevision",0,"saveState","superseded","applicationState","superseded","scope","session","message",message);}
  static JSONObject uncertain(EnvironmentSpec.Identity identity,String message){return J.obj("environmentId",identity.environmentId,"generation",identity.generation,"candidateId","","savedRevision",0,"appliedRevision",0,"saveState","uncertain","applicationState","unconfirmed","scope","session","message",message,"recoveryRequired",true);}
  static JSONObject failed(EnvironmentSpec.Identity identity,String message){return J.obj("environmentId",identity==null?"":identity.environmentId,"generation",identity==null?-1:identity.generation,"candidateId","","savedRevision",0,"appliedRevision",0,"saveState","failed","applicationState","saved-unconfirmed","scope","session","message",message);}
}
