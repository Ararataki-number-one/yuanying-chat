# Chromium Activity lifecycle host

Run with Java 17 and either supported `org.json` jar:

```
python3 tests/chromium-fingerprint-activity-host/run.py --java-home /path/to/jdk --json-jar /path/to/json.jar --output work/chromium-fingerprint-activity/results.json
```

The runner extracts current production method bodies from `BrowserActivity.java` without rewriting them, and executes them alongside the complete production fingerprint store, typed specification, identity, address policy and browser history. The store uses the explicitly declared temporary filesystem, catalog and plain-vault boundaries from the storage host suite. History uses an explicit in-memory SharedPreferences boundary. Manual worker/UI queues and WebView/provider/chooser boundaries make lifecycle order deterministic.

The cases cover a genuine selected-file callback both before and after resume, native receipt readiness before upload delivery, cancellation on stale page/profile/provider, queued address changes, pre-navigation restore and popup gates, bounded observation parsing, stale observation callbacks, and durable receipt publication. Actual production start/finish/history callbacks also exercise dispatch-time loading, stopping a pending navigation, failed/stale completion and SPA history without a finish callback. The exact Android fixture completion predicate rejects missing/old-view/old-epoch/other-tab/other-URL receipts while leaving failed completion visible to the original history assertion. A getter-only predicate supplies the explicit earlier-advancement negative baseline.

Seven compiled counterfeits must fail their named behavioral assertion: immediate file delivery, dropped queued address, accepting the old document callback, omitting loading at go/back/reload dispatch, and starting a never-finishing load for SPA history.

This is host behavior evidence. It does not execute Android lifecycle, URI permission validation, actual WebView network traffic, native UA metadata, page fingerprint APIs or AES-GCM. The separately required Android HTTPS integration supplies real engine observations.
