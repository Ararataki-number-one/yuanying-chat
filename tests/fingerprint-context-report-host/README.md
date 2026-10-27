# Context API report model controls

`actual-chromium-contexts-v1.json` preserves the positive page-world observation
from `work/coverage-probes/context-browser-results-final.json`, case
`real-context-operations`. It includes the capture's asset SHA, browser version,
original fixed fixture nonce, and distinct frame/Worker API sources. The values
were obtained in actual local Chromium; this fixture and the JVM test do not
represent a current browser, Android, Gecko, or real ChatGPT execution.

The host compiles the actual `AuditReport.java` with Java 8 API compatibility on
both pinned functional JSON libraries. It exercises valid captured Worker limits
(audio/font operation counts are zero), source/probe/schema/limit failures,
stale or missing main-world evidence, unavailable/restricted APIs, Worker WebGL
readback validation, and differing per-context hashes. A full-report control adds
an explicitly labelled host bridge envelope; it is not native freshness proof.

The wrapper also compiles a separately labelled source mutant that restores the
two obsolete Worker limit expectations (`2048` audio frames and `5` font choices).
That mutant must fail the captured Worker positive control. This is a causal
regression check, not a claim that a historical commit or Android build ran.
The production source is never changed by the test.

```sh
python3 tests/profile_fingerprint_context_report_test.py
```

Set `PROFILE_JAVA`, `PROFILE_JSON_JAR`, and `PROFILE_ANDROID_JSON_JAR` if the
repository's local JDK and pinned jars are not already present. Both JSON
runtimes are required; a missing runtime does not silently skip the controls.
Raw compiler/runtime streams and source hashes are written to
`work/coverage-context-report/results.json`; earlier executions are archived.
