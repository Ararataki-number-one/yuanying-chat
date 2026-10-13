package local.pocketchat;

/** SDK request/readback and explicit privacy API acknowledgements only.
 * Locale content-process completion is not exposed by this SDK; observe pages. */
final class GeckoSettings {
  String userAgent="";boolean networkBlocked=true;
  boolean desktop,policyAcknowledged,rfpAcknowledged;String policyError="";
  // The SDK getter confirms the requested descriptor, not content adoption.
  boolean localesRequestAcknowledged;String[] requestedLocales=new String[0],expectedSdkLocales=new String[0];
  org.json.JSONObject acceptedBrowserIdentity=new org.json.JSONObject();
  String getUserAgentString(){return userAgent;}
  boolean getBlockNetworkLoads(){return networkBlocked;}
  void setBlockNetworkLoads(boolean value){networkBlocked=value;}
}
