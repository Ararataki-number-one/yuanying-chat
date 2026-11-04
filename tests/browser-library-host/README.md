# Universal browser library checks

The complete production `BrowserLibrary`, `BrowserAddressPolicy` and `J` execute
against real JSON libraries. Explicit Android preference adapters provide two
separate contexts; this verifies use of the supplied environment store without
claiming to execute `ProfileContext`, Android storage, a browser or networking.

```sh
python3 tests/browser-library-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/browser-library-host/jvm.json
```

Repeat with `work/ux-build-deps/android-json.jar`. Source hashes bind each report
to the complete classes and test inputs actually executed.
