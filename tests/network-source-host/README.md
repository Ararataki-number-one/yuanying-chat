# Source references and per-environment snapshots

Run the production selection and candidate logic with:

```sh
python3 tests/network-source-host/run.py --json-jar /path/to/json-20240303.jar --java-home /path/to/jdk
```

The runner compiles the actual `NetworkDraft`, `NetworkSourceSelection`,
`NetworkChanges`, `EntrySelection` and `NetworkCatalog` classes. Its 62 checks
exercise migration, rename/removal, same-name credential replacement, constrained
entry pools, role separation, subscription-address reversal, candidate publication
failure, per-environment provider payloads, payload hashes and generation receipts,
complete seven-record rollback, manual-exit compatibility, explicit node aliases, and a real cross-process source-publication lease.

Host fixtures use atomic plain files and a minimal preferences implementation.
They do **not** test Android encryption, keystore, UI, profile IPC, native provider
parsing or actual route application. Android integration and native-core gates
remain independently required. Fixture payloads and endpoints are synthetic;
no user subscription or authentication data is read.
# Additional snapshot checks

UI candidate reference validation is exercised with a SecretStore read counter;
it must perform no payload reads. Worker resolution is separately tested against
a removed real fixture payload file and must reject it.

Private generation receipts bind role, source ID, address revision and actual
payload SHA. Shared catalogue cache rotation does not change that private receipt.

Two independent JVMs exercise a paused partial active-provider update and a
concurrent source-copy reader. The reader must wait for the private profile lease
and receive matching settings, bytes, metadata and node identities. Another
profile's lease remains available. Nested write/rollback, stale transactions and
stale rollback are also tested. These remain host plain-file tests, not Android
encryption, IPC or native-proxy tests.
