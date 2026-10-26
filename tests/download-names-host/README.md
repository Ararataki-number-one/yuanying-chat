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

This does **not** execute Android SQLite, Android layout, a phone or frame timing.
The query-count result concerns the selected actual production method calls,
not the total SQL or visible speed of the entire app. Existing original policy
tests and controlled Android release checks remain separate.
