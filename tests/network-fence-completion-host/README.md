This host harness compiles the complete, unchanged production `captureTransition`, `commitGate`, `finish`, `releaseCapture` and `recordResult` methods together with the actual integration owner/collector methods. `Boundaries.java` declares its JVM main loop, view, document, identity and network boundaries; the capture document takes the non-ChatGPT branch. It does not run Android, Gecko, a native core or an APK.

The controlled order finishes the original operation, records its actual released capture and touch fence, then runs a queued observer that acquires a new internal transition. This includes the JVM's legitimate reuse of a noncapturing production touch lambda for different transitions. The fixture keeps the old completion proof and the later current ownership observation separate. Its original capture-and-touch-release predicate is unchanged.

Nine scenarios cover the original closed owner, later internal capture, missing/wrong completion owner, unowned global capture, unknown later direct job, and raw/direct callback accounting. Two one-hunk production mutations are scratch-only: leaving the original touch listener installed must fail the exact original release assertion; leaving capture active must fail the completion proof. Mutated sources never enter the app.

Run with both JSON implementations:

```sh
python3 tests/network-fence-completion-host/run.py --java-home "$JAVA_HOME" --json-jar "$JSON_JAR" --output work/network-fence-desktop
python3 tests/network-fence-completion-host/run.py --java-home "$JAVA_HOME" --json-jar "$ANDROID_JSON_JAR" --output work/network-fence-android-json
```

The reports bind complete production, fixture, harness and JSON input hashes, extracted method hashes, generated source and each case log. Full source-bound Android integration still has to pass in CI.
