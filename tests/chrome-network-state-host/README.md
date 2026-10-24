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

Run once per pinned Android and desktop JSON library:

```sh
python3 tests/chrome-network-state-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/json.jar \
  --output /path/to/chrome-network-state-results.json
```
