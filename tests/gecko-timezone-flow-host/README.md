# Gecko timezone application flow host checks

Run with JDK 17 and either supported JSON implementation:

```sh
python3 tests/gecko-timezone-flow-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/gecko-timezone-flow-host/desktop.json
```

The harness compiles the **complete current production** `GeckoTimeZoneController`,
timezone spec/store/policy, `EnvironmentSpec`, strict JSON parser, `J` and
`BrowserSettingsPolicy`. It copies the actual current UI `summary`, `busy`,
`Fence`, `activity`, `applySafely`, `confirm` and `commit` declarations verbatim
into a compilation wrapper. It similarly executes the actual audit `hash`,
`policyStamp` and `observationCurrent` declarations. Every source and every
extracted declaration is hashed in the report; an ambiguous or missing
declaration is an error. No old implementation is substituted for current code.

Controlled queues distinguish native bootstrap, native apply, writer publication,
UI revalidation, delayed preparation timeout, task-status callback and draft
callback. The checks include wrong session/token/context/zone, late callbacks,
independent live native sessions, close/reopen, desired revision changes,
read/write failure, recovery without ACK revival, default-system compatibility,
RFP priority and historical observation invalidation. The actual generic-site UI
flow must reach explicit manual confirmation without invoking the ChatGPT
observer. Cancel, busy/unknown tasks, draft archival/rechecks and explicit
approval all use the actual application methods.

This is a **host control-flow and storage-lifecycle** test, not Android or native
Gecko execution. Context/catalog/vault adapters are reused explicitly from the
core timezone host. Temporary files, atomic replacement and Java file locks are
real; SQLite and Android Keystore are not. Handler/executor time advancement,
native ACK callbacks, Activity/WebView, modal clicks, draft storage and page
signals are explicit boundaries. These synthetic ACKs cannot prove native BC
support, page `Date`/`Intl`, Worker or Service Worker coverage. The report keeps
all of those actual-execution fields false.
