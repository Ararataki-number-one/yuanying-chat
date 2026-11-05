Run the offline rejection and fixture-scope tests with:

```
python3 -m unittest discover -s tests -p 'browser_fingerprint_*test.py' -v
```

These schema/trust tests use synthetic metadata and do not claim Android execution.
The real Android workload is `tools/browser/run_fingerprint_integration.py --adb adb --serial emulator-5554 --output work/browser-acceptance`; it requires a clean source-bound integration APK and records installed version/source/tree/APK/SDK identity. It writes only `browser-fingerprint-results.json`, preserving the existing browser workload and its cold-input budgets. The strict checker is called by the existing browser evidence gate for 2.1.1 and later.

The integration resource overlay allows user-CA trust only for exactly two reserved synthetic hosts. A fresh CA and leaf key are generated exclusively in a host `/tmp` directory for each invocation; no TLS private key is packaged, committed, copied to Android, or placed in an artifact directory. Only the public CA is installed into the controlled rootable emulator user store, read back with owner/mode/SELinux checks, and removed afterward. Native certificate validation and exact leaf-DER hashes remain required; root/store failures are fatal. The host loopback proxy never forwards traffic. First-inline JS records bounded hashes and native identity values; it never reads account/session content, storage, cookies, or screenshots.

Coverage: real native UA/UA-CH and server headers on HTTPS, native feature availability, first-inline top/same-origin/cross-origin frames, stable Canvas policy across reload and native display changes, independent saved environment policy seed, current-document self-test versus stale document/receipt rejection, and both real native URL UIs with ChatGPT-only hot paths absent on ordinary sites. The secondary environment-policy probe does not prove cookie/storage/process isolation. Dedicated Worker is executed and explicitly observed unprotected; ServiceWorker is unsupported and unexecuted. Original Gecko fingerprint acceptance remains required separately. No complete-fingerprint/public-site/physical-phone performance claim.
