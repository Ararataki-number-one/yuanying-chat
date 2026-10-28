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

/** Application/SDK boundaries for the 2.0.26 identity adapter check.
 * Android framework classes come from the real platform JAR. The JVM host
 * executes only the production runtime projection and these app/SDK doubles. */
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
}

final class GeckoWebView {
  static final String VERSION = "compile-boundary-only";
  final GeckoSettings settings = new GeckoSettings();
  boolean networkAllowed;
  GeckoSettings getSettings() { return settings; }
  String getUrl() { return ""; }
  boolean hasVisibleDocument() { return false; }
  JSONObject protectionStatus() { return null; }
  boolean protectionAllowsNetwork() { return networkAllowed; }
  boolean retryProtection() { return false; }
}

final class EnvironmentAudit {
  boolean running;
  JSONObject report;
  boolean observationCurrent(JSONObject report) { return false; }
  String policyStamp() { return ""; }
  String routeStamp() { return ""; }
  static String hash(String value) { return ""; }
}

final class BrowserNetworkGuard {
  boolean routeAllowed;
  boolean allowed() { return routeAllowed; }
}

final class IdentityTemplateController {
  boolean queueUnavailable, routeAdmitted;
  EnvironmentSpec cached;
  boolean pendingWork() { return false; }
  boolean actualRouteAdmitted() { return routeAdmitted; }
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
  static final int INK = 0;
}

final class EnvironmentAuditUi {
  static Button button(MainActivity activity, LinearLayout parent, String text) { return new Button(activity); }
}
