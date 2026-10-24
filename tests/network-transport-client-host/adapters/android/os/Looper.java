package android.os;
import java.util.concurrent.*;
public final class Looper {
 private static final Looper MAIN=new Looper();private static final ThreadLocal<Looper> CURRENT=new ThreadLocal<>();
 private final ConcurrentLinkedQueue<Runnable> tasks=new ConcurrentLinkedQueue<>();
 public static Looper getMainLooper(){return MAIN;}public static Looper myLooper(){return CURRENT.get();}
 public static void onMain(Runnable task){Looper old=CURRENT.get();CURRENT.set(MAIN);try{task.run();}finally{if(old==null)CURRENT.remove();else CURRENT.set(old);}}
 public void enqueue(Runnable task){tasks.add(task);}public int pending(){return tasks.size();}
 public Runnable take(){return tasks.poll();}public boolean runOne(){Runnable task=take();if(task==null)return false;onMain(task);return true;}
 public void drain(){int count=0;while(runOne())if(++count>1000)throw new AssertionError("Unbounded host main queue");}
 public void reset(){tasks.clear();}
}
