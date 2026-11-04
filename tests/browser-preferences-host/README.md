# Browser startup preference and dispatch checks

The runner compiles the complete production `BrowserPreferences` and
`BrowserAddressPolicy`, plus the verbatim `MainActivity.dispatchBrowser` method.
Android preferences, intents, activity lifecycle calls, catalog availability and
browser launches use explicit host adapters. The real `ProfileContext` and
`BrowserActivity` are outside this suite's scope.

```sh
python3 tests/browser-preferences-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/browser-preferences-host/jvm.json
```

Repeat with `work/ux-build-deps/android-json.jar`. These tests do not execute
Android, Chromium, Gecko, networking, cookies or physical-device measurements.
