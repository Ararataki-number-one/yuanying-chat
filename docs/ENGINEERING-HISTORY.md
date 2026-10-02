# Build

Source: Java + Android SDK 35, min API 26. Run build.ps1 with PowerShell on Windows. It expects JDK 17, Android build tools and platform folders under workspace/work/android-tools/{java,build,platform}. Dependencies are bundled in libs and app/src/main/jniLibs. The signing key is generated locally under work/android-test/private and is intentionally not distributed. A locally regenerated key cannot update an existing installation signed with another key.

Default builds PocketChat-1.5.0.apk (versionCode 26). -Test builds the separate local.pocketchat.test package and fixtures. -Development enables local WebView inspection; neither mode is used for the delivered release. The source snapshot contains no private account or network configuration.

`-ToolsRoot <path>` optionally reuses an existing android-tools directory. Retain the original signing key under workspace/work/android-test/private/local-test.jks when building an in-place update. No signing key is included in the source distribution.

## Webpage reply observation (1.2.2)

WebReplyObserver.java installs an origin-scoped, main-frame WebMessage listener. web-reply-observer.js watches trusted send-button clicks and Enter key events. It never fills, clicks, prevents a website event, submits, or retries. A trusted form-submit event alone is deliberately ignored because JavaScript requestSubmit() can generate one.

Only one new stable message identity matching the observed gesture can confirm a request. Confirmed requests use the existing persisted polling, foreground service and notification flow. Stop gestures suppress success notifications. Unconfirmed requests lose automatic binding after page/process reload and require manual review. Repeated text, old history, missing identities, errors, wrong conversation routes and duplicate notifications are covered by isolated Android WebView tests.

Run the test build only in its separate test package; its fixtures intercept the ChatGPT origin locally and do not contact an account. Added activities: WebReplyTestActivity, WebReplyBackgroundTestActivity and WebReplyRecoveryTestActivity. The result files record actual checks. Production remains non-debuggable and has no test activities.

Mihomo v1.19.31 is bundled as an unmodified executable for Android arm64 and amd64, under GPL-3.0. Upstream: https://github.com/MetaCubeX/mihomo/tree/v1.19.31 . Corresponding upstream source is included in third-party/source/mihomo-v1.19.31.tar.gz; license text in third-party/licenses and the APK assets. Other bundled libraries retain their notices in the license folder. Android binaries use upstream release assets mihomo-android-arm64-v1.19.31.gz and mihomo-android-amd64-v1.19.31.gz.




The optional -Personal build uses a local private preset packer and includes personal network credentials in the APK. That APK is for the owner only. The source distribution and normal build contain no such preset. First use imports the preset into Android Keystore storage; existing saved settings are preserved.


## 元婴期院士 1.3.0 webpage performance

The Android application label, local reader title, settings and waiting notifications use 元婴期院士. Package local.pocketchat, databases and key aliases remain compatible with existing installations.

Web mode uses a persistent read-only driver, lightweight status reads and a MutationObserver cache that re-serializes changed messages. It exchanges incremental updates with WebTranscriptMirror; it does not remove website elements or apply third-party layout overrides. Simple mode continues to use the original full transcript reader.

WebTranscriptStore coalesces snapshots independently per conversation, serializes and writes SQLite records on one low-priority worker, and invalidates superseded saves. Old background snapshots cannot overwrite a newer simple-mode snapshot. The local reader loads on demand and replays deferred messages when reopened.

WebPerfStats is disabled in ordinary use. WebPerformanceBenchmarkActivity enables aggregate counters and frame-interval sampling in the isolated test package. Response sizes are UTF-16 character counts of the WebView callback, not network byte measurements. Fixtures do not contact a real ChatGPT account.

## 元婴期院士 1.3.1 webpage entry speed

Cold startup first restores the remembered entry and verifies its exit through HTTPS. A successful check replaces the redundant generate_204 probe for this path. Probe groups are initialized on demand. If the remembered route fails, at most four complete-chain probes run concurrently, and the first healthy candidate whose fixed exit is verified can release the webpage. Other probes are cancelled; the search is bounded to 45 seconds (an in-progress exit check retains its own timeout). An exit-IP mismatch aborts immediately. Manual scans still measure all entries; existing health checks, route scoring and fixed-exit safeguards remain in place.

Page commit and a read-only composer/content readiness signal wake the existing polling flow. During the initial ten seconds, fallback status checks run at 250ms; transcript extraction waits for target composer and conversation content. The original receipt/message binding and completion gates still apply. Connection status separates network preparation from page usability timing. These timings describe app phases, not internet throughput.

