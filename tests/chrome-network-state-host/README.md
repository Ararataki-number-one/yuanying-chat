The runner executes the complete production `WindowNetworkState` constructor,
the actual initial chrome metadata expressions, and the whole production chrome
update/render/metadata methods. Its callback queues make catalogue completion,
UI delivery, destruction and repeated updates deterministic.

The adapters model Android view storage, preferences, catalogue rows and an
already-produced network observation. This is a host regression test: it does
not execute Android scheduling, SQLite, Gecko, the native core or real latency
measurements. The controlled `42 ms` and `02:00` values test display preservation.

`--before-ref 62a0ff6` executes the historical production methods, expects the
same valid route to display normally, and retains the actual failing report.
The complete-row constructor control still passes in that run.

The state matrix additionally executes the complete constructor and `mainline`
method with controlled timestamps and identities. It distinguishes an available
environment with unverified state from an unavailable process, rejects missing
or zero timestamps, and preserves the existing 60-second future-clock tolerance.
The original metadata/render checks remain; three exact labels change from
`未运行` to `状态待核实` while retaining their disconnected assertions.

The runner also executes the complete `readModelFreshnessChecks` method extracted
from the Android network fixture. This verifies the device fixture and its raw
projection shape with host adapters; it is not Android execution. The Android
fixture must execute those same 14 named checks on the selected APK, and the
existing interaction gate requires every case and its recorded input/output.
The existing per-check log transport carries bounded raw projections; the final
Android log message does not grow by the full matrix. Identity-mismatched readings
are retained as observations without requiring their IP or latency to remain
visible or treating them as trusted history.

Run once per pinned Android and desktop JSON library:

```sh
python3 tests/chrome-network-state-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/json.jar \
  --output /path/to/chrome-network-state-results.json
```
