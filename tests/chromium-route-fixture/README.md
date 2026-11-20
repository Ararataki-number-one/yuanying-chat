# Local Chromium device fixture

This instrumentation APK targets a debuggable `local.pocketchat` candidate on a disposable Android x86_64 emulator. Build and sign it with the same synthetic test key as that candidate's base and Chromium split. The test uses the installed Chromium classes rather than packaging a second engine.

```sh
bash tests/chromium-route-fixture/build-fixture.sh \
  "$VERIFIED_CEFRIUM_SDK_AAR" "$OUTPUT/fixture-unsigned.apk"
```

Run the installed-package checks in `tests/gecko/run_chromium_delivery.py` first. Those checks start offline with Android System WebView disabled. Before starting instrumentation, make an Internet-capable non-VPN default network available on the disposable guest. The fixture binds the installed APK hashes and nonce to the install receipt and opens Chromium through the normal app activity.

- Explicit HTTP, HTTPS, and SOCKS tests each start an upstream mock on 127.0.0.1. The mock opens no outbound sockets and accepts only a per-run reserved `.invalid` origin. Each mock records the exact HTTP CONNECT or domain-based SOCKS5 negotiation, then serves a unique HTTP page to Chromium. The page title and live renderer must match the mock's own observed request. The mocks reject escaped proxy credentials. The HTTPS proxy mock also requires an actual TLS handshake. The test uses a per-invocation JSSE trust store containing only the existing localhost fixture certificate. Production hostname verification remains active and the default context is restored.
- Each proxy test holds an incomplete response open, switches the environment to an unavailable VPN route, and requires the old upstream socket and Chromium browser to close. An independent private-address listener records any bypass during native and in-page request attempts and after the switch. Late navigation must stay blocked while the old mock remains observable.
- The direct test uses a Java-backed HTTPS page on a different reserved origin. It disables the guest's network and checks browser retirement and denied late navigation again.

```sh
adb -P "$TEST_ADB_PORT" -s "$TEST_SERIAL" install -t "$OUTPUT/fixture-signed.apk"
adb -P "$TEST_ADB_PORT" -s "$TEST_SERIAL" shell am instrument -w \
  -e runNonce "$NONCE" -e baseSha256 "$BASE_SHA" -e featureSha256 "$FEATURE_SHA" \
  local.pocketchat.chromiumfixture/.RouteFixture
```

Join the successful instrumentation transcript with the exact install receipt using `run_chromium_delivery.py join-renderer`. The debug receipt requires separate HTTP, HTTPS, and SOCKS evidence. The TLS handshake covers the HTTPS upstream proxy transport. The page origin carries HTTP, and the Java-backed direct page does not perform a network TLS handshake.

## VPN and built-in route

Build the x86_64 `bundleIntegration` candidate from the same clean commit and tree with the optional feature enabled. The app ID is `local.pocketchat.test`. Sign the installed base, Chromium split and instrumentation APK with the same synthetic key. Build the instrumentation APK with a third argument, `local.pocketchat.test`. Run on a disposable x86_64 emulator with API 33 or later. Disable System WebView and confine guest traffic to its test environment. Pass the exact installed base/feature byte hashes, the clean build's commit and tree, and the isolated run nonce.

```sh
adb -s "$TEST_SERIAL" shell appops set local.pocketchat.test ACTIVATE_VPN allow
adb -s "$TEST_SERIAL" shell am instrument -w \
  -e fixtureMode vpn -e sourceCommit "$SOURCE_COMMIT" -e sourceTree "$SOURCE_TREE" \
  -e runNonce "$NONCE" -e baseSha256 "$BASE_SHA" -e featureSha256 "$FEATURE_SHA" \
  local.pocketchat.chromiumfixture/.RouteFixture
adb -s "$TEST_SERIAL" shell am instrument -w \
  -e fixtureMode internal -e sourceCommit "$SOURCE_COMMIT" -e sourceTree "$SOURCE_TREE" \
  -e runNonce "$NONCE" -e baseSha256 "$BASE_SHA" -e featureSha256 "$FEATURE_SHA" \
  -e coreSha256 "$MIHOMO_LIB_SHA" local.pocketchat.chromiumfixture/.RouteFixture
```

The VPN lane reuses the app's existing non-forwarding TUN fixture. It matches a CEF-mediated TCP attempt to an IPv6 benchmarking-only address and a per-nonce port on the selected full TUN. It stops that exact generation and observes the descriptor close, active network change, browser retire, and late request denial. The shell-prepared consent state does not measure user consent UI. The TUN fixture does not serve a page or forward packets.

The built-in route lane starts the app's existing authenticated entry and fixed exit on its real local core. The integration-only fixed-exit mock maps one nonce-bound reserved origin and port to an owned loopback HTTP server. The active native core, generation, route serial, installed core checksum, authenticated circuit counters and observed DOM must agree. The test stops the core while an upstream socket is open, confirms socket and browser closure, and denies late navigation. The hook never changes production destination rules.

Public server traffic, physical devices, application-level module download, Android installer confirmation, and original release-signer verification require their own evidence.

## Files and profile state

Use a fresh English-language disposable emulator and the same integration base, Chromium split and signed fixture as above. After installing them and disabling System WebView, pass the matching receipt inputs and a fresh 32-character lowercase hexadecimal nonce. `TEST_ADB_PORT` can select an existing dedicated ADB server. The runner requires an explicitly selected emulator serial and saves all three Android transcripts.

```sh
TEST_SERIAL="$TEST_SERIAL" SOURCE_COMMIT="$SOURCE_COMMIT" SOURCE_TREE="$SOURCE_TREE" \
  NONCE="$NONCE" BASE_SHA="$BASE_SHA" FEATURE_SHA="$FEATURE_SHA" \
  bash tests/chromium-route-fixture/run-files-profiles.sh "$OUTPUT/chromium-files-profiles"
```

- The files check opens a non-default environment through the real app entry point. A Chromium tap opens Android DocumentsUI and selects synthetic text from Android Downloads. The originating page must read the exact name and contents. Chromium then downloads a generated PDF and a Word OOXML document. The app's saved-file index and Android content URI must identify the correct owner, name, MIME type and exact source bytes.
- The profile check writes distinct persistent HTTP-only cookies and local storage values at a single reserved origin in two environments. It confirms clean storage before seeding. The runner force-stops the app, checks that a new Chromium host process opens the same two native profiles, and requires each request's cookie and the page's storage value to match its original environment.

All content is owned by the fixture at a reserved `.invalid` origin behind the loopback proxy. These checks cover the Android file selection handoff and same-install process restart. A real account, a public-site upload, physical devices and replacement by a newer APK require separate validation.
