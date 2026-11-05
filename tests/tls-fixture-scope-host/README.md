# TLS fixture scope host controls

This suite compiles the complete current `GeckoTlsFixtureScopes` and the complete
production timezone store/spec/policy classes. It uses both supported real JSON
implementations and JDK 17. Missing timezone defaults and manual-system CAS saves
therefore execute the current store body. Profile preparation/catalog, Android
Context/process/clock/AtomicFile and a plain atomic file vault are declared host
boundaries; no SDK, native timezone, TLS, wire, encrypted vault or cold-runtime
success is claimed.

Only integration slots 1 and 2 and their exact TLS Activity classes can consume a
claim. A marker proves fixture scope, never native admission or a cold runtime.
Existing IP/custom/legacy/corrupt/foreign records are rejected before the actual
loader can migrate or overwrite them. A current schema2 manual-system record is
retained byte for byte. Warm cases require the original claim and a fresh bounded
case nonce. An explicit owned clear removes only the marker, never the timezone
choice. The original 104-case IP setup suite and its mutants remain unchanged;
this runner pins those files without borrowing their results.

```sh
python3 tests/tls-fixture-scope-host/run.py --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar --output /path/to/host-controls.json
```
