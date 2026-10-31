# Background reply runtime policy host harness

This compiles the complete current production `BackgroundReplyPolicy.java`.
Its policy logic is executed directly. `AppSettings`, profile contexts, Android
framework calls, notification cleanup, service hooks, and the existing-session
hook are explicit synthetic dependencies. The authority helper has a separate
`background-reply-policy-host` harness; this suite does not substitute for it.

Checks cover dynamic receiver registration and package hints, eight exact reply
service targets, preserving the independent proxy target, same-process peek/hook
delivery, no provider/service/browser creation, unknown authority, stale revisions
across authority failure, owner versus cold/live preference migration, failed
commit retry bits, and queuing local hooks from a worker. Private runtime state is
reset by reflection between cases to represent isolated policy instances.

The release hook updates a synthetic wake flag only. The preferences and process
list are in-memory models; the main handler is an explicit host queue; SQLite is
a writer-gate call recorder. This does **not** prove real Android service or
wakelock behavior, receiver permissions, lifecycle order, preference-cache or
process-start races, SQLite/WAL locking, retained browser behavior, proxy
continuity, or phone acceptance.

```sh
python3 tests/background-reply-runtime-host/run.py \
  --java-home /workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar /workspace/yuanying-chat/work/ui-detail/json.jar \
  --output /workspace/yuanying-chat/work/experience46-unified-20261031/background-reply-runtime-host-results.json
```

The report records each check, the exact production hash and all execution input
hashes, with explicit `false` Android/SQLite/phone execution flags. Compiler and
process output are retained beside the report in `.log`. No existing test
checklist or source guard is changed.
