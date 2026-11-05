# Generic Gecko download source metadata

```sh
python3 tests/generic-download-source-host/run.py \
  --java-home /path/to/jdk-17 \
  --json-jar /path/to/org.json.jar \
  --output work/generic-download-source/results.json
```

The runner extracts complete production `FileDownloads` methods for
`downloadSource`, `acceptResponse`, `accept`, `newTask`, `sameSource`, `valid`,
`https` and filename/MIME helpers. It compiles actual `J` and
`BrowserRuntimePolicy` against the supplied real JSON dependency. Its explicit
owner predicate delegates to `BrowserRuntimePolicy.official`, covering the
ChatGPT origin including the port requirement.

The native-response tests execute the actual response consumer and copy known
synthetic bytes into temporary host files. They verify current generic HTTP(S)
page metadata in both the task and active source, one shared URL sample, wrong
ChatGPT port/scheme handling, and continued GPT conversation/DOM restrictions.
An HTTP native response remains distinct from active URL fetching: actual
`accept` must still reject HTTP and unsafe URL activation without a task,
worker, DOM driver or client dispatch. Positive HTTPS URL activation preserves
its existing worker dispatch. Existing attachment metadata, task persistence
failure and route denial retain their original behavior.

The test defines no Gecko SDK package. `WebResponse` is renamed to the explicitly
supplied `ResponseBoundary`, while Android URI parsing is replaced with the JVM
URI boundary only in the actual HTTPS predicate. Browser location, task storage,
filename/MIME lookup, network admission, worker/Handler queues and sealed-file
lease are controlled boundaries. Publication, real URL fetching and DOM/blob
execution are outside this test; unexpected blob/DOM dispatch fails. No Android,
Gecko native API, TLS, socket, actual private data or user-file result is claimed.

Six focused controls compile temporary copies restoring the stale GPT task or
active-source assignment independently at each actual consumer, restoring the
old source helper, or disabling active URL refusal. Each pristine focused
schedule must pass, and each mutant must fail its precise original assertion.
Generated sources, source/dependency hashes, commands and raw logs accompany the
report. The production files are never rewritten for these controls.
