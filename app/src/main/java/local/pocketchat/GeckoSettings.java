package local.pocketchat;

/** Acknowledged metadata only; it is never a substitute for page observations. */
final class GeckoSettings {
  String userAgent="";boolean networkBlocked=true;
  boolean desktop,policyAcknowledged,rfpAcknowledged;String policyError="";
  boolean localesAcknowledged;String[] appliedLocales=new String[0];
  org.json.JSONObject acceptedBrowserIdentity=new org.json.JSONObject();
  String getUserAgentString(){return userAgent;}
  boolean getBlockNetworkLoads(){return networkBlocked;}
  void setBlockNetworkLoads(boolean value){networkBlocked=value;}
}
