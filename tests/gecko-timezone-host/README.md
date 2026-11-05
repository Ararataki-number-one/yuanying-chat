# Independent Gecko timezone host checks

Use JDK 17 with each JSON implementation:

```sh
python3 tests/gecko-timezone-host/run.py --java-home "$JDK17" \
  --json-jar work/ux-build-deps/json-20240303.jar --output work/timezone-store.json
python3 tests/gecko-timezone-host/report.py --java-home "$JDK17" \
  --json-jar work/ux-build-deps/json-20240303.jar --output work/timezone-report.json
node tests/gecko-timezone-host/signal.test.cjs --output work/timezone-signal.json
```

Repeat the Java commands with `work/ux-build-deps/android-json.jar`. The store
harness compiles the complete current spec/store/policy and the actual
`EnvironmentSpec`, strict `NetworkShareJson` parser and `J`. Real `java.time`
TZDB rules cover whole-hour, half-hour and quarter-hour zones and DST. Actual
temporary files, Java file locks, random tokens, concurrent callers and separate
JVMs exercise CAS, owner/generation reuse, publication failures, process restart,
late ACK rejection and independently bound live native sessions. Context,
catalog identity transactions and atomic vault operations are explicit adapters;
Android SQLite and Keystore are not executed.

The report harness compiles the complete current `AuditReport`. An independent
timezone item needs current native ACK eligibility, a fresh main-world sample,
the exact requested zone name and a numeric timestamp/offset from that sample.
It evaluates IANA rules at the sample time, including a DST transition between
sampling and report delivery. Unknown aliases remain uncovered; equal current
offsets never prove equal regions. Missing/stale/isolated signals and absent ACKs
cannot fall back to the phone timezone. Original system/RFP cases remain checked.

The JS test executes the verbatim current `signal()` with explicit Date, Intl,
navigator and canvas boundaries. It checks a single Date supplies both sample
time and offset and compares all prior fields to the original function extracted
from commit `8a0a487002993f5dacc02ed313fab00648ccb79a`. The fixture pins the
original complete source SHA and method SHA; its origin was verified with
`git show` before copying it. Three mutations demonstrate detection of a missing
sample timestamp, a separate clock read, and a second Date across a transition.
The historical fixture avoids depending on shallow checkout history.

All reports bind actual source/test hashes and check unchanged execution inputs.
These tests use synthetic native ACKs and public signals. They do **not** prove
Android execution, actual BC support, page Date/Intl behavior, Worker or Service
Worker coverage. Actual native support is a separate device-probe gate. The
application does not modify Android's timezone, inject a fake Date or weaken RFP.
