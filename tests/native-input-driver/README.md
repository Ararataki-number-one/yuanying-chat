# Fixed native input for disposable Android tests

This signed test APK contains an API 35 emulator-only shell entry point. The
host verifies the installed APK, then loads that exact path with `app_process`
under the existing adb shell UID 2000. It never instruments, launches, clears,
or force-stops `local.pocketchat.test`. The original self-target instrumentation
manifest is retained for package compatibility, but the runtime has no fallback
to it. The APK has no privileged permissions or shared UID. Only the ephemeral
CI test certificate is permitted; this is not a release APK.

The two protocols were fixed before new device samples:

| Purpose | Nominal duration | MOVE offsets | Maximum lateness |
| --- | --- | --- | --- |
| qualification | 300 ms | 15, 30, …, 285 ms | 30 ms |
| formal-collapse | 320 ms | 16, 32, …, 304 ms | 32 ms |

Both submit DOWN, nineteen linear MOVE events, and one UP. All share the
original DOWN time. The schedule is absolute; it never slides after a slow
call. Event timestamps and injection call start/end are actual device uptime.
Late, refused, incomplete, or expired sequences fail and are never replayed.
If a failed sequence left DOWN active, one separately recorded cleanup CANCEL
may release it; cleanup cannot qualify as a successful gesture.

The fixed API 35 backend resolves the hidden, three-argument
`InputManagerGlobal.injectInputEvent(InputEvent, int, int targetUid)` once before
READY. DOWN and MOVE use mode 0 (ASYNC); the sole final UP uses mode 2
(WAIT_FOR_FINISH). Every event, including failure-only CANCEL, is restricted to
the actual PackageManager UID of the measured app on display 0. There is no
untargeted, UiAutomation, shell-swipe, or DOM-scroll fallback. This controlled
reflection exists only in the test tool; no production code or permissions
change. The final UP return must still meet the original device deadline.

The 05afa cohort failed all three fixed-scroll qualifications. Its DOWN calls
returned after 133, 26, and 223 ms; the first and third produced no MOVE, while
the second produced two before lateness exceeded 30 ms. The actual Android 15
source shows that the public two-argument UiAutomation call always enables
window-animation synchronization, including before DOWN even when `sync=false`.
The raw failures do not identify how much time was spent in that internal
synchronization, Binder, scheduling, or other work. Per-event full JSON encoding
and file replacement also ran inside the old 15/16 ms schedule; their individual
cost was not measured. Those three failures remain failures.

The unchanged scheduler now only retains the actual attempts in memory during
the gesture. The full trace is written at terminal success or failure; an
initial failed receipt and owner record are persisted before injection. Killing
or losing the driver can leave incomplete evidence, which fails qualification.
It must never be filled in from expected events. An adb timeout signals only
the matching nonce, PID, process start ticks, name, and UID; it cannot revoke
an already queued event and does not restart the measured app.

Each gesture has one shell invocation. Process startup, package/source and
foreground checks, input-service lookup (the existing `connect*` timestamp
fields), READY, planned trajectory, actual calls, and host return are recorded
separately. All setup and final collection remain within the original action
and flow wall times. Eliminating automation synchronization and per-event file
I/O is a tool correction, not evidence that the user application became faster.
The fixed 300/320 ms trajectory, 30/32 ms maximum lateness, original device
watchdog, native MOVE requirement, and original scroll assertions do not change.

The small driver APK is checked against actual installed bytes and its actual
signing certificate. The large measured APK reuses a prior actual byte-transfer
receipt before measurement, then checks the real installed path, package file
metadata, source stamp, and actual `/proc` PID/start-ticks/UID identity around
each gesture. Actual PackageManager SigningInfo supplies the driver certificate;
request arguments are never reported as independently observed certificates.
Current display and focused package observations must identify the AUT before
and after injection. No repeated
large-APK hash read is inserted into a timed action. Original Gecko session,
document, surface, and real scroll assertions remain required. Android may
coalesce MOVE delivery: the driver must submit all nineteen, while the actual
Gecko view must receive a real MOVE and satisfy the original scroll oracle.

`native-input-*.json` and `.log` are raw, source/run/nonce-bound evidence. Public
verification reads these receipts and signature-check outputs; it does not
download or re-verify the sidecar binary. The exact binary remains required in
the immutable CI build bundle. Neither private test keys nor this test APK are
included in the production Release APK list.

Signing verification uses the public `ApkVerifier` API from the same canonical
SDK 37 JAR used by the signing CLI. It requires one effective certificate, no
global or per-signer lineage, no ignored or extra signers, and the same sole
certificate in every verified scheme. Certificate chains, development-target
rotation, and V3.2/PQC signatures are outside this fresh test-driver contract.
The original CLI and API streams, API JSON, and build receipt bind the exact
APK, verifier source, loaded JAR, source commit, and CI run. All seven build
artifacts are mandatory for restore; API evidence is also retained in each
measurement sample. A separate always-run diagnostic upload preserves only the
six explicitly named signature outputs and signed test APK if building fails.
The missing signature streams from failed run 40067662758 were not recovered;
the SDK 37 format defect was reproduced separately with an existing public APK.

The failed 64be sample (319 ms DOWN delay, missing MOVE, adjacent skipped frames)
remains a failed historical sample. Its delay has not been attributed or fixed
by changing the input driver. Both A/B arms require the same declared driver
code/protocol and fresh complete CI qualification before measurement.
