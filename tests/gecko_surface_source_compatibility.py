"""One exact native-surface successor for retained historical source guards.

Current Java extraction, SDK compilation and producer reports keep raw bytes.
The resource view only extends one old contextual oracle to the reviewed file.
"""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GV = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
FIXTURE = ROOT / 'tests/fixtures/gecko-surface-source-deltas.json'
FIXTURE_SHA256 = '21f15180afcc45b9ffaac194cf035419ddd75a050e6b689e198c28559fe2df10'
PREVIOUS_SHA256 = '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364'
CURRENT_SHA256 = '3e20d18790110422acb9c622bf3dfd508d893c4a7f87a663b600a36bccc1e12a'
RESOURCE_CONFIG_SHA256 = 'e7ab39b1772d153f8babe5e734354583c44aea9fda5e726a6a8517eedd37d7a4'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate native-surface guard metadata')
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError('Nonfinite native-surface guard metadata')


def manifest():
    if FIXTURE.is_symlink() or not FIXTURE.is_file() or FIXTURE.resolve() != FIXTURE.absolute():
        raise ValueError('Exact ordinary native-surface guard fixture required')
    raw = FIXTURE.read_bytes()
    if not 0 < len(raw) <= 128 * 1024 or sha(raw) != FIXTURE_SHA256:
        raise ValueError('Exact bounded native-surface guard fixture required')
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    if (type(value) is not dict or set(value) != {'schema', 'kind', 'baseCommit', 'baseTree', 'path',
            'previousBlob', 'previousSha256', 'previousBytes', 'reviewedSha256', 'reviewedBytes',
            'actualAndroidExecution', 'runtimeAcceptance', 'deltas', 'resourcePreviousRow',
            'resourceCurrentRow', 'finalPreviousRow', 'finalCurrentRow',
            'finalManifestPreviousSha256', 'finalManifestCurrentSha256'}
            or type(value['schema']) is not int or value['schema'] != 1
            or value['kind'] != 'historical-gecko-surface-source-input-only'
            or value['baseCommit'] != '7402ead321ca74b9fbefeab32a1aaffb32832011'
            or value['baseTree'] != '2aaec06687b65d9511ace499528b6946dc1b8d53'
            or value['path'] != GV or value['previousBlob'] != 'bbf8242a8b7d1d3cb8a6dbe17e64b076b8eea412'
            or (value['previousSha256'], value['previousBytes']) != (PREVIOUS_SHA256, 128874)
            or (value['reviewedSha256'], value['reviewedBytes']) != (CURRENT_SHA256, 128871)
            or value['actualAndroidExecution'] is not False or value['runtimeAcceptance'] is not False
            or len(value['deltas']) != 1 or len(value['finalPreviousRow']['deltas']) != 9
            or len(value['finalCurrentRow']['deltas']) != 9
            or (value['resourcePreviousRow']['currentSha256'], value['resourcePreviousRow']['currentBytes']) != (PREVIOUS_SHA256, 128874)
            or (value['resourceCurrentRow']['currentSha256'], value['resourceCurrentRow']['currentBytes']) != (CURRENT_SHA256, 128871)
            or (value['finalPreviousRow']['reviewedSha256'], value['finalPreviousRow']['reviewedBytes']) != (PREVIOUS_SHA256, 128874)
            or (value['finalCurrentRow']['reviewedSha256'], value['finalCurrentRow']['reviewedBytes']) != (CURRENT_SHA256, 128871)
            or value['resourceCurrentRow']['previousSha256'] != value['resourcePreviousRow']['previousSha256']
            or value['finalCurrentRow']['previousSha256'] != value['finalPreviousRow']['previousSha256']):
        raise ValueError('Native-surface guard scope or public predecessor differs')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative != GV or not 0 < len(raw) <= 256 * 1024:
        raise ValueError('Complete owned native-surface source bytes required')
    value = manifest()
    if (len(raw), sha(raw)) != (value['reviewedBytes'], CURRENT_SHA256):
        raise ValueError('Unreviewed complete native-surface source')
    for delta in reversed(value['deltas']):
        current, previous = delta['current'].encode(), delta['previous'].encode()
        for name, literal in (('current', current), ('previous', previous)):
            if (not 0 < len(literal) <= 32768
                    or (len(literal), sha(literal)) != (delta[name + 'Bytes'], delta[name + 'Sha256'])):
                raise ValueError('Exact bounded native-surface context required')
        if raw.count(current) != 1:
            raise ValueError('Unique native-surface contextual inverse required')
        raw = raw.replace(current, previous, 1)
    if (len(raw), sha(raw)) != (value['previousBytes'], PREVIOUS_SHA256):
        raise ValueError('Entire public native-surface predecessor did not restore')
    return raw


def historical_input(raw, relative=GV):
    """Only a complete known successor changes; original guards see all else."""
    if (type(raw) is bytes and type(relative) is str and relative == GV
            and len(raw) == 128871 and sha(raw) == CURRENT_SHA256):
        return source_input(raw, relative)
    return raw


def historical_report_sha(raw, reported_sha):
    """Check the actual reported hash before comparing a historical oracle."""
    if type(raw) is not bytes or type(reported_sha) is not str or sha(raw) != reported_sha:
        raise ValueError('Actual raw source report differs')
    return sha(historical_input(raw, GV))


def wrap_raw_guard(original):
    @functools.wraps(original)
    def current_raw(name, raw):
        guarded = historical_input(raw, GV) if type(name) is str and name == 'GeckoWebView' else raw
        original(name, guarded)
        return raw
    return current_raw


def wrap_recovery_guard(original):
    @functools.wraps(original)
    def historical_recovery(raw, composed_raw):
        return original(historical_input(raw, GV), composed_raw)
    return historical_recovery


def wrap_resource_config(original):
    @functools.wraps(original)
    def native_surface_rows():
        value, fixture = original(), manifest()
        if (sha(_encoded(value)) != RESOURCE_CONFIG_SHA256
                or value['sources'][GV] != fixture['resourcePreviousRow']
                or value['finalAfter'] != fixture['finalPreviousRow']
                or value['finalAfterSha256'] != fixture['finalManifestPreviousSha256']):
            raise ValueError('Exact original resource rows required before native-surface extension')
        result = copy.deepcopy(value)
        result['sources'][GV] = copy.deepcopy(fixture['resourceCurrentRow'])
        result['finalAfter'] = copy.deepcopy(fixture['finalCurrentRow'])
        result['finalAfterSha256'] = fixture['finalManifestCurrentSha256']
        return result
    return native_surface_rows


def historical_resource_row(relative, row):
    """The retained unrelated-row comparison still sees its original GV row."""
    if (type(relative) is str and relative == GV and type(row) is dict
            and row == manifest()['resourceCurrentRow']):
        return copy.deepcopy(manifest()['resourcePreviousRow'])
    return row

