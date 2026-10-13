package local.pocketchat;

/** Regression cases for detector outages, stale routes and repeated corroborated failures. */
public final class NetworkHealthPolicyTest {
  static int checks;
  static void check(String name,boolean result){if(!result)throw new AssertionError(name);checks++;}
  public static void main(String[] args){
    check("Only the exact previously verified route may retain detector-outage admission",NetworkHealthPolicy.afterFailure(true,true)==NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION);
    check("A first connection or changed route cannot borrow saved exit proof",!NetworkHealthPolicy.afterFailure(true,false).usable());
    check("Mismatch and core errors cannot use detector-outage retention",!NetworkHealthPolicy.afterFailure(false,true).usable());
    check("Verification-degraded admission remains usable",NetworkHealthPolicy.Admission.DEGRADED_VERIFICATION.usable());
    NetworkHealthPolicy.Assessment a=NetworkHealthPolicy.assess(false,true,false,NetworkHealthPolicy.TargetEvidence.TRANSPORT_UNAVAILABLE,0);
    check("One corroborated transport failure is only suspect",a.action==NetworkHealthPolicy.Action.SUSPECT&&a.consecutiveFailures==1);
    a=NetworkHealthPolicy.assess(false,true,false,NetworkHealthPolicy.TargetEvidence.TRANSPORT_UNAVAILABLE,a.consecutiveFailures);
    check("Two consecutive primary plus target transport failures allow recovery",a.action==NetworkHealthPolicy.Action.RECOVER&&a.consecutiveFailures==2);
    for(int code:new int[]{200,204,302,401,403,405,429,500,501,503,599}){
      a=NetworkHealthPolicy.assess(false,true,false,NetworkHealthPolicy.response(code),1);
      check("HTTP "+code+" proves route transport without treating website policy as dead network",a.action==NetworkHealthPolicy.Action.HEALTHY&&a.consecutiveFailures==0);
    }
    for(int code:new int[]{-1,0,101,199,600})check("Invalid or interim HTTP "+code+" is inconclusive",NetworkHealthPolicy.response(code)==NetworkHealthPolicy.TargetEvidence.INCONCLUSIVE);
    for(int repeat=0;repeat<100;repeat++){
      a=NetworkHealthPolicy.assess(false,true,false,NetworkHealthPolicy.TargetEvidence.HTTP_RESPONSE,1);
      if(a.action==NetworkHealthPolicy.Action.RECOVER)throw new AssertionError("Primary detector outage changed route");
    }
    check("Repeated detector outages with reachable target never switch",a.action==NetworkHealthPolicy.Action.HEALTHY);
    a=NetworkHealthPolicy.assess(false,true,false,NetworkHealthPolicy.TargetEvidence.INCONCLUSIVE,1);
    check("TLS or unknown target outcomes break consecutive proof instead of switching",a.action==NetworkHealthPolicy.Action.SUSPECT&&a.consecutiveFailures==0);
    a=NetworkHealthPolicy.assess(true,true,false,NetworkHealthPolicy.TargetEvidence.TRANSPORT_UNAVAILABLE,1);
    check("Busy reply defers action without manufacturing a second failure",a.action==NetworkHealthPolicy.Action.DEFER&&a.consecutiveFailures==1);
    a=NetworkHealthPolicy.assess(false,false,false,NetworkHealthPolicy.TargetEvidence.TRANSPORT_UNAVAILABLE,1);
    check("A late result for a changed route cannot trigger recovery",a.action==NetworkHealthPolicy.Action.DEFER&&a.consecutiveFailures==1);
    a=NetworkHealthPolicy.assess(false,true,true,NetworkHealthPolicy.TargetEvidence.INCONCLUSIVE,1);
    check("Primary success clears earlier transport suspicion",a.action==NetworkHealthPolicy.Action.HEALTHY&&a.consecutiveFailures==0);
    System.out.println("{\"passed\":"+checks+",\"scope\":\"production health and admission decisions on JVM; no Android transport execution\"}");
  }
}
