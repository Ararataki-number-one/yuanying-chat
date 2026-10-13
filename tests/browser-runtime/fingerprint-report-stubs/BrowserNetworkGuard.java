package local.pocketchat;
/** Host scope has no network activity. Only report-local address classification. */
final class BrowserNetworkGuard{static boolean localHost(String value){return value.equals("localhost")||value.equals("::1")||value.startsWith("127.")||value.startsWith("10.")||value.startsWith("192.168.");}}
