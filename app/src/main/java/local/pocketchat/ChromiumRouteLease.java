package local.pocketchat;

import java.util.*;

/** Process-local route retention for real Chromium surfaces and native work.
 * No website content or reply state is inferred. Change handles fence new
 * work; existing network workers/coordinators still serialize route mutations. */
final class ChromiumRouteLease {
  static final String REASON="通用浏览器有网页或下载，已保留线路，请关闭浏览器后应用";
  static final Registry PROCESS=new Registry();
  static boolean held(){return PROCESS.held();}
  static Snapshot snapshot(){return PROCESS.snapshot();}
  static Handle acquireSurface(){return PROCESS.acquireSurface();}
  static Handle acquireDownload(){return PROCESS.acquireDownload();}
  static Handle tryChange(){return PROCESS.tryChange();}
  static void addListener(Runnable listener){PROCESS.addListener(listener);}
  static void removeListener(Runnable listener){PROCESS.removeListener(listener);}
  static final class Snapshot {
    final int surfaces,downloads,changes;final long revision;
    Snapshot(int surfaces,int downloads,int changes,long revision){this.surfaces=surfaces;this.downloads=downloads;this.changes=changes;this.revision=revision;}
    boolean held(){return surfaces>0||downloads>0;}
  }
  static final class Handle implements AutoCloseable {
    final Registry registry;final int kind;boolean closed;
    Handle(Registry registry,int kind){this.registry=registry;this.kind=kind;}
    @Override public void close(){registry.release(this);}
  }
  static final class Registry {
    private int surfaces,downloads,changes;private long revision;
    private final Set<Runnable> listeners=new LinkedHashSet<>();
    synchronized boolean held(){return surfaces>0||downloads>0;}
    synchronized Snapshot snapshot(){return new Snapshot(surfaces,downloads,changes,revision);}
    synchronized void addListener(Runnable listener){listeners.add(listener);}
    synchronized void removeListener(Runnable listener){listeners.remove(listener);}
    Handle acquireSurface(){return acquire(0);}
    Handle acquireDownload(){return acquire(1);}
    Handle tryChange(){return acquire(2);}
    private Handle acquire(int kind){
      Handle handle;List<Runnable> notify;
      synchronized(this){if(kind==2?held():changes>0)return null;handle=new Handle(this,kind);if(kind==0)surfaces++;else if(kind==1)downloads++;else changes++;revision++;notify=new ArrayList<>(listeners);}
      notifyListeners(notify);return handle;
    }
    private void release(Handle handle){
      List<Runnable> notify;
      synchronized(this){if(handle.closed)return;handle.closed=true;if(handle.kind==0)surfaces--;else if(handle.kind==1)downloads--;else changes--;revision++;notify=new ArrayList<>(listeners);}
      notifyListeners(notify);
    }
    private static void notifyListeners(List<Runnable> listeners){for(Runnable listener:listeners)try{listener.run();}catch(RuntimeException ignored){}}
  }
}
