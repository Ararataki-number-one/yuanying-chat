package local.pocketchat;

import java.util.Locale;

/** Cadence for a small current-route probe, independent of route optimization. */
final class LatencyRefreshPolicy {
  static final long INTERVAL=120000;
  static boolean fresh(long at,long now){return at>0&&now>=at&&now-at<INTERVAL;}
  static long remaining(long at,long now){return fresh(at,now)?INTERVAL-(now-at):0;}
  static String countdown(long remaining){long seconds=Math.min(120,Math.max(0,(remaining+999)/1000));return String.format(Locale.ROOT,"（%02d:%02d）",seconds/60,seconds%60);}
}
