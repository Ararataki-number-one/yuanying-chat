# Experience 46 guard host checks

This executes the listed production `ChatSession` method bodies and the production
`TaskGuardSnapshot` and `BrowserSettingsPolicy` classes. The runner records exact
source hashes, extracted members, raw commands/stdout/stderr and a JSON report in
a new `work/experience46-guards-host/<attempt>/` directory on every invocation.
It does not delete or overwrite prior failed attempts.

```sh
python3 tests/experience46-guards-host/run.py \
  --json-jar /path/to/android-json.jar \
  --java-home /path/to/jdk
```

The test owns explicit doubles for Handler/Looper scheduling, monotonic and wall
time, Gecko evaluate callbacks, visible-document state, resource ports, network
proof/current-route checks and the activity-policy hook. `System.currentTimeMillis()`
is replaced only by the declared wall-clock boundary. No Android, Gecko, real
network proof, physical phone or webpage execution is claimed.

The native trusted-intent event boundary changes `webWorkGeneration` and clears
`resourceObservedAt`, matching a source-checked production `WebReplyObserver`
block. `WebReplyObserver.receive` itself is not run here. The finite JavaScript
resource protocol has separate existing JS coverage; this test does not repeat it.

Coverage includes finite nonce delivery and timeout, concurrent requests, retired
ports/bindings/documents, old observations, trusted and file work arriving during
a request, new idle evidence with a stale preserved pending record, disabled
optional reply polling/capture with independent file guards retained, and network
begin/adopt ownership/proof/lease checks without navigation or automatic sending.
The identity acknowledgment hook is an explicit double that records successful
protected-admission ordering and performs no model/task/browser-data mutation.
