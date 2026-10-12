package local.pocketchat;

/** Compatibility for old callers; browser selection is no longer an app action. */
final class BrowserEngineUi {
  static void show(MainActivity activity){activity.showPage(true);}
  static void switchTo(MainActivity activity,boolean ignoredEngine,boolean ignoredMode){activity.showPage(true);}
}
