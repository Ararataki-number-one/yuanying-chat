# Background reply policy authority host harness

This compiles the complete current production `AppSettings.java` and executes its
policy authority helpers. The dependency supplies only the immutable
`BackgroundReplyPolicy.Snapshot` carrier; initialization, validation, policy
decisions, revision management, and compatibility acknowledgments are production
code.

The in-memory `SQLiteDatabase` adapter uses a reentrant writer lock, snapshots
transaction state, rolls back unsuccessful nested transactions, and supports
deliberate query/write failures. Java worker threads exercise concurrent
initialization and both writer orderings of enable versus compatibility cleanup.
Cases also cover stale initialization, idempotent decisions, write rollback,
malformed and incomplete authority, revision overflow, and generic-write guards.

This is synthetic JVM evidence. It does **not** prove Android SQLite/WAL,
cross-process locking, lifecycle, service/wakelock behavior, or phone acceptance.
It does not alter any existing test checklist or source guard.

Run with a JDK 17 home, the existing JSON jar, and a private output path:

```sh
python3 tests/background-reply-policy-host/run.py \
  --java-home /workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar /workspace/yuanying-chat/work/ui-detail/json.jar \
  --output /workspace/yuanying-chat/work/experience46-unified-20261031/background-reply-policy-host-results.json
```

The JSON result records the selected production source hash, all execution input
hashes, explicit execution limits, and each check. Compiler and process output
are retained beside it in a `.log` file.
