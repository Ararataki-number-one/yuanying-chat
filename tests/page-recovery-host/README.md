# Page recovery and explicit browser reload host

This host executes exact current production recovery, capture, reload and status
methods with controlled Android, UI, network and SDK-session boundaries. It does
not execute Android, Gecko, real network recovery, a website, or the full app.

The sending/result-detection feature has been removed. The current fixture uses
`PageConnectionUi` for explicit page-error recovery and retains the original
network retry, draft preservation, navigation ownership and stale-callback
checks. Assertions for old `ReplyState` banners, reply progress diagnostics and
result-confirmation status were retired with that feature. They are not replaced
by a simulated sending lifecycle.

## Recovery and native ownership

The URL dependency runs the actual `ChatSession.chatAutomationAllowed` and
`MainActivity.chatUrl` methods with a `java.net.URI` implementation of the Android
Uri boundary. Complete `GeckoNavigationPolicy` and `BrowserAddressPolicy` classes
keep ordinary public HTTP(S) browsing separate from ChatGPT synchronization.

Content-process exit runs actual `contentStopped` and `forgetGeneralRoute`,
actual desired/deferred identity collections, and complete production
`ChromiumRouteLease`. A stopped session loses only its own desired/deferred state
and route lease; another page and a native download retain their leases. Initial
route ownership is controlled input, not Gecko admission/provider evidence.

The current content-exit and close-all consumers execute actual `retireTimeZone`
and waiting-callback delivery. Native controller retirement is a counted default
system collaborator; custom-zone use throws. There is no execution of
GeckoTimeZoneController, native time-zone settings, Date or Intl.

Navigation-ownership checks execute `timezoneConfigurationChanged`,
`recoverClosed`, `contentStopped`, `closePopup`, `prepareBrowserNavigation`,
`beginNavigation` and `closeWebsitePages`. Reentrant status, bridge, native-stop
and time-zone callbacks replace a navigation epoch or surface, or delete an
owner. The older action must stop without erasing the newer document. Cleanup
still closes old popups and preserves independent downloads. Native allocation,
activation, load and checkpoint restoration are counted SDK boundaries.

Seven compiled negative controls check generic-site synchronization, desired
session retirement, route lease close, navigation ownership, intermediate popup
navigation, native-stop fencing and time-zone-retirement fencing. Each control
must fail its specific behavioral assertion; no production file is changed.

## Reload and upgrade migration

The independent reload host runs afterward. It extracts current production
`requestReload`, `ReloadTarget`, `reloadTargetAfterInspection`, `confirmReload`,
`confirmIndependentReload`, `reloadCurrent`, `verifyReloadDraft`, and
`reloadConfirmed`. Explicit confirmation, fresh draft rechecking, profile/route
identity, native port and document generations all remain exercised. A new
navigation or changed input cannot borrow an earlier reload acknowledgement.
Driver responses, preferences, draft archive writes, navigation and UI widgets
are explicit controlled boundaries; the host does not claim disk durability or
native button/touch execution.

Legacy pending records are tested only through actual
`WebReplyObserver.restorePending`: preserve history, clear active result checking,
never restart it after storage failure, and retain a synchronous replacement
owner. Actual `receive` rejects retired intent/bound/uncertain/stop/complete
messages while preserving resource-route and resource-work dispatch. Reload no
longer performs old send-result archival or treats it as permission to rebind a
stale callback.

Run with either supported JSON implementation:

```sh
python3 tests/page-recovery-host/run.py --java-home path/to/jdk --json-jar path/to/json.jar
```

The JSON report records exact selected members, source/dependency hashes,
compiled-negative outcomes and the reload subreport. The same runner's `member`
extractor is imported by other host suites and remains available.
