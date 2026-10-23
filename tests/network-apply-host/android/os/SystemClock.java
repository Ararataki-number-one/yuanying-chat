package android.os;
/** Explicit controlled monotonic clock; no Android runtime is claimed. */
public final class SystemClock { public static long now;public static long elapsedRealtime(){return now;} }
