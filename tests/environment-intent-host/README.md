# Environment intent transaction regression

This runs the production `EnvironmentSpecRuntime`, immutable model and migration,
`NetworkChanges`, source/snapshot code and actual per-profile OS intent lease.
The repository, UUID catalogue, preferences and SecretStore are explicit host
doubles; files are atomic plain bytes. This does **not** execute Android SQLite,
AES-GCM/Keystore, Gecko, the native network core, accounts or WAN traffic.

The v46 dependency adaptation additionally compiles the complete production
`NetworkApplicationReceipt` and `NetworkApplyCoordinator`. The original cases
do not exercise live core application or publish share selections: explicit
boundary adapters reject every core-proof invocation and report optional share
migration/invalidation unavailable, instead of manufacturing successful results.
The production configuration and share-selection host suites cover those new
behaviors separately. All original intent cases and transaction guards remain.

The 124 checks include the production proxy validation method, extracted verbatim
from MainActivity, with positive HTTP/HTTPS/SOCKS and invalid syntax controls.
Only the Android URI parser has a JVM syntax adapter; actual Android storage
checks use the real Android validator. Legal synthetic routes use `socks://`.
Transaction checks cover staged/ready publication, model failure after staging,
predecessor intent and private payload retention, exact rollback refusing newer
receipts, concurrent browser revision CAS, interruption before promotion,
cancellation/model reconciliation, malformed/future data retention, legacy v24
pending compatibility, stale UUID/generation protection, and a separate JVM
holding the actual production file lease.

Postcommit controls throw after durable ready bytes, fail their first readback,
and fail exact predecessor withdrawal. Exact ready/model verification returns
committed success; an unreadable outcome has a distinct recovery-required error.
Idle cache controls mutate the model from another repository, cancel/replace the
authority, delete/reuse identity, and corrupt or advance the model schema. Cached
results bind both authority/identity and the exact verified model bytes.

```sh
python3 tests/environment-intent-host/run.py --json-jar /path/to/json.jar \
  --java-home /path/to/jdk17
```

The runner writes `work/environment-intent-host/results.json`, including exact
check names, count, scope and hashes of all compiled inputs. Actual Android storage
and production deletion/reuse are covered separately by
`tests/gecko/EnvironmentIntentIntegrationActivity.java`.
