package local.pocketchat;

/** Main-actor retry state. A wakeup never bypasses the provider's live fences. */
final class NetworkApplyRetry {
  static final long MAX_DELAY=30000;
  String key="",reason="",event="";long nextAttempt;int failures;
  void bind(String candidate){if(!key.equals(candidate)){key=candidate;reason="";nextAttempt=0;failures=0;}}
  boolean due(String candidate,long now){bind(candidate);return now>=nextAttempt;}
  void defer(String candidate,String why,long now){bind(candidate);reason=why;long delay=Math.min(MAX_DELAY,2000L<<Math.min(failures,4));failures=Math.min(failures+1,5);nextAttempt=now+delay;}
  boolean observe(String value,boolean available){if(event.equals(value))return false;event=value;if(!available||key.isEmpty()||reason.isEmpty())return false;nextAttempt=0;return true;}
  void clear(){key="";reason="";nextAttempt=0;failures=0;}
}
