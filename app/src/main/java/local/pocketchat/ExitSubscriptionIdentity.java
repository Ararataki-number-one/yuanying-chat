package local.pocketchat;

/** Typed catalog identifiers and alphabetic-only SecretStore slots. Inputs never appear in keys. */
final class ExitSubscriptionIdentity {
  static String source(String url){return "exit-source-"+ExitSubscriptionParser.digest("source",url);}
  static String node(String sourceId,String nodeKey){return "exit-node-"+ExitSubscriptionParser.digest(sourceId,nodeKey);}
  static String cacheSlot(String sourceId){StringBuilder name=new StringBuilder("exit-pool-");for(char nibble:ExitSubscriptionParser.digest("cache",sourceId).toCharArray())name.append("abcdefghijklmnop".charAt(Character.digit(nibble,16)));return name.toString();}
}
