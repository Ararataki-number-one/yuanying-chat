This suite compiles the **complete production** `NetworkTransportClient.java`
and `J.java` directly, then runs the same lifecycle assertions against both an
immutable old source and the candidate. It does not extract or rewrite client
methods. Old failures stay failed in their original report.

The adapters implement only the APIs used by this client: a controlled main
queue, `Context.bindService`/`unbindService` callback scripts, message envelopes,
and in-process Messenger endpoints. Background calls use real JVM threads,
futures, and latches. Tests inspect the exact latches already captured by callers;
they do not change the production 10/15/5 second timeouts.

One case actually waits for the unchanged fifteen-second reply timeout using
the real JVM future. It retains the elapsed monotonic interval and then checks
expired and duplicate replies. This is a timeout/correlation correctness test,
not Android or network performance evidence.

The deferred-detach test deliberately delays a posted cleanup while admitting
a replacement binding. This is a controlled ordering probe for owner fencing,
not a claim about Android Handler scheduling or a physical-device reproduction.

No Android Service, kernel Binder transport, foreground-service restrictions,
process death, automatic OS reconnect, real proxy, or webpage executes. A fresh
Android lifecycle fixture is still required before device acceptance. The normal
service currently returns a non-null Binder; this suite does not claim that the
user's observed failures came from `onNullBinding`.
