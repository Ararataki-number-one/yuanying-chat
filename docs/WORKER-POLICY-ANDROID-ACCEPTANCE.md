# Android Chromium Worker policy acceptance

The Worker option defaults to `allow` for existing saved environments. `restrict`
adds page/frame creation guards for Dedicated and Shared Workers and Service
Worker registration. Native `ServiceWorkerWebSettings` separately blocks later
Service Worker network loads while the policy or route is unconfirmed, or the
confirmed policy requests restriction. It does not terminate existing workers,
prevent all cached execution, cancel in-flight requests, or spoof Worker realm
fingerprints. These boundaries remain false in every acceptance report.

The independent real-device command is:

```sh
python3 tools/browser/run_worker_policy_integration.py \
  --adb adb --serial emulator-5554 --output work/browser-acceptance
```

It uses the actual integration APK built from clean selected source, verifies
the installed source/tree/APK/SDK identity, clears only integration app data,
and drives production `BrowserActivity.saveFingerprint` through allow, restrict,
fresh route admission under restriction, and allow restoration. The 43 checks
require actual provider readback, real page/frame outcomes, real Service Worker
cache execution, rejected subsequent network traffic, stale policy/callback
rejection, and new revision/surface/document bindings. SharedWorker absence is
reported as unsupported; Dedicated, module, Blob and Service Worker execution
must actually succeed in allow mode. Existing fingerprint and browser gates
remain separate.

`newworker_fixture_server.py` is a closed loopback HTTP proxy to exactly
`fp-a.pocketchat.test` and `fp-b.pocketchat.test`. It never forwards traffic.
TLS keys are freshly generated under host `/tmp`, never sent to Android or
placed in source, APKs or artifact directories. Only the public CA is installed
into the controlled emulator's user CA store, with actual root/user/SELinux,
public-byte readback and cleanup checks. Shell evidence is read as UID 2000.
Integration-only trust remains scoped to the two exact domains. Native TLS
certificate hashes must match the actual ephemeral leaf; no TLS error bypass
or permissive verifier is used.

The native fixture and independent host count actual HTTPS requests by engine,
policy phase, realm, document UUID and allowlisted UA/UA-CH headers. A single
forbidden Worker script or fetch request under either restricted phase fails
qualification. Successful allow and restored phases require positive script and
network receipts, so zero requests alone cannot pass.

The runner writes only `worker-policy-results.json`. The public gate calls
`verify_worker_policy_evidence(directory, source, expected, reader=source_bytes)`
from `check_worker_policy_evidence.py`; it independently verifies all behavior,
trust cleanup, selected-source hashes and same source/tree/APK/SDK run/attempt.
It also binds the current page receipt to the actual environment owner, provider,
runtime, surface and navigation. This report does not replace
`browser-fingerprint-results.json` or the original browser result.

Local controls (synthetic report schemas and real host TLS, not Android):

```sh
PYTHONPATH=tests python3 -m unittest -v \
  browser_worker_policy_evidence_test browser_worker_policy_server_test
```

The server additionally supports a separate Gecko measurement script and
receipt bucket. `/env-policy?phase=gecko-coop` alone adds the actual COOP
`same-origin` response header. Served worker responses include direct native
Date/Intl January/July observations for Gecko's separate native timezone gate.
This additional support does not qualify Gecko until its own real-device
fixture and checker pass.
