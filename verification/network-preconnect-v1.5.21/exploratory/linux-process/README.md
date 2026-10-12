# Actual complete-core controlled process experiment

This runs the exact local `work/mihomo-build/bin/mihomo-linux-amd64` process, with the production patch SHA `24f9b3a5db65265bc719107bc1eb79752c4e115e1babdfc79838237abc849ef9` and source commit `140a9d840d42af21754d6791c1e6e2dde8a01559`. It does not edit the core, app, caches, or frozen prototype. All network destinations are loopback fixtures with public test credentials.

`results.json` contains four fixed AB/BA pairs. Each request uses a new client TCP connection to an actual forced `PocketOnly` mixed listener, then trusted target TLS and HEAD. Both environments load raw provider nodes, apply the actual `Entry|` prefix, and resolve the real `EntryChoice` selector and `dialer-proxy` wrappers. The baseline has only the preconnect option false. Production has it true plus its own private ready network epoch file.

Actual request p50 was **270.97 ms baseline / 77.22 ms production ready**. Deliberate server delays were entry setup 80 ms, each entry SOCKS phase 15 ms, each fixed-exit phase 35 ms. Preparation itself still took **199.98–209.17 ms**, ahead of the measured request. This establishes critical-path phase shifting, not less total network work, a lower physical RTT, or a WAN/Android/browser speed guarantee.

The timing field `targetTlsMs` spans the client TLS phase after the mixed listener ACKs CONNECT; it includes any still-pending proxy chain setup. It is not an isolated target TLS RTT. Overall request time and actual wire phases establish the reported comparison.

Every successful production sample has a pre-request wire snapshot showing its specific exit socket already authenticated and lacking any destination CONNECT. The request consumes it once, traverses the same fixed exit, and performs target CONNECT plus a new target TLS handshake and HEAD. Entry, exit, and target socket IDs are joined through actual TCP source ports; no direct request reaches the target.

The primary process run tested the controller with default unified-delay false (one first probe, 276 ms), retaining the exact idle socket. `focused-unified/results.json` separately runs the actual app setting `unified-delay: true`: first 257 ms, second 247 ms, two fresh authenticated probe sockets, `cold-retest`, and the exact ready exit-5 remains untouched. The server intentionally closes target HTTP connections, so `secondConnectionReused: false` is expected. This test never consumes or refills the business preconnect pool to make latency look smaller.

All unsuccessful harness attempts are retained. They include controller publication preceding selector installation, an ignored incorrect fixture-CA field, executor InnerLoading preceding full running state, a focused launcher path typo, and an incorrect `first` oracle for a correctly reported `cold-retest`. No failed runtime sample is silently replaced. The final readiness barrier uses only stable controller/provider snapshots before the first request, and confirms zero prior fixture wire traffic. No measured handshake is retried or paced by the harness.

The Linux binary SHA/version/build metadata and exact locked patch/recipe are recorded. The Android build receipt itself does not contain a Linux binary byte hash; its fields should not be misrepresented as independent Linux reproducible-build proof. Android acceptance remains the separate normal CI suite.
