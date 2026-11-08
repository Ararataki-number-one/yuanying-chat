"""Exact ProfileContext callback inverse for retained whole-source guards.

Actual directory extraction, Java compilation and JVM hosts keep current bytes.
This input supplies no callback, Android, filesystem or runtime acceptance.
"""
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/profile-context-callback-source-deltas.json'
FIXTURE_SHA256 = '3b51e16b7fc676a46fb847811d5bdcb59ed5623617703c86ac77d1f7fb283cc8'
PATH = 'app/src/main/java/local/pocketchat/ProfileContext.java'
PREVIOUS_SHA256 = '2b72094396c21c235e77ce79fbd6a6eb134abf14a71bf4c8c0ae010aa2369178'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest():
    if FIXTURE.is_symlink() or not FIXTURE.is_file() or FIXTURE.resolve() != FIXTURE.absolute():
        raise ValueError('Exact ordinary ProfileContext guard fixture required')
    raw = FIXTURE.read_bytes()
    if not 0 < len(raw) <= 16384 or sha(raw) != FIXTURE_SHA256:
        raise ValueError('Exact bounded ProfileContext guard fixture required')
    value = json.loads(raw)
    if (type(value['schema']) is not int or value['schema'] != 1
            or value['kind'] != 'historical-profile-context-guard-input-only'
            or value['baseCommit'] != '7402ead321ca74b9fbefeab32a1aaffb32832011'
            or value['baseTree'] != '2aaec06687b65d9511ace499528b6946dc1b8d53'
            or value['path'] != PATH or value['previousSha256'] != PREVIOUS_SHA256
            or value['previousBlob'] != '2a705b04125af80d4e578c8145a00be9a9eb70e0'
            or value['actualAndroidExecution'] is not False or value['runtimeAcceptance'] is not False
            or len(value['deltas']) != 1):
        raise ValueError('ProfileContext guard scope or public predecessor differs')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative != PATH or not 0 < len(raw) <= 32768:
        raise ValueError('Complete owned ProfileContext source bytes required')
    row = manifest()
    if (len(raw), sha(raw)) != (row['reviewedBytes'], row['reviewedSha256']):
        raise ValueError('Unreviewed complete ProfileContext source')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        for name, literal in (('current', current), ('previous', previous)):
            if (not 0 < len(literal) <= 32768
                    or (len(literal), sha(literal)) != (delta[name + 'Bytes'], delta[name + 'Sha256'])):
                raise ValueError('Exact bounded ProfileContext guard context required')
        if raw.count(current) != 1:
            raise ValueError('Missing, repeated or moved ProfileContext guard context')
        raw = raw.replace(current, previous, 1)
    if (len(raw), sha(raw)) != (row['previousBytes'], PREVIOUS_SHA256):
        raise ValueError('Entire original ProfileContext source did not restore')
    return raw


def historical_guard_input(raw, name):
    """Only the exact current ProfileContext changes; unknown bytes face old guards."""
    if (type(raw) is bytes and type(name) is str and name == 'ProfileContext'
            and 0 < len(raw) <= 32768 and sha(raw) == manifest()['reviewedSha256']):
        return source_input(raw, PATH)
    return raw


def wrap_raw_guard(original):
    @functools.wraps(original)
    def current_raw(name, raw):
        guarded = historical_guard_input(raw, name)
        original(name, guarded)
        return raw
    return current_raw
