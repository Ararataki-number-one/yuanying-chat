# Independent Chromium file workflows

```sh
python3 tests/browser-files-host/transfer.py --java-home work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64
python3 tests/browser-files-host/chooser.py --json-jar work/ux-build-deps/json-20240303.jar --output work/browser-files-chooser-desktop-final
python3 tests/browser-files-host/chooser.py --json-jar work/ux-build-deps/android-json.jar --output work/browser-files-chooser-android-final
```

`transfer.py` runs the complete production `BrowserDownloadTransfer` and
`BrowserAddressPolicy`: 68 checks cover GET/identity headers, per-target cookies
across redirects, manual redirect bounds, unsafe/private addresses, TLS
downgrades, route loss at each transfer stage, request-header injection, HTTP
errors/partial status, size/truncation/encoding limits, cancellation, EOF and
private partial-file cleanup. Route and HTTP connection objects are explicit
test adapters; no actual proxy or Android networking is claimed.

`chooser.py` runs the verbatim production chooser prefix, handoff and destroy methods,
complete download store/address/transfer classes, and exact existing saved-file
provider resolution and filename sanitizer. Its 185 checks pass with desktop
and Android JSON libraries. They cover stale request codes, same-URL navigation
cancellation, callback reentry and destruction, malformed picker results,
read-only grants, private providers, MIME/multiple selection, limits, legacy
file targets at slots 0/3, pending MediaStore targets at API29+, and URI-to-file
round trips through the existing provider. The complete production store save
path copies and syncs real API28 fixture files, publishes through a controlled
global DownloadLibrary, confirms identity and saved-byte metadata, and rolls
back failures through a controlled reentrant saved-file deletion boundary.
Cases preserve all original122 checks and add rejected/throwing index writes,
unconfirmed cleanup, newer-publication protection, cancellation, per-slot
global-library filtering, and survival after clearing profile preferences.
External handoff checks retain all162 preceding cases and verify that the
system chooser excludes this app's exported browser component, carries only a
fresh HTTP(S) URL with BROWSABLE category, forwards no cookies/headers/grants,
requires confirmation, and does not report stale/cancelled/failed launches as
successful downloads.
Android activity, intent, provider, permission, MediaStore, catalogue and
SQLite/library boundaries remain explicit adapters; actual system behavior
requires Android integration checks.

Reports record actual production and harness hashes and reject changes during
execution. These host checks do not establish Android permission behavior,
real WebView/provider operation, route proof or end-to-end download success.
