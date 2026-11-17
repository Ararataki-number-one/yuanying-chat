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
guards, retired completion commands, compact reload expected URLs in both normal and
slash-escaped JSON, and the fingerprint followup's exact HTTPS source URL.
Wrong host, port, scheme, subframe and expected document remain rejected. The
historical performance assets are checked against their existing `source.json`
byte counts and hashes and remain unchanged.

The immutable before completion method still emits its original four bridge
calls. Its origin-refusal negative control uses the exact final 2.1.7 production
page driver from 5bf46502f37ffe8f3c6f17054a2a7c9ec7d53df5, frozen byte-for-byte
in fixtures/completion-driver-2.1.7.js. Its adjacent source receipt pins the
commit, tree, blob, byte count and complete-file SHA256; the receipt itself also
has a fixed SHA256. This introduces no Git history fetch during execution.
The current driver rejects the removed poll and latest
commands before any DOM/origin inspection, so it cannot reproduce that retired
polling failure. The after method emits its actual two rejection calls and
uses only current driver bytes. Its receipt checks no task/service, while JSDOM
independently verifies rejection without DOM reads, draft changes or scheduled
work, including exact-origin and foreign documents and real subframes.
Current page-state origin, expected-path and subframe guards remain exercised
by the performance, compact and fingerprint captures.

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
