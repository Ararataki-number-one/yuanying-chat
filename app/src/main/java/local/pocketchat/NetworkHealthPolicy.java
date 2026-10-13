package local.pocketchat;

/** Decisions use transport evidence, not a particular site's availability. */
final class NetworkHealthPolicy {
  enum Admission { BLOCKED, VERIFIED, DEGRADED_VERIFICATION;
    boolean usable(){return this!=BLOCKED;}
  }
  enum TargetEvidence { HTTP_RESPONSE, TRANSPORT_UNAVAILABLE, INCONCLUSIVE }
  enum Action { DEFER, HEALTHY, SUSPECT, RECOVER }
  static final class Assessment {
    final Action action;final int consecutiveFailures;
    Assessment(Action action,int failures){this.action=action;consecutiveFailures=failures;}
  }
  static Admission afterFailure(boolean detectorUnavailable,boolean exactVerifiedRoute){
    return detectorUnavailable&&exactVerifiedRoute?Admission.DEGRADED_VERIFICATION:Admission.BLOCKED;
  }
  static TargetEvidence response(int code){
    // A challenge, rate limit, HEAD rejection or server error still proves the
    // protected transport reached the website. It does not prove GPT usable.
    return code>=200&&code<=599?TargetEvidence.HTTP_RESPONSE:TargetEvidence.INCONCLUSIVE;
  }
  static Assessment assess(boolean busy,boolean sameRoute,boolean primaryHealthy,TargetEvidence secondary,int priorFailures){
    if(busy||!sameRoute)return new Assessment(Action.DEFER,Math.max(0,priorFailures));
    if(primaryHealthy||secondary==TargetEvidence.HTTP_RESPONSE)return new Assessment(Action.HEALTHY,0);
    if(secondary!=TargetEvidence.TRANSPORT_UNAVAILABLE)return new Assessment(Action.SUSPECT,0);
    int failures=Math.min(2,Math.max(0,priorFailures)+1);
    return new Assessment(failures>=2?Action.RECOVER:Action.SUSPECT,failures);
  }
}
