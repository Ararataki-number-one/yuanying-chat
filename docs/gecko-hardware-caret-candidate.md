# Isolated Gecko hardware caret candidate

This branch is an experiment against the hash-pinned official GeckoView
157.0.20260924084938 AAR. It does not replace the production browser SDK or
publish a release APK. The integration package uses synthetic documents and
accounts only.

## Recorded official SDK failure

The unchanged-SDK diagnostic source is
`8f61060f7968b6798060947009310fc1f14e69f1`; its complete ten-trial evidence is
`6eb6d06655bbda116db20975f7fcf70d874c7b70` on
`apk/gecko-sdk-input-diagnostics`. All ten attempts are retained; trial 1
failed and trials 2–10 passed.

During the first original single input burst, the Java shadow caret moved
from 24 to 23 while syncing the current text after an accepted native
selection callback. The next original `onImeReplaceText` wrote the third
character at explicit offset 23 rather than 24. The DOM log contained every
expected original trusted key in order. This is evidence of an actual writer
using a stale caret, rather than a delayed selection notification alone.

## Candidate boundary

The candidate builder preserves the original input thread, posting order,
queues, native library and resource records. It changes the collapsed
selection predicate only while the original View `processKey` Runnable is
handling keyboard-source `ACTION_DOWN`, without `FLAG_SOFT_KEYBOARD`, and
after exactly one original nonmodifier synthesized down event actually ran
outside a batch. Multiple down events, including dead-key sequences, retain
the original predicate. The replacement must be an unstyled single character and must
satisfy the existing no-composition and collapsed-selection checks. Only
then can the original negative-offset native-caret path be used. All other
paths use the original predicate.

The helper uses an input-thread scope restored by `finally`; it neither
waits for notifications nor corrects DOM text. The pinned builder verifies
the method and instruction shape, original call counts, bytecode and helper
negative cases. The trace builder reconstructs the entire candidate from
the official AAR before accepting it as diagnostic input.

## Validation sequence

The candidate workflow retains every attempt and publishes partial evidence
after each of ten fixed original single-burst diagnostic trials. It then
rebuilds the same candidate without any SDK observer and executes the
original performance/input gate with no diagnostic flags. A separate real
Gecko fixture exercises Android touch and keyboard actions, different
carets, selected replacement, navigation/deletion, undo, clipboard paste,
and the original InputConnection's commit, composition and batch paths.

`apk/gecko-hardware-caret-candidate` contains whitelisted synthetic reports,
logs, screens and transformation receipts, never an APK, signing key or
browser profile. Its manifest records exact source and run identities,
failed trials, skipped steps and observer-free results. A diagnostic pass
does not substitute for the observer-free original gate or establish real
phone, touch-keyboard, account-login or production acceptance.
