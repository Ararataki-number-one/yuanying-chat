# Local controlled Mihomo chain baseline

Run: `python3 work/chain-performance/benchmark.py`. Results are ignored investigation artifacts, not release acceptance or a phone performance claim.

Uses the official same-version Linux Mihomo 1.19.31 binary. Download receipt and SHA are in core-receipt.json. Source is the repository's fixed v1.19.31 tarball. No system Go compiler was installed, no SDK or core production changes were made.

Two configurations share exactly the same entry SOCKS, fixed-exit SOCKS, generated local-only credentials, HTTP/HTTPS destinations, trusted local fixture certificate, and deliberate per-stage waits. Entry allowlist only permits the fixed-exit fixture; fixed exit only permits the two target fixtures. Four actual core processes run AB/BA. All 200 outgoing circuits pass both authentication stages; all 280 HEAD responses succeed.

Same-core config overhead is small in this experiment: HTTPS cold medians 301.43 vs 300.06 ms; HTTPS reused medians 62.48 vs 63.94 ms. The approximately 239 ms gap is cold versus reused HTTPS, not app versus Clash config. Controlled keepalive unified probes report 61.5 vs 63 ms, while Connection:close probes report 302.5 vs 306 ms even though core reports positive alive/history.

The HTTP `warmHead-http` rows only retain the client-to-proxy socket. This core forwarding path opens fresh target circuits, so these rows are not warm target transport. HTTPS CONNECT rows genuinely reuse a target TLS connection.

Limits: Linux loopback, simulated stage waits rather than WAN packet RTT, literal IP fixtures (no DNS workload), no user node credentials, no physical phone, no Clash Verge GUI, no browser-engine measurement. This establishes cost mechanisms but does not reproduce or resolve the user's 100 ms versus 400 ms comparison.
