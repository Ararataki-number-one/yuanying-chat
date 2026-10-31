package android.os;
import java.util.concurrent.ConcurrentLinkedQueue;
/** Explicit host queue; does not model Android message scheduling. */
public final class Handler {
  static final ConcurrentLinkedQueue<Runnable> queued=new ConcurrentLinkedQueue<>();
  public Handler(Looper looper){if(looper!=Looper.getMainLooper())throw new AssertionError("Main handler required");}
  public boolean post(Runnable runnable){queued.add(runnable);return true;}
  public static int pending(){return queued.size();}
  public static void reset(){queued.clear();}
  public static void drain(){if(Looper.myLooper()!=Looper.getMainLooper())throw new AssertionError("Drain from main host thread");Runnable next;while((next=queued.poll())!=null)next.run();}
}
