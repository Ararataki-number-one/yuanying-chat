The host executes the complete production chrome renderer and state constructor,
the actual fixture snapshot/capture/presentation/lifecycle methods, and the whole
test-only `CompactChromePresentationCapture` helper.

A controlled Android callback queue reproduces the old sequence: synthetic paint
at 200 ms, an actual queued production render at 250 ms, and the old report at
300 ms. `--before-ref 62a0ff6` retains a failing expectation for that old sequence.
The current capture waits for a matching laid-out frame; tests also execute the
actual release paths for completion, errors, deadline, destruction and replacement.

Views, handlers, catalogue data, runtime observations and frame/layout delivery
are narrow host adapters. They are not real Android frames, SQLite, native-core
or latency measurements. The geometry report callback records displayed values;
the original full report body (apart from two scope labels), Android runner,
42 ms / 120-second sample and 200/100 ms preparation intervals are checked for
source preservation. Real geometry, touch targets and the original Android
runner remain mandatory device acceptance.

Run with the pinned desktop and Android JSON implementations:

```sh
python3 tests/compact-chrome-capture-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/json.jar \
  --output /path/to/compact-chrome-capture-results.json
```
