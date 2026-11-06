This host compiles the whole current `AppUpdates.java`, with named JVM-only
Android ContentResolver/JobScheduler/Context and queued Executor boundaries.
It proves that a MainActivity schedule queues the private update provider origin
request before the automatic-check switch is read. It preserves and checks both
original job criteria. An explicit modeled provider-denial control is a possible
future fixture boundary; it does not change any device component setting.

A deliberately held request is released after a modeled stop to demonstrate a
possible causal sequence. This is **not** evidence that the real Android PID5011
was started by that provider or any update job. Only the next exact-source native
process-start event can identify that component. No Android, network or native
TLS execution or release qualification is claimed. Four compiled mutations of
the actual source must fail the original behavior assertions.

Run `python3 tests/tls-fixture-update-cause-host/run.py --java-home JDK17
--output NEW_REPORT.json`. There is no JSON JAR dependency or network access.

The added isolation workload executes the exact current fixture pause/check and
onResume members, complete AppUpdates, actual fail/failed publication guards, and actual AppSettings get/put/bool
methods. SQLite, JobScheduler, Context and superclass lifecycle are explicitly
named JVM seams. It checks persisted false before actual schedule, two owned
cancellations/readback, late warm interference, write/read/scheduler faults,
wrong package/class, and unchanged TRANSFER/unrelated sentinels. Six compiled
helper changes must fail, including preservation of a previously passed record. The original twelve causal assertions and four
mutants remain. The modeled data-clear case checks default policy restoration;
only the existing device finally pm-clear result proves real cleanup. No
production/test-package branch or component disable is added.
