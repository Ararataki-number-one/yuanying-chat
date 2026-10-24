This suite compiles the **complete production** `NetworkTransportClient.java`
and `J.java` directly, then runs the same lifecycle assertions against both an
immutable old source and the candidate. It does not extract or rewrite client
methods. Old failures stay failed in their original report.

`BeforeNetworkTransportClient.java.in` is the complete verbatim class at
`3eac2891438d37aa62f695b34a90f0aa02215ca2`, pinned by source path, byte count and
SHA256 in `before-source.json` and the runner. The current shared `J.java` must
match that same source's pinned bytes too. The snapshot was checked against
the original Git blob before committing; execution needs only the current tree,
so shallow CI never fetches or silently substitutes a different before source.

The adapters implement only the APIs used by this client: a controlled main
queue, `Context.bindService`/`unbindService` callback scripts, message envelopes,
and in-process Messenger endpoints. Background calls use real JVM threads,
futures, and latches. Tests inspect the exact latches already captured by callers;
they do not change the production 10/15/5 second timeouts.

One case actually waits for the unchanged fifteen-second reply timeout using
the real JVM future. It retains the elapsed monotonic interval and then checks
expired and duplicate replies. This is a timeout/correlation correctness test,
not Android or network performance evidence.

The dispatcher adapter follows Android 15 `Context.bindService` documentation
and `ContextImpl.bindServiceCommon` / `LoadedApk.getServiceDispatcherCommon`:
the framework records the connection before the AMS result. A false result or
`SecurityException` must therefore be followed by `unbindService` too. The
earlier 74-check candidate incorrectly treated only accepted bindings as owned;
its reports remain preserved, and its false/exception cleanup oracles are
explicitly corrected here. The new 92-check suite tests twenty failed explicit
attempts of each kind, deferred cleanup after synchronous callbacks, generations
never actually attempted, and bounded cleanup failure.

Official source reference: `aosp-mirror/platform_frameworks_base`, immutable tag
`android-15.0.0_r1`, `core/java/android/content/Context.java`,
`core/java/android/app/ContextImpl.java`, and `core/java/android/app/LoadedApk.java`.

The deferred-detach test deliberately delays a posted cleanup while admitting
a replacement binding. This is a controlled ordering probe for owner fencing,
not a claim about Android Handler scheduling or a physical-device reproduction.

No Android Service, kernel Binder transport, foreground-service restrictions,
process death, automatic OS reconnect, real proxy, or webpage executes. A fresh
Android lifecycle fixture is still required before device acceptance. The normal
service currently returns a non-null Binder; this suite does not claim that the
user's observed failures came from `onNullBinding`.
