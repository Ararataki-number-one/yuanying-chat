"""Two exact metadata after-views; immutable JSON and normalizer bodies stay raw.

Only historical comparison edges use these views. Current Android runners,
compilers, receipts and runtime source readers never import this module.
"""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/navigation-metadata-source-deltas.json'
FIXTURE_SHA256 = '75b295b98d203c10e7ba2b7189e0e814fb03a91f1853b211abb4352fae04f58d'
DUAL = 'tests/dual_browser_source_compatibility.py'
JOURNAL = 'tests/event_journal_source_compatibility.py'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
BEFORE = (5199, '2f36e797407ecee55bce6545c461ad9b0fb4879bb4d01b1e8e6378122efc6cf8')
AFTER = (5745, 'da735453e54478eec47863a3c6e147a114593d7e5e5a99d621cac75bafb23302')


def reject():
    raise ValueError('Unreviewed navigation metadata comparison image')


def unique(items):
    result = {}
    for key, value in items:
        if key in result:reject()
        result[key] = value
    return result


def manifest():
    expected = ROOT / 'tests/fixtures/navigation-metadata-source-deltas.json'
    if FIXTURE != expected or FIXTURE.is_symlink() or not FIXTURE.is_file():reject()
    raw = FIXTURE.read_bytes()
    if not 0 < len(raw) <= 32768 or SHA(raw) != FIXTURE_SHA256:reject()
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda unused: reject())
    if (set(value) != {'schema', 'kind', 'actualAndroidExecution', 'runtimeAcceptance', 'workflowFixtureSha256',
            'dualFixtureSha256', 'dualJournalBefore', 'dualJournalAfter', 'rootDualBefore', 'rootDualAfter', 'sourceImages'}
            or type(value['schema']) is not int or value['schema'] != 1
            or value['kind'] != 'historical-navigation-metadata-only'
            or value['actualAndroidExecution'] is not False or value['runtimeAcceptance'] is not False
            or value['workflowFixtureSha256'] != '5d1f33ee4997b73e4c8785fbac39e831311247b5cae7c6d3e8c6182a8350a6ee'
            or value['dualFixtureSha256'] != 'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933'
            or set(value['sourceImages']) != {DUAL}):reject()
    for relative, digest in (('tests/fixtures/gradle-workflow-test-source-deltas.json', value['workflowFixtureSha256']),
                             ('tests/fixtures/dual-browser-source-deltas.json', value['dualFixtureSha256'])):
        if SHA((ROOT / relative).read_bytes()) != digest:reject()
    image = value['sourceImages'][DUAL]
    if ((image['previousBytes'], image['previousSha256']) != BEFORE
            or (image['currentBytes'], image['currentSha256']) != AFTER):reject()
    if not all(type(image[key]) is str and 0 < len(image[key].encode()) <= 16384 for key in ('previous', 'current')):reject()
    if not image['current'].startswith(image['previous']):reject()
    for before_key, after_key in (('dualJournalBefore', 'dualJournalAfter'), ('rootDualBefore', 'rootDualAfter')):
        before, after = value[before_key], value[after_key]
        if (set(before) != set(after) or len(before['deltas']) != 1 or len(after['deltas']) != 1
                or any(before[key] != after[key] for key in before if key not in ('deltas', 'reviewedBytes', 'reviewedSha256'))):reject()
        for delta in after['deltas']:
            for key in ('previous', 'current'):
                literal = delta[key].encode()
                if not 0 < len(literal) <= 16384 or SHA(literal) != delta[key+'Sha256']:reject()
    if ((value['dualJournalBefore']['reviewedBytes'], value['dualJournalBefore']['reviewedSha256']) !=
            (5971, 'b35122f03dca997a2b5e3f25675371ec4f8f83d77e5a8ca2fbac7d40079fde31')
            or (value['dualJournalAfter']['reviewedBytes'], value['dualJournalAfter']['reviewedSha256']) !=
            (6536, '16f44c6a6896513672ee260c2a18fed174c74bc6e9d19cded2e223bf09b81abd')
            or (value['rootDualBefore']['reviewedBytes'], value['rootDualBefore']['reviewedSha256']) != BEFORE
            or (value['rootDualAfter']['reviewedBytes'], value['rootDualAfter']['reviewedSha256']) != AFTER):reject()
    return value


def source_input(raw):
    if type(raw) is not bytes:reject()
    image = manifest()['sourceImages'][DUAL]
    if (len(raw), SHA(raw)) == BEFORE:return raw
    if (len(raw), SHA(raw)) != AFTER:reject()
    current, previous = image['current'].encode(), image['previous'].encode()
    if raw.count(current) != 1:reject()
    restored = raw.replace(current, previous, 1)
    if (len(restored), SHA(restored)) != BEFORE:reject()
    return restored


def wrap_dual_manifest(original):
    @functools.wraps(original)
    def current_dual_metadata():
        value = original()
        cfg = manifest()
        if value['files'][JOURNAL] != cfg['dualJournalBefore']:reject()
        result = copy.deepcopy(value)
        result['files'][JOURNAL] = copy.deepcopy(cfg['dualJournalAfter'])
        return result
    return current_dual_metadata


def wrap_root_factory(original):
    @functools.wraps(original)
    def factory(loader):
        reviewed = original(loader)
        @functools.wraps(reviewed)
        def current_root_metadata():
            value = reviewed()
            cfg = manifest()
            if value['files'][DUAL] != cfg['rootDualBefore']:reject()
            result = copy.deepcopy(value)
            result['files'][DUAL] = copy.deepcopy(cfg['rootDualAfter'])
            return result
        return current_root_metadata
    return factory
