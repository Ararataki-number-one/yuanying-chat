# TLS desired editor host

Compiles and executes the complete current GeckoTlsUi and GeckoTlsSpec with explicit queued widget/activity/vault/controller boundaries. Covers actual button/confirmation/cancel flows, stale owners, concurrent editors, failed CAS, pending cold boot, unchanged reply/upload/download/draft and strict native-summary tuple controls. There is no Android UI, real native preference or wire handshake execution here; those are separate native/product acceptance gates. System WebView unsupported scope stays explicit.

Run `python3 tests/gecko-tls-ui-host/run.py --java-home JDK17 --json-jar REAL_JSON_JAR --output REPORT.json`.
