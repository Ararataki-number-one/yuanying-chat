This fixture compiles and executes the production `ResourcePressureController`.
`ActivityManager`, its `MemoryInfo`, typed `Context` lookup, and `SystemClock` are
explicit JVM doubles. Values describe test inputs, not measured Android memory.

Checks cover API field provenance, missing/failed/invalid observations, fresh and
stale pressure, monotonic-clock rollback, existing runtime and genuine recovery
priority, optional warmup, and separate request/creation counters. The test does
not start Gecko, exercise Activity lifecycle, prove physical capacity, or authorize
session disposal. Android admission and unchanged-login tests remain separate.

Run with Java 17 and an explicit JSON-java jar:

`python3 tools/gecko/run_resource_host_checks.py --json-jar /path/to/json.jar`

The runner preserves failed reports, enforces the exact literal checklist, and
records hashes of every compiled production/double/test input and its runner.
Dirty development sources are reported honestly and cannot be used as clean-source
release evidence. Output defaults to `work/resource-pressure-host/results.json`.
