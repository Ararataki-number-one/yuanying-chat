package local.pocketchat;

import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Exact production registry, real thread races, and deterministic lifecycle
 * checks. Timeouts diagnose deadlocks; no elapsed-time performance assertion. */
public final class RouteLeaseCases {
  static int checks;
  static void check(String label,boolean pass){checks++;if(!pass)throw new AssertionError(label);}
  static void close(ChromiumRouteLease.Handle handle){if(handle!=null)handle.close();}
  static void lifecycle(){
    ChromiumRouteLease.Registry registry=new ChromiumRouteLease.Registry();
    AtomicBoolean wasHeld=new AtomicBoolean();AtomicInteger wakeups=new AtomicInteger();
    registry.addListener(()->{boolean held=registry.held();if(wasHeld.getAndSet(held)&&!held)wakeups.incrementAndGet();});
    ChromiumRouteLease.Snapshot empty=registry.snapshot();
    ChromiumRouteLease.Handle selected=registry.acquireSurface(),backgroundTab=registry.acquireSurface(),download=registry.acquireDownload();
    check("surface and native download acquisitions succeed before any mutation",selected!=null&&backgroundTab!=null&&download!=null);
    ChromiumRouteLease.Snapshot active=registry.snapshot();
    check("selected and background surfaces both retain route",registry.held()&&active.surfaces==2&&active.downloads==1&&active.changes==0);
    check("captured empty snapshot remains immutable",empty.surfaces==0&&empty.downloads==0&&empty.changes==0&&active.revision>empty.revision);
    check("automatic route change denied with live pages/download",registry.tryChange()==null);
    selected.close();selected.close();check("retiring selected page is idempotent and retains background tab",registry.snapshot().surfaces==1&&registry.snapshot().downloads==1&&registry.held()&&wakeups.get()==0);
    backgroundTab.close();check("download keeps route after final surface retired",registry.held()&&registry.snapshot().surfaces==0&&registry.snapshot().downloads==1&&wakeups.get()==0);
    check("download alone still denies pending route application",registry.tryChange()==null);
    download.close();download.close();check("last route hold wakes candidate processing exactly once",!registry.held()&&wakeups.get()==1&&registry.snapshot().downloads==0);
    check("captured active snapshot survives later retirements",active.surfaces==2&&active.downloads==1);
    ChromiumRouteLease.Handle change=registry.tryChange();check("explicitly closed browser allows pending route mutation",change!=null&&registry.snapshot().changes==1&&!registry.held());
    check("new page and download cannot enter a mutation in flight",registry.acquireSurface()==null&&registry.acquireDownload()==null);
    ChromiumRouteLease.Handle secondChange=registry.tryChange();check("coordinated nested route change barriers do not deadlock",secondChange!=null&&registry.snapshot().changes==2);
    change.close();change.close();check("closing only one mutation barrier does not reopen page admission",registry.snapshot().changes==1&&registry.acquireSurface()==null);
    secondChange.close();ChromiumRouteLease.Handle reopened=registry.acquireSurface();check("last mutation completion allows browser startup",reopened!=null&&registry.snapshot().changes==0&&registry.held());
    close(reopened);check("reopened surface closes normally",!registry.held()&&wakeups.get()==2);
  }
  static void listenerSafety()throws Exception{
    ChromiumRouteLease.Registry registry=new ChromiumRouteLease.Registry();
    AtomicInteger delivered=new AtomicInteger();AtomicBoolean recurse=new AtomicBoolean();AtomicReference<Throwable> callbackFailure=new AtomicReference<>();
    ExecutorService reader=Executors.newSingleThreadExecutor();
    Runnable listener=()->{
      delivered.incrementAndGet();
      if(Thread.holdsLock(registry))callbackFailure.compareAndSet(null,new AssertionError("callback still owns registry monitor"));
      if(recurse.compareAndSet(false,true)){
        try{
          Future<Boolean> read=reader.submit(()->registry.snapshot().surfaces==1);
          if(!read.get(30,TimeUnit.SECONDS))callbackFailure.compareAndSet(null,new AssertionError("concurrent snapshot did not see held surface"));
          ChromiumRouteLease.Handle nested=registry.acquireDownload();
          if(nested==null)callbackFailure.compareAndSet(null,new AssertionError("reentrant download admission failed"));
          close(nested);
        }catch(Throwable error){callbackFailure.compareAndSet(null,error);}
      }
    };
    registry.addListener(()->{throw new IllegalStateException("fixture listener failure");});
    registry.addListener(listener);
    try{
      ChromiumRouteLease.Handle surface=registry.acquireSurface();
      check("callbacks run outside locks and support concurrent reads/reentrancy",callbackFailure.get()==null&&surface!=null&&registry.snapshot().surfaces==1&&registry.snapshot().downloads==0);
      surface.close();check("one listener failure cannot suppress later listeners or release",delivered.get()>=2&&!registry.held());
      registry.removeListener(listener);int count=delivered.get();ChromiumRouteLease.Handle download=registry.acquireDownload();close(download);
      check("removed observer no longer receives lifecycle events",count==delivered.get());
    }finally{reader.shutdownNow();}
  }
  static void races()throws Exception{
    ExecutorService workers=Executors.newFixedThreadPool(2);
    try{
      for(int round=0;round<1000;round++){
        ChromiumRouteLease.Registry registry=new ChromiumRouteLease.Registry();CountDownLatch ready=new CountDownLatch(2),go=new CountDownLatch(1);
        Future<ChromiumRouteLease.Handle> hold=workers.submit(()->{ready.countDown();go.await();return registry.acquireSurface();});
        Future<ChromiumRouteLease.Handle> mutation=workers.submit(()->{ready.countDown();go.await();return registry.tryChange();});
        if(!ready.await(30,TimeUnit.SECONDS))throw new AssertionError("race workers did not enter fixture barrier");go.countDown();
        ChromiumRouteLease.Handle acquiredHold=hold.get(30,TimeUnit.SECONDS),acquiredMutation=mutation.get(30,TimeUnit.SECONDS);
        check("surface versus mutation has exactly one winner "+round,(acquiredHold==null)!=(acquiredMutation==null));
        ChromiumRouteLease.Snapshot winner=registry.snapshot();
        check("race cannot overlap a route mutation with a live surface "+round,winner.downloads==0&&(winner.surfaces==1&&winner.changes==0||winner.surfaces==0&&winner.changes==1));
        ChromiumRouteLease.Handle winnerHandle=acquiredHold==null?acquiredMutation:acquiredHold;
        CountDownLatch closeReady=new CountDownLatch(2),closeGo=new CountDownLatch(1);
        Future<?> closeFirst=workers.submit(()->{closeReady.countDown();closeGo.await();winnerHandle.close();return null;});
        Future<?> closeSecond=workers.submit(()->{closeReady.countDown();closeGo.await();winnerHandle.close();return null;});
        if(!closeReady.await(30,TimeUnit.SECONDS))throw new AssertionError("close workers did not enter fixture barrier");closeGo.countDown();
        closeFirst.get(30,TimeUnit.SECONDS);closeSecond.get(30,TimeUnit.SECONDS);close(acquiredHold);close(acquiredMutation);
        check("concurrent close is idempotent without leaking or negative counts "+round,!registry.held()&&registry.snapshot().surfaces==0&&registry.snapshot().downloads==0&&registry.snapshot().changes==0);
      }
    }finally{workers.shutdownNow();}
  }
  static void repeatLifetimes(){
    ChromiumRouteLease.Registry registry=new ChromiumRouteLease.Registry();
    for(int round=0;round<1000;round++){
      ChromiumRouteLease.Handle first=registry.acquireSurface(),second=registry.acquireSurface(),download=registry.acquireDownload();
      check("repeated combined lifetime holds route "+round,first!=null&&second!=null&&download!=null&&registry.tryChange()==null);
      first.close();second.close();check("repeated native-only lifetime holds route "+round,registry.held()&&registry.snapshot().surfaces==0&&registry.tryChange()==null);
      download.close();ChromiumRouteLease.Handle change=registry.tryChange();check("repeated final release permits application "+round,change!=null&&registry.acquireDownload()==null&&registry.acquireSurface()==null);
      change.close();first.close();second.close();download.close();check("old handles cannot alter later epoch "+round,!registry.held()&&registry.snapshot().changes==0&&registry.snapshot().surfaces==0&&registry.snapshot().downloads==0);
    }
  }
  public static void main(String[] args)throws Exception{
    lifecycle();listenerSafety();races();repeatLifetimes();
    System.out.println("Chromium production route lease: "+checks+" checks passed");
  }
}
