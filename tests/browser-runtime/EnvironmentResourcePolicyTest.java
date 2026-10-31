package local.pocketchat;

import java.util.Arrays;
import java.util.Collections;

public final class EnvironmentResourcePolicyTest {
  private static int checks;
  private static void check(String name, boolean pass) { if (!pass) throw new AssertionError(name); checks++; }
  private static final String ENGINE = NativeCapabilityManifest.UPSTREAM_REVISION;
  private static final String RECEIPT = "a".repeat(64);
  private static EnvironmentResourcePolicy.State state(int slot, boolean foreground, boolean task,
      boolean upload, boolean download, boolean navigation, boolean checkpoint, boolean dirty, long used) {
    return new EnvironmentResourcePolicy.State(slot, 3, true, foreground, task, upload, download, navigation, checkpoint, dirty, used);
  }
  private static EnvironmentResourcePolicy.Plan plan(EnvironmentResourcePolicy.Budget budget,
      java.util.List<EnvironmentResourcePolicy.State> states, int slot, long generation) {
    return EnvironmentResourcePolicy.admit(budget, states, slot, generation, 1024, "test-device", ENGINE);
  }
  public static void main(String[] args) {
    check("Retained idle session may lower activity without a disposal permit",
        !EnvironmentResourcePolicy.keepActivityRunning(false,false,false,false,false,false));
    for (int flag = 0; flag < 6; flag++) {
      boolean[] work = new boolean[6]; work[flag] = true;
      check("Retained-session protected activity flag " + flag,
          EnvironmentResourcePolicy.keepActivityRunning(work[0],work[1],work[2],work[3],work[4],work[5]));
    }
    check("Busy page plus deferred maintenance keep activity even in background",
        EnvironmentResourcePolicy.keepActivityRunning(false,true,false,false,false,true));
    // Official webpage regeneration can be busy without a native pending job.
    boolean currentReply=BrowserSettingsPolicy.currentReply(true,true,true,8,8);
    check("Background website-only reply remains observable without a pending job",
        EnvironmentResourcePolicy.observePage(false,false,false,false,false,currentReply,true));
    check("Current reply keeps the retained background runtime active",
        EnvironmentResourcePolicy.keepActivityRunning(false,currentReply,false,false,false,false));
    currentReply=BrowserSettingsPolicy.currentReply(true,true,false,8,8);
    check("Fresh terminal observation stops otherwise idle background inspection",
        !EnvironmentResourcePolicy.observePage(false,false,false,false,false,currentReply));
    check("Fresh terminal observation permits retained activity to pause",
        !EnvironmentResourcePolicy.keepActivityRunning(false,currentReply,false,false,false,false));
    check("Prior document busy state cannot keep an idle new document inspecting",
        !EnvironmentResourcePolicy.observePage(false,false,false,false,false,
            BrowserSettingsPolicy.currentReply(true,true,true,8,9)));
    check("Another conversation busy state cannot keep this document inspecting",
        !EnvironmentResourcePolicy.observePage(false,false,false,false,false,
            BrowserSettingsPolicy.currentReply(true,false,true,8,8)));
    EnvironmentResourcePolicy.Budget budget = EnvironmentResourcePolicy.Budget.measured(2, 512, "test-device", ENGINE, RECEIPT);
    EnvironmentResourcePolicy.State safe = state(0, false, false, false, false, false, true, false, 10);
    check("Idle checkpointed background runtime is eligible", EnvironmentResourcePolicy.canSuspend(safe));
    boolean[][] protectedCases = {
      {true,false,false,false,false,true,false}, {false,true,false,false,false,true,false},
      {false,false,true,false,false,true,false}, {false,false,false,true,false,true,false},
      {false,false,false,false,true,true,false}, {false,false,false,false,false,false,false},
      {false,false,false,false,false,true,true}
    };
    for (int i = 0; i < protectedCases.length; i++) {
      boolean[] f = protectedCases[i];
      check("Protected work flag " + i, !EnvironmentResourcePolicy.canSuspend(f[0],f[1],f[2],f[3],f[4],f[5],f[6]));
    }
    check("Absent runtime is not a suspend candidate", !EnvironmentResourcePolicy.canSuspend(new EnvironmentResourcePolicy.State(0,3,false,false,false,false,false,false,true,false,10)));
    EnvironmentResourcePolicy.State active = state(1, true, true, false, false, false, false, true, 20);
    EnvironmentResourcePolicy.Plan p = plan(budget, Arrays.asList(safe, active), 2, 3);
    check("Capacity may suggest one safe runtime", p.decision == EnvironmentResourcePolicy.Decision.ALLOW_AFTER_SAFE_SUSPEND && p.suspendCandidates.size() == 1 && p.suspendCandidates.get(0).slot == 0);
    check("Planning leaves active work untouched", active.taskActive && active.live && safe.live);
    check("Already live selection needs no reclamation", plan(budget, Arrays.asList(safe,active), 1, 3).reason == EnvironmentResourcePolicy.Reason.ALREADY_LIVE);
    check("No measured budget preserves existing admission without suspending", plan(EnvironmentResourcePolicy.Budget.unmeasured(), Arrays.asList(safe,active), 2, 3).reason == EnvironmentResourcePolicy.Reason.UNMEASURED);
    check("No resource test can imply unlimited concurrency", !EnvironmentResourcePolicy.Budget.unmeasured().measured);
    check("Two protected runtimes deny extra activation", plan(budget,Arrays.asList(state(0,false,true,false,false,false,true,false,10),active),2,3).reason == EnvironmentResourcePolicy.Reason.ACTIVE_WORK_PROTECTED);
    check("Old generation cannot authorize new slot reuse", plan(budget,Arrays.asList(safe,active),0,4).reason == EnvironmentResourcePolicy.Reason.STALE_GENERATION);
    check("Duplicate slot metadata is rejected", plan(budget,Arrays.asList(safe,safe),2,3).reason == EnvironmentResourcePolicy.Reason.INVALID_SNAPSHOT);
    check("Within budget opens without suspension", plan(budget,Collections.singletonList(active),2,3).allowedWithoutSuspension());
    check("Low memory blocks new allocation without eviction", EnvironmentResourcePolicy.admit(budget,Arrays.asList(safe,active),2,3,511,"test-device",ENGINE).reason == EnvironmentResourcePolicy.Reason.LOW_MEMORY);
    check("Low memory does not interrupt existing runtime", EnvironmentResourcePolicy.admit(budget,Arrays.asList(safe,active),1,3,0,"test-device",ENGINE).allowedWithoutSuspension());
    check("Unknown memory cannot authorize a measured suspension plan",EnvironmentResourcePolicy.admit(budget,Arrays.asList(safe,active),2,3,-1,"test-device",ENGINE).reason==EnvironmentResourcePolicy.Reason.UNKNOWN_MEMORY);
    check("Other-device receipt cannot apply", EnvironmentResourcePolicy.admit(budget,Arrays.asList(safe,active),2,3,1024,"other-device",ENGINE).reason == EnvironmentResourcePolicy.Reason.DEVICE_SCOPE_MISMATCH);
    check("Other-engine receipt cannot apply", EnvironmentResourcePolicy.admit(budget,Arrays.asList(safe,active),2,3,1024,"test-device","b".repeat(40)).reason == EnvironmentResourcePolicy.Reason.DEVICE_SCOPE_MISMATCH);
    EnvironmentResourcePolicy.Budget one = EnvironmentResourcePolicy.Budget.measured(1,0,"test-device",ENGINE,RECEIPT);
    p = plan(one,Arrays.asList(safe,state(1,false,false,false,false,false,true,false,5)),2,3);
    check("Over-budget snapshot returns minimal complete reclamation plan", p.suspendCandidates.size()==2 && p.suspendCandidates.get(0).slot==1);
    try { p.suspendCandidates.clear(); throw new AssertionError("mutable plan"); } catch (UnsupportedOperationException expected) { checks++; }
    check("A newly started task invalidates old advice", !EnvironmentResourcePolicy.canSuspend(state(0,false,true,false,false,false,true,false,10)));
    try { EnvironmentResourcePolicy.Budget.measured(8,0,"","bad",""); throw new AssertionError("invalid measurement"); } catch (IllegalArgumentException expected) { checks++; }
    System.out.println("{\"status\":\"passed\",\"checks\":"+checks+",\"actualAndroidExecution\":false,\"scope\":\"Deterministic admission and protected-work policy; no measured capacity claim.\"}");
  }
}
