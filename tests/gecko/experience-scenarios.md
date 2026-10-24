# Optional measured scenarios

This extends the fixed experience experiment, not release acceptance. No Android
samples have been executed by this tooling change. A new baseline must follow the
first/second repair batches and include the identical measurement files in both
source-derived integration APKs. The old 757e0a5 measurements are historical, not
current baseline samples. Preserve every failed run; never replace it with a retry.

The default `--scenario core` keeps the same 13 actions and bounds. The real
MainActivity/AppHub/GeckoView opens a fixed local document through the existing
loopback SOCKS fixture. This measures shell/local processing; it is not actual
ChatGPT, WAN latency, vendor keyboard behavior or physical display presentation.
Normal product timers remain enabled. The fixture is static and localhost, so
ChatGPT-only streaming/resource messages are not part of this benchmark.

| Scenario | Real exercised path | Fixed additional inputs |
| --- | --- | --- |
| `core` | Existing actual UI input and controlled Gecko document | None |
| `download-history-0` | Actual downloads page, DownloadTasks.save, Android SQLite and SharedPreferences | 0 saved records, 1 paused progress record |
| `download-history-1000` | Same | 1,000 saved records, 1 paused record |
| `download-history-3000` | Same | 3,000 saved records, 1 paused record |
| `idle-120` | Normal foreground chat, then actual HOME/onPause background lifecycle | Device target of 120 s per interval; actual callback overshoot remains recorded |

Download scenarios provision current-schema records and 19-byte private files in
the integration package, outside the timed launch. Seed start/end device clocks,
host seed command cost, source input manifest, data/file hashes and its direct
SQLite/production migration scope are recorded separately. Seeding does not claim
to measure the production save chain. The timed additional workload calls the
actual main-thread `DownloadTasks.save` eight times with 64 KiB paused-record byte
increments, spaced by a 2 s handler delay after the preceding observation. This is
controlled persistence work, not HTTP transfer or the product's normal transfer
cadence. The existing downloads navigation oracle additionally requires all
expected real controller rows. Before/after verification checks record identities,
file existence/size, actual prefs and SQLite index counts/progress. It remains
outside each narrow save-call duration; the wider CPU window includes observation
and verification overhead. The original UI/action timeouts remain unchanged; a
large-history workload that cannot finish is a retained failure.

Idle starts only after the full core flow. The foreground interval starts on the
device, and the background interval begins after the actual HOME pause. One device
handler callback ends each interval; no app broadcasts, content-provider reads or
JS probes occur periodically inside it. The start receipt is read from logcat only
for scheduling. After the host wait, the runner must observe a later device
`scenarioFinished` receipt from the same invocation before reading any complete
provider payload. A late callback therefore extends the raw interval; elapsed
host time alone never opens the read boundary. Missing/error end receipts fail
without reading the pending start payload. Full payload/digest and assertions are
then checked through the original event transport. External `/proc` sampling continues. A
visibility interruption, lost process, missing endpoint or truncated frame capture
fails the scenario. The app is resumed and the original document, draft, cookie,
reply fingerprint, send count and native Gecko identities are checked afterwards.

Measurements retain these boundaries:

- Each CPU sample stores raw `ps`, `/proc/uptime` start/end, two `/proc/PID/stat`
  reads around the actual `/proc/PID/cmdline` bytes. The observed cmdline and parent
  must match discovery, and PID/startTicks/name must remain equal around cmdline;
  a race, denied identity read or decreasing counter is unavailable, never CPU
  attributed using a stale `ps` label. Both stat observations and cmdline hex are
  retained on success or failure. This adds fixed observer work, frozen in both
  ABBA builds; these samples cannot be compared to the older observer as a product
  speed change. Accounting keys are `(PID, startTicks)`. Main/profile/Gecko/core names and other
  descendants are explicitly listed when observed; categories are descriptive,
  and an absent category is not proof of zero work. Attribution can miss orphaned
  processes. CPU totals are observed lower bounds; denied counters, process tails,
  short-lived processes and incomplete windows are disclosed. The sampler waits
  1 s after each collection, so it does not claim exact 1 Hz sampling.
- Window CPU uses only complete sample envelopes contained in actual device
  `elapsedRealtime` endpoints. It neither interpolates boundary counters nor fills
  missing data with zero. Native frames instead use uptime timestamps, so the
  clocks are not subtracted from each other.
- PSS comes only from successful, matching-PID/process `dumpsys meminfo` output;
  every raw output/error is retained. Processes are sampled serially and discovery
  is not atomic. The preceding `/proc` starttime is recorded where available; a
  restart during dumpsys remains a limitation. This is not memory peak coverage.
- Native HWUI/foreground Choreographer records have actual uptime timestamps.
  Only delivered frames wholly inside each interval are included. Dropped reports
  and >32/>100 ms observations are descriptive; they do not measure the complete
  Gecko compositor or physical presentation. Empty background frames mean
  unobserved, not zero jank. Existing core swipe timing still begins at ACTION_UP;
  collapse may occur at MOVE, so it cannot identify the first swipe response.
- Startup now exports existing production elapsedRealtime fields (connection
  start, proxy ready, navigation start, first visible, page usable). Zero means
  absent. These are observations, not a fabricated exclusive timing breakdown.

