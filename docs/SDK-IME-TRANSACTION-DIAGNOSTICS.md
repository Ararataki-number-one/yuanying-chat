# Isolated Gecko input transaction diagnostics

This diagnostic branch is based on production source `e4a4a08202cf50ce60d36dd86a625366de9bb2f4`.
It is not a browser fix or release acceptance. The ordinary production SDK and source remain unchanged in the production branch.

The original regression sometimes receives every trusted hardware character in order while a native caret movement inserts them at the wrong positions. The current investigation must distinguish native selection writes, Java shadow synchronization, and selection notifications intentionally ignored by the SDK. An ACK before a selection notification alone does not establish the cause: Android selection spans can move automatically when text changes.

`tools/build-gecko-ime-trace.py` validates the exact official GeckoView 157.0 AAR, `classes.jar`, and `GeckoEditable.class` hashes. It adds bounded primitive recording to the original Java class and one helper. Other classes, native libraries, resources, and their compressed ZIP records remain unchanged. It does not change the selection predicate, native writer arguments, handler, Binder target, task scheduling, or exception handling of the original calls.

The helper records method boundaries and the original replacement/composition call arguments. Current and shadow selection snapshots are read only on the original input-connection looper; the current snapshot uses the SDK's existing `AsyncText` monitor. Other threads record primitive arguments and flags without reading either Spannable. The receipt documents the event codes and field layout. The observer may change timing, including through the additional snapshot lock. Passing diagnostics cannot prove that an intermittent defect disappeared.

Recording begins before the existing real caret gesture. The visible IME, stable geometry and caret must still settle for at least 600 ms. Each trial executes exactly one original Android text burst, with the existing draft, trusted-key, and no-send assertions. There are no character delays, input retries, native proxy wrappers, extra JavaScript selection hooks, text replacement, or DOM corrections.

The ring is drained only after input finishes or the trial fails. The workflow runs all ten independent trials and preserves every outcome. The diagnostic APK uses the synthetic `.test` application and signing key. Only a filename whitelist of synthetic reports, logs, screenshots, and SDK instrumentation metadata is published to `apk/gecko-sdk-input-diagnostics`; APKs, AARs, signing keys and browser profiles are excluded.

`-PimeSdkTraceAar` is restricted to integration build tasks. Without that property the original SDK dependency is used. The local AAR replacement retains the exact upstream SDK POM dependency versions.
