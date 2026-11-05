# Gecko CPU desired-state host checks

```sh
python3 tests/gecko-cpu-host/run.py --java-home "$JDK17" \
  --json-jar /path/to/json-20240303.jar --output work/cpu-store-desktop.json
python3 tests/gecko-cpu-host/run.py --java-home "$JDK17" \
  --json-jar /path/to/android-json.jar --output work/cpu-store-android-json.json
```

The runner compiles the complete current production `GeckoCpuSpec` and
`GeckoCpuStore`, together with the real `EnvironmentSpec`, strict
`NetworkShareJson` parser and `J`. It never substitutes an older implementation.
Reports hash all executed source/test inputs and the actual JSON jar and reject
changes during execution.

The checks exercise automatic/1/2 selection, strict schema and raw JSON typing,
missing owner identity, UUID/generation/slot replacement, revision CAS,
preservation of corrupt files and read/write failures, stable unchanged saves,
independent desired files, revision exhaustion and native-admission identity
checks. Twelve callers race through actual production CAS. A controlled catalog
boundary verifies that owner replacement cannot cross an active write. Separate
JVMs exercise the real file lock and the durable desired state after restart.

The actual `withCurrent` path also executes profile-preparation callbacks while
holding the existing owner/revision transaction. Rejected identity, null action
and stale revision never invoke that callback. Competing desired saves and
owner replacement wait until the action returns, and a throwing action releases
the locks for a subsequent writer from another thread. The callback must not
wrap the store in an outer catalog transaction or reenter the store itself.

Temporary files, atomic rename and Java `FileLock` are real. Android `Context`,
the catalog identity transaction and the atomic vault publication are explicit
host adapters; Android SQLite and AES/Keystore are not executed. The state under
test is desired state only. No Gecko preference, webpage, Worker or Service
Worker runs here, and no native setting acknowledgement or environment
fingerprint isolation is inferred. Those execution flags remain false.