StartupRouteTestActivity tests route restoration, early selection, fallback, mismatches, bounded search, stale probes and manual scans. WebEntryBenchmarkActivity and run-paired-entry.cjs compare isolated old/new cold process launches with six composer delay values and an unrelated slow image. They do not contact a real account or measure real proxy/server latency.
## 元婴期院士 1.3.2 continuity and idle work

NetworkWork makes maintenance cancellable: reconnect/send/exit-check/select operations interrupt background scans, cancel pending probes and disconnect their sockets off the UI thread. Intentional cancellation does not stop a healthy core or record artificial failures. Core recovery verifies the persisted fixed-exit baseline; reusing a core also requires matching saved settings. Automatic recovery remains blocked by an exit mismatch, while explicit manual reconnect can retry through the same baseline checks.

An idle, same-profile page can be retained after fixed-exit verification and a bounded same-origin HEAD check. Pending replies and unhealthy pages use the existing verified reload path. PageMemory holds eight in-process snapshots scoped to the applied network profile and a cookie hash. Reloads wait for a different document identity before accepting content. Draft restoration fills only an empty, nonbusy composer and never submits; existing drafts win and the older draft is archived. Scroll and selection are restored for matching pages. This is not cross-process webpage session restoration.

Historical conversation navigation first tries the website's real link, opening a collapsed sidebar if needed. It verifies source URL, navigation generation and two stable changes in content identities before publishing the target. Unhandled links fall back after 1.4 seconds; a changed route with delayed content gets up to eight seconds. Newer navigation supersedes older callbacks. No private website API or synthetic history-only navigation is used.

ConnectionTrace reports local kernel/subscription/exit-check, website response, first-visible and usable phase timings. Clipboard diagnostics contain only durations, software versions and route method; no URL, IP, cookie, credentials or message text. Notification intents have distinct per-task URI identities, and both warm and cold launches honor their bound conversation.

When no UI, foreground reply service, upload, download, native operation or connection/navigation is active, the app stops page polling and pauses its WebView timers. Work resumes for active tasks. Idle network health checks slow to approximately two minutes and skip full-entry scans; active operation keeps the prior health-check cadence. Upload readiness is still checked in the background.

New isolated tests cover actual stalled HTTP-socket cancellation, retained-page identity and exact drafts, reload conflict handling, delayed and rapid SPA navigation, collapsed mobile sidebars, actual JavaScript timer suspension/resumption, unique notification intents and cold notification routing. The test-only MainActivity alias leads to an intercepted local fixture and is absent from release builds. Tests do not contact a real ChatGPT account.
## 元婴期院士 1.3.3 independent environments and privacy

PocketApplication assigns a separate WebView data-directory suffix before any WebView API is initialized in profile processes. The default process never assigns a suffix, preserving prior login data. ProfileContext separates preferences, SQLite names, files, caches, sealed settings and Mihomo runtime directories. SecretStore uses a separate Keystore alias for each additional environment. Each environment has its own activity, waiting service, preview component and notification identities/IDs. Network configuration can be copied explicitly; cookies, messages and drafts are not copied. Independent environments require Android 9 or newer and remain within the same application's OS sandbox.

MainActivity uses explicit edge-to-edge fitting on Android 11+ and consumes the insets after the native root applies them, preventing duplicate native/WebView safe-area spacing. Tests verify the WebView follows the toolbar directly and the local fixed webpage header starts at its viewport origin. Older Android uses the existing fitsSystemWindows path.

BrowserPrivacy uses the Chromium/WebView reduced mobile UA format while retaining the WebView marker and the installed Chromium major version. It denies geolocation and sensitive media permissions, blocks third-party cookies and keeps HTTPS/mixed-content restrictions. When document-start scripts are supported, all matching frames receive RTC constructor restrictions, coarse memory/concurrency values and reduced WebGL renderer information. Strict mode additionally restricts canvas/audio readout, with potential compatibility effects; it cannot load under an unsupported early-protection policy. These JavaScript controls reduce selected signals and are detectable; they do not implement a different browser/TLS kernel or complete fingerprint anonymity.

Final normal DNS uses encrypted resolvers through FixedExit. Bootstrap/subscription and proxy-host resolution remain separate to avoid cyclic initialization; they are not claimed to be anonymous or entirely routed through the fixed exit. No device-wide VPN is introduced. Privacy settings cannot be changed while a reply/upload/download operation is active. Each environment uses its own settings.

PrivacyTestActivity validates early script execution, RTC constructor restriction, strict canvas controls, permissions, DNS configuration and safe-area geometry. ProfileIsolationTestActivity launches two actual child processes and verifies cookies, database records, local files and sealed-key separation. ProfileSessionTestActivity creates a usable child environment and validates its actual waiting service and separate foreground notification. Android can defer foreground notification publication for a short interval, so the test waits for the system event.

