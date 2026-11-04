This host suite compiles the complete current `IntegrationEventStore.java` and
`IntegrationEvidenceProvider.java`, plus the real application JSON helper.
Android Context, Binder, URI, AtomicFile, ParcelFileDescriptor and Log are
explicit stateful adapters. Worker concurrency and file bytes are real JVM
operations; Android fsync/AtomicFile guarantees, Binder enforcement and device
execution are not claimed. Existing strict device sequence and identity gates
remain authoritative.

```sh
python3 tests/gecko-event-journal-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/gecko-event-journal-host/json-org.json
```

Repeat with `--json-jar work/ux-build-deps/android-json.jar` and a distinct
output path. JDK 17 is required. The JSON report records complete source,
actual method, adapter, case and dependency hashes and explicitly sets
`actualAndroidExecution` to false.

Controlled failures target the actual worker's payload and journal start,
write and finish boundaries. Latches exercise the old complete prefix while
the next journal is uncommitted, concurrent producers on the actual single
worker, and count/byte queue bounds. The suite also checks the full native
provider's pending pipe, exact file bytes, owner paths, shell UID, read-only
mode and size bounds. It never reconstructs missing native receipts, sorts
them, accepts an empty committed list or converts a transport failure into
successful application evidence.
