# CPU environment deletion boundary

```sh
python3 tests/gecko-cpu-host/cleanup.py --java-home "$JDK17" \
  --output work/cpu-cleanup.json
```

The runner extracts the complete actual current `slot>0 / else` private cleanup
branch and recursive `erase` method from `EnvironmentDeleteActivity`, without
replacing their logic. It also compiles the full current `EnvironmentBrowserData`.
Real temporary directories contain stale and malformed opaque CPU sealed files,
all fourteen earlier private record names, startup/runtime and transfer leftovers,
other-environment CPU records, shared data and saved downloads. Both slot zero
and the existing slot-N path execute against this filesystem.

The Context path and sealed-file remove operations are explicit adapters. There
is no Keystore/decryption operation here. Activity/process shutdown, catalog
ownership and the rest of the deletion transaction are tested elsewhere.

Four mutations of the actual extracted source must compile and then fail real
filesystem assertions: omitting CPU, skipping private cleanup, selecting the
wrong slot branch, and deleting another environment. Reports bind source,
extracted method and compiled adapter hashes. No Android, native CPU or AES
execution is claimed.
