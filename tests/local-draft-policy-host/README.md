# Local draft policy host regression

Run with JDK 17 and either supported `org.json` implementation:

```sh
python3 tests/local-draft-policy-host/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar \
  --output work/local-draft-policy-results.json
```

This compiles the complete production `LocalDraftPolicy`, `PageMemory`,
`DraftArchive`, and `BrowserSessionStore` classes, plus the exact production
`AppPrefs.enabled/apply` and `GeckoWebView.restoreCheckpoint` methods. It uses
controlled Android, SQLite, and Gecko adapters, actual JVM workers, and temporary
files. It does not establish Android SQLite/AtomicFile durability, native Gecko
restoration, a real webpage result, or preservation of a real logged-in account.

The failure reproduction can select the pre-fix production `PageMemory` and
`DraftArchive` classes without replacing their implementations with a model:

```sh
python3 tests/local-draft-policy-host/run.py \
  --before-ref a7f1d7410ff0b7e9e0f97ff3ab8a71420408d7c7 \
  --json-jar /path/to/json.jar
```

That mode should fail its two disabled-policy assertions while its two sanity
checks pass. Every report records the selected immutable class hashes, the
current fixture/adapters, and whether execution inputs changed during the run.
The default current-code mode must pass all assertions. CI must invoke this
runner explicitly; placing the directory here alone does not run it.
