# 1.7 candidate — template requests and verifiable browser observations

This is source work on top of v1.5.23 plus the v1.5.24 downloaded-file deletion changes and the frozen 1.6 network/environment foundation (6076b2b). It is not a claim that an Android release has passed all acceptance checks. The browser remains one official GeckoView runtime per existing Android environment process, using the original ChatGPT webpage.

## Delivered code

- `BrowserIdentitySpec`: six coherent standard/compatibility/native-RFP mobile/desktop combinations. RFP variants are explicitly experimental. Template ID, display, protection and timezone strategy must agree. Existing desktop + compatibility/strong settings migrate without normalization. Arbitrary UA is restricted by the product to tested templates even though the SDK has a public UA override. Unimplemented custom hardware/timezone controls and unknown schemas are rejected.
- `GeckoPolicyAdapter`: actual SDK calls for session mobile/desktop UA and the v1.5.23 mobile-fit viewport, existing native tracking-list protection, and per-runtime locale request/readback. Session desktop UA is not a runtime-wide HTTP UA control. Worker fetch requests may retain the SDK build's mobile UA. The stored request, SDK language-region normalization prediction, and actual page/header readings remain separate. There is no JavaScript timezone, Canvas, font, GPU or audio replacement.
- `FingerprintTemplateUi`: quiet editor with persisted desired/applied/observed revisions, native status and a selfcheck entry. Opening/saving does not reset an existing language list by default. Database and encrypted repository loads run on the session worker.
- `GeckoSettings`: accepted-browser snapshot, locale readback and native privacy acknowledgment are kept separate from desired configuration and page observations.
- `GeckoWebView`: locale preparation gates opening the first session; async UA results have configuration revisions; privacy commands have a monotonically increasing token echoed by the extension to prevent A→B→A stale acknowledgment. The exact SDK-accepted coherent browser request is available to the environment coordinator; a getter is not webpage verification.
- `main-world-audit.js`: fixed code observes public page-main-world signals, a same-origin srcdoc iframe and a dedicated Blob Worker. Content-Security-Policy may prevent any of these paths; the resulting report explicitly leaves them uncovered.
- Extension bridge: a typed native `audit` operation injects only the packaged observer. Page events can submit bounded observations for one nonce; they cannot select a URL, submit code, invoke native evaluation or receive the existing privileged integration port.
- `AuditReport`: provenance and scope are explicit; extension-isolated fallback cannot verify actual webpage fields. The Dedicated Worker row verifies public JS fields only. A separate Worker HTTP UA row stays uncovered; matching JS or a content-script echo cannot verify it. Cross-origin frames, Shared Workers, Service Workers, DNS and UDP/TLS remain uncovered. Native RFP standardized time is not falsely compared with the phone offset. HTTP UA/Accept-Language evidence is from an actual Gecko content-script fetch to the permitted public echo service, not Java header emulation and not ChatGPT's server logs. Full desktop UA consistency and fingerprint-template acceptance remain explicitly false.

## Exact SDK evidence and limits

The shipped 1.5.21 APK (same GeckoView 157 SDK as 1.5.23) was checked against its published SHA-256. Its extracted SDK class signatures confirm `GeckoRuntimeSettings.setLocales(String[])` / `getLocales()` and native mobile/desktop viewport constants in GeckoView 157. The getter returns the requested locale descriptor; tags such as zh-Hant-TW are sent to content as language-region zh-TW. Duplicate tags after SDK normalization are rejected. this is request/readback evidence, **not proof that every content process, worker and HTTP path has applied it**. Those require Android runtime tests and the observation report. The current implementation does not use unsupported private prefs for independent timezones.

Native `browser.privacy.websites.resistFingerprinting` is set and read by the background extension; native configuration acknowledgment requires matching request token, protection level and returned value. Settings readback does not certify protection of all APIs or website compatibility. Advanced RFP is therefore not presented as a verified production preset.

## Root integration contract

- `FingerprintTemplateUi.show(MainActivity)` invokes `ChatSession.applyIdentityTemplate(MainActivity, BrowserIdentitySpec, Consumer<String>)`; completion uses an empty/null string for accepted save and a nonempty string for an actionable error.
- Before applying legacy browser settings, the session calls `web.configureIdentity(specification)`. Existing webpage draft preservation and busy-task deferral remain authoritative. Locale-only changes need the same safe application flow.
- `web.acknowledgeIdentity()` calls `owner.identityPolicyAcknowledged()` only after the current native UA/readback and privacy-token acknowledgment match. `metadata.acceptedBrowserIdentity` is the exact actual coherent browser snapshot. Root must verify the **network binding and guard too** before marking the complete environment revision applied.
- A fresh audit calls `owner.identityObserved(report)`. Root must bind persistence to the starting/current actual policy and applied revision, and reject late results after profile generation, connection epoch or configuration changes.
- `EnvironmentSpecRepository` remains the authority for desired/applied/observed revisions. A successful save alone does not advance applied or observed revisions.

