package local.pocketchat.hierarchydriver;

import android.app.UiAutomation;
import android.graphics.Point;
import android.os.Build;
import android.os.Process;
import android.os.SystemClock;
import android.view.Display;
import android.view.accessibility.AccessibilityNodeInfo;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.security.MessageDigest;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import org.json.JSONObject;

/** Read-only emulator hierarchy capture using the installed AOSP formatter. */
public final class NativeHierarchyCapture {
  static final String ENTRY = "local.pocketchat.hierarchydriver.NativeHierarchyCapture";
  static final String SYSTEM_JAR = "/system/framework/uiautomator.jar";
  static final String STAMP = "hierarchy-driver-build.json";
  static final String SOURCE = "sources/NativeHierarchyCapture.java";
  static final String NULL_ROOT = "ERROR: null root node returned by UiTestAutomationBridge.";
  static final long ROOT_POLL_MILLIS = 1000;
  static final long MAX_BUDGET_MILLIS = 90000;

  private NativeHierarchyCapture() {}

  static void require(boolean condition, String message) {
    if (!condition) throw new IllegalArgumentException(message);
  }

  static void supportedEnvironment() throws Exception {
    require(Process.myUid() == 2000, "Hierarchy capture requires shell UID 2000");
    require(Build.VERSION.SDK_INT == 32 || Build.VERSION.SDK_INT == 35,
        "Hierarchy capture supports only API 32 and 35");
    Class<?> properties = Class.forName("android.os.SystemProperties");
    String qemu = (String) properties.getMethod("get", String.class).invoke(null, "ro.kernel.qemu");
    require("1".equals(qemu) && ("ranchu".equals(Build.HARDWARE) || "goldfish".equals(Build.HARDWARE)),
        "Hierarchy capture requires a supported Android emulator");
  }

  static String hash(InputStream stream, long maximum) throws Exception {
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    byte[] buffer = new byte[32768];
    long count = 0;
    for (int n; (n = stream.read(buffer)) != -1;) {
      count += n;
      require(count <= maximum, "Hierarchy dependency exceeds its bound");
      digest.update(buffer, 0, n);
    }
    StringBuilder result = new StringBuilder();
    for (byte value : digest.digest()) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
    return result.toString();
  }

  static String hash(File file, long maximum) throws Exception {
    try (InputStream stream = new FileInputStream(file)) { return hash(stream, maximum); }
  }

  static byte[] bytes(InputStream stream, int maximum) throws Exception {
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    byte[] buffer = new byte[4096];
    for (int n; (n = stream.read(buffer)) != -1;) {
      require(output.size() + n <= maximum, "Hierarchy metadata exceeds its bound");
      output.write(buffer, 0, n);
    }
    return output.toByteArray();
  }

  static JSONObject verifyStamp(ZipFile archive, String source, String tree, String run, String attempt)
      throws Exception {
    int entries = 0;
    for (Enumeration<? extends ZipEntry> all = archive.entries(); all.hasMoreElements();) {
      String name = all.nextElement().getName();
      require(name.equals("classes.dex") || name.equals(STAMP) || name.equals(SOURCE),
          "Unexpected hierarchy driver archive entry");
      entries++;
    }
    require(entries == 3 && archive.getEntry("classes.dex") != null && archive.getEntry(STAMP) != null
        && archive.getEntry(SOURCE) != null, "Incomplete hierarchy driver archive");
    JSONObject stamp;
    try (InputStream input = archive.getInputStream(archive.getEntry(STAMP))) {
      stamp = new JSONObject(new String(bytes(input, 131072), "UTF-8"));
    }
    require(stamp.getInt("schema") == 1 && ENTRY.equals(stamp.getString("entryPoint"))
        && stamp.getInt("executionUid") == 2000 && stamp.getBoolean("readOnly")
        && source.equals(stamp.getString("sourceCommit")) && tree.equals(stamp.getString("sourceTree"))
        && run.equals(stamp.getString("runId")) && attempt.equals(stamp.getString("runAttempt")),
        "Hierarchy driver embedded source/run identity differs from preparation");
    String expected = stamp.getJSONObject("inputs").getString("tests/ui-hierarchy-driver/NativeHierarchyCapture.java");
    try (InputStream input = archive.getInputStream(archive.getEntry(SOURCE))) {
      require(hash(input, 131072).equals(expected), "Hierarchy driver embedded Java source differs from Git bytes");
    }
    return stamp;
  }

  static void verifyArchive(String expectedHash, String source, String tree, String run, String attempt,
      String expectedSystemHash) throws Exception {
    require(expectedHash.matches("[0-9a-f]{64}") && expectedSystemHash.matches("[0-9a-f]{64}")
        && source.matches("[0-9a-f]{40}") && tree.matches("[0-9a-f]{40}")
        && run.matches("[1-9][0-9]*") && attempt.matches("[1-9][0-9]*"), "Invalid hierarchy driver identity");
    String classpath = System.getenv("CLASSPATH");
    require(classpath != null && classpath.matches("/data/local/tmp/pocketchat-ui-hierarchy-"
        + source.substring(0, 12) + "-" + run + "-" + attempt + "-[0-9a-f]{32}\\.jar:"
        + SYSTEM_JAR.replace(".", "\\.")), "Unexpected hierarchy driver classpath");
    File jar = new File(classpath.substring(0, classpath.indexOf(':')));
    require(jar.isFile() && jar.getAbsolutePath().equals(jar.getCanonicalPath()), "Hierarchy driver jar is not a regular owned path");
    require(hash(jar, 2097152).equals(expectedHash), "Installed hierarchy driver SHA-256 mismatch");
    require(hash(new File(SYSTEM_JAR), 33554432).equals(expectedSystemHash), "AOSP hierarchy dependency changed");
    try (ZipFile archive = new ZipFile(jar)) { verifyStamp(archive, source, tree, run, attempt); }
  }

