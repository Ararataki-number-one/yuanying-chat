package local.pocketchat;

/** Test-only budget. It never schedules work or changes a readiness decision. */
final class DeviceReadinessObservation {
  static final int LIMIT=24;
  static final long[] HEARTBEATS={1000,5000,30000,60000,110000};
  final long started;long sampled=Long.MIN_VALUE;int emitted,heartbeat;String previous="";
  DeviceReadinessObservation(long started){this.started=started;}
  boolean sample(long now,boolean terminal){
    if(emitted>=LIMIT)return false;
    if(!terminal&&sampled!=Long.MIN_VALUE&&now-sampled<250)return false;
    sampled=now;return true;
  }
  boolean emit(long now,String key,boolean terminal){
    if(emitted>=LIMIT)return false;
    boolean due=heartbeat<HEARTBEATS.length&&now-started>=HEARTBEATS[heartbeat];
    if(!terminal&&!due&&key.equals(previous))return false;
    while(heartbeat<HEARTBEATS.length&&now-started>=HEARTBEATS[heartbeat])heartbeat++;
    previous=key;emitted++;return true;
  }
}
