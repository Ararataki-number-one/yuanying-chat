package local.pocketchat;

/** Minimal browser metadata. Actual page settings belong to the Gecko SDK. */
final class GeckoSettings {
  String userAgent="";boolean networkBlocked=true;
  String getUserAgentString(){return userAgent;}
  boolean getBlockNetworkLoads(){return networkBlocked;}
  void setBlockNetworkLoads(boolean value){networkBlocked=value;}
}
