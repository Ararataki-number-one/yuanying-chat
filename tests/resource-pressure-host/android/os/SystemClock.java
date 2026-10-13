package android.os;

/** Controllable monotonic-clock double, including impossible inputs for rejection tests. */
public final class SystemClock {
  private static long now;
  public static void set(long value) { now = value; }
  public static long elapsedRealtime() { return now; }
}
