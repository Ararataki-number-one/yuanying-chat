# On-demand browser API observations

The production `main-world-audit.js` executes these checks only when the native
self-check explicitly supplies `apiChecks: true`. The existing light check does
not draw/read canvas pixels, render offline audio, or measure the fixed font set.
There is no timer or MutationObserver that repeats these API checks during chat.

Each `sample.apiChecks.probes` entry reports an operation state (`available`,
`restricted`, `failed`, `uncovered`) and a reason. SHA-256 digests are local
observation values, not an anonymity or privacy-protection verdict. A changed
hash may be expected randomization/standardization. Font checks and widths are
not proof that a named font is installed. Probe coverage is only the current
page's main execution world; frame/Worker API operations remain uncovered.
If CSP blocks that world, the isolated extension fallback cannot fill its data.

Limits are finite: a 128x32 canvas, 2048 offline audio frames at 44100 Hz (no
speaker output), five font candidates, and one 16x16 WebGL context with seven
selected extension names. Work yields between probes; a cooperative 1200 ms
elapsed guard stops starting further operations, with shorter asynchronous
waits. JavaScript cannot preempt a synchronous native browser call, so this is
not a hard CPU/frame guarantee. WebGL/audio/worker/frame/blob resources are
retired after completion, timeout, cancellation or page exit. A removed/late
main-world script has its configuration cleared so it cannot start a new probe.

Run the existing bridge boundary test and the optional real-browser check:

```sh
node tests/review-host/audit-bridge.test.cjs
python3 tests/fingerprint-api-probes/browser_probe.py \
  --chromium /usr/bin/chromium --output /tmp/fingerprint-api-browser-results.json
```

The optional check requires Python Playwright and a local Chromium binary. It
serves only a loopback fixture, uses a fresh browser context and software WebGL,
and labels security-denial, missing-API, pending-audio, graph-setup and cancel
fault injection. It checks real canvas/audio/font/WebGL operations in Chromium;
it is not Gecko, Android, RFP effectiveness, ChatGPT or physical-phone acceptance.
The Node test uses a DOM/port harness, so its CSP/error tests are protocol failure
injection rather than a real Gecko CSP test. The existing original bridge
controls remain in that file unchanged; the new controls are additive.
