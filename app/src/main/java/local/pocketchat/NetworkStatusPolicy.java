package local.pocketchat;

/** A failed synthetic latency sample must not override newer target evidence. */
final class NetworkStatusPolicy {
  static boolean freshTargetResponse(String health,int code,long at,long now){
    return "primary-detector-unavailable".equals(health)&&code>=200&&code<=599
        &&at>0&&now>=at&&now-at<=90000;
  }
  static String admission(String state){
    return "DEGRADED_VERIFICATION".equals(state)?"原线路可用，出口核验暂不可用"
        :"VERIFIED".equals(state)?"当前线路已核验":"当前线路尚未准入";
  }
}
