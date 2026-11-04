package local.pocketchat;

/** Native chrome visibility only. The browser document and session are never replaced. */
final class FocusReadingPolicy {
  static boolean active(boolean requested,boolean chat,boolean visibleDocument){return requested&&chat&&visibleDocument;}
  static boolean navigation(boolean focused,boolean chat,boolean keyboard){return !focused&&!(chat&&keyboard);}
  static boolean exitControl(boolean focused,boolean keyboard){return focused;}
}
