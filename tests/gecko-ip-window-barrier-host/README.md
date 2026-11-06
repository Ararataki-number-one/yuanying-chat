# IP lookup window barrier host

Run the current production `startTimeZone`, gate/liveness methods and application
session-ID adapter with explicit SDK, controller, scheduler and IP-transport
boundaries:

```
python3 tests/gecko-ip-window-barrier-host/run.py --java-home JDK17 --json-jar JSON.jar --output results.json
```

The workload covers initial preparation and revalidation while the SDK window
result is pending, true, false, failed, timed out, late, or retired. It preserves
the original five-second deadline and checks session, gate, document, port and
route ownership again when the queued lookup continuation executes. A false
window may still enter the original controller preparation path for manual
system-timezone fallback; it must never enter IP lookup. Read/apply retain their
existing window gate.

The actual before-image from Git and two separately compiled guard mutations
must fail precise behavioral assertions. Current acceptance always extracts raw
current production methods. This host does not execute Android, Gecko,
networking, native settings, or page/worker timezone effects, and supplies no
native success receipt. `GeckoResult` dispatch is an explicitly queued model;
the real SDK API is checked separately by production compilation.
