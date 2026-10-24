# Fixed native input for disposable Android tests

This separate, self-targeting instrumentation APK uses public Android APIs. It
never instruments, launches, clears, or force-stops `local.pocketchat.test`.
The build rejects a different target, UI components, or privileged permissions.
Only the ephemeral CI test certificate is permitted. It is not a release APK.

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

DOWN and MOVE use `UiAutomation.injectInputEvent(event, false)`. The final UP
uses the public two-argument method with `true`, so its actual dispatch return
is recorded before instrumentation finishes. This is not a guarantee of a
nonblocking Binder call: Android still synchronizes window transactions around
DOWN and UP. The original device watchdog applies to events and the final UP
return. Diagnostic file collection may occur afterward; it cannot rescue a
failed workload. No hidden APIs or synthetic DOM scrolling are used.

Each complete gesture has one instrumentation invocation. Its process startup,
connection, READY, scheduled trajectory, actual calls, and host return are
recorded separately. This automation cost remains in the original action and
flow wall times. It is not a measurement of user application responsiveness or
evidence that the application became faster.

The small driver APK is checked against actual installed bytes and its actual
signing certificate. The large measured APK reuses a prior actual byte-transfer
receipt before measurement, then checks the real installed path, package file
metadata, source stamp, and process identity around each gesture. No repeated
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
