package local.pocketchat;

/** A display deadline only. It never admits or cancels an environment connection. */
final class EnvironmentOverviewState {
  static final long DISPLAY_MS=5000;
  final String nonce,environmentId;final int slot,generation;
  long visibleAt=-1;boolean closed;
  EnvironmentOverviewState(String nonce,String environmentId,int slot,int generation){this.nonce=nonce;this.environmentId=environmentId;this.slot=slot;this.generation=generation;}
  boolean matches(String id,int selected,int version){return !closed&&environmentId.equals(id)&&slot==selected&&generation==version;}
  void visible(long now){if(!closed&&visibleAt<0&&now>=0)visibleAt=now;}
  long remaining(long now){return closed?0:visibleAt<0?DISPLAY_MS:Math.max(0,DISPLAY_MS-Math.max(0,now-visibleAt));}
  boolean expired(long now){return !closed&&visibleAt>=0&&remaining(now)==0;}
  void close(){closed=true;}
}
