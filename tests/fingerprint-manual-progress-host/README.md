# 2.0.28 manual progress boundaries

`profile_fingerprint_manual_progress_test.py` runs the production
`FingerprintReportComparison` on both pinned desktop and Android JSON runtimes.
It reuses the existing two-report host fixtures and compile dependencies. The
manual-progress portion of the later handoff's joint test is covered here
independently, without importing the 2.0.29 reference-overview feature.

Coverage includes untouched findings, independent slots, existing state recovery,
per-item recording times, detached display results, malformed persisted data,
environment/generation ownership, replacing or clearing a report, and all entries
recorded with a failure or inapplicable result. Record completion never attests
physical-phone compatibility, protection effectiveness or a leakage verdict.

```sh
PROFILE_JAVA=/path/to/java17 \
PROFILE_JSON_JAR=/path/to/pinned/json.jar \
PROFILE_ANDROID_JSON_JAR=/path/to/pinned/android-json.jar \
python3 tests/profile_fingerprint_manual_progress_test.py
```

This is a JVM model test, not Android/Gecko execution, an actual UI selection,
encrypted repository persistence, or a real login/input/attachment action.
Production UI compilation and controlled Android integration use the normal CI;
physical-phone acceptance remains separate.
