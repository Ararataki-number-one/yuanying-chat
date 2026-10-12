# Isolated Gecko synthesized insertion candidate

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

## First scoped candidate

The first View-origin scoped candidate source is
`860a6777ab4dd09d110f603de8754f2e76fefc50`; its immutable evidence is
`407600ef334e18734f4b38e72e32bb974bec60cc`. Ten fixed attempts were retained:
trial 2 failed when ADB logcat returned 255, and the nine SDK reports passed
without using the candidate predicate. All 99 observed replacements were
batched and retained explicit offsets, so those passes cannot establish a
repair. The observer-free original gate passed 128 checks. The additional
fixture could not read its first page-defined global from Gecko's isolated
evaluation world and completed zero scenarios. The corrected fixture installs
read-only observations in that same world; response HTML still seeds the
initial draft.

## Candidate boundary

The new candidate scopes only the original no-composition
`TYPE_REPLACE_TEXT` branch around `sendCharKeyEvents`, the existing shadow
predicate and the actual original child replacement call. Exactly one
successful original nonmodifier synthesized DOWN and an unstyled single
character can change the predicate operand from length 1 to -1. Existing
collapsed action/shadow checks remain. Multiple synthesized DOWN events,
no emitted down, styled or multicharacter input, composition and noncollapsed
replacement retain the original predicate. Both batched and nonbatched
single-character insertion are admitted; no View-origin assumption is made.

The original posting, handlers, queues and calls are unchanged. An input-thread
scope is restored by `finally` on normal return and exceptions, without waits,
resend or DOM correction. The builder pins the official AAR and verifies
bytecode, unique instruction shape, original call preservation, scope negative
cases and unchanged native/resource records. The diagnostic builder fully
reconstructs the candidate before accepting its input.

## Validation sequence

The candidate workflow retains every attempt and publishes partial evidence
after each of ten fixed original single-burst diagnostic trials. Each requires the successful synthesized DOWN count,
original action/shadow range, predicate input/output and actual negative-offset
native writer for all eleven original characters. Original key action/source/
flags and batch transitions are recorded as bounded primitive metadata. It then
rebuilds the same candidate without any SDK observer and executes the
original performance/input gate with no diagnostic flags. A separate real
Gecko fixture exercises Android touch and keyboard actions, different
carets, selected replacement, navigation/deletion, undo, clipboard paste,
and the original InputConnection's commit, composition and batch paths.

`apk/gecko-synthetic-caret-candidate` contains whitelisted synthetic reports,
logs, screens and transformation receipts, never an APK, signing key or
browser profile. Its manifest records exact source and run identities,
failed trials, skipped steps and observer-free results. A diagnostic pass
does not substitute for the observer-free original gate or establish real
phone, touch-keyboard, account-login or production acceptance.
