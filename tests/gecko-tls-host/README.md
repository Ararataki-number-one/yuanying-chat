# TLS desired-state host

Runs the complete current GeckoTlsSpec and GeckoTlsStore with real files, FileLock, thread races, independent JVM restart and concurrent-process CAS. Android Context/catalog/vault are explicit fault-injectable host adapters; encryption and Keystore are not exercised. Two modes only: kernel default and TLS 1.3 only. Missing files default to kernel policy, without inventing a numeric range.

The stored sidecar is desired-only. Native DEFAULT/USER readback and actual TLS handshakes are separate product gates, never granted by these tests. Owner reuse, generation changes, stale revisions, corrupt bytes, write failure and current-revision transaction races are covered.

Run `python3 tests/gecko-tls-host/run.py --java-home JDK17 --json-jar REAL_JSON_JAR --output REPORT.json`.
