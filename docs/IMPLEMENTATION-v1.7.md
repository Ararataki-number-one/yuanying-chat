# 1.7 implementation — verified Firefox environment templates

This is mergeable source work on top of the 1.5.23 released source baseline and the 1.6 environment/network foundation. It is not a claim that an Android release has passed all acceptance checks. The browser remains one official GeckoView runtime per existing Android environment process, using the original ChatGPT webpage.

## Delivered code

- `BrowserIdentitySpec`: six coherent standard/compatibility/native-RFP mobile/desktop combinations. RFP variants are explicitly experimental. Template ID, display, protection and timezone strategy must agree. Existing desktop + compatibility/strong settings migrate without normalization. Unsupported custom UA/hardware/timezone controls and unknown schemas are rejected.
- `GeckoPolicyAdapter`: actual SDK calls for native mobile/desktop UA and the v1.5.23 mobile-fit viewport, existing native tracking-list protection, and per-runtime locale requests/readback. There is no JavaScript timezone, Canvas, font, GPU or audio replacement.
- `FingerprintTemplateUi`: quiet editor with persisted desired/applied/observed revisions, native status and a selfcheck entry. Opening/saving does not reset an existing language list by default. Database and encrypted repository loads run on the session worker.
- `GeckoSettings`: accepted-browser snapshot, locale readback and native privacy acknowledgment are kept separate from desired configuration and page observations.
- `GeckoWebView`: locale preparation gates opening the first session; async UA results have configuration revisions; privacy commands have a monotonically increasing token echoed by the extension to prevent A→B→A stale acknowledgment. The exact accepted coherent browser configuration is available to the root environment coordinator.
- `main-world-audit.js`: fixed code observes public page-main-world signals, a same-origin srcdoc iframe and a dedicated Blob Worker. Content-Security-Policy may prevent any of these paths; the resulting report explicitly leaves them uncovered.
- Extension bridge: a typed native `audit` operation injects only the packaged observer. Page events can submit bounded observations for one nonce; they cannot select a URL, submit code, invoke native evaluation or receive the existing privileged integration port.
- `AuditReport`: provenance and scope are explicit; extension-isolated fallback cannot verify actual webpage fields. Cross-origin frames, Shared Workers, Service Workers, DNS and UDP/TLS remain uncovered. Native RFP standardized time is not falsely compared with the phone offset. HTTP UA/Accept-Language evidence is from an actual Gecko content-script fetch to the permitted public echo service, not Java header emulation and not ChatGPT's server logs.

## Exact SDK evidence and limits

The shipped 1.5.21 APK (same GeckoView 157 SDK as 1.5.23) was checked against its published SHA-256. Its extracted SDK class signatures confirm `GeckoRuntimeSettings.setLocales(String[])` / `getLocales()` and native mobile/desktop viewport constants in GeckoView 157. The getter returns the requested locale descriptor; this is request/readback evidence, **not proof that every content process, worker and HTTP path has applied it**. Those require Android runtime tests and the observation report. The current implementation does not use unsupported private prefs for independent timezones.

Native `browser.privacy.websites.resistFingerprinting` is set and read by the background extension; native configuration acknowledgment requires matching request token, protection level and returned value. Settings readback does not certify protection of all APIs or website compatibility. Advanced RFP is therefore not presented as a verified production preset.

## Root integration contract

- `FingerprintTemplateUi.show(MainActivity)` invokes `ChatSession.applyIdentityTemplate(MainActivity, BrowserIdentitySpec, Consumer<String>)`; completion uses an empty/null string for accepted save and a nonempty string for an actionable error.
- Before applying legacy browser settings, the session calls `web.configureIdentity(specification)`. Existing webpage draft preservation and busy-task deferral remain authoritative. Locale-only changes need the same safe application flow.
- `web.acknowledgeIdentity()` calls `owner.identityPolicyAcknowledged()` only after the current native UA/readback and privacy-token acknowledgment match. `metadata.acceptedBrowserIdentity` is the exact actual coherent browser snapshot. Root must verify the **network binding and guard too** before marking the complete environment revision applied.
- A fresh audit calls `owner.identityObserved(report)`. Root must bind persistence to the starting/current actual policy and applied revision, and reject late results after profile generation, connection epoch or configuration changes.
- `EnvironmentSpecRepository` remains the authority for desired/applied/observed revisions. A successful save alone does not advance applied or observed revisions.

## Verification included

`tests/browser-runtime/FingerprintTemplateTest.java` exercises production configuration validation and report semantics: all presets and legacy combinations, coherent fields, native language lists and immutable snapshots, unsupported custom UA/timezone, future schema rejection, main-world vs isolated fallback provenance, RFP timezone semantics, cross-context differences, actual header scope and stale observations. The local host run passed 50 assertions.

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

Cross-origin/shared/service-worker probing and a controlled-server document-request header harness remain planned validation work; this source does not pretend these are already covered.

## 已接入的配置协调流程

IdentityTemplateController 是实际应用桥接：期望配置先 CAS 保存；活动任务
仅排队，语言不立即修改；空闲应用沿用已有草稿保存检查。旧模板回调在
写入偏好之前再次检查编辑代次。重启若有排队设置，先恢复已应用配置。

完整环境确认同时要求实际 acceptedBrowserIdentity、当前线路绑定和
保护门禁匹配；出口核验回执也重新核对服务实例。自检报告带采样开始时
的 appliedRevision，旧观测不能确认后来应用的新版本。网络恢复在门禁
解除后再触发完整环境确认。

完整源码和 Android 测试 Activity 的接口编译已可执行；未运行 Android
设备测试、完整官方 AAR/Gradle APK 构建或真实 ChatGPT 登录。


## 1.5.23 基线复查

保留新版本手机自适应视口、原生缩放适配、键盘焦点滚动及草稿恢复。桌面模板切换 Firefox 原生桌面 UA，视口继续使用移动适配，避免重新引入横向裁切；不会伪装成实际桌面硬件。模板应用覆盖 Activity 结束后的后台队列、父编辑页控件同步、重复保存语言与真正无变化的保存。
