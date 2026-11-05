# Chromium fingerprint policy storage host controls

`run.py` compiles the complete production store, `EnvironmentSpec`, and `J`
against the supplied JSON jar. The aggregate runs it once with desktop JSON and
once with Android JSON. Each invocation starts independent JVMs over shared
temporary fixture files to check that a persisted receipt cannot become current
after process restart, including when the same provider/view binding is activated.

The workload covers concurrent compare-and-set saves, environment identity and
generation changes, stable random seeds and explicit rotation, strict bounded
payloads, failed reads/publications, and receipt retirement/reactivation. It uses
real JVM `SecureRandom`, files and file locks. Context, catalog transactions and
the sealed-file boundary have explicit test adapters; these checks do not execute
Android, SQLite, AES-GCM, Android Keystore, AtomicFile, Chromium, or webpage
fingerprint behavior. The report records production and adapter hashes and exports
no seed or raw stored receipt.

```sh
python3 tests/chromium-fingerprint-store-host/run.py \
  --java-home /path/to/jdk-17 --json-jar /path/to/json.jar \
  --output work/chromium-fingerprint-store-host/results.json
```
