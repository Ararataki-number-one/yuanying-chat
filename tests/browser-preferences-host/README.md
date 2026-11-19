# Browser startup preference and dispatch checks

The runner compiles production `BrowserPreferences` and
`BrowserAddressPolicy` alongside the exact Main and Chromium intent handlers.
It also uses the production profile preference-name calculation with independent
in-memory stores. The checks cover the default Gecko binding, existing choices,
same-engine settings isolation, home and native routes, and HTTP(S) deep-link
handoff. A launch without a URL preserves the selected Chromium tab. An open
file operation must keep its current owner during an engine change.

Android preferences, Intents, activity lifecycle calls, catalog availability
and tab actions use explicit host adapters.

```sh
python3 tests/browser-preferences-host/run.py \
  --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64 \
  --json-jar work/ux-build-deps/json-20240303.jar \
  --output work/browser-preferences-host/jvm.json
```

Repeat with `work/ux-build-deps/android-json.jar`. These tests do not execute
Android, Chromium, Gecko, networking, cookies or physical-device measurements.
