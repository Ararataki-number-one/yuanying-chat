# Browser control observation workload

Run with an existing JSDOM installation:

```sh
JSDOM_MODULE="$PWD/work/chat-smoothness-deps/node_modules/jsdom" python3 tests/browser-controls-performance-host/run.py
```

The runner executes the complete `page-driver.js`, `web-performance.js` and
`web-reply-observer.js` from commit `1e3086a` and the current workspace, without
rewriting either source. The report records their hashes, the harness hashes,
observable output parity and deterministic operation counters. Sources must
remain unchanged during execution.

The measured scenario warms the observer, then performs 40 streamed updates
and 40 pairs of inspect/reply polls with 600 historical controls labelled
`Copy response`/`Rename chat`. It dispatches scroll/input events and checks
that reply, error, draft, cookie and zero-action behavior agree. Current source
must rebuild no page-wide button collection or attribute group in this loop.
The before/current document-wide button queries are 200/0, materialized query
nodes 120800/0 and control `aria-label` reads 120880/160. Text-only controls
remain live fallbacks; this workload does not claim the same reduction for
pages whose historical controls all lack labels.

The 80 current-source checks also cover same-task insertion/removal and subtree
moves, role/label/test-id changes, localized and text-only controls, SVG text,
CSS visibility, retry context, completion, actual resource/upload APIs, older
helper fallback, and complete transcript invalidation after synchronously
draining the shared observer. The prior source passes 76 equivalent checks;
four additional assertions require the new cache counters and reuse behavior.

JSDOM uses explicit `innerText`/geometry adapters. These are DOM operation
counts, not Gecko, Android, real website, elapsed-time or frame-rate evidence.
The production assets are loaded dynamically by `ChatSession`/`WebReplyObserver`;
they are outside the built-in extension's `content_scripts`, so this change
does not alter its manifest or version protocol.
