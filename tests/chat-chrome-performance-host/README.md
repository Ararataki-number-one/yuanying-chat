This host suite replays the selected production chrome update/render methods,
metrics maintenance and both snapshot-save overloads. It runs the complete
network-state constructor. The Handler queue and display-frame queue advance
separately, so requests in one Handler turn and separate Handler turns can be
compared without inventing native frame durations.

For 100 requests queued together, the baseline Handler already coalesces work:
the baseline derives two observations and current source derives one. For 100
separate Handler turns before a single controlled display frame, baseline source
derives 200 observations and current source derives one. These are synthetic
scheduling comparisons, not measured Android frame or latency improvements.

The live-projection boundary produces controlled observations and counts calls;
real network projection internals, Android scheduling, SQLite and native timing
are not executed. Inspection of the actual asynchronous save lambda's captured
JSONObject verifies that rendering and persistence share the identical current
observation. Existing signature throttling and runtime-root restrictions execute
through the real save methods.
Moving the saved timestamp back by 5001 ms also checks recurring unchanged
snapshot publication after the original five-second throttle, without sleeping.

Run the same suite against current source and baseline with each JSON library:

```sh
python3 tests/chat-chrome-performance-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/json.jar \
  --output /path/to/current.json
python3 tests/chat-chrome-performance-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/json.jar \
  --before-ref 1e3086a --output /path/to/baseline.json
```
