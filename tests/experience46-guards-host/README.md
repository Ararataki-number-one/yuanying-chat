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

Resource busy/idle fixtures call the exact `resourceWebsiteObservation` method.
A newer busy sequence prevents an older idle packet from acknowledging a pending
nonce, and a later real idle packet is distinct work evidence. No synthetic
trusted-send handler or native result task is recreated. `WebReplyObserver.receive`
is not executed here. The finite JavaScript resource protocol has separate JS
coverage; this host does not repeat it.

Coverage includes finite nonce delivery and timeout, concurrent requests, retired
ports/bindings/documents, old observations, resource busy and file work arriving during
a request, new idle evidence with a stale preserved pending record, foreground-only
page observation with independent file guards retained (the legacy background
option cannot restore sending/result detection), and network
begin/adopt ownership/proof/lease checks without navigation or automatic sending.
The identity acknowledgment hook is an explicit double that records successful
protected-admission ordering and performs no model/task/browser-data mutation.
