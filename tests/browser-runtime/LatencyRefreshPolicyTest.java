package local.pocketchat;

public final class LatencyRefreshPolicyTest {
  static int checks;
  static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);checks++;}
  public static void main(String[] args){
    check(!LatencyRefreshPolicy.fresh(0,1000),"first connection is immediately due");
    check(LatencyRefreshPolicy.fresh(1000,120999),"sample stays current through the two-minute interval");
    check(!LatencyRefreshPolicy.fresh(1000,121000),"next probe is due at two minutes");
    check(!LatencyRefreshPolicy.fresh(5000,1000),"clock rollback cannot pin a future reading");
    check(LatencyRefreshPolicy.countdown(LatencyRefreshPolicy.remaining(1000,1000)).equals("（02:00）"),"initial countdown");
    check(LatencyRefreshPolicy.countdown(LatencyRefreshPolicy.remaining(1000,2000)).equals("（01:59）"),"one-second tick");
    check(LatencyRefreshPolicy.countdown(LatencyRefreshPolicy.remaining(1000,120999)).equals("（00:01）"),"never display zero before due");
    check(LatencyRefreshPolicy.countdown(LatencyRefreshPolicy.remaining(1000,121000)).equals("（00:00）"),"due countdown");
    check(LatencyRefreshPolicy.countdown(Long.MAX_VALUE-999).equals("（02:00）"),"bounded presentation");
    System.out.println("{\"passed\":"+checks+",\"actualAndroidExecution\":false}");
  }
}
