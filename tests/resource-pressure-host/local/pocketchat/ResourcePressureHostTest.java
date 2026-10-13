package local.pocketchat;

import android.app.ActivityManager;
import android.content.Context;
import android.os.SystemClock;
import org.json.JSONArray;
import org.json.JSONObject;

/** Executes production controller code with explicit JVM Android API/fault doubles. */
public final class ResourcePressureHostTest {
  static final JSONArray checks = new JSONArray();
  static int passed;
  static void check(String name, boolean pass) {
    checks.put(new JSONObject().put("name", name).put("pass", pass));
    if (!pass) throw new AssertionError(name);
    passed++;
  }
  static ResourcePressureController.MemorySample sample(boolean low, long at) {
    return new ResourcePressureController.MemorySample(true, low, 2048, 4096, 512, at, "fixture-explicit");
  }
  static boolean unknown(ResourcePressureController.MemorySample value) {
    return !value.known && !value.lowMemory && value.availableBytes == -1 && value.totalBytes == -1
        && value.thresholdBytes == -1 && value.source.equals("unavailable");
  }
  static ResourcePressureController.MemorySample read(ActivityManager manager, long now) {
    SystemClock.set(now);
    return ResourcePressureController.read(new Context(manager));
  }
  static void platformRead() {
    ActivityManager manager = new ActivityManager();
    manager.lowMemory = true; manager.availMem = 256; manager.totalMem = 8192; manager.threshold = 700;
    Context context = new Context(manager); SystemClock.set(1234);
    ResourcePressureController.MemorySample value = ResourcePressureController.read(context);
    ActivityManager.MemoryInfo firstDestination = manager.lastDestination;
    check("Read requests the actual typed ActivityManager service", context.lookups == 1 && context.lastRequestedClass == ActivityManager.class);
    check("Read calls getMemoryInfo with a destination exactly once", manager.reads == 1 && manager.lastDestination != null);
    check("Read preserves the platform lowMemory flag", value.known && value.lowMemory);
    check("Read preserves availMem in bytes", value.availableBytes == 256);
    check("Read preserves totalMem in bytes", value.totalBytes == 8192);
    check("Read preserves the platform threshold in bytes", value.thresholdBytes == 700);
    check("Read records the platform source and monotonic observation time", value.source.equals("android-ActivityManager.MemoryInfo") && value.sampledAt == 1234);
    check("The freshly read valid sample is usable", value.fresh(1234));
    manager.lowMemory = false; manager.availMem = 1;
    ResourcePressureController.MemorySample clear = read(manager, 2000);
    check("Admission does not invent low memory from available bytes below threshold", clear.known && !clear.lowMemory && ResourcePressureController.admission(false, false, clear, 2000) == ResourcePressureController.Admission.START);
    manager.lowMemory = true; manager.availMem = manager.totalMem;
    ResourcePressureController.MemorySample low = read(manager, 3000);
    check("Admission honors platform lowMemory even above the threshold", low.known && ResourcePressureController.admission(false, false, low, 3000) == ResourcePressureController.Admission.DEFER);
    check("Each API read uses a newly allocated MemoryInfo destination", manager.reads == 3 && manager.lastDestination != null && manager.lastDestination != firstDestination);
  }
  static void unavailableReads() {
    check("Missing ActivityManager returns explicit unknown fields", unknown(read(null, 3100)));
    ActivityManager manager = new ActivityManager(); manager.failure = new SecurityException("fixture permission failure");
    ResourcePressureController.MemorySample denied = read(manager, 3200);
    check("getMemoryInfo failure returns unknown rather than fake zero capacity", unknown(denied) && manager.reads == 1 && denied.sampledAt == 3200);
    Context failed = new Context(new ActivityManager()); failed.failure = new IllegalStateException("fixture service lookup failure"); SystemClock.set(3300);
    check("Service lookup failure returns unknown without querying memory", unknown(ResourcePressureController.read(failed)) && failed.lookups == 1 && failed.manager.reads == 0);
    SystemClock.set(3400);
    check("Unavailable context returns unknown without throwing", unknown(ResourcePressureController.read(null)));
    ActivityManager invalid = new ActivityManager(); invalid.availMem = -1;
    check("Negative available bytes from the platform are unknown", unknown(read(invalid, 3500)));
    invalid = new ActivityManager(); invalid.totalMem = 0;
    check("Zero total bytes from the platform are unknown", unknown(read(invalid, 3500)));
    invalid = new ActivityManager(); invalid.totalMem = -1;
    check("Negative total bytes from the platform are unknown", unknown(read(invalid, 3500)));
    invalid = new ActivityManager(); invalid.availMem = invalid.totalMem + 1;
    check("Available bytes greater than total bytes are unknown", unknown(read(invalid, 3500)));
    invalid = new ActivityManager(); invalid.threshold = -1;
    check("Negative platform threshold is unknown", unknown(read(invalid, 3500)));
    check("Negative observation clock cannot become a known measurement", unknown(read(new ActivityManager(), -1)));
    invalid = new ActivityManager(); invalid.availMem = 0;
    check("Zero available bytes remain valid platform evidence", read(invalid, 3600).known);
  }
  static void freshnessAndAdmission() {
    ResourcePressureController.MemorySample low = sample(true, 1000), clear = sample(false, 1000);
    ResourcePressureController.MemorySample unavailable = ResourcePressureController.MemorySample.unknown(1000);
    check("Cold runtime creation defers for fresh known platform low memory", ResourcePressureController.admission(false, false, low, 1000) == ResourcePressureController.Admission.DEFER);
    check("An existing runtime remains admitted during low memory", ResourcePressureController.admission(true, false, low, 1000) == ResourcePressureController.Admission.EXISTING);
    check("Restoring a genuine task remains admitted during low memory", ResourcePressureController.admission(false, true, low, 1000) == ResourcePressureController.Admission.RECOVERY);
    check("Existing runtime takes priority over the recovery classification", ResourcePressureController.admission(true, true, low, 1000) == ResourcePressureController.Admission.EXISTING);
    check("Known clear memory permits cold runtime creation", ResourcePressureController.admission(false, false, clear, 1000) == ResourcePressureController.Admission.START);
    check("Unknown memory preserves explicit runtime admission", ResourcePressureController.admission(false, false, unavailable, 1000) == ResourcePressureController.Admission.START);
    check("Missing sample preserves explicit runtime admission", ResourcePressureController.admission(false, false, null, 1000) == ResourcePressureController.Admission.START);
    check("A sample is fresh through the exact freshness deadline", low.fresh(1000 + ResourcePressureController.FRESH_MS));
    check("Freshness expires one millisecond after the deadline", !low.fresh(1001 + ResourcePressureController.FRESH_MS));
    check("Stale low memory does not indefinitely defer explicit creation", ResourcePressureController.admission(false, false, low, 1001 + ResourcePressureController.FRESH_MS) == ResourcePressureController.Admission.START);
    check("Clock rollback invalidates an otherwise valid sample", !low.fresh(999));
    check("Clock rollback cannot manufacture a low memory deferral", ResourcePressureController.admission(false, false, low, 999) == ResourcePressureController.Admission.START);
    check("Unknown fields cannot become fresh merely by age", !unavailable.fresh(1000));
    check("An invalid direct sample cannot block explicit admission", ResourcePressureController.admission(false, false, new ResourcePressureController.MemorySample(true, true, -1, 4096, 512, 1000, "invalid-fixture"), 1000) == ResourcePressureController.Admission.START);
    check("Existing runtime remains admitted with unknown or missing memory", ResourcePressureController.admission(true, false, unavailable, 1000) == ResourcePressureController.Admission.EXISTING && ResourcePressureController.admission(true, false, null, 1000) == ResourcePressureController.Admission.EXISTING);
    check("Genuine recovery remains admitted with stale or invalid memory", ResourcePressureController.admission(false, true, low, 1001 + ResourcePressureController.FRESH_MS) == ResourcePressureController.Admission.RECOVERY && ResourcePressureController.admission(false, true, null, -1) == ResourcePressureController.Admission.RECOVERY);
  }
  static void warmup() {
    ResourcePressureController.MemorySample low = sample(true, 1000), clear = sample(false, 1000);
    check("Automatic warmup requires fresh clear platform evidence", ResourcePressureController.automaticWarmup(clear, 1000));
    check("Automatic warmup is disabled during known low memory", !ResourcePressureController.automaticWarmup(low, 1000));
    check("Automatic warmup is disabled when memory is unknown", !ResourcePressureController.automaticWarmup(ResourcePressureController.MemorySample.unknown(1000), 1000));
    check("Automatic warmup is disabled when the sample is missing", !ResourcePressureController.automaticWarmup(null, 1000));
    check("Automatic warmup is disabled after a clear sample expires", !ResourcePressureController.automaticWarmup(clear, 1001 + ResourcePressureController.FRESH_MS));
    check("Automatic warmup is disabled after clock rollback", !ResourcePressureController.automaticWarmup(clear, 999));
    check("Automatic warmup remains allowed at the exact freshness deadline", ResourcePressureController.automaticWarmup(clear, 1000 + ResourcePressureController.FRESH_MS));
    check("Automatic warmup rejects malformed clear memory", !ResourcePressureController.automaticWarmup(new ResourcePressureController.MemorySample(true, false, 2048, 0, 512, 1000, "invalid-fixture"), 1000));
  }
  static void counters() {
    ActivityManager manager = new ActivityManager(); manager.lowMemory = true;
    ResourcePressureController controller = new ResourcePressureController(new Context(manager)); SystemClock.set(5000);
    check("A new controller does not claim samples attempts or runtime creation", controller.samples == 0 && controller.attempts == 0 && controller.deferred == 0 && controller.created == 0 && controller.last == null);
    ResourcePressureController.MemorySample low = controller.sample();
    check("Sampling records one API observation and the exact returned sample", controller.samples == 1 && manager.reads == 1 && controller.last == low);
    manager.failure = new SecurityException("fixture read unavailable"); ResourcePressureController.MemorySample unknown = controller.sample();
    check("Unavailable sampling is counted without inventing a known observation", controller.samples == 2 && manager.reads == 2 && controller.last == unknown && !unknown.known);
    check("Request uses the supplied sample without an extra API read", controller.request(false, false, low) == ResourcePressureController.Admission.DEFER && manager.reads == 2 && controller.samples == 2 && controller.last == low);
    check("Deferred requests count attempts and deferrals without creation", controller.attempts == 1 && controller.deferred == 1 && controller.created == 0);
    controller.request(false, false, low);
    check("Repeated deferred requests remain requests rather than live runtimes", controller.attempts == 2 && controller.deferred == 2 && controller.created == 0);
    check("Existing runtime requests do not count as new deferrals", controller.request(true, false, low) == ResourcePressureController.Admission.EXISTING && controller.attempts == 3 && controller.deferred == 2);
    check("Recovery requests do not count as new deferrals", controller.request(false, true, low) == ResourcePressureController.Admission.RECOVERY && controller.attempts == 4 && controller.deferred == 2);
    check("Unknown explicit admission is distinct from a completed runtime creation", controller.request(false, false, unknown) == ResourcePressureController.Admission.START && controller.attempts == 5 && controller.created == 0 && controller.last == unknown);
    controller.runtimeCreated();
    check("Only the explicit creation acknowledgement increments created", controller.created == 1 && controller.attempts == 5 && controller.deferred == 2 && controller.samples == 2);
    SystemClock.set(5001 + ResourcePressureController.FRESH_MS);
    check("Counter requests use the current monotonic time for freshness", controller.request(false, false, low) == ResourcePressureController.Admission.START && controller.attempts == 6 && controller.deferred == 2 && controller.created == 1);
    boolean warm = ResourcePressureController.automaticWarmup(sample(false, 11000), 11000);
    check("Warmup advice cannot inflate runtime or sample counters", warm && controller.created == 1 && controller.samples == 2 && controller.attempts == 6);
  }
  public static void main(String[] args) {
    String error = "";
    try { platformRead(); unavailableReads(); freshnessAndAdmission(); warmup(); counters(); }
    catch (Throwable failure) { error = failure.toString(); }
    JSONObject result = new JSONObject().put("schema", 1).put("status", error.isEmpty() ? "passed" : "failed")
        .put("passed", passed).put("total", 58).put("executed", checks.length()).put("checks", checks)
        .put("actualAndroidExecution", false).put("synthetic", true).put("capacityAcceptance", false)
        .put("actualPlatformMemoryObservation", false).put("error", error)
        .put("scope", "Production ResourcePressureController on JVM with explicit Android API and fault doubles; no device capacity, Gecko runtime or Android execution");
    System.out.println(result);
    if (!error.isEmpty()) System.exit(1);
  }
}
