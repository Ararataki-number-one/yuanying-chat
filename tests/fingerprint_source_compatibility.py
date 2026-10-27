"""Exact inverse of reviewed fingerprint additions for the older reading oracle.

No production source or runtime behavior is changed. The original whole-file
digest remains required after reversing only this separately pinned patch.
Unlisted layout, timing or fixture edits cannot pass by updating a baseline hash.
"""
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10'
PATCH_SHA256 = 'f831967e6d6a4265ffadc8ffa008402a091da1204812ec71e6593b37256c22b9'


def reading_preservation_bytes(raw):
    if hashlib.sha256(raw).hexdigest() == BASELINE:
        return raw
    patch = ROOT / 'tests/fixtures/fingerprint-gecko-reading-preservation.patch'
    data = patch.read_bytes()
    if hashlib.sha256(data).hexdigest() != PATCH_SHA256:
        raise ValueError('Fingerprint compatibility patch differs from reviewed bytes')
    lines = data.decode('utf-8').splitlines(keepends=True)
    path = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
    if lines[:2] != ['--- a/' + path + '\n', '+++ b/' + path + '\n']:
        raise ValueError('Unexpected protected source path')
    hunks = []
    cursor = 2
    while cursor < len(lines):
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', lines[cursor])
        if not match:
            raise ValueError('Unexpected inverse hunk header')
        old_count, new_count = int(match[2] or 1), int(match[4] or 1)
        start = int(match[3]) - (1 if new_count else 0)
        previous, current = [], []
        cursor += 1
        while cursor < len(lines) and not lines[cursor].startswith('@@ '):
            line = lines[cursor]
            if not line or line[0] not in ' +-':
                raise ValueError('Unexpected inverse source line')
            if line[0] in ' -':
                previous.append(line[1:])
            if line[0] in ' +':
                current.append(line[1:])
            cursor += 1
        if len(previous) != old_count or len(current) != new_count:
            raise ValueError('Inverse hunk line counts differ')
        if hunks and start < hunks[-1][0] + len(hunks[-1][1]):
            raise ValueError('Overlapping or reordered inverse hunks')
        hunks.append((start, current, previous))
    if not hunks:
        raise ValueError('Reviewed fingerprint delta is empty')
    source = raw.decode('utf-8').splitlines(keepends=True)
    for start, current, previous in reversed(hunks):
        if source[start:start + len(current)] != current:
            raise ValueError('Source differs outside the exact approved inverse')
        source[start:start + len(current)] = previous
    restored = ''.join(source).encode('utf-8')
    if hashlib.sha256(restored).hexdigest() != BASELINE:
        raise ValueError('Original whole-source reading guard no longer matches')
    return restored
