# Unused authenticated exit sockets: controlled wire experiment

`python3 -B work/exit-preauth-benchmark/benchmark.py --pairs 20`

This is a separate Python protocol candidate. It executes actual nested SOCKS5
authentication, target CONNECT, trusted target TLS and HEAD over loopback TCP.
It does **not** run a pooled production Mihomo core, Android or user WAN nodes.
The preserved 200-circuit configuration comparison and 52 native trace cases
were not changed or rerun.

The candidate socket has reached the fixed exit and completed method selection
and authentication. It has **not** sent the website CONNECT command. One socket
can be checked out once. An established SOCKS CONNECT stream cannot be reused
for a different target. Target CONNECT, TLS and the entire response remain on
the request critical path in both variants.

The fixture deliberately waits 80 ms before entry setup, 15 ms before each
entry SOCKS response, and 35 ms before each exit SOCKS response. These are server
response delays, not measured WAN RTTs. The client never subtracts individual
node readings. Both variants use the same actual entry, fixed exit, destination,
SOCKS authentication frames, target TLS verification and 204 HEAD response.

`results.json` contains 20 paired AB/BA trials, all preparation durations, socket
handoff IDs, frame lengths/digests and 1,744 wire send/receive events. Cold
request p50/p95 was 249.84/259.97 ms; prepared request p50/p95 45.28/67.45 ms.
Preparation still cost median 201.30 ms. Total socket work was similar:
249.23 ms cold and 247.02 ms prepared. The candidate moves work ahead of demand;
it does not remove that work or improve physical network distance. A miss takes
the original complete cold path. Prepared lead time and preparation cost must
remain visible in any comparison.

Thirty protocol checks include no website CONNECT during preparation, capacity,
one-time checkout, environment mismatch, TTL expiry, entry/lifetime purge,
cancellation with a real socket EOF, restart after checkout, and a cold miss.
EOF is bound to an exact accepted socket by real source ports, not a global
counter. Entry cancellation includes the injected entry setup delay. The test
certificate private key remains local and must not be copied to an evidence
archive or APK.

## Reuse the fixtures for a native implementation

`python3 -B work/exit-preauth-benchmark/serve.py`

The first JSON line gives two actual entry servers, one fixed exit, a trusted
public certificate and an HTTPS target. Write `{"action":"snapshot"}` to stdin
to get original socket events; write `{"action":"stop"}` to finish. The
credentials are generated local fixture credentials, never user nodes.
Go tests can start this child process and feed these addresses to the actual
SOCKS transport. Linux live Mihomo can load the equivalent two-entry/fixed-exit
configuration. Android can use `adb reverse` for the listed ports and the
existing integration-only certificate trust hook. The SOCKS target retains
`bench.invalid` as an ATYP=domain; the fixed-exit fixture alone maps it locally.
No direct or alternate-route target is permitted.

Native acceptance must additionally prove all of the following; the Python
candidate cannot substitute for it:

- Off and on use the same native core build, URL, HEAD, expected 204, entry,
  fixed exit, DNS/IPv4 policy and target TLS parameters. Keep native PID and
  browser WSS unchanged across the paired trials.
- Record actual method/auth completion, checkout, target CONNECT, TLS and first
  response. Join native connection IDs to server source-port events. Assert
  zero target CONNECT/HEAD while prewarming and exactly one target per checkout.
- Include cold core/resolver startup separately, warm core with a cold target
  tunnel, a successfully prepared tunnel, and a pool miss. Do not label repeated
  requests warm without an actual reused socket/stream identity.
- Permit opt-in pooling only for the fixed exit. Key it by the exact entry
  selection and configuration, fixed-exit/auth/TLS identity, environment,
  verified core/service lifetime, route generation and Android default network.
  Node/group aliases alone are not sufficient.
- Purge unused, preparing and checked-out-but-not-handed-off sockets on route,
  network, restart, deletion or cancellation. Late work must close its real
  socket before publishing. TTL and capacity must bound idle resource use.
- A stale/closed prepared socket may take one same-route cold establishment
  attempt only before any application data is handed off. It must not replay
  HTTP requests, switch fixed exits or fall back to direct networking.
- Actual Android tests must exercise two environment processes, core restart,
  deletion, cancellation, untrusted TLS, authenticated error paths and existing
  WSS. Compare CPU, memory, idle battery/socket count, p50/p95 and failure rate;
  faster isolated medians are insufficient if p95 or active transfers regress.

## Source-backed comparison boundaries

The app's line probe calls `FixedExit/delay` for HTTPS gstatic. Its website
first response uses a separate Java HTTP HEAD for ChatGPT and intentionally
closes the probe's previous tunnels. The latter stopwatch starts after the core
is running, so it is not the app's service-start duration.

Official Mihomo URLTest invokes the named adapter and its configured
`dialer-proxy` dependencies. An entry card does not automatically include a
downstream fixed exit that happens to use that entry. An exit card can include
the chain if its adapter has that dialer dependency. Two card numbers cannot
be added or treated as the complete-chain reading.

The normal forced-listener HTTP CONNECT path selects `SpecialProxy` before DNS
rules; SOCKS5 retains the target domain and lets the exit resolve it. The local
DoH nameserver `#FixedExit` is not automatically in that target's critical path.
Entry-server hostname bootstrap uses the proxy-server resolver and needs its
own trace. XUDP only applies to VLESS UDP; the current TCP-only fixed exit does
not gain HTTPS/HTTP3 transport by setting an XUDP flag.
