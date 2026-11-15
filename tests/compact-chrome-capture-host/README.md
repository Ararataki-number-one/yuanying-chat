The host executes the complete production chrome renderer and state constructor,
the actual fixture snapshot/capture/presentation/lifecycle methods, and the whole
test-only `CompactChromePresentationCapture` helper.

A controlled Android callback queue reproduces the old sequence: synthetic paint
at 200 ms, an actual queued production render at 250 ms, and the old report at
300 ms. `--before-ref 62a0ff6` retains a failing expectation for that old sequence.
The current capture waits for a matching laid-out frame; tests also execute the
actual release paths for completion, errors, deadline, destruction and replacement.

Views, handlers, catalogue data, runtime observations and frame/layout delivery
are narrow host adapters. They are not real Android frames, SQLite, native-core
or latency measurements. The geometry report callback records displayed values;
the original full report body (apart from two scope labels), Android runner,
42 ms / 120-second sample and 200/100 ms preparation intervals are checked for
source preservation. Real geometry, touch targets and the original Android
runner remain mandatory device acceptance.

The browser address row adds a separate, exact source comparison layer. Its
5329-byte `report` member must match the pinned current hash before two complete
insertions can be reversed: the five-control measurement block and its two JSON
fields. The result must match the unchanged 3982-byte v2 member. The original
v2 inverse then restores the unchanged 3507-byte presentation member and, after
the two existing scope labels, the original 3445-byte report. Unknown fields,
partial additions, moved measurements and changed original or browser geometry
are rejected. Separate controls exercise each inverse even when only that
layer's current input hash is replaced. These source inverses feed only the
historical report assertion; Java extraction uses the actual current methods,
and live Android acceptance still requires the measured browser address row.

Run with the pinned desktop and Android JSON implementations:

```sh
python3 tests/compact-chrome-capture-host/run.py \
  --java-home /path/to/jdk17 --json-jar /path/to/json.jar \
  --output /path/to/compact-chrome-capture-results.json
```

The character adapter now also covers legal Android end ellipsis. It follows
`Layout.Ellipsizer` and `Layout.ellipsize` from AOSP `android-15.0.0_r1`:
https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/text/Layout.java
Given an already chosen line range, `getChars`/`charAt`/`subSequence` replace its
first character with U+2026 and the rest with U+FEFF while preserving source
length. The host does not calculate fonts, line breaks or real ellipsis bounds.
The `TextUtils.equals` adapter compares actual characters, including this
non-String representation, following the same platform version.

`--before-ref 4644e90` runs the current controls against the original full
fixture methods: legitimate title/address ellipsis prevents a ready report and
reaches the unchanged 20-second failure. The corrected fixture accepts the real
laid-out text while retaining exact untransformed model matching. Missing
Layouts and `setText` followed by pending layout still block capture. The older
host control which directly replaced `layoutText` without setting a layout
request was corrected: that adapter invented a stale-text predicate rather
than modeling Android's legal transformed Layout text. The original Android
geometry/ellipsis assertions and runner are unchanged.

The 46 update scene changes only its readiness text to `当前安装版本`. A scoped
inverse restores that single dictionary entry before the original readiness-map,
capture-function and full-module AST checks. All prior expected digests, actions,
deadlines and 44 host cases remain intact; other label/scene changes are rejected.
