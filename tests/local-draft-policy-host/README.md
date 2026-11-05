# Local draft policy host regression

Run with JDK 17 and either supported `org.json` implementation:

```sh
python3 tests/local-draft-policy-host/run.py \
  --java-home /path/to/jdk17 \
  --json-jar /path/to/json.jar \
  --output work/local-draft-policy-results.json
```

This compiles the complete current production `LocalDraftPolicy`, `PageMemory`,
`DraftArchive`, `BrowserSessionStore`, `ChromiumRouteLease`, `BrowserRuntimePolicy`,
`BrowserAddressPolicy`, and `GeckoNavigationPolicy` classes, plus the verbatim
production `AppPrefs.enabled/apply`, `GeckoWebView.restoreCheckpoint`, deferred
restore holder, generic route retention/readiness/retry/release methods and
their actual session/map/listener fields. It uses
controlled Android, SQLite, and Gecko adapters, actual JVM workers, and temporary
files. It does not establish Android SQLite/AtomicFile durability, native Gecko
restoration, a real webpage result, or preservation of a real logged-in account.

The current restore consumer also executes its verbatim time-zone intent
claim/clear helpers and actual identity-map fields. Its time-zone collaborator
is explicitly modeled as an already-ready system default, with readiness,
preparation and URI-dispatch counters. Custom zones or an unready default throw;
six separate adapter controls verify that boundary. These are synthetic adapter
observations, not execution of GeckoTimeZoneController, native SDK settings,
Date, Intl or engine time zones. Original draft and route assertions are
unchanged. Per-member and field hashes bind the extracted current closure.

The original draft assertions remain intact. Additional generic website cases
exercise successful SDK checkpoint dispatch while holding the actual process
route lease, disabled-draft filtering, refusal during a real change barrier,
retry after that barrier closes, all desired session owners, unavailable
route/protection/identity, and stale navigation/session callbacks. Constructor
listener registration and cleanup are explicit lifecycle adapters. The owner,
guard, handler and SDK methods are declared controlled boundaries; route helpers
and the lease registry execute current production code. Four compiled
counterfeits must fail their exact behavioral assertion: bypassing the restore
route gate, ignoring an unowned session, prematurely closing the native lease,
and accepting a deferred checkpoint from an old navigation epoch.

The failure reproduction can select the pre-fix production `PageMemory` and
`DraftArchive` classes without replacing their implementations with a model:

```sh
python3 tests/local-draft-policy-host/run.py \
  --before-ref a7f1d7410ff0b7e9e0f97ff3ab8a71420408d7c7 \
  --json-jar /path/to/json.jar
```

That mode should fail its two disabled-policy assertions while its two sanity
checks pass. Every report records the selected immutable class hashes, the
current fixture/adapters, and whether execution inputs changed during the run.
The default current-code mode must pass all assertions. CI must invoke this
runner explicitly; placing the directory here alone does not run it.
