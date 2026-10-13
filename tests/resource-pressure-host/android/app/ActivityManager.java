package android.app;

/** JVM fault double. These fields are fixture input, never device measurements. */
public final class ActivityManager {
  public static final class MemoryInfo {
    public boolean lowMemory;
    public long availMem, totalMem, threshold;
  }
  public boolean lowMemory;
  public long availMem = 2048, totalMem = 4096, threshold = 512;
  public int reads;
  public RuntimeException failure;
  public MemoryInfo lastDestination;
  public void getMemoryInfo(MemoryInfo destination) {
    reads++;
    if (failure != null) throw failure;
    if (destination == null) throw new AssertionError("Production did not supply MemoryInfo");
    lastDestination = destination;
    destination.lowMemory = lowMemory;
    destination.availMem = availMem;
    destination.totalMem = totalMem;
    destination.threshold = threshold;
  }
}
