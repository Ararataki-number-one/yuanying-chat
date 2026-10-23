package local.pocketchat;

/** Main-actor retry state. A wakeup never bypasses the provider's live fences. */
final class NetworkApplyRetry {
  static final long MAX_DELAY=30000;
  String key="",reason="",event="";long nextAttempt;int failures;boolean observed;
  void bind(String candidate){if(!key.equals(candidate)){key=candidate;reason="";nextAttempt=0;failures=0;}}
  boolean due(String candidate,long now){bind(candidate);return now>=nextAttempt;}
  void defer(String candidate,String why,long now){bind(candidate);reason=why;long delay=Math.min(MAX_DELAY,2000L<<Math.min(failures,4));failures=Math.min(failures+1,5);nextAttempt=now+delay;}
  boolean observe(String value,boolean available){
    // Attaching an observer reports its current state synchronously. That first
    // sample establishes a baseline; it is not evidence of page recovery.
    if(!observed){observed=true;event=value;return false;}
    if(event.equals(value))return false;event=value;if(!available||key.isEmpty()||reason.isEmpty())return false;nextAttempt=0;return true;
  }
  boolean observePage(String scope,boolean idle,boolean page,boolean composer){return observe(scope+":"+idle+":"+page+":"+composer,idle&&page&&composer);}
  void clear(){key="";reason="";nextAttempt=0;failures=0;}
}
