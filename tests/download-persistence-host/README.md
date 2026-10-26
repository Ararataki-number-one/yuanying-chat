# Download persistence fault checks

`run.py` extracts the actual production `FileDownloads` UI callbacks and their
storage boundary, and compiles the complete production task, publication and
recovery classes against the existing explicit host Android/provider adapters.
Its fault model includes permanent `commit(false)` after preference memory has
changed, a throwing storage write, failed pending cleanup, and an external
provider publication whose final metadata commit fails.

The same 39 checks run against `--before-ref da5004111eaf3e20322ca1fca3f756db82f44c90`
or the current source. Progress faults first append real host bytes and make the
next progress checkpoint due, so an unchanged-record optimization cannot skip
the injected write. Exceptions escaping the real host UI queue are recorded;
the baseline is expected to fail, rather than relabelling that run as a pass.

The provider is a host file model, not an Android `DocumentsProvider`. These
checks do not establish phone behavior, UI rendering, or performance. If storage
remains unwritable, the paused task remains unconfirmed; a durable restart cannot
be promised until a later commit succeeds. Source files and unresolved target
information are retained without claiming a file was saved.

```sh
python3 tests/download-persistence-host/run.py --json-jar /path/to/android-json.jar --java-home /path/to/jdk17 --output /path/to/after.json
python3 tests/download-persistence-host/run.py --json-jar /path/to/android-json.jar --java-home /path/to/jdk17 --output /path/to/before.json --before-ref da5004111eaf3e20322ca1fca3f756db82f44c90
python3 tests/download-persistence-host/sql_indexes.py --output /path/to/sql-indexes.json
python3 tests/download-persistence-host/pending_viewer.py --json-jar /path/to/android-json.jar --java-home /path/to/jdk17 --output /path/to/pending-viewer.json
```

`sql_indexes.py` separately executes the production DDL and upgrade thresholds
in real host SQLite. It checks schema 1/2/3 to 4 migration, row preservation,
nonunique index definitions, actual query plans/results, and transaction rollback.
This does not execute Android `SQLiteOpenHelper`, reduce the number of history
queries, or establish phone frame-time gains. Full-history prune, serialization
and synchronization remain separate work.

The existing 42 recovery checks and 37 continuation/retirement checks retain
their original cases and thresholds. Their adapter only gained the actual new
storage-boundary methods, the associated field, and a nonexecuted viewer stub.

`pending_viewer.py` separately invokes the actual `taskActions` button callback
and all `openSaved` overloads on a host UI queue. Its 28 checks cover successful
launch, a missing viewer, and denied permission for ordinary files, PDFs and
images. Unconfirmed targets keep their pending metadata and real host source
bytes, and never claim to be saved; confirmed files retain their existing
missing-viewer message. The viewer and permissions are host injections, not
Android or actual provider validation. The original 39/42/37 checks are unchanged.
