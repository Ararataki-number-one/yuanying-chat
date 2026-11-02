package local.pocketchat;

/** Display ownership only. Leaving the dashboard is always an explicit action. */
final class EnvironmentOverviewState {
  final String nonce,environmentId;final int slot,generation;
  boolean closed;
  EnvironmentOverviewState(String nonce,String environmentId,int slot,int generation){this.nonce=nonce;this.environmentId=environmentId;this.slot=slot;this.generation=generation;}
  boolean matches(String id,int selected,int version){return !closed&&environmentId.equals(id)&&slot==selected&&generation==version;}
  void close(){closed=true;}
}
