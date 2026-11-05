# Production Gecko web TLS acceptance

This diagnostic exercises the actual `MainActivity` → `ChatSession` → `GeckoWebView` cold-start path. It does not replace the existing standalone native capability probe or qualify a release. A new immutable source must build and pass this diagnostic before its observations can be assessed. The later formal release still requires its complete same-source CI attempt and other browser, CPU, IP/timezone and combined-policy gates.

The setting covers **Gecko web connections** in the selected environment's Gecko runtime and the persistent Service Worker fetch specifically measured here. It does not cover the app's independent downloader, connection checks, proxy entrance Java/other TLS stacks, System WebView, arbitrary TLS fingerprints, HTTP/2 transport or QUIC. Offering `h2` in ALPN and reading H2/H3 preferences do not prove H2 transport or QUIC.

The desired sidecar supports `default` and `tls13`. Default uses the actual current kernel defaults without a hardcoded range. The strict cold snapshot requests native DEFAULT/effective minimum and maximum 4/4, with no TLS USER overrides. Saving through the production UI only changes desired state for a genuine future cold start; it must not modify the active runtime or navigate the current page.

## Fixed workloads

The ordered immutable contract is `tools/gecko/tls_acceptance_server.py::CASE_SPECS`:

| Original JSON | Product action and required independent observation |
| --- | --- |
| `case-default-tls12.json` | Cold default environment reaches the TLS1.2-only peer. |
| `case-strict-tls12.json` | Cold strict environment gets exact native security category 2 / SSL code 34 at the requested URI; actual ClientHello and peer OpenSSL protocol rejection, no HTTP. |
| `case-strict-tls13.json` | Same strict runtime reaches a fresh TLS1.3-only peer with exact native start/location, nonce title, trusted native leaf and HTTP receipt. |
| `case-pending-default-tls12.json` | Actual `GeckoTlsUi.saveDesired(default)` first preserves the PID/runtime, URL/navigation/connection/load counters and task snapshot. A separate explicit browse then still fails against a fresh TLS1.2-only peer under the old strict boot. |
| `case-restored-default-tls12.json` | Same profile and desired UI revision, true process cold start, old nonempty USER 4/4 seeded before bootstrap: production reconciliation removes the two old keys and TLS1.2 succeeds. |
| `case-rfp-strict-tls13.json` | Strict TLS1.3 success with a fresh typed strong-RFP readback; RFP is not lowered. |
| `case-persistent-before.json` | Strict HTTPS origin registers a stable Service Worker and measures its own nonce-bound TLS fetch, separately from page and script-download connections. |
| `case-persistent-after.json` | Same origin/profile/registration across true cold stop; existing registration, a new worker instance nonce, and a new independent TLS worker fetch. |
| `case-concurrent-strict-tls13.json` | Environment1 strict runtime remains alive. |
| `case-concurrent-default-tls12.json` | Environment2 default runtime succeeds on TLS1.2 with distinct UUID/process/runtime ownership while environment1 remains resident. |
| `case-concurrent-strict-resample-tls12.json` | Original environment1 process/runtime still rejects TLS1.2 after environment2 is alive; both PIDs checked again. |

Each case has a fresh nonce and controlled authority port; the persistent pair deliberately retains its exact HTTPS origin. No request is forwarded upstream. The peer captures the original bounded ClientHello handshake and reparses it independently. Tickets are disabled, PSK/resumption is refused, randoms must be distinct, and ALPN offers remain available within each independent RFP policy.

The protocol-rejection evidence is an actual ClientHello, actual peer `SSLError: UNSUPPORTED_PROTOCOL` and exact native error URI/category/code. It does **not** claim that a raw fatal-alert packet was decoded. URL-less `onPageStop` and security callbacks remain explicitly marked as lacking their own URL; stop callbacks cannot certify document completion. Success additionally requires exact start/location/nonce title and independently bound server HTTP.

## Cold profile proof

The nonempty USER seed is test setup only. It uses the actual canonical `GeckoCpuProfile.storage()` anchor and `GeckoTlsProfile.withoutTls`, appending only the two owned TLS USER keys and retaining all other original bytes. The product boot separately records `remote.tlsBoot.preparation.evidence()`: actual pre-runtime before/after hashes and lengths, non-TLS bytes preserved, and the original CPU/closed-route config prefix preserved. Runtime `prefs.js` is allowed to change as Gecko flushes its own state; no whole-file post-runtime equality is invented.

The earlier standalone probe restored absent USER values and established the existing API/wire capability. It did not prove restoration of an original nonempty USER value or production per-environment behavior. This product case measures cleanup of old app-owned TLS overrides followed by actual default behavior, rather than claiming arbitrary USER-value restoration.

## Evidence and replay

The runner requires the selected clean source, exact installed APK/SDK identity, API35 emulator, four real guest CPUs and shell UID2000. It installs a temporary domain-scoped public CA for the controlled integration hosts and verifies the exact native leaf without a certificate exception. App data is integration-only and starts fresh; retained-profile cases do not clear that profile between their two measurements.

```sh
python3 tools/gecko/run_gecko_tls_acceptance.py \
  --adb ADB --serial emulator-5554 --apk EXACT_INTEGRATION_APK \
  --source EXACT_SOURCE --output NEW_EVIDENCE_DIRECTORY
python3 tools/browser/check_gecko_tls_evidence.py NEW_EVIDENCE_DIRECTORY \
  --source EXACT_SOURCE --apk EXACT_INTEGRATION_APK --output NEW_REPLAY_RECEIPT
```

The original directory has `results.json` and exactly the eleven `case-*.json` originals. For later standard publication the normalized summary is `gecko-tls-results.json`, with originals under `gecko-tls-evidence/`. A source-side `results.json` alias must be byte-identical to the normalized summary; it is not a second public original. Each device file is at most 262,144 bytes; the summary is at most 4 MiB. Unknown JSON, logs, directories, symlinks, private material, duplicate keys and nonfinite values are refused.

`verify_gecko_tls_evidence(directory, source, expected, reader)` executes the selected immutable validator, matches the original same-installed APK/SDK/source/tree/run/attempt, replays all eleven original packets and ClientHellos, and rechecks file bytes after validation. The server, contract, native/profile/controller/Store/Ui, assets, fixture and workflow source pins belong to the tested application source. A mutable release-tools revision cannot supply their behavior.

Cleanup stops and clears the integration app, removes the reverse mapping, closes all actual server connections and joins its thread set, removes the public CA and temporary private host material, and confirms shell UID2000. The final full socket snapshot is taken only after those cleanup boundaries. Late completed or failed sockets remain in the bounded original set.

Generic worker/SW coverage, whole-app TLS coverage, full TLS fingerprint emulation, QUIC and release acceptance remain false. The native status receipt and exact measured worker fetch are separate observations. The UI pending case records actual task-state equality; it does not claim that a real ChatGPT reply or user upload was running in the diagnostic.

## Offline controls

```sh
python3 tests/gecko_tls_acceptance_test.py --output HOST_CONTROLS.json
```

These controls use real host OpenSSL sockets plus explicitly modeled Android/process/SW/CA-install metadata to exercise parser, selected-source and late-callback boundaries. They do not execute Android, Gecko native preferences, real Service Workers or a product release. Store/Ui/controller/profile hosts and actual SDK compilation are separately reported. The diagnostic-only workflow is `.github/workflows/gecko-tls-acceptance.yml`, restricted to `diagnostics/gecko-tls-*` with `contents: read`; it has no publication step.