  static AccessibilityNodeInfo root(UiAutomation automation, long deadline) {
    long limit = Math.min(deadline, SystemClock.uptimeMillis() + ROOT_POLL_MILLIS);
    while (SystemClock.uptimeMillis() < limit) {
      AccessibilityNodeInfo node = automation.getRootInActiveWindow();
      if (node != null) {
        if (SystemClock.uptimeMillis() >= deadline) {
          node.recycle();
          throw new IllegalStateException("Hierarchy deadline expired during root acquisition");
        }
        return node;
      }
      long remaining = limit - SystemClock.uptimeMillis();
      if (remaining > 0) SystemClock.sleep(Math.min(40, remaining));
    }
    return null;
  }

  static Point displaySize(Display display, int api) {
    Point size = new Point();
    // Match each supported AOSP DumpCommand; do not alter its viewport semantics.
    if (api == 32) display.getSize(size);
    else if (api == 35) display.getRealSize(size);
    else throw new IllegalArgumentException("Unsupported hierarchy display API");
    require(size.x > 0 && size.y > 0, "Invalid hierarchy display size");
    return size;
  }

  static boolean capture(File output, long deadline) throws Exception {
    require(!output.exists(), "Refusing to replace an existing hierarchy attempt");
    Class<?> wrapperType = Class.forName("com.android.uiautomator.core.UiAutomationShellWrapper");
    Object wrapper = wrapperType.getConstructor().newInstance();
    AccessibilityNodeInfo node = null;
    boolean connected = false;
    try {
      wrapperType.getMethod("connect").invoke(wrapper);
      connected = true;
      wrapperType.getMethod("setCompressedLayoutHierarchy", boolean.class).invoke(wrapper, false);
      UiAutomation automation = (UiAutomation) wrapperType.getMethod("getUiAutomation").invoke(wrapper);
      node = root(automation, deadline);
      if (node == null) return false;
      Class<?> managerType = Class.forName("android.hardware.display.DisplayManagerGlobal");
      Object manager = managerType.getMethod("getInstance").invoke(null);
      Display display = (Display) managerType.getMethod("getRealDisplay", int.class).invoke(manager, Display.DEFAULT_DISPLAY);
      require(display != null, "Default display is unavailable");
      Point size = displaySize(display, Build.VERSION.SDK_INT);
      require(SystemClock.uptimeMillis() < deadline, "Hierarchy deadline expired before formatting");
      Class.forName("com.android.uiautomator.core.AccessibilityNodeInfoDumper")
          .getMethod("dumpWindowToFile", AccessibilityNodeInfo.class, File.class, int.class, int.class, int.class)
          .invoke(null, node, output, display.getRotation(), size.x, size.y);
      require(output.isFile() && output.length() > 0, "AOSP formatter did not create the current hierarchy");
      require(SystemClock.uptimeMillis() < deadline, "Hierarchy deadline expired during formatting");
      return true;
    } catch (Exception error) {
      if (output.exists() && !output.delete()) error.addSuppressed(new IllegalStateException("Cannot remove failed hierarchy attempt"));
      throw error;
    } finally {
      if (node != null) node.recycle();
      if (connected) wrapperType.getMethod("disconnect").invoke(wrapper);
    }
  }

  public static void main(String[] args) {
    int exit = 1;
    Thread watchdog = null;
    try {
      require(args.length == 8, "Expected hierarchy path, budget, jar/source/tree/run/attempt and system identity");
      require(args[0].matches("/sdcard/pocketchat-ui-visual-[0-9a-f]{32}-[1-9][0-9]*\\.xml"),
          "Invalid current-attempt hierarchy path");
      require(args[1].matches("[1-9][0-9]*"), "Invalid hierarchy budget");
      long budget = Long.parseLong(args[1]);
      require(budget <= MAX_BUDGET_MILLIS, "Hierarchy budget exceeds caller limit");
      final long deadline = SystemClock.uptimeMillis() + budget;
      watchdog = new Thread(() -> {
        long remaining;
        while ((remaining = deadline - SystemClock.uptimeMillis()) > 0) {
          try { Thread.sleep(remaining); } catch (InterruptedException finished) { return; }
        }
        System.err.println("ERROR: native hierarchy deadline expired.");
        System.exit(3);
      }, "hierarchy-deadline");
      watchdog.setDaemon(true);
      watchdog.start();
      supportedEnvironment();
      verifyArchive(args[2], args[3], args[4], args[5], args[6], args[7]);
      File output = new File(args[0]);
      boolean captured = capture(output, deadline);
      require(SystemClock.uptimeMillis() < deadline, "Hierarchy deadline expired before acknowledgement");
      if (captured) System.out.println("UI hierchary dumped to: " + args[0]);
      else System.err.println(NULL_ROOT);
      exit = 0;
    } catch (Throwable error) {
      Throwable cause = error;
      while (cause instanceof InvocationTargetException && cause.getCause() != null) cause = cause.getCause();
      cause.printStackTrace(System.err);
    } finally {
      if (watchdog != null) watchdog.interrupt();
    }
    System.exit(exit);
  }
}
