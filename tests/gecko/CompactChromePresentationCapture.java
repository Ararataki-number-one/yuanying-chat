package local.pocketchat;

/** Test-only frame ownership for a synthetic chrome layout, never a route receipt. */
final class CompactChromePresentationCapture {
  interface Host {
    boolean current();
    boolean matches();
    boolean laidOut();
    void paint();
    void nextFrame();
    void report();
    void failed(Throwable error);
    void release();
  }
  final Host host;
  final long deadline;
  boolean active=true;
  CompactChromePresentationCapture(Host host,long deadline){this.host=host;this.deadline=deadline;}
  boolean beforeDraw(long now){
    if(!active)return true;
    try{
      if(!host.current()){cancel();return true;}
      if(now>=deadline){expire(now);return true;}
      if(!host.matches()){host.paint();host.nextFrame();return false;}
      if(!host.laidOut()){host.nextFrame();return false;}
      active=false;
      try{host.report();}catch(Throwable error){host.failed(error);}finally{host.release();}
      return true;
    }catch(Throwable error){fail(error);return true;}
  }
  void expire(long now){if(active&&now>=deadline)fail(new AssertionError("Synthetic chrome presentation did not reach a matching laid-out frame"));}
  void cancel(){if(!active)return;active=false;host.release();}
  private void fail(Throwable error){if(!active)return;active=false;try{host.failed(error);}finally{host.release();}}
}
