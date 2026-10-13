package local.pocketchat;

public final class NetworkStatusPolicyTest {
  static int checks;
  static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
  public static void main(String[] args){
    for(int code:new int[]{200,204,403,429,500,599})check(NetworkStatusPolicy.freshTargetResponse("primary-detector-unavailable",code,1000,2000));
    for(int code:new int[]{0,199,600})check(!NetworkStatusPolicy.freshTargetResponse("primary-detector-unavailable",code,1000,2000));
    check(!NetworkStatusPolicy.freshTargetResponse("transport-unavailable",200,1000,2000));
    check(!NetworkStatusPolicy.freshTargetResponse("primary-detector-unavailable",200,0,2000));
    check(!NetworkStatusPolicy.freshTargetResponse("primary-detector-unavailable",200,2001,2000));
    check(!NetworkStatusPolicy.freshTargetResponse("primary-detector-unavailable",200,1000,91001));
    check(NetworkStatusPolicy.freshTargetResponse("primary-detector-unavailable",200,1000,91000));
    check(NetworkStatusPolicy.admission("DEGRADED_VERIFICATION").contains("原线路可用"));
    check(!NetworkStatusPolicy.admission("BLOCKED").contains("可用"));
    System.out.println("{\"passed\":"+checks+",\"scope\":\"UI transport evidence, JVM only\"}");
  }
}
