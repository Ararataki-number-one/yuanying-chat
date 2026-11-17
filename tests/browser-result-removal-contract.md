# Browser result-observation retirement (2.1.8)

The browser no longer detects whether a website message was sent, binds that
message to a generated reply, decides whether a reply finished, records native
delivery receipts, or posts reply-result notifications. The user explicitly
removed this product feature. Hiding its warning while continuing to collect
send/result evidence would not satisfy that requirement.

The retained observation is for browser safety: current document/route identity,
page readiness, visible resource/upload work, attachment metadata, local drafts,
transcript capture, and finite guards before changing network or browser
configuration. Those checks neither send messages nor determine their results.
The short trusted-input guard records only a timestamp; it does not read a
prompt, infer a completed send, or start a background task.

## Production contract

- The Java bridge accepts only `ready`, `resource-route`, and `resource-work`.
  Old documents' `intent`, `bound`, `uncertain`, and `stop` events have no native
  task, notification, or banner consumer.
- The read driver rejects the retired `poll` and `latest` actions. Explicit
  browser actions and the original website input remain available.
- Existing `pending` records are archived as `retiredWebObservation` or
  `legacyPending` during upgrade and are not resumed. Failed durable migration
  leaves the original record available for a later attempt, while runtime
  observation remains disabled.
- The former service can retire a queued Android restart, but cannot start
  reply observation or foreground reply notifications. File download and proxy
  services keep their independent behavior.
- `backgroundWait` and `replyNotice` are no longer enumerable settings and always
  resolve to false. Their names remain in the portable configuration schema so
  older backups can still be read; import normalizes them to false.
- Attachment disappearance is not evidence of a successful send. Known upload,
  error, explicit removal, and stale-document guards remain.

## Explicit test migrations

The current contract discriminator is `browser-result-removal-v1`, except for
the separately versioned native notification and network-safe-idle evidence.
Historic evidence readers keep their older branches; new reports must satisfy
the current branch. No current test should manufacture a reply task to restore
a removed assertion.

| Previous assertion | Current assertion and retained coverage |
| --- | --- |
| Website send intent creates a native pending task and eventually becomes bound/uncertain/stopped. | Trusted website interaction creates no native pending task, receipt, reply service, result banner, or automatic send. Resource observation still checks route/document/port ownership, finite busy/idle transitions, and stale nonces. |
| `reply-observation.test.cjs` classifies reply completion. | The production read driver preserves complete transcript bodies, file metadata, order, streaming deltas, same-ID replacements, detached/virtualized nodes, and route resets. Retired read actions are rejected. |
| `reply-binding-loading.test.cjs` binds a reply to a user prompt. | Browser lifecycle and resource/readiness checks replace binding. The real 42-case socket surface matrix remains, including ordinary conversation text that must not become a connection error. |
| Attachment evidence marks a disappeared file as sent after message binding. | Upload/removal/stale/overlap tests remain. A file never observed in the current DOM stays unknown instead of claiming send success. |
| Background policy can enable eight reply observers/services. | Actual policy migration closes admission, retires old services, preserves process ownership and the SQLite writer gate, rejects stale policy hints, and retries failed compatibility writes without enabling capture. |
| Delivery-store persistence and receipt recovery. | `DeliveryStore` and `ReplyTaskPersistence` are deleted. Navigation/lifecycle tests verify upgrade archival of both confirmed and unconfirmed legacy records, storage failures, and reentrant record replacement. The old `tests/reply-task-persistence-host` source is historical only; its runner explicitly reports retirement rather than a pass. |
| Navigation retires a task through `WebReplyObserver.navigationStarted`. | Navigation retains the browser's epoch, route, proxy, cache, ownership, and late-callback fences without task inspection. The negative control for reentry into the removed method is retired explicitly; the other compiled controls remain. |
| Queued network/settings work waits for a synthetic reply to finish. | Fixtures use actual counted file work and visible page resource work. The reader selects the contract from the installed source commit's actual Git producer, requiring the observed native file phase to finish before idle. Historical producers still require no native file work. Busy deferral, six original business assertions, owner identity, rollback, generation, nonce, deletion, owned VPN close and the original 3,500 ms application budget remain. |
| NetworkSafeIdle waits for a native pending reply after a trusted tap. | `safeIdleContract=2` requires the actual trusted DOM tap, one website send, visible Stop state, and a newer owned production `resource-work` observation. All seven network transaction races remain. The result requires no native/durable pending record. Between cases, fresh current document/epoch/binding observations must reach actual idle within the original single 5,000 ms reset budget; the production interaction guard is never cleared or shortened. Contract 1 remains a historical reader branch. |
| Reply notification opt-in/out and completion/error notices. | `notificationContract=2` verifies upgrade retirement and no reply notices/services while preserving actual proxy and opt-in file notification checks. |
| Performance workloads use reply `poll` as their observation action. | Both prior and current source run the same retained `web-inspect` plus transcript workload. Original topology/control/streaming workloads and operation-count thresholds remain. Removed result fields are excluded explicitly, and the current script additionally rejects the retired actions. |
| Input scheduling prewarms a reply-result cache. | User interaction still defers background work and coalesces bounded current-browser observation. Result-producing work must remain absent; insertion invalidation retains its walker limits and same-object cache/scope assertions. |
| Independent strict-input receipts require a native reply-binding boolean. | The sidecar-bound committed runner and activity select browser observation v2 and its complete lifecycle/appearance/performance contract. Historical producers still require the old binding field. Original source/APK/SDK identity, one unreplayed workload, IME readiness, all 11 ordered trusted keys, full checks and native input qualification remain mandatory. |
| Compact chrome injects conversation-change and send-result banners. | Normal browser connection status and cleared errors stay quiet; a real webpage connection error remains visible and actionable. The fixture rejects native or durable pending state, delivery IDs, submission state and reply services before and after these checks. Geometry, captures, real input and the original 600 ms callback are unchanged. |
| Native integration `completion` action waits for a terminal reply. | It checks that `poll`/`latest` are rejected and that no native task or reply service is created. Actual website send tests preserve trusted input and no duplicate-send checks. |

`tools/browser/check_maintenance.py` replaces its removed receipt-persistence
gate with the actual policy-retirement host. Upgrade-record tests remain in the
navigation/lifecycle hosts. Mixed fixtures continue to exercise their browser,
resource, upload, download, network, and performance behavior.

## Evidence boundaries

Host reports execute production code with the boundaries documented in their
individual harnesses. JSDOM reports establish controlled DOM behavior and
operation counts, not Android rendering, frame timing, or live-site behavior.
Native fixture compilation establishes API compatibility, not device execution.
Reader unit tests establish acceptance/rejection of evidence shapes, not the
events that only a device can produce.

The two before/current performance runners still require their exact historical
Git commits (`1e3086a` and `f43adac`) and unchanged production-source hashes during
the run. A current-only workload must not be reported as passing that historical
comparison. Full acceptance still requires the complete release workflow and
its fresh Android/Gecko evidence; retiring this product feature does not waive
unrelated gates.
