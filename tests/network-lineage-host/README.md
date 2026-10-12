# Unconfirmed network transition lineage

Run:

```sh
python3 tests/network-lineage-host/run.py --json-jar /path/to/json-20240303.jar --java-home /path/to/jdk
```

Twenty-six controlled checks exercise the production pending-record logic when a
newer candidate is validated against an older transition's unconfirmed write.
Only the exact transition, generation and before/after hashes can rebase the
newer candidate after the active configuration has really been restored. The
chosen configuration, both provider snapshots, references and save order remain
unchanged. Independent candidates, missing lineage, replay, and failed atomic
publication are covered. Pointer cleanup also proves that completion of an older
apply cannot delete a newer desired route, while exact cancellation removes both
owned payloads and preserves the active connection configuration. Use
`--output /path/to/receipt.json` to choose the receipt destination.

This is host-only metadata and plain atomic-file storage evidence. It does not
prove Android encryption, real browser sends, native traffic or real-world
network speed. The Android safe-idle integration suite covers the live webpage
intent and transition boundaries separately.
