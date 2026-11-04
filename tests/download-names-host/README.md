# Download refresh environment-name query audit

This executes the exact selected production catalogue reads, `Profiles.display`,
`DesignDownloads.Controller.apply`, and `Row.bind` methods, with explicit counted
SQL/cursor and deterministic widget adapters. The complete production
`DownloadListPolicy` is compiled without replacement.

The paired audit pins published 2.0.20 (`da50041`) and one name-projection change.
It verifies query API invocation counts for 1/100/1000/10000 rows, fresh names on
the next refresh, empty and unknown names/slots, duplicate identities/slots,
filters, row identity reuse and the existing anchor calculations. Empty or fully
filtered data does not read names. The candidate projects only `slot,name` and
records that read with `UiPerfStats.catalogRead`.

```sh
python3 tests/download-names-host/run.py --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar --before-ref da5004111eaf3e20322ca1fca3f756db82f44c90 \
  --output work/download-names-before.json
python3 tests/download-names-host/run.py --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar --output work/download-names-after.json
```

The audit also reverses the small projection/label substitution and compares the
remaining UI/catalogue source bytes to that pinned baseline. This is a scope
check for this paired change, not a new permanent release gate. Future deliberate
UI/catalogue changes require reviewing that comparison rather than treating an
old source snapshot as a universal product specification.

For 2.1.0, `reviewed210-scaffold-inverse.json` records three exact bounded
UI-scaffold changes between source `856e7ccbb8f032d5ced7b01c6f43884f9d61a4b7`
and original candidate2 `5900426428e00a95acf5126f6154f34ff2d46930`, including
commit/tree/file hashes. The restored original file hash is exactly the existing
reviewed46 manifest's approved hash. This test-only projection removes the
reviewed search/collection/read-gate scaffold before the untouched reviewed46,
reviewed38 and four original whole-file preservation checks run.

The compiled `apply`, `bind`, text/visibility and time-label methods still come
from the actual current production source. Their complete bodies are pinned
and asserted byte-identical before/after scaffold projection; the generated
Java host never uses projected behavioral methods. Reports include source,
method, fixture and adapter hashes. New negative controls reject mutations to
each current tested method, changed/duplicated scaffold, manifest tampering,
and unknown unrelated source through the original whole-file guard. Existing
historical mutation/duplicate controls and all 44 case bodies are preserved.

Both desktop and checked-exception Android JSON implementations run with JDK17.
Only host case declarations and strict JSON construction adapters are adjusted
for checked exceptions; failures still fail the checks. The paired 44/44
baseline/current audit retains one projected owner-label query for 1/100/1000/
10000 current records, versus the original per-row historical queries.

This does **not** execute Android SQLite, Android layout, a phone or frame timing.
The query-count result concerns the selected actual production method calls,
not the total SQL or visible speed of the entire app. Existing original policy
tests and controlled Android release checks remain separate.
