# Actual stale timezone ticket fixture and store

Run from the repository root with JDK 17 and each real JSON implementation:

```sh
python3 tests/gecko-timezone-stale-host/run.py --java-home /path/to/jdk17 --json-jar work/ux-build-deps/json-20240303.jar --output /tmp/timezone-stale-desktop.json
python3 tests/gecko-timezone-stale-host/run.py --java-home /path/to/jdk17 --json-jar work/ux-build-deps/android-json.jar --output /tmp/timezone-stale-android-json.json
```

The runner compiles the complete current `GeckoTimeZoneStore`, spec, policy,
`EnvironmentSpec`, `NetworkShareJson` and `J`. The current integration fixture's
`newYork`, `staleNativeTicket` and `staleRevisionTicket` declarations are extracted
verbatim into the wrapper, hashed, and executed. The complete existing core
timezone host supplies its explicitly declared Android Context, catalog and
plain atomic-vault adapters. Filesystem, atomic replacement and file locks are
real; SQLite and Android Keystore are outside this host.

Queued writer and probe boundaries expose the asynchronous completion order.
The named navigation/capture/UI boundaries supply synthetic page and native ACK
data. The UI save boundary actually executes the current store's desired CAS,
activates its next ticket and publishes its receipt. The actual `newYork`
orchestration must reject the old native-context ticket before that save advances
the desired revision. After the save, the separate actual helper must reject
both old-revision record and receipt operations while independently reading and
preserving the current receipt. Page clock/first-inline preconditions are
controlled inputs here, never native or page-effect evidence. This focused host
ends before the later Android reload/restore workload.

The old after-revision order is reproduced as an expected failure of the exact
original assertion: the old record is rejected, while the old receipt lookup
also throws rather than returning an empty object. A live current ticket cannot
be mislabeled stale, a vault read failure cannot become successful absence, and
two old-revision denials cannot hide a counterfeit current receipt.

Each semantic negative control separately compiles and passes its pristine
focused case. Its compiled mutation must then fail the named actual assertion:
moving the current orchestration back to the old faulty order, removing the
store's current-ticket guard, or removing its old-revision receipt guard.
Compile failures, unrelated assertion failures and mutant successes are errors.
Generated sources, exact commands, compiler output and execution output remain
beside the report. All inputs, including the JSON jar, must stay hash-identical
through execution. No existing assertion, production store or device gate is
modified by this suite. Results explicitly make no Android, Gecko native,
Date/Intl, Worker or network-traffic claim.
