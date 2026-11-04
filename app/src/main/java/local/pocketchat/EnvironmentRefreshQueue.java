package local.pocketchat;

import java.util.Objects;
import java.util.concurrent.Callable;
import java.util.concurrent.Executor;
import java.util.function.Consumer;

/** One environment metadata read plus one coalesced refresh; no account session is opened. */
final class EnvironmentRefreshQueue<T> {
  private final Executor worker,main;
  private final Callable<T> read;
  private final Consumer<T> apply;
  private final Consumer<Exception> failed;
  private boolean visible,closed,running,pending;
  private long epoch;

  EnvironmentRefreshQueue(Executor worker,Executor main,Callable<T> read,Consumer<T> apply,Consumer<Exception> failed){
    this.worker=Objects.requireNonNull(worker);this.main=Objects.requireNonNull(main);
    this.read=Objects.requireNonNull(read);this.apply=Objects.requireNonNull(apply);this.failed=Objects.requireNonNull(failed);
  }

  /** Each new visible lifetime needs fresh metadata; old in-flight results are discarded. */
  synchronized void visible(boolean value){
    if(closed||visible==value)return;
    visible=value;epoch++;
    pending=value;
    dispatch();
  }

  synchronized void request(){
    if(closed||!visible)return;
    pending=true;dispatch();
  }

  synchronized void close(){closed=true;visible=false;pending=false;epoch++;}

  private void dispatch(){
    if(closed||!visible||running||!pending)return;
    running=true;pending=false;final long captured=epoch;
    try{worker.execute(()->{
      T value=null;Exception failure=null;
      try{value=read.call();}catch(Exception error){failure=error;}
      post(captured,value,failure);
    });}catch(RuntimeException unavailable){post(captured,null,unavailable);}
  }

  private void post(long captured,T value,Exception failure){
    try{main.execute(()->complete(captured,value,failure));}
    catch(RuntimeException unavailable){
      // A dead UI executor cannot receive an error either. Release the queue so
      // a later explicit request can retry; never spin on a rejected executor.
      synchronized(this){running=false;pending=false;}
    }
  }

  private synchronized void complete(long captured,T value,Exception failure){
    try{
      // Paint same-lifetime metadata even when another refresh is due: a slow
      // read must not starve the screen behind a periodic refresh cadence.
      if(!closed&&visible&&epoch==captured){
        if(failure==null)apply.accept(value);else failed.accept(failure);
      }
    }finally{running=false;dispatch();}
  }
}
