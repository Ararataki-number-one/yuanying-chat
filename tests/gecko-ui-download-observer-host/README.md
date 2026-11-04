This host suite compiles the complete, hash-bound current
`DownloadLocationLayoutEvidence.java`, the three verbatim current Activity
observation methods, and the real application JSON helper. The Android
Activity, Intent, View, Layout, Handler, assets and log boundaries are explicit
stateful adapters. This verifies observation and rejection logic; it does not
claim Android rendering, gesture execution, glyph acceptance or release UI
acceptance. The existing device runner and its strict visual verifier remain
authoritative for those boundaries.

Run under the CI JDK 17 with either real supported JSON dependency:

```sh
python3 tests/gecko-ui-download-observer-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/ui-download-observer-host/json-org.json
python3 tests/gecko-ui-download-observer-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/android-json.jar \
  --output work/ui-download-observer-host/android-json.json
```

The report records source, extracted method, adapter, case template and JSON
dependency hashes. Unknown observer or Activity source fails before compilation.
The tests preserve the clipped initial record, observe fresh controlled geometry
on the same native object identities, reject invalid ownership before observer
creation, exercise stale posts and replay, preserve negative layout properties,
and check every actual observer timer remains exactly 5,000 ms. UI mutator
adapters throw if observation code tries to alter layout, visibility, scrolling,
intent ownership or Activity content.