## Verification included

`tests/browser-runtime/FingerprintTemplateTest.java` exercises production configuration validation and report semantics: all presets and legacy combinations, coherent fields, native language lists and immutable snapshots, unsupported custom UA/timezone, future schema rejection, main-world vs isolated fallback provenance, RFP timezone semantics, cross-context differences, actual header scope and stale observations. The source includes 91 host assertions; their result must come from a clean source-bound host execution, not this document.

`tests/review-host/audit-bridge.test.cjs` exercises the actual extension source with a controlled host: CSP fallback, bounded nonce/replay/cancel handling, static network endpoints and omission of credentials, untrusted page signal disclosure, and absence of page-driven native code/URL execution. It is not an Android browser test.

`tests/review-host/protection-handshake.test.cjs` runs three production-background-script tests for queued A→B→A privacy commands, request-token echo and failed readback. Native receiver/runtime execution still requires Android integration evidence.

All three extension scripts pass JavaScript syntax checks. The shipped-SDK signature compilation is an extra local compatibility check; Gradle assembly with the official AAR, Android execution and real-device tests are separate required release checks.

## Android release acceptance still required

1. Two environments concurrently using different native language settings; verify actual page/iframe/Worker values and Gecko request headers before and after restart. Do not accept SDK getter equality alone.
2. Mobile/desktop viewport, Chinese IME, keyboard/rotation/caret, long reply, tools, attachment upload/download and popup login.
3. A→B→A changes while a protection request and a UA callback are delayed; only the final configuration can be acknowledged. Test extension disconnect/reconnect and native setting API failures.
4. Browser templates applied while reply/upload/download is active: defer without losing draft or replaying a submission.
5. CSP-blocked main-world/iframe/Worker paths remain uncovered; forged page observations cannot invoke privileged integration code or create diagnostic requests.
6. Deletion/reused slot, upgrade from 1.5.23 and earlier versions, stored cookies/IndexedDB/CacheStorage/Service Workers, and old async callbacks cannot cross environment generations.
7. Standard and experimental RFP modes are tested separately. Failed real ChatGPT compatibility or unproven context coverage keeps the affected mode experimental.

Cross-origin/Shared/Service Worker probes remain uncovered. A separate controlled-server document/header harness is now implemented as test source, pending actual Android execution. It cannot certify ChatGPT headers or those other contexts.

## 已接入的配置协调流程

IdentityTemplateController 是实际应用桥接：期望配置先 CAS 保存；活动任务
仅排队，语言不立即修改；空闲应用沿用已有草稿保存检查。旧模板回调在
写入偏好之前再次检查编辑代次。重启若有排队设置，先恢复已应用配置。

完整环境确认同时要求实际 acceptedBrowserIdentity、当前线路绑定和
保护门禁匹配；出口核验回执也重新核对服务实例。自检报告带采样开始时
的 appliedRevision，旧观测不能确认后来应用的新版本。网络恢复在门禁
解除后再触发完整环境确认。

源码已接入官方 SDK 编译；实际 Android 执行、正式候选构建和真实 ChatGPT 验收仍须独立完成。


## 1.5.23 基线复查

保留新版本手机自适应视口、原生缩放适配、键盘焦点滚动及草稿恢复。桌面模板切换 Firefox 原生桌面 UA，视口继续使用移动适配，避免重新引入横向裁切；不会伪装成实际桌面硬件。模板应用覆盖 Activity 结束后的后台队列、父编辑页控件同步、重复保存语言与真正无变化的保存。


## Current application and failure boundaries

Template saving now publishes only the desired configuration and the existing deferred browser queue. It does not rewrite the environment name, other preferences or an open editor draft. `DeferredBrowserSettings.drain` remains the owner of safe draft capture and runtime reconfiguration. Saving during a live task does not interrupt it.

Controller route/catalogue reads in acknowledgement and observation run on `environmentIo`, with connection, policy and environment-generation fences. Template UI callbacks no longer read SQLite metadata. A failed deferred preference write sets a retryable queue-unavailable state; it preserves the last applied policy and does not invent runnable work or keep a background browser awake indefinitely. The sealed desired edit is retained for explicit retry. Saving unrelated environment metadata does not overwrite such a browser edit.

