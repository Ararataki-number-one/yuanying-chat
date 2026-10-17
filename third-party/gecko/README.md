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
