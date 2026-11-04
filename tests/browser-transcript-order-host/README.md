# Transcript order cache workload

```sh
JSDOM_MODULE="$PWD/work/chat-smoothness-deps/node_modules/jsdom" python3 tests/browser-transcript-order-host/run.py
```

The runner executes the complete production `page-driver.js`,
`web-performance.js` and `web-reply-observer.js` from commit `f43adac` and the
current workspace without modifying either source. Reports bind source and
harness hashes and require that production assets remain unchanged during
execution.

The fixed workload contains 1,200 messages and 20 streamed updates to the last
reply, each followed by a transcript snapshot. Node24 produced 47,960 DOM
order comparisons in the prior source and zero after warming the new cache.
Both versions rebuilt exactly 20 entries and emitted identical full deltas.
The test requires a positive prior count and zero current comparisons; the
exact prior count can depend on the JavaScript engine's sort implementation.

The current source passes 70 checks, including 27 topology mutation scenarios
and two additional streaming-cache assertions; the baseline passes 41 checks.
Every complete delta is compared, including order, identities, contents,
attachments, downloads, resets and revision. Current topology reads occur in
the same task as the mutations; baseline reads permit its original observer
microtask delivery before comparing the resulting document state.

Coverage includes moved and removed message wrappers, role/search-unit
membership changes, nested owner deduplication, positional identities,
malformed dual-role multiplicity, detached edits and reattachment, hydration,
content/identity/file attribute changes without sorting, completion, errors,
resource/upload transitions and older/absent-helper fallback. Drafts, cookies
and zero-send/zero-fetch behavior are checked throughout.

These are deterministic DOM operations in JSDOM with explicit innerText and
geometry adapters. No Gecko, Android, real website or frame timing is claimed.
The dynamic assets remain outside the built-in extension manifest, so this
change does not alter its version or installation protocol.
