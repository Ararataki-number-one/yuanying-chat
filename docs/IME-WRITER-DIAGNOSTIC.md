# Diagnostic witness for the unresolved caret rollback

This isolated review branch starts at `1f970ea51f90466fb69fc282692ecb535c38ce64`.
It creates a **tainted integration APK**, never a production APK or candidate.
Its output always declares `diagnosticOnly=true` and `releaseAcceptance=false`.

The frozen normal failure delivered every character of `-user-typed` in order.
Between `t` keyup and `y` keydown, the DOM caret moved from 29 to 28 in nine
milliseconds without a text change. The writer remains unidentified. A passing
diagnostic attempt cannot explain that failure or establish a fix.

The pinned official SDK is `157.0.20261005135250`, Firefox 157.0.1, release
revision `737ec77d798755890b062aab541a90d6c75afd19`. Its `IMEHandler` logging in
`GeckoEditableSupport.cpp` is compiled out outside NIGHTLY builds. Java
`GeckoEditable.LOGGING` is also disabled in release. The supported runtime API
is `configFilePath`, whose YAML accepts `env`; the production wrapper supplies
and rewrites an explicit configuration file, so a default `/data/local/tmp`
debug YAML cannot instrument this runtime. Release-active `IMEContentObserver`
logs can expose selection requests, but do not identify Java outgoing ranges
and ACKs. Android system IME traces do not record write-method arguments.

The diagnostic tool SHA-verifies the official AAR, sources JAR, classes JAR and
GeckoEditable source before compiling that one Java class family. It enables
only existing log blocks, routes their messages to `PocketSDKIME`, and adds
observations immediately before both existing `onImeReplaceText` calls, at
native ACK, and at the accepted native selection callback. `DEBUG=false`,
the original range predicate, InputConnection, Editable proxy, listeners,
delegates, handlers and native libraries remain unchanged. Compilation checks
original Java/native descriptors and every other AAR archive entry. All APK
native SDK bytes are independently compared with their original receipt.

Log records include sequence, uptime and thread identity. Outgoing records
include actual start/end, action identity, length and one-character code.
Existing logs retain action offer/reply, native text and selection callbacks.
The activity adds a clock read to its existing pre-input snapshot; it adds no
event listeners or composer writes. The runner retains the original tap, one
full `adb shell input text` burst, readiness timing and exact marker/draft
oracle. Both previous observer modes stay disabled.

The Gradle override accepts exactly `:app:assembleIntegration`, requires the
receipt's external SHA and current clean source/tree/script identity, and
rejects release tasks. Normal official SDK verification is unchanged and
rejects the transformed AAR. The installed APK stamp must match the receipt
before diagnostic execution; the activity rejects a tainted SDK invoked as
ordinary performance acceptance.

The source-branch-specific `gecko-ime-writer-diagnostics.yml` uses the current pinned
toolchain and emulator preflight. It performs one trial, keeps failure status
and all evidence. A fixed allowlist preserves raw synthetic text/JSON/screens
under `debug/gecko-ime-writer-evidence-1f970ea`, with an exact source first
parent, immutable run path and SHA manifest. It never publishes an APK, AAR,
class file, key, browser profile or shared candidate-artifact branch. Actions
upload is secondary. Repeated workflow attempts are rejected.

After review, this push triggers the single diagnostic trial:

```sh
git push origin review/ime-writer-diagnostic-1f970ea
```

Inspect the retained input shape before interpreting SDK logs. The required
witness is a reproduced rollback with the original 45-event path, linked to
the outgoing range/action and native callback sequence. A different input
route or a passing attempt is diagnostic evidence only. Chinese composition,
Baidu IME and the physical phone complaint remain untested by this fixture.
