This suite executes the actual origin adapters used by four Gecko integration
fixtures after the production page driver began requiring the top frame and
the exact ChatGPT origin.

The original fixture source files come directly from immutable commit
`72e3bcac55285fea483e612ba4481f7e073a5422`, with pinned complete-file SHA256
checks. They are negative controls. The current methods and constants always
come from the actual tracked `tests/gecko` files. No preview or reconstructed
source tree is used for current execution.

The runner extracts complete Java methods, compiles them with the real Android
`ValueCallback` interface, and captures the JavaScript passed through explicit
app/Gecko facades. JSDOM then executes those captured scripts in documents and
real subframes. The callback facade supplies synthetic JSON only to drive
script generation; it does not establish Android or Gecko behavior.

The controls cover the performance fixture's separate historical/current asset
guards, completion polling, compact reload expected URLs in both normal and
slash-escaped JSON, and the fingerprint followup's exact HTTPS source URL.
Wrong host, port, scheme, subframe and expected document remain rejected. The
historical performance assets are checked against their existing `source.json`
byte counts and hashes and remain unchanged.

Run each JSON implementation separately:

```sh
python3 tests/runtime-origin-adapter-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --android-jar work/cloud-setup/platform/android-35/android.jar \
  --jsdom-module work/chat-smoothness-deps/node_modules/jsdom \
  --output work/runtime-origin-adapter-current/desktop.json
```

Use `work/profile-host/android-json.jar` and a different output filename for
the Android JSON implementation. Reports record source, extracted-member,
generated-host, baseline and dependency hashes. This is a JVM/JSDOM fixture
test, not Android, Gecko, HTTP, account or release acceptance.
