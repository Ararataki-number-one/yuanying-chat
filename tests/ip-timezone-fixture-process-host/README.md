This host compiles the complete current integration `IpTimeZoneFixtureApplication` and
`IpTimeZoneFixtureScopes`, the actual `EnvironmentProcessPolicy`, and extracted
current parent lifecycle/profile/context methods. Android process names, lifecycle,
UIDs, metadata, catalog, vault and timezone storage are explicit JVM collaborators.
It does not execute Android, Gecko, a keystore, native timezone settings or a network.

Non-owner children use throwing collaborators: no fixture metadata, filesystem,
catalog, vault or store operation may occur, including after later same-profile
access. Exact main/profile owners retain all eight generic seeds. The dedicated
setup process still checks its declared scope without early catalog/profile6 access.
The exact fifteen legacy fixture roles match the actual integration manifest.
Read-only Android application UID identity is separate from fixture metadata IO;
isolated UID boundaries cannot borrow even an exact UI process name.
The actual original Application, a removed guard, bypassed owner policy and fake
profile slot must compile and fail. The older 104 assertions and seven mutants
remain unchanged; its collaborators gain only the three required Android UID API
declarations. That suite remains a separate check. The complete original Application
is embedded verbatim with its public-source SHA, so shallow CI needs no ancestor.

Run once for each real JSON jar, using the selected JDK17:

```
python3 tests/ip-timezone-fixture-process-host/run.py --java-home "$PROFILE_JAVA_HOME" --json-jar "$PROFILE_JSON_JAR" --output "$REPORT_DIR/process-desktop.json"
python3 tests/ip-timezone-fixture-process-host/run.py --java-home "$PROFILE_JAVA_HOME" --json-jar "$PROFILE_ANDROID_JSON_JAR" --output "$REPORT_DIR/process-android-json.json"
```

Both variants are mandatory in the diagnostic workflow. Source/method/generated
collaborator hashes and raw compilation/execution logs accompany each report.

Final 2.1.4 adds only the exact declared `:native_tls_probe` role. The final integration manifest is a hashed execution input and must exactly match all fifteen literal roles. Unknown suffixes, foreign-package lookalikes and SDK child suffixes remain denied even when application UID matches. This scope concerns test Application prerequisites, not a production native timezone proof.

Eight compiled unsafe source variants are rejected, including removing the native TLS role and overgranting prefix roles. Eight additional actual manifest/source validator counterexamples reject missing, duplicate, foreign, wildcard, undeclared and same-size substituted roles. These controls supplement the whole-class lifecycle checks; they do not establish Android SDK child ordering or real network behavior.
