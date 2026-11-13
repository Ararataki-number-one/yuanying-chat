# Gecko TextureView surface lifecycle

This host compiles the **complete current `GeckoTextureSurface` production class**.
It keeps content notifications distinct from the availability, size and retirement
of the Android surface supplied to Gecko. It does not pause a view, a session,
rendering, or any application task.

The fixed Gecko 157 wrapper creates a new `Surface` and calls
`Listener.onSurfaceChanged` for every `onSurfaceTextureUpdated`. The original
causal case sends 12 content notifications with unchanged texture and dimensions:
it observes 12 extra allocations and 12 extra surface notifications. The adapter
case still presents every content notification at the declared Android boundary,
while preserving real resize, texture replacement and destruction callbacks.
Gecko's explicit `requestNewSurface` recovery is also retained: the current
production and caret-fixture overrides record one pending replacement and call
the original SDK method. That method still posts the visibility change; the
next valid content update creates a new Surface even when texture and dimensions
are unchanged. Size callbacks keep the request pending because the fixed SDK
forwards its old Surface for a resize. Real availability satisfies the request.

`fixtures/SurfaceViewWrapper.java` is the **entire unmodified official file**,
including its MPL-2.0 notice, from the source archive already pinned by
`third-party/sdk/geckoview-157.0.1-official.json`. Its provenance, source digest and
actual runtime class digests are recorded beside it. The fixture supplies no new
SDK implementation and is never packaged into the app. `stubs.py` declares the
Android/graphics boundary and `MagnifiableSurfaceView` constructor boundary; it
does not model Gecko compositor rendering or timing.

The complete public `GeckoView.requestNewSurface` method is a separately pinned
source fragment with its MPL notice. `RecoveryHost` executes it with the verbatim
current application/caret overrides and the actual SDK wrapper in strict mode.
The surrounding `GeckoView`, View posting and visibility behavior remain declared
boundaries; it does not execute the real GeckoView class or Android event loop.
Normal destruction models Android's listener-before-release/clear order. The
separately labelled direct adapter reentry case is synthetic, and does not claim
that Android permits rebuilding a TextureView inside its destruction callback.

Default maintenance execution needs the existing JDK and JSON dependency:

```sh
python3 tests/gecko-texture-surface-host/run.py \
  --java-home /path/to/jdk-17 \
  --json-jar /path/to/json.jar \
  --output /path/to/texture-surface.json
```

The full host gate additionally requires the **actual derived SDK bytecode**:

```sh
python3 tests/gecko-texture-surface-host/run.py \
  --java-home /path/to/jdk-17 \
  --json-jar /path/to/json.jar \
  --output /path/to/texture-surface-actual-sdk.json \
  --require-sdk
```

Strict mode uses `work/native-caret-sdk/geckoview-caret.aar` and its adjacent
`sdk-build-receipt.json` by default. It verifies the selected runtime manifest,
receipt, AAR and extracted `classes.jar`; no download or fallback occurs. Existing
dependency preparation can instead pass `--sdk-classes /path/to/classes.jar` and
`--sdk-receipt /path/to/sdk-build-receipt.json`. In that mode the complete JAR must
still match both receipt and selected manifest. The receipt's build source is
reported separately from the current application source. It is valid to reuse an
identical, receipt-bound SDK built at an earlier application commit.

Both modes compile and execute 41 lifecycle cases, 19 recovery cases and fifteen
compiled semantic mutations (thirteen adapter mutations and two actual hook
mutations). Strict mode omits the complete SDK wrapper source fixture from compilation
and checks that no replacement `SurfaceViewWrapper` class was emitted. Its causal
case and the production adapter execute the actual pinned wrapper bytecode. The
JSON report records source/dependency digests and verifies unchanged inputs. The
original SDK recovery method and its anonymous Runnable are additionally tied to
the selected actual class hashes in the provenance file.

This is JVM behavior evidence, **not Android/GPU execution, a native compositor
test, or device idle acceptance**. The API 32/35 device gate retains its original
frame budget and remains the end-to-end check for the complete rendering chain.
