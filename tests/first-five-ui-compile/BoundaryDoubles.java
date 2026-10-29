package local.pocketchat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.os.Handler;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.concurrent.Executor;
import org.json.JSONObject;

/** Application/SDK edges for compile-only Android API checking.
 * No android.* type is replaced. None of these doubles executes in this check. */
final class MainActivity extends Activity {
  boolean destroyed;
  ChatSession session;
  int dp(int value) { return value; }
  TextView label(String text, int size, int color) { return new TextView(this); }
}

final class ChatSession {
  Context context;
  boolean deleted, navigating, networkReady;
  String environmentId;
  int environmentGeneration;
  long navigationEpoch;
  Executor environmentIo;
  Handler handler;
  GeckoWebView web;
  EnvironmentAudit audit;
  BrowserNetworkGuard guard;
  IdentityTemplateController identity;
  BrowserPrivacy privacy;
  long identityAuditAppliedRevision() { return 0; }
}

final class GeckoWebView {
  static final String VERSION = "compile-boundary-only";
  GeckoSettings getSettings() { return null; }
  String getUrl() { return ""; }
  boolean hasVisibleDocument() { return false; }
  JSONObject protectionStatus() { return null; }
  boolean protectionAllowsNetwork() { return false; }
  boolean retryProtection() { return false; }
}

final class EnvironmentAudit {
  boolean running;
  JSONObject report, fingerprintComparison;
  boolean observationCurrent(JSONObject report) { return false; }
  String policyStamp() { return ""; }
  String routeStamp() { return ""; }
  static String hash(String value) { return ""; }
  String comparisonCaptureIssue(String slot) { return ""; }
  boolean comparisonHas(String slot) { return false; }
  String comparisonSlotSummary(String slot) { return ""; }
  String comparisonSummary() { return ""; }
  String comparisonCopy() { return ""; }
  String captureComparison(String slot) { return ""; }
  String clearComparison(String slot) { return ""; }
  String setComparisonManual(String slot, String key, String state) { return ""; }
}

final class BrowserNetworkGuard {
  boolean allowed() { return false; }
  static boolean localHost(String value) { return false; }
}

final class IdentityTemplateController {
  boolean queueUnavailable;
  EnvironmentSpec cached;
  boolean pendingWork() { return false; }
  boolean actualRouteAdmitted() { return false; }
}

final class BrowserPrivacy {
  int level() { return 1; }
}

final class Profiles {
  static int slot(Context context) { return 0; }
}

final class EnvironmentSpecRepository {
  EnvironmentSpecRepository(Context context) {}
  EnvironmentSpec load() throws Exception { return null; }
}

final class AppAppearance {
  static AlertDialog.Builder dialog(Context context) { return new AlertDialog.Builder(context); }
}

final class Ui {
  static final int INK = 0, MUTED = 0;
}

final class EnvironmentAuditUi {
  static boolean current(MainActivity activity, ChatSession session, EnvironmentAudit audit) { return false; }
  static Button button(MainActivity activity, LinearLayout parent, String text) { return new Button(activity); }
  static LinearLayout section(MainActivity activity, LinearLayout parent) { return new LinearLayout(activity); }
  static void toggle(LinearLayout section, Button toggle, String show, String hide) {}
  static void show(MainActivity activity) {}
}
