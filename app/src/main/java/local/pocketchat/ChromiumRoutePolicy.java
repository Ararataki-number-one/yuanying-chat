package local.pocketchat;

/** Callback admission: a late proxy callback can never reopen a replaced route. */
final class ChromiumRoutePolicy {
  static final class Ticket {final long serial;Ticket(long serial){this.serial=serial;}}
  private long serial;private Ticket ticket;private boolean ready,closed;
  synchronized Ticket begin(){if(closed)return null;ready=false;return ticket=new Ticket(++serial);}
  synchronized boolean admit(Ticket expected,boolean evidenceCurrent){if(closed||ticket!=expected||expected==null||!evidenceCurrent)return false;ready=true;return true;}
  synchronized boolean pending(Ticket expected){return !closed&&expected!=null&&expected==ticket;}
  synchronized boolean current(Object expected){return !closed&&ready&&expected!=null&&expected==ticket;}
  synchronized boolean retain(Object expected,boolean evidenceCurrent){return evidenceCurrent&&current(expected);}
  synchronized void block(){ready=false;ticket=null;serial++;}
  synchronized void close(){block();closed=true;}
  /** ProxyController is process-global. Never overlap async mutations, including
   * a retiring Activity and its replacement. Only the newest queued intent runs. */
  static final class ProxyQueue {
    private boolean running;private Runnable next;
    synchronized void submit(Runnable request){next=request;drain();}
    synchronized void complete(){running=false;drain();}
    private void drain(){if(running||next==null)return;Runnable request=next;next=null;running=true;request.run();}
  }
}
