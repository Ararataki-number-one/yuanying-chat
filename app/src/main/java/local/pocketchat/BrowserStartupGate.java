package local.pocketchat;

/** A cold manual launch paints its native overview before creating the browser. */
final class BrowserStartupGate {
  final String environmentId;final int slot,generation;
  private boolean frame,foreground,started,closed;
  BrowserStartupGate(String id,int slot,int generation){environmentId=id;this.slot=slot;this.generation=generation;}
  boolean matches(String id,int slot,int generation){return !closed&&environmentId.equals(id)&&this.slot==slot&&this.generation==generation;}
  void frame(){frame=true;}
  void foreground(boolean value){foreground=value;}
  boolean take(){if(closed||started||!frame||!foreground)return false;started=true;return true;}
  void close(){closed=true;}
}
