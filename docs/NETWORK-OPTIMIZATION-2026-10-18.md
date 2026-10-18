# Network optimization, 2026-10-18

Baseline: `80606539a3e58e66dc0f454d2d19fa823729b257`, following the 2.0.9 release.
User observations: 409 ms complete-route reading, 3168 ms initial response;
an earlier update download showed 26 KB/s through environment 2.
These measurements do not identify the dominant DNS, proxy, TLS or server phase.

## Changes

- Automatic selection previously chose the website-quality store as soon as the
  current route had three successes, even when no challenger had comparable
  website evidence. This could exclude a proven faster complete-chain route.
  Website comparisons now require recent successful observations and at least
  three samples for the current route and a challenger. Otherwise selection uses
  complete-chain evidence. Recent website transport failures exclude a challenger;
  challenges are inconclusive. Pool membership, busy deferral, cooldown, repeated
  wins and the fixed exit remain enforced.
- Updates with at least 8 MiB remaining can use two concurrent bounded ranges on
  the selected route. A one-byte probe first requires exact range support and a
  strong ETag. A server ignoring ranges or omitting a strong ETag keeps the serial
  path. Redirect trust, every segment's size/range/ETag and the final full-file SHA
  and APK signer checks remain enforced. There is no mirror or direct fallback.
- Two segment offsets are checkpointed only after file synchronization. Sparse
  file size never represents completion. Existing serial partial files migrate;
  pauses and reconstruction preserve both offsets. Route invalidation and cancel
  close every connection, and transfer completion waits for both workers to exit.
- The resolved official asset URL is reused by both ranges within the attempt;
  a new attempt resolves the original URL again so expired CDN links are refreshed.

## Verification

- Actual HTTP parallel-transfer tests: 19 checks, including throttled concurrency,
  pause, reconstruction, both resume offsets, serial migration, route revocation,
  transient failure, changed ETag, invalid ranges, sparse-file recovery and cleanup.
- Same local per-connection throttle: 8 MiB plus 123 bytes took 859 ms serial and
  497 ms with two connections in the final run (about 42% less elapsed time).
  This is a controlled HTTP test, not phone or WAN throughput evidence.
- Existing actual HTTP resume/security tests: 28 checks passed.
- Production route-comparison tests with in-memory preferences: 10 checks passed.
- Scheduler policy tests: 49 checks passed.
- The broader profile host runner passed before the final route transport-failure
  exclusion was added; the changed comparison and transfer suites were rerun.
- All application Java sources compiled against the verified official GeckoView
  157 API and Android 37.1, including generated Android resources. This is source
  compilation, not a packaged SDK-derived APK build or Android runtime test.
- New tests are connected to the existing host and integration workflows.

## Remaining Evidence

No connected ARM phone or local KVM is available. Android runtime validation of
parallel download cancellation across processes, a signed APK build and release
publication have not been performed for this change. Existing small-file Android
fixtures continue to exercise the serial path; they do not prove the new parallel
path. The user's actual proxy/TLS/first-byte diagnostic is still needed to locate
the 3168 ms wait. No claim is made that 409 ms has become 200 ms or that a shared
exit bandwidth limit can be removed by adding another connection.

## Window Diagnostics Follow-up

The current window-details dialog and the active About screen did not expose
the older copy-diagnostics action. Window details now links to a selectable,
copyable diagnostic view. It uses that window's runtime snapshot, not the
viewing process's ChatSession, and does not start a probe or reconnect.
Configuration-mismatched measurements are excluded; old measurements are marked.
Existing native probe formatting is reused, with an explicit distinction between
the probe website's phase timings and ChatGPT's separate first-response result.
Export excludes node addresses, subscription URLs, credentials and chat content.
All application Java sources compiled again and `git diff --check` passed.
The new modal has not yet been exercised on an Android device or packaged.