## 1.3.4 connection protection

BrowserNetworkGuard couples page and Service Worker network settings, checks the configured route at new request boundaries and rejects known local HTTP(S) destinations without resolving arbitrary hostnames. Phone-network mode requires an OS-reported VPN by default; the explicit network setting can opt out. Standard and strict modes require document-start and Service Worker coverage. Downloads check the shared gate before new requests, redirects and writes. Bootstrap DoH uses literal encrypted resolver endpoints; final website DNS always uses FixedExit, including compatibility mode. This is a process-local request gate, not a kernel kill switch or a promise of VPN invisibility. Already established connections and unhandled engine/protocol behavior remain outside that guarantee.

NetworkShieldTestActivity tests real Service Worker fetches and a test-package-only VPN sink. ShieldFixtureVpnService and its permission are test-build-only. Test fixtures explicitly opt out of requiring a real VPN; production defaults remain protected. The runner resets the test VPN app-op on completion. Existing profile separation and signing identity are preserved. Re-entering an already visible webpage no longer repeats focus changes that could reset a saved scroll position.


## 1.3.5 environment audit

EnvironmentAudit uses a separate local diagnostic WebView with the current UA and protection script. It samples an actual parent, srcdoc iframe and blob Worker, then builds evidence-limited rows through AuditReport. Network checks require an explicit per-dialog opt-in and use credential-omitting browser requests plus a bounded native IPv4 query through the configured route. Both live requests and results check the connection generation and policy identity. DNS and UDP/QUIC/TLS are not certified by these HTTPS probes, and a failed IPv6 request is not proof of no IPv6 leak. Current coarse hardware and UA controls do not fully cover Worker realms; differences are reported, not concealed.

Baselines include native policy and device/runtime settings plus configuration and observed IPv4 digests. They and diagnostic results are sealed with the environment-specific Keystore key under noBackup storage. Updates can legitimately change the baseline. Accepting a new baseline does not fix issues or clear login data. Public IP checks never run as background monitoring. Cancelling the dialog or leaving the activity closes the diagnostic WebView and native connection without clearing a prior report. The brief clipboard copy redacts IPv4 and IPv6 values.

The test build includes EnvironmentAuditTestActivity with local intercepted endpoints. EnvironmentNetworkSmokeActivity is an explicitly invoked public-service test on the isolated test package, not a default test-suite step. The recorded public-service observation did not receive a verifiable IPv4 result on this test instance; coverage was left unverified. The release manifest includes neither activity nor any test VPN service.


## 1.4.0 functional modules and profile pool

AppHub adds five native module destinations while retaining the original chat stack, toolbar, drivers, drawer and dialogs. Existing default and profile1/profile2 process names, storage suffixes, preference/database namespaces and Keystore aliases are preserved. The manifest adds profile3 through profile7 using the same pre-WebView data-directory suffix architecture. Profiles.MAX is 8; unopened slots do not start processes. Android 8 can continue using the default environment but cannot open additional environments.

ProfileCatalog is a shared SQLite metadata catalog for names, editor drafts and last-observed process state, without cookies, sealed network settings or chat data. It migrates the prior names and initialization markers. Native process checks distinguish an actually started process from stale connection metadata. Editor drafts do not apply settings; committing preferences does. OS, browser engine, language and timezone fields are real read-only values, and no unsupported random fingerprint or fake Windows engine selection is offered.

AppPrefs defaults preserve existing behavior. Background waiting and completion notifications are independent flags. WiFi-only applies to managed file downloads, with checks before requests and during transfers; unverifiable WiFi is not accepted. Cleanup is off by default and only removes old unreferenced top-level download .part files after a canonical-path check. User files, resumable task data, chats and cookies are retained. NetworkJournal stores only fixed categories in the owning environment. Download notifications have separate per-profile identifiers and per-task PendingIntents.

FunctionalHubTestActivity exercises actual native module views and existing local chat fixtures. ExpandedProfileTestActivity starts an actual profile7 process and verifies data/notification/service mappings. Production excludes test components and remains non-debuggable.


## 1.5.0 designed native interface

BrandLaunchActivity routes to the selected default window in webpage mode after the first brand screen. Five native destinations, shared UI-only catalog options, and cross-window sanitized download progress preserve existing account and storage scopes. Unsupported controls use FutureFeatures.Adapter development slots rather than fake operational settings. Website content, fingerprint policy and network backend are not replaced by design-board sample data. See docs/UI-FUNCTIONS.md for the complete mapping.
