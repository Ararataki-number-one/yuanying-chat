# Gecko CPU editor host checks

Run the complete current UI with JDK 17 and either supported JSON implementation:

```sh
python3 tests/gecko-cpu-ui-host/run.py --java-home "$JDK17" \
  --json-jar "$JSON_JAR" --output work/gecko-cpu-ui-host/results.json
```

The runner compiles the complete current production `GeckoCpuUi`, `GeckoCpuSpec`,
`EnvironmentSpec` and `J`; it never substitutes an earlier UI or copied method
implementation. Actual source, host boundary and JSON-library hashes are bound
to each report, with an unchanged-input check after execution.

Controlled writer and main queues separate entry load, confirmation, desired
publication and status notification. The real modal callbacks exercise option
labels and validation, cancellation, explicit approval, read/CAS/publication
failure, wrong owner, deleted/replaced environments, destroyed/finishing Activity,
and a committed save that outlives its editor. Two actual open modal instances
verify status refresh does not silently advance an old editor's CAS revision.
Pending work, reply/upload/download/operation flags and an unsent draft remain
unchanged. Native runtime mutation, page reload and process restart counters
remain zero. RFP/native preference claims are checked separately from page and
Worker verification; a string `"true"` cannot become an ACK.

Android widget/Activity/Modal, desired-store I/O and CAS, and native-controller
status are explicit synthetic boundaries. The companion core suite executes the
real store and file-lock implementation. These UI tests do not execute Android,
Gecko, Keystore or SQLite and do not prove CPU clamp behavior, live old Worker or
Service Worker mutation, or environment fingerprint isolation. All actual-native
execution fields remain false in the report.
