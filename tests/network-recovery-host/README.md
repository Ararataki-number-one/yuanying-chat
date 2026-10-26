# Fault recovery search regression

Run both:

```
python3 tests/network-recovery-host/run.py --java-home <JDK17> --json-jar <org.json jar> --output <transaction-report.json>
python3 tests/network-recovery-host/run_real_probes.py --java-home <JDK17> --json-jar <org.json jar> --output <producer-report.json>
```

Use `--source <historical NativeNetwork.java> --scenario ordinary` to replay the
same desired behavior against the published baseline. A failing historical
report is an expected reproduction, not an accepted result.

The original 32-case `run.py` extracts production recovery, candidate search,
selection, receipts, scope checks and owned cleanup verbatim, with real Java
executors and `NetworkWork`. It substitutes candidate measurement and captures
its fixture binding at completion. **It cannot establish production probe
lifetime or serial validity.** Independent review found that all 32 passed while
the real producer discarded C's successful result after selecting B. Those
unchanged assertions remain transaction regressions, not proof of the producer fix.

The additional 18-case `run_real_probes.py` extracts complete production
`ProbeTicket`, `ProbeResult`, `probeMeasured`, `probeCurrent`, `probe`, trace parsing
and scope helper bodies, along with the complete `LatencyProbePolicy`, and keeps
the same real recovery/search/selection path. Its controlled delay/history
controller API ensures C captures its ticket **before** B selection and returns
20 during B verification. No binding or result conversion is substituted.
The same runner against pre-correction source `d0a9059...` reproduces 0/1: C's
controller response is 20 but its consumed production result is -1; no C exit
verification occurs. After correction, C remains 20 and must be exit-verified
before commit. The archived source hash and verbatim block hashes bind receipts.

The producer checks include local and service recovery, C's response during the
unconfirmed B-selection window, extra route-serial
movement, token/controller/maintenance/fingerprint/configuration/core changes,
deadline, cancellation, closed-scope rejection, and strict ordinary candidate
and current FixedExit bindings. The recovery scope authorizes only its own one
serial advance around `selectNow`; current-route and healthy optimization probes
retain the original serial requirement. A single highest authorized serial
avoids a torn read while opening/closing an own-selection window; the production
serial only increases, and each owned increment must exactly reach its prior
authorization. Probe threads inspect live frozen
identity; the owner still freshly checks controller, service snapshot and durable
configuration before selecting and committing. No probe-thread IPC or durable
file read was added. Clock jumps are fault boundaries, not phone timing data.

The main case makes A's primary/secondary transport observations fail, returns a
normal B exit-request IOException, and completes C's positive isolated probe
before B fails. The old path retries A, stops its core and never verifies C. The
fixed path must verify/commit C without retrying A or replacing the core/exit.

Other cases retain ordinary healthy-route rollback, failed rollback cleanup,
startup, busy/cancel behavior and the original 45-second/four-probe bounds. They
reject detector, TLS, certificate, cancellation, programming, cyclic-cause,
configuration, controller and receipt failures. Both process ownership and
service-generation ownership are represented, including preserving a replacement
generation. A wrapped ordinary connection error still permits the next candidate.

These are JVM fault-injection checks. They do not prove Android IPC, native
Mihomo routing, browser state preservation, real-site behavior or phone speed.
The original 28-case network-core host runner and Android release checks remain
required. The original core harness still substitutes its candidate-search
boundary; the additional producer runner is required to cover the real probe
lifetime within the complete production recovery/search. These tests do not
qualify the unchanged startup/healthy optimization probe scheduling on a device.
