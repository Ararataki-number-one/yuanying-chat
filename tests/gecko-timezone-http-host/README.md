# Native timezone HTTP wait host

This JDK 17 host extracts the complete current `GeckoWebView` HTTP wait wrappers,
queue completion, `TimeZoneGate`, native-session admission and native completion
methods. Actual `J.java` runs against a caller-provided real JSON implementation.
The generated source replaces only SDK type names with explicitly declared JVM
boundaries. No `org.mozilla` package, Android API or native timezone implementation
is simulated as SDK execution.

The workload covers bootstrap bypass, committed-document revalidation, SDK/object/
open-epoch/port/document/navigation/connection/identity/protection/desired-setting
fences, both helper callbacks, current target and guard rechecks, queue cap 128,
four-second deterministic Handler deadline, cleanup, private completion independent
of public listeners, private document proof callbacks before public HTTP replay,
shutdown/next-commit failure and completion/timeout races.
Each separately compiled one-hunk negative control must fail its unchanged focused
behavior assertion; a pristine focused run must pass first. Existing route and
request-header host suites retain responsibility for the original helper guards.

```sh
python3 tests/gecko-timezone-http-host/run.py \
  --java-home "$JAVA_HOME" --json-jar path/to/actual-json.jar \
  --output work/gecko-timezone-http/current.json
```

Run once per JSON implementation. Output includes production member hashes,
dependency hash, generated pristine/mutant sources and exact compile/run logs.
This is host callback/queue semantics evidence, not Android, Gecko, HTTP network,
native readback, frame-rate or performance acceptance.
