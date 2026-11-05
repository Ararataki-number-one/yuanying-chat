# Gecko public navigation and ChatGPT driver callback binding

Run with a real JDK and either declared org.json implementation:

```sh
python3 tests/gecko-navigation-host/run.py \
  --java-home /path/to/jdk-17 \
  --json-jar /path/to/org.json.jar \
  --output work/gecko-navigation-host/results.json
```

The runner compiles the complete production `GeckoNavigationPolicy`,
`BrowserAddressPolicy`, `BrowserRuntimePolicy` and `J`. It extracts complete
`ChatSession` declarations for `DriverTarget`, the automation/target predicates,
`runDriver`, both `evaluateDriver` overloads, `asyncDriver` and both `waitResult`
overloads. The only method-body substitution replaces the wall clock with a
deterministic clock; the report records this and every source/dependency hash.

`DriverHost` controls the Web surface, extension port, JavaScript callback queue,
optional-observation setting, driver script strings and Handler scheduling. Its
`MainActivity.chatUrl` boundary delegates to production
`BrowserRuntimePolicy.official` with a JVM URI. These boundaries do not execute
Android, GeckoView, a WebExtension, a website, DNS or a network route.

The workload checks public HTTP(S) navigation, unsafe/private-address refusal,
normalization, home and restoration. Driver checks cover current ChatGPT
immediate/compact-fallback/async results and finite timeout, plus cross-origin,
same-URL/new-epoch, changed path/query, replaced surface, replaced port and
deleted-session races at immediate callbacks, initial async callbacks, queued
polls, poll responses and retries. Cancellation must complete once and cannot
inject a fallback script, poll or delete a property in a replacement document.
Replacing a surface deliberately retains the prior port, isolating the surface
identity check from the port check.

Five focused negative controls compile temporary copies that each remove exactly
one actual epoch, full-URL, surface, port or deleted-session predicate. Each
pristine focused schedule must pass; its one-predicate mutant must reach and fail
the original no-fallback/no-deletion assertion. The repository production files
are never rewritten. Generated sources, commands and raw logs accompany the JSON
report. This is JVM behavior evidence, not Android or Gecko runtime acceptance.

`route_hold.py` runs the actual `GeckoWebView` generic-route readiness,
retain/forget/release, admission-change and deferred-retry helpers with the actual
`ChromiumRouteLease` registry. Use the same arguments as `run.py`, with a separate
output file. The runner extracts the actual session identity-map fields and
rewrites only Gecko session type tokens to the explicitly declared
`SessionBoundary`; it supplies controlled guard/protection, Handler/Looper and
session load/state boundaries. It does not define an `org.mozilla` SDK package
or execute Gecko native APIs. Restore-state and native URL-dispatch boundaries
fail if unexpectedly invoked; they are outside this helper workload.

Route checks cover separate primary/popup ownership, ChatGPT exclusion, exact
readiness keys, denied/failed/crashed/destroyed pages, blocked-route release and
recovery, no admission under a real change barrier, deferred retry after barrier
release, off-main callback dispatch, and popup/download combinations. Listener
callbacks assert that the actual registry monitor is not held; final and duplicate
closes check wake counts and idempotence. Actual `onNewSession` tests also cover
HTTP(S) popup ownership, GPT/about-blank exclusion, admission barriers, constructor
failure cleanup, and late failed/crashed opener rejection while preserving the
primary page and native download. Nine focused negative controls replace one
readiness, barrier, release, unavailable-page or popup-cleanup guard in temporary
source copies and must fail their precise original assertion. Actual Gecko
construction, page-closing UI, native protection and session-state restoration
still require the separate real Android integration workload.
