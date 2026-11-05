# Real Chromium page Worker controls

```sh
python3 tests/chromium-worker-browser/run.py \
  --chromium /usr/bin/chromium --output work/chromium-worker-browser
```

Requires a real desktop Chromium, modern Node with WebSocket, and permission to
bind loopback sockets. A fresh temporary browser profile loads controlled local
HTTP pages; loopback is a browser trustworthy context for Service Workers.
Only the test enables a loopback CDP endpoint. Production remains unchanged.

The exact production asset executes before inline scripts in the page and a
frame. Native Dedicated/module/Shared Worker scripts and Service Worker
registration execute in allow mode, are refused in restrict mode, and execute
again after a new allow document. Independent server counts require script
requests on both allow documents and zero corresponding requests under
restrict. A deliberately earlier Worker and an already activated Service
Worker remain executable, documenting the feature's boundary.

This is desktop page-semantic evidence. It does not prove AndroidX injection,
Android ServiceWorkerWebSettings enforcement, UA-CH identity or Worker realm
fingerprint spoofing. The report sets these Android/coverage claims false.
