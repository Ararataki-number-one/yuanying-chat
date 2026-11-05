# Native Gecko HTTP-UA policy host

```sh
python3 tests/gecko-request-headers-host/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar \
  --output work/native-header-policy/results.json
node --test tests/request-identity/worker_request_headers_test.cjs
```

Run the Java host with both desktop JSON and the Android JSON compatibility jar.
The runner extracts the current `HeaderPolicyRead`, UA validation, invalidation,
native context guard and `requestHeaderPolicy` methods unchanged. Only Gecko SDK
type tokens become declared session, result and port interfaces. Routing and
Android app state are explicit boundaries; no fake `org.mozilla` SDK is provided.

Controls execute concurrent requests sharing one actual-method UA read, fresh
per-target completion checks, cached success, retry after failure, revision,
navigation, protection-token, port, session, setting and route changes, invalid UA
bytes and failed invalidation posts. Internal private admissions retain their original
headers without SDK UA reads, while route, target and admission denial still win.
Ten one-hunk mutants must fail their precise
existing assertions. Generated sources, commands, raw logs, dependency hashes and
source-stability results accompany each report.

These are host behavior checks, not Android, Gecko SDK, network or full Worker
fingerprint acceptance. The separate extension test executes actual production
modules with declared VM browser/native/timer boundaries, including the existing
diagnostic header sanitizer and independent control-request scopes.
