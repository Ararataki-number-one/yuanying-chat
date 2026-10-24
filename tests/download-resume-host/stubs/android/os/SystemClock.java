package android.os;public final class SystemClock{public static long elapsedRealtime(){return java.util.concurrent.TimeUnit.NANOSECONDS.toMillis(System.nanoTime());}}
