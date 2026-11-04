# Transcript persistence workload

Run from the repository root, with JDK 17 and either supported JSON jar:

```sh
python3 tests/transcript-store-performance-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar
```

Repeat with `work/ux-build-deps/android-json.jar` and a separate `--output` path.
The default comparison baseline is commit `f43adac`. The runner executes the
complete production `WebTranscriptStore` and `J`, and the actual `chatUrl`
method, with the real single-worker executor. Handler, cache, preferences and
URI boundaries are explicit controlled adapters. Reports bind production,
harness and jar hashes and require unchanged execution inputs.

Both JSON implementations pass 139 baseline and 139 current checks. The
workloads cover 100 changing 64-message snapshots, a 40-offer burst, stale
queued snapshots, native cancellation, cross-conversation saves, legacy
preference preservation, offline loading and failure recovery. Assertions
compare full saved payloads and count actual preference setters, their UTF-16
characters, and production serialization calls. They do not execute Android,
SQLite or SharedPreferences and do not measure device frame time or disk I/O.
