# Browser startup preference and dispatch checks

The runner compiles the complete production `BrowserPreferences` and
`BrowserAddressPolicy`, the verbatim `MainActivity.dispatchBrowser` method, and
the actual `BrowserActivity.activity`, `resume`, `intentAddress` and `onNewIntent`
methods. The generated launch Intent is delivered to that actual receiver to
check that environment re-entry retains the selected page, while explicit URL
requests still select or create the requested tab.

Android preferences, Intents, activity lifecycle calls, catalog availability and
tab selection/creation use explicit host adapters. Real `ProfileContext`, cold
`BrowserActivity.onCreate`, WebView construction and Android lifecycle delivery
are outside this suite's scope. Homepage preference checks remain unchanged;
the old dispatch-only requirement to force that homepage is replaced by the
current resume contract, which sends no URL.

```sh
python3 tests/browser-preferences-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/browser-preferences-host/jvm.json
```

Repeat with `work/ux-build-deps/android-json.jar`. These tests do not execute
Android, Chromium, Gecko, networking, cookies or physical-device measurements.
