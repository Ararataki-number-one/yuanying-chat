package local.pocketchat;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Pure admission advice. Callers must recheck live work before a checkpoint or suspension. */
final class EnvironmentResourcePolicy {
  /** Pauses only a retained live session's activity; does not authorize disposal. */
  static boolean keepActivityRunning(boolean foreground, boolean taskActive, boolean uploading,
      boolean downloading, boolean navigating, boolean maintenanceActive) {
    return foreground || taskActive || uploading || downloading || navigating || maintenanceActive;
  }

  static boolean canSuspend(boolean foreground, boolean taskActive, boolean uploading,
      boolean downloading, boolean navigating, boolean checkpointReady, boolean draftUncheckpointed) {
    return !foreground && !taskActive && !uploading && !downloading && !navigating
        && checkpointReady && !draftUncheckpointed;
  }

  /** A reply started entirely on the website still needs inspection in the
   * background so its eventual idle state can release retained activity. */
  static boolean observePage(boolean foreground,boolean service,boolean pending,
      boolean navigating,boolean deferred,boolean currentReply){
    return foreground||service||pending||navigating||deferred||currentReply;
  }

  static final class State {
    final int slot;
    final long generation, lastUsedAt;
    final boolean live, foreground, taskActive, uploading, downloading, navigating,
        checkpointReady, draftUncheckpointed;
    State(int slot, long generation, boolean live, boolean foreground, boolean taskActive,
        boolean uploading, boolean downloading, boolean navigating, boolean checkpointReady,
        boolean draftUncheckpointed, long lastUsedAt) {
      if (slot < 0 || generation < 0 || lastUsedAt < 0) throw new IllegalArgumentException("Invalid environment state.");
      this.slot = slot; this.generation = generation; this.live = live;
      this.foreground = foreground; this.taskActive = taskActive; this.uploading = uploading;
      this.downloading = downloading; this.navigating = navigating;
      this.checkpointReady = checkpointReady; this.draftUncheckpointed = draftUncheckpointed;
      this.lastUsedAt = lastUsedAt;
    }
  }

  static boolean canSuspend(State state) {
    return state != null && state.live && canSuspend(state.foreground, state.taskActive,
        state.uploading, state.downloading, state.navigating, state.checkpointReady, state.draftUncheckpointed);
  }

  static final class Budget {
    final boolean measured;
    final int maximumLive;
    final long minimumAvailableBytes;
    final String deviceScope, engineRevision, evidenceSha256;
    private Budget(boolean measured, int maximumLive, long minimumAvailableBytes,
        String deviceScope, String engineRevision, String evidenceSha256) {
      this.measured = measured; this.maximumLive = maximumLive;
      this.minimumAvailableBytes = minimumAvailableBytes; this.deviceScope = deviceScope;
      this.engineRevision = engineRevision; this.evidenceSha256 = evidenceSha256;
    }
    static Budget unmeasured() { return new Budget(false, 0, 0, "", "", ""); }
    /** Only call after independently accepting a matching real-device measurement receipt. */
    static Budget measured(int maximumLive, long minimumAvailableBytes, String deviceScope,
        String engineRevision, String evidenceSha256) {
      if (maximumLive < 1 || maximumLive > 8 || minimumAvailableBytes < 0
          || deviceScope == null || deviceScope.trim().isEmpty()
          || engineRevision == null || !engineRevision.matches("[0-9a-f]{40}")
          || evidenceSha256 == null || !evidenceSha256.matches("[0-9a-f]{64}"))
        throw new IllegalArgumentException("A device- and engine-bound measured budget is required.");
      return new Budget(true, maximumLive, minimumAvailableBytes, deviceScope, engineRevision, evidenceSha256);
    }
    boolean appliesTo(String device, String engine) {
      return measured && deviceScope.equals(device) && engineRevision.equals(engine);
    }
  }

  enum Decision { ALLOW, ALLOW_AFTER_SAFE_SUSPEND, DENY }
  enum Reason { ALREADY_LIVE, UNMEASURED, WITHIN_BUDGET, DEVICE_SCOPE_MISMATCH,
    LOW_MEMORY, ACTIVE_WORK_PROTECTED, STALE_GENERATION, INVALID_SNAPSHOT, SAFE_BACKGROUND_AVAILABLE }
  static final class Plan {
    final Decision decision;
    final Reason reason;
    final List<State> suspendCandidates;
    private Plan(Decision decision, Reason reason, List<State> candidates) {
      this.decision = decision; this.reason = reason;
      this.suspendCandidates = Collections.unmodifiableList(new ArrayList<>(candidates));
    }
    boolean allowedWithoutSuspension() { return decision == Decision.ALLOW; }
  }

  static Plan admit(Budget budget, List<State> snapshot, int requestedSlot, long requestedGeneration,
      long availableBytes, String deviceScope, String engineRevision) {
    if (budget == null || snapshot == null || requestedSlot < 0 || requestedGeneration < 0 || availableBytes < -1)
      return result(Decision.DENY, Reason.INVALID_SNAPSHOT);
    Set<Integer> slots = new HashSet<>();
    int live = 0;
    List<State> safe = new ArrayList<>();
    boolean alreadyLive = false;
    for (State state : snapshot) {
      if (state == null || !slots.add(state.slot)) return result(Decision.DENY, Reason.INVALID_SNAPSHOT);
      if (state.slot == requestedSlot) {
        if (state.generation != requestedGeneration) return result(Decision.DENY, Reason.STALE_GENERATION);
        alreadyLive = state.live;
      }
      if (state.live) live++;
      if (state.slot != requestedSlot && canSuspend(state)) safe.add(state);
    }
    if (alreadyLive) return result(Decision.ALLOW, Reason.ALREADY_LIVE);
    if (!budget.measured) return result(Decision.ALLOW, Reason.UNMEASURED);
    if (!budget.appliesTo(deviceScope, engineRevision)) return result(Decision.DENY, Reason.DEVICE_SCOPE_MISMATCH);
    // Unknown available memory cannot justify a destructive reclamation decision.
    if (availableBytes >= 0 && availableBytes < budget.minimumAvailableBytes)
      return result(Decision.DENY, Reason.LOW_MEMORY);
    if (live < budget.maximumLive) return result(Decision.ALLOW, Reason.WITHIN_BUDGET);
    int required = live - budget.maximumLive + 1;
    if (safe.size() < required) return result(Decision.DENY, Reason.ACTIVE_WORK_PROTECTED);
    safe.sort(Comparator.comparingLong((State state) -> state.lastUsedAt).thenComparingInt(state -> state.slot));
    return new Plan(Decision.ALLOW_AFTER_SAFE_SUSPEND, Reason.SAFE_BACKGROUND_AVAILABLE, safe.subList(0, required));
  }

  private static Plan result(Decision decision, Reason reason) {
    return new Plan(decision, reason, Collections.emptyList());
  }
}
