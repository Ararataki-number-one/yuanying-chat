# Chromium Worker native policy controls

```sh
python3 tests/chromium-worker-policy-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/real-json.jar \
  --output work/chromium-worker-policy-host/results.json
```

Run once with each real JSON implementation used by the main host aggregate.
The runner extracts nine exact current `ChromiumRuntime` members and compiles
them with full production `EnvironmentSpec`, `ChromiumRoutePolicy`, and `J`.
Two exact UI summary methods separately verify that displayed native readback
is based on the actual boolean and that absent/stale confirmations stay unknown.
The declared JVM edges are the main Looper, handler, route evidence/listener,
and native Service Worker settings. These edges exercise actual production
control flow; they do not emulate an Android provider.

Coverage includes early confirmation before route identity, admitted allow,
restrict, pending policy, stale tokens, duplicate confirmation, slot/UUID/login
generation changes, route loss, replaced/closed owners, exhausted tokens,
off-main rejection, and native setter/getter faults. Independent mutations of
the real methods must fail their normal behavior assertions. Source guards
also require the live native callback and route admission sites to use the gate.

For actual page API behavior see `tests/chromium-worker-browser/run.py`.
Neither host suite proves native Android settings enforcement or complete
Worker fingerprint coverage; fresh real Android acceptance is separate.
