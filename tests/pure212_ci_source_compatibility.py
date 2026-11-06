"""Exact pure212 source inputs for unchanged historical metadata only.

Actual Java/JavaScript hosts, device runners and release checkers use current
source bytes and never import this adapter. No public Git fetch occurs here.
"""
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/pure212-ci-source-deltas.json'
FIXTURE_SHA256 = 'bc0b96d515e44c4fa9088dd46866f1f86819abe2bb06dee120c15344fa565137'
PATHS = frozenset(('app/src/main/java/local/pocketchat/GeckoWebView.java', 'tests/baselines/public-source-history.json', 'tests/ip_timezone_source_compatibility.py', 'tests/profile_ip_timezone_source_compatibility_test.py'))


def sha(raw):return hashlib.sha256(raw).hexdigest()


def manifest():
    raw = FIXTURE.read_bytes()
    if FIXTURE.is_symlink() or not 0 < len(raw) <= 512 * 1024 or sha(raw) != FIXTURE_SHA256:
        raise ValueError('Exact bounded pure212 source fixture required')
    value = json.loads(raw)
    if value.get('schema') != 1 or type(value['schema']) is not int or value.get('kind') != 'pure212-source-oracles-only' or value.get('actualAndroidExecution') is not False or value.get('runtimeAcceptance') is not False or set(value['files']) != PATHS:
        raise ValueError('Pure212 metadata fixture scope differs')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        raise ValueError('Complete bytes and a fixed pure212 metadata path required')
    row = manifest()['files'][relative]
    if (len(raw), sha(raw)) == (row['previousBytes'], row['previousSha256']):return raw
    if (len(raw), sha(raw)) != (row['reviewedBytes'], row['reviewedSha256']):raise ValueError('IP timezone inverse rejects unknown whole source bytes (pure212 image)')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        if not current or not previous or sha(current) != delta['currentSha256'] or sha(previous) != delta['previousSha256'] or raw.count(current) != 1:
            raise ValueError('Missing, duplicate, moved or changed pure212 context')
        raw = raw.replace(current, previous, 1)
    if (len(raw), sha(raw)) != (row['previousBytes'], row['previousSha256']):raise ValueError('Entire original pure212 source did not restore')
    return raw


def wrap_bytes(original):
    @functools.wraps(original)
    def metadata_input(raw, relative):
        if type(raw) is bytes and type(relative) is str and relative in PATHS:
            row = manifest()['files'][relative]
            if (len(raw), sha(raw)) == (row['reviewedBytes'], row['reviewedSha256']):raw = source_input(raw, relative)
        return original(raw, relative)
    return metadata_input


def metadata_input(raw, relative):
    """Leave non-owned old metadata inputs with their original strict guard."""
    if type(raw) is not bytes or type(relative) is not str:raise ValueError('Exact metadata bytes and relative string required')
    return source_input(raw, relative) if relative in PATHS else raw

# Later CPU additions are reversed only for retained source oracles.
from cpu_source_compatibility import wrap_bytes as _cpu_wrap_bytes
source_input = _cpu_wrap_bytes(source_input)
