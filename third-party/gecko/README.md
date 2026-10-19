# Gecko input correction

The upstream input is Mozilla GeckoView 157.0.1, Maven coordinate
`org.mozilla.geckoview:geckoview:157.0.20261005135250`, revision
`737ec77d798755890b062aab541a90d6c75afd19`.
`GeckoEditable.java` retains its upstream MPL 2.0 notice. The adjacent patch
records the complete local source change against the pinned sources archive.

The caret correction is confined to non-composition, unstyled single UTF-16 characters
with a collapsed action and shadow selection and exactly one submitted
non-modifier key down. It retains the existing fallback and explicit selection
paths. A returned submission is not a native acceptance acknowledgement.

The `pocket2` build also keeps a pending action in the queue until its reply has
finished updating current text and composing spans. Removing it before that work
allows the IC thread to synchronize an incomplete state. Completion removes the
exact action, preserving newer work after a queue reset. The host barrier test
executes the actual queue and synchronization methods against controlled doubles;
it is separate from Android composition acceptance.

The `pocket3` candidate submits hardware key work through the parent Gecko
Looper, then requests a synchronization reply from the currently focused child
before releasing one queued key. It preserves FIFO order, waits for the actual
reply rather than a returned submission, and invalidates queued work on blur.
There is no fixed delay, selection write, or replay. The parent forwarding fence
and child synchronization are an ordering hypothesis; APZ touch completion and
the intermittent rapid-tap failure still require actual Android evidence.
`run_key_order_host.py` checks the actual candidate queue methods with controlled
parent/child doubles. It cannot establish native touch completion. CI also
predeclares two additional independent Android devices, each running the original
performance and 14-case editing workloads once on the exact same built APK.
All three results must pass; a failed sample cannot be replaced by a rerun.

`tools/gecko/build_caret_sdk.py` verifies the upstream archives, applies the patch
without fuzz, compiles original and candidate source with Java 17, checks sibling
method semantics, and replaces only `org/mozilla/geckoview/GeckoEditable.class`.
All sibling classes and native/resource payloads retain the upstream bytes.
The derived artifact uses its own `local.pocketchat.sdk:geckoview-caret` coordinate;
it never replaces the upstream artifact in a Mozilla dependency cache.

The selected manifest pins the patch, build recipe and resulting archive/class
hashes. APKs include a source/run-bound SDK receipt. The release gate also requires
the unchanged original Android input burst, 14 additional editing scenarios,
actual installed APK definition audits, and the existing independent regression
gates. Compilation and host checks alone cannot establish an input repair.

Baidu IME on a physical ARM phone and real ChatGPT editing, login, attachments,
downloads and sustained use remain a separate acceptance checklist. This change
does not implement independent timezone, Canvas, WebGL, audio or font controls.
