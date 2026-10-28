# Mobile public-identity evidence

`profile_mobile_identity_consistency_test.py` compiles the production
`AuditReport` and runs synthetic host observations through it. It also retains
the existing `FingerprintTemplateTest` assertions. The new cases cover
platform/appVersion differences, malformed/missing/oversized values, stale and
isolated-world evidence, keyboard/iframe viewport changes, screen rotation,
DPR/touch validation, absent Worker window APIs, and desktop-display compatibility.

```sh
PROFILE_JSON_JAR=/path/to/json.jar python3 tests/profile_mobile_identity_consistency_test.py
```

`PROFILE_JAVA` may select a Java 17 executable. No browser, Android, Gecko or
network executes in this test. Equality of public fields does not attest a phone
model, HTTP request identity, anonymity or the effectiveness of native protection.
Production collection remains on demand and unchanged; no JavaScript property
overrides or extra requests are introduced.