`experience-results.json` contains the canonical `scenarioManifest` and SHA-256,
observer source hashes, each iteration's untimed seed receipt, raw process sample
file, scenario window records, boundary PSS, save-call samples, frame records and
all original preservation snapshots. Raw file hashes/byte counts remain in its
`rawEvidence`; unavailable observations stay unavailable. The paired runner also
freezes the new Java/Python helper bytes and scenario inputs, preserves the ABBA
phase order, and rejects missing/reordered scenario work. Summary differences are
descriptive and do not decide whether a product change improved performance.

Use one new immutable plan per scenario. The following is a recipe only; it must
reference exact post-repair build sources/artifacts, not an old baseline or a
newly rebuilt substitute APK:

```sh
python3 tools/gecko/run_experience_comparison.py prepare \
  --mode baseline \
  --baseline-root /absolute/clean/source-A \
  --baseline-bundle /absolute/original-build-bundle-A \
  --baseline-source FULL_SOURCE_SHA_A --baseline-run ORIGINAL_RUN_A \
  --baseline-attempt ORIGINAL_ATTEMPT_A \
  --repetitions 3 --scenario download-history-1000 \
  --plan work/experience-history-1000-plan.json

python3 tools/gecko/run_experience_comparison.py run \
  --plan work/experience-history-1000-plan.json --adb /absolute/adb \
  --out work/experience-history-1000-original-run
```

For a candidate use `--mode compare` plus the five corresponding `--candidate-*`
arguments. All four ABBA phases use the same emulator boot and fresh installation
of **local.pocketchat.test only**, with three unchanged repetitions per phase.
Each new scenario needs its own frozen baseline and candidate comparison; changing
the scenario between A and B is rejected. Keep setup/native endpoint validation,
normal animations and existing functional/input gates unchanged. The dedicated
`gecko-experience.yml` workflow accepts these five fixed choices through its
`scenario` dispatch input. Selection validates and records the exact manifest/hash
before source checkout or device setup; the sealed plan carries it unchanged
through every ABBA phase. The default and automatic baseline push remain `core`.
The workflow has read-only repository/actions permissions and no release step.
Preparing these tools does not dispatch it or publish an APK.

When dispatch is unavailable, an explicit push to `benchmark/experience-*` can
use `.github/experience-request.json` from that orchestration commit. Commit only
the request on the dedicated branch; the selected A/B application sources stay
unchanged. Selection rejects missing/unknown/duplicate fields, partial source
identities, non-string build references and impossible idle budgets. It records
the request's original byte hash and orchestration source/branch. This path never
discovers or substitutes a newer successful build. A baseline request has exactly:

```json
{
  "schema": 1,
  "mode": "baseline",
  "baseline_source": "FULL_40_CHARACTER_SOURCE_A",
  "baseline_run": "ORIGINAL_BUILD_RUN_A",
  "baseline_attempt": "1",
  "scenario": "download-history-1000",
  "repetitions": 3
}
```

Replace the source/run placeholders with exact original build references before
committing. A compare request additionally requires `candidate_source`,
`candidate_run`, and `candidate_attempt` as strings, and changes `mode` to
`compare`. Use a new immutable request/run; retain original failures. The
`benchmark/experience-*` and `tools/*` branches do not match the production build
or release push triggers. The historical automatic
`release/gecko-2.0.16-experience` push path remains an unchanged-build `core` run.

This workflow restores existing original integration artifacts; it does not build
either APK. A baseline repeats one source/build in all four phases. A comparison
reuses that exact A artifact and requires one separately built B artifact with
the same observer/setup bytes and only the intended product change. Include the
measurement tools before the post-repair A build so the resulting full-CI build
artifact can be reused. Copying new tools beside an older APK is rejected.
The existing fixed integration APK is synthetic and freshly reinstalled per
phase; formal packages and user environments are outside this experiment.

Direct runner usage (already-installed exact APK, one phase) is:

```sh
python3 tests/gecko/run_experience_benchmark.py \
  --adb /absolute/adb --serial emulator-5554 \
  --apk /absolute/exact-integration.apk --source FULL_SOURCE_SHA \
  --label baseline-1 --out work/experience-idle-phase-1 \
  --repetitions 3 --scenario idle-120
```

Runtime is not yet measured for these new scenarios. Idle adds at least 4 minutes
per iteration (48 minutes across 12 ABBA iterations), plus the original core flow,
seeding, PSS and setup. History adds at least 16 seconds per iteration plus actual
save costs; large-history rendering/seed may take substantially longer or fail.
The existing 20-minute phase timeout stays fixed. Plans with five or more idle
repetitions are rejected before artifact/device access because the fixed idle
intervals alone exhaust it. Three remains the default; this is not a guarantee
that every permitted combination completes within the bound. Poll long-running shell tasks
at intervals no longer than 60 seconds to maintain communication.

Deferred scenarios are explicit coverage gaps:

- **P02:** this external-proxy fixture does not execute internal Mihomo/provider
  parsing. It needs a real internal-core fixture with configuration/parse stage
  observations. Calling synthetic parser stand-ins would not measure that path.
- **P04:** one preserved static cookie does not measure real WebExtension cookie
  change bursts, getAll/storage calls, or the persistence checkpoint/restart path.
- **F03:** actual picker/copy/Gecko file handoff and ownership evidence are absent.
  DOM completion alone cannot prove an upload copy is no longer read by Gecko.

Host validation: `python3 -m unittest discover -s tests -p 'gecko_experience*_test.py'`.
These are accounting/contract controls, never synthetic Android speed results.
