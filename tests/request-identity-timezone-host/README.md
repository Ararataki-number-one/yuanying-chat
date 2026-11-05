# Authorized request-identity document transition

```sh
python3 tests/request-identity-timezone-host/run.py \
  --java-home work/browser-ci-jdk/jdk-17.0.21+9 \
  --json-jar work/profile-host/json.jar \
  --output work/request-identity-timezone-fix/desktop.json
```

Run again with the real Android JSON jar. This compiles the entire current
`RequestIdentityAuditSession`, request comparator/report, timezone controller,
store, policy and specification. Audit full/configuration stamps, expected values,
ordinary observation freshness, and Gecko's exact native-open/proof/finish methods
are copied verbatim from the current production files and hashed individually.
No historical source projection is imported or executed.

The original full stamp must fail during the detector's own document transition.
Only its registered, exact nonce URL may wait for the same SDK object, runtime,
open gate, navigation, port, desired revision and current document native proof.
The actual controller parses a controlled native read/apply message, publishes its
receipt through the real filesystem store, rechecks ownership on the UI queue,
and completes the actual Gecko proof predicate. The audit then synchronously
rebinds its full stamp before queued HTTP retries. Its unchanged preflight,
request-scope and report completion checks continue to require the full stamp.

Checks cover pending proof, writer/UI ordering, late or duplicate callbacks,
changed configuration/endpoint/route/identity/revision/file generation, same-object
close/reopen, failed native input or publication, original overall deadline,
ordinary observation invalidation and late collector results. Six mutations must
compile and fail named behavioral assertions; compilation failures do not count.
The old production request-comparison host supplies controlled JSON fixtures only.

SDK objects, document commit, native ACK inputs, preferences, handler/clock,
draft/driver and report persistence are explicit adapters. The actual native
setter, Android, real SDK callbacks, HTTP, page getters and Workers are **not**
executed. No native or Android evidence is inferred from these host results.
