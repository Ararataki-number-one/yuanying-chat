package local.pocketchat;

/** Explicit recovery for a page/network error, independent of website messages. */
final class PageConnectionUi {
  private PageConnectionUi() {}
  static void show(MainActivity a) {
    ChatSession session = a.session;
    if (!NetworkStatusUi.current(a, session)) return;
    AppAppearance.dialog(a).setTitle("网页需要恢复")
      .setMessage((session.pageError.isEmpty() ? "网页连接需要检查。" : session.pageError)
        + "\n\n可以先保存当前输入，再重新加载网页。")
      .setPositiveButton("重新加载", (d, w) -> {
        if (NetworkStatusUi.current(a, session)) a.requestReload();
      })
      .setNeutralButton("连接状态", (d, w) -> {
        if (NetworkStatusUi.current(a, session)) NetworkStatusUi.show(a);
      })
      .setNegativeButton("暂不恢复", null).show();
  }
}
