# Download continuation and partial retirement regression

Run with JDK 17 and either supported JSON implementation:

```sh
python3 tests/download-resume-host/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar \
  --output work/download-resume-results.json
```

The suite executes complete production task, revision, continuation, range and
publication helpers plus exact selected `FileDownloads` methods. It uses real
JVM worker threads, file leases and synthetic files, with controlled Android,
SQLite, UI, Gecko-response and HTTP adapters. It executes production
`acceptResponse`, `download`, `readChunk`, `pause`, and `destroy`; this is not an
actual Android Activity lifecycle or a native Gecko/network execution.

The native-response test holds an actual production writer in a controlled
blocked read, calls production `destroy` (and its `pause`), lets a new instance
claim the paused task, and confirms retirement waits for the old writer's lease.
The range-reset race blocks the original header callback, retires the selected
nonreusable file, and verifies the late reset cannot recreate it. Normal HTTP
206 append and HTTP 200 restart controls retain their byte-level assertions.

For the original inaccurate menu text, execute the immutable prior
`taskActions` method with the same controlled UI adapter:

```sh
python3 tests/download-resume-host/run.py \
  --before-ref 2c5a92a328e073afdb5ca2033ee0bb537506c6b9 \
  --json-jar /path/to/json.jar \
  --output work/download-resume-before.json
```

The old native-response, complete-file and unknown-row labels should fail;
its Range continuation label should pass. Reports pin exact selected method and
input hashes. The prior 42 download recovery checks remain a separate required
suite. CI must invoke this new runner explicitly.

This change does not infer that a later webpage response is the same download.
The user explicitly selects and confirms retirement of one incomplete private
copy; later responses are independent tasks. Automatic attempt matching,
state/age batch cleanup, real-device behavior and native-Gecko acceptance remain
outside these host checks.

Two further negative controls substitute only immutable original production
writer methods into the current retirement harness:

- `--before-writer-ref 2c5a92a`: the original `acceptResponse` fails the check
  that the retiring worker is blocked inside the real partial-file lease while
  the old response read remains blocked. This observes the actual worker stack
  and uses barriers, not a sleep-based timing guess.
- `--before-range-ref 2c5a92a`: the original `download` appends a 206 response
  after a controlled prior writer changes the partial length; the current
  method rejects this stale range basis after acquiring the lease, preserving
  the old bytes. The prior tail writer here is an explicit filesystem adapter;
  the HTTP download and Range validation are production methods.

These two controls explain protections needed by the new explicit retirement
flow; they do not claim the old release already had that new cleanup operation.

`--before-load-ref 2c5a92a` substitutes the original `loadTask` and invokes a
previously opened Continue saving callback while a different selected task is
retiring. Both protections should fail with that old method. The current guard
keeps the original task/generation, finishes its cleanup, and preserves the
unrelated complete file.