`AuditReport` requires presence and valid types for UA, CPU, memory API result (explicit null is an observed unavailable API), language, full language list, timezone offset and timezone ID in both compared contexts. UA-only and filtered malformed arrays cannot become verified. Known differences remain visible even when another field is uncovered. The bounded isolated-world fetch reads at most 12,000 accepted response bytes through a stream and cancels oversized bodies; it never falls back to unbounded response.text().

## Separate 1.7 controlled Android fixture

Actual 1.6 SDK testing exposed a desktop limit: session/page/frame/Worker-script UA and public Worker JS can be desktop, while HTTP fetches from HTTP and Blob Workers retain the SDK build mobile UA. Existing desktop display and login data are preserved. No HTTP header is rewritten, no permission added, and no runtime-wide UA setter is claimed. The template UI and production self-check explain this supported scope quietly. The controlled fixture inherits the independent `GeckoSession.getDefaultUserAgent()` build baseline and strict role-specific HTTP observations from the corrected 1.6 parent. That static API ignores session overrides; it is not native runtime acknowledgement. The 190 names remain unchanged, but HTTP checks now follow the actual supported role: four document/script/page-fetch roles match session UA, while two Worker fetch roles match the independent SDK default. All real rows, differences, source and nonce ownership are preserved. The previous all-roles-equal-session-UA expectation was rejected by actual Android; this corrected 1.7 source still requires fresh actual Android execution.

`GeckoTemplateIntegrationActivity` applies four standard/compatibility mobile/desktop templates through the production adapter, then checks the production controller's desired/SDK-request-applied/observed acknowledgement. It records real main-world, same-origin iframe, Dedicated HTTP Worker and Blob Worker values, plus actual server-observed document, frame, worker-script and page/worker fetch headers. The zh-Hant-TW request is retained while actual content is compared with SDK-normalized zh-TW. Standard tracking-list enablement and compatibility disablement are checked separately from the experimental native-RFP mode.

The shared local HTTP harness preserves raw arrival records and validates them once in deterministic target order. The distinct template contract requires all original 181 ordered template assertions plus the nine inherited actual closed-guard checks (190 total), all five session/header records, and the same mandatory source-bound guard semantics as 1.6. The last real document attempts a new-nonce fetch and HTTP Worker after the production guard closes; native sender, blocked routes, actual rejection events and unchanged server connection/request/header counters must agree. Source commit, clean build tree, installed APK bytes, invocation nonce and raw report hash are checked by the runner and public evidence gate. The 1.6 prototype remains diagnostic-only and cannot satisfy the 1.7 template gate. The production proxy VM host receipt (28 checks) remains a separate mandatory inherited 1.6 gate; it does not claim actual Gecko execution.

The fixture deliberately uses an idle local document and directly prepares the candidate. It does not certify real-task safe-idle application, a real ChatGPT account, separate Android process/profile isolation, restart persistence, native IME, experimental RFP or cross-origin/Shared/Service Worker coverage. Those remain explicit acceptance requirements. Per-session `userAgentScope` and ordered case `workerFetchMismatchSessions` are independently derived from the unchanged raw HTTP records by the shared 1.6 contract. The two desktop Worker fetch roles are explicitly unsupported for session-UA uniformity. The gate's `controlledTemplateAcceptance` describes this limited regression scope; `fullDesktopUaConsistency`, `fingerprintTemplateAcceptance` and `releaseAcceptance` remain false. Production self-check Worker HTTP UA also stays uncovered instead of inheriting a matching JS verdict.

Both candidate and stable release pipelines require the original 1.6 gates plus this source-bound template gate for version 1.7 or later. Host bridge/controller receipts are retained with their production-source hashes. Metadata-only negative tests verify rejection behavior; they are not Android execution evidence.


The UI labels the applied revision as the network plus SDK-request confirmation revision. Locale setter/getter equality confirms only request acceptance/readback; the public SDK has no independent asynchronous locale-content completion callback. The persisted applied snapshot is not a claim that every webpage or Worker adopted it. The actual-observation revision and context/header evidence provide that narrower proof. Standard or compatibility privacy-setting readback does not imply native RFP was enabled.


A failed new queue also revokes an already-running deferred capture: entry, inspect, page-state, draft-write completion, final inspection and direct apply all recheck candidate availability before reconfiguration. The production DeferredBrowserSettings host fixture controls those delayed callbacks and preserves its real coordinator source; Android I/O and webpage callbacks are explicitly doubles. Unrelated metadata saves classify browser fields against the parent editor baseline, so an accepted B followed by failed C cannot overwrite C merely by saving a name. Explicitly changing B back to already-running A remains a new browser intent, mirrors the desired replacement before the safe queue is re-enabled, and wakes a retained background environment.
