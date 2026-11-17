"""Lossless, bounded storage for the three current chrome-collapse cases.

This module only transports complete evidence. The producer validates the
original inline report before storing it, and consumers must still run the
unchanged chrome-collapse oracle after loading it. Historical inline reports
remain inline; no historical assertion or public-diagnostic limit is changed.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat


COHORTS = ((360, 1), (412, 1), (360, 2))
CASE_FILES = tuple('chrome-collapse-case-%d-%d.json' % cohort for cohort in COHORTS)
STORAGE_KEYS = frozenset(('caseStorageVersion', 'caseFiles'))
REFERENCE_KEYS = frozenset(('name', 'bytes', 'sha256', 'runNonce', 'viewport', 'fontScale'))


def _require(condition, message):
    if not condition:
        raise ValueError('Chrome-collapse case storage: ' + message)


def _hex(value, length):
    return type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON field')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Chrome-collapse case storage: non-finite JSON constant')


def _decode(raw):
    try:
        return json.loads(raw.decode('utf-8', errors='strict'),
                          object_pairs_hook=_unique_object, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Chrome-collapse case storage: malformed UTF-8 JSON') from error


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def _same(left, right):
    # JSON types, including bool versus int, are part of an evidence identity.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _privacy():
    # Only the new external format needs this dependency. Isolated historical
    # readers can continue to import this module and read their inline reports.
    if __package__:
        from .caret_ime_guard import PRIVACY_MAX_BYTES, assert_public_diagnostic_text
    else:
        from caret_ime_guard import PRIVACY_MAX_BYTES, assert_public_diagnostic_text
    return PRIVACY_MAX_BYTES, assert_public_diagnostic_text


def _directory(value):
    directory = Path(value).absolute()
    _require(directory.is_dir(), 'case directory is missing')
    _require(not any(path.is_symlink() for path in (directory, *directory.parents)),
             'case directory contains a symbolic link')
    return directory


def _read(directory, name):
    limit, scan = _privacy()
    path = directory / name
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            details = os.fstat(stream.fileno())
            _require(stat.S_ISREG(details.st_mode), 'case file is not a regular original')
            _require(0 < details.st_size <= limit, 'case file exceeds the unchanged diagnostic bound')
            raw = stream.read(limit + 1)
            _require(len(raw) == details.st_size, 'case file changed while reading')
    except OSError as error:
        raise ValueError('Chrome-collapse case storage: missing or unsafe case file') from error
    scan(path, raw)
    return raw


def _identity(report, source, apk_sha):
    _require(type(report) is dict and type(report.get('navigationContract')) is int
             and report['navigationContract'] in (3,4), 'external storage requires a recognized current navigation contract')
    _require(_hex(source, 40) and _hex(apk_sha, 64), 'expected source and APK identity')
    _require(report.get('sourceCommit') == source, 'report belongs to another source')
    identity = report.get('buildIdentity')
    _require(type(identity) is dict and identity.get('sourceCommit') == source
             and identity.get('apkSha256') == apk_sha and _hex(identity.get('sourceTree'), 40),
             'report build identity differs from the selected source or APK')
    sdk = identity.get('sdkBuildIdentity')
    _require(type(sdk) is dict and sdk.get('sourceCommit') == source
             and sdk.get('sourceTree') == identity['sourceTree'], 'SDK source identity differs')
    for key in ('runId', 'runAttempt'):
        _require(type(sdk.get(key)) is str and re.fullmatch('[1-9][0-9]*', sdk[key]) is not None,
                 'SDK workflow invocation is missing')
    return identity


def _owned_case(case, identity, cohort, nonce=None, *, navigation_contract=3):
    _require(type(case) is dict and type(case.get('navigationContract')) is int
             and case['navigationContract'] == navigation_contract, 'case navigation contract differs')
    _require(all(type(case.get(key)) is int for key in ('viewport', 'fontScale'))
             and (case['viewport'], case['fontScale']) == cohort, 'case cohort or order differs')
    current_nonce = case.get('runNonce')
    _require(_hex(current_nonce, 32) and (nonce is None or current_nonce == nonce), 'case invocation differs')
    _require(case.get('sourceCommit') == identity['sourceCommit'], 'case belongs to another source')
    transfer = case.get('eventTransfer')
    _require(type(transfer) is dict and transfer.get('runNonce') == current_nonce
             and transfer.get('fixtureAction') == 'chromeCollapse'
             and type(transfer.get('processSlot')) is int and transfer['processSlot'] == 0,
             'case event transport belongs to another invocation')
    rows = transfer.get('events')
    _require(type(rows) is list and bool(rows), 'complete original event transport is required')
    for row in rows:
        _require(type(row) is dict and type(row.get('rawUtf8')) is str
                 and type(row.get('receipt')) is dict, 'original event bytes and receipt are required')
        raw = row['rawUtf8'].encode('utf-8')
        receipt = row['receipt']
        _require(type(receipt.get('payloadBytes')) is int and receipt['payloadBytes'] == len(raw)
                 and receipt.get('payloadSha256') == hashlib.sha256(raw).hexdigest(),
                 'original event bytes differ from their receipt')
        _require(receipt.get('runNonce') == current_nonce, 'event receipt belongs to another invocation')
        envelope = _decode(raw)
        _require(type(envelope) is dict and envelope.get('sourceCommit') == identity['sourceCommit']
                 and envelope.get('runNonce') == current_nonce, 'event envelope belongs to another source or invocation')
        actual_identity = envelope.get('buildIdentity')
        _require(type(actual_identity) is dict and all(key in actual_identity
                 and _same(actual_identity[key], value) for key, value in identity.items()),
                 'event build/source/tree/workflow/APK identity differs')
    return current_nonce


def case_file_names(report):
    """Return exactly the owned flat filenames, or none for historical inline data."""
    _require(type(report) is dict, 'report must be an object')
    present = STORAGE_KEYS.intersection(report)
    if not present:
        return ()
    _require(present == STORAGE_KEYS and 'cases' not in report,
             'mixed, partial or ambiguous case storage')
    _require(type(report.get('caseStorageVersion')) is int and report['caseStorageVersion'] == 1,
             'unknown case storage version')
    _require(type(report.get('navigationContract')) is int and report['navigationContract'] in (3,4),
             'external storage requires a recognized current navigation contract')
    references = report['caseFiles']
    _require(type(references) is list and len(references) == len(COHORTS), 'all three case references are required')
    nonces = set()
    for row, name, cohort in zip(references, CASE_FILES, COHORTS):
        _require(type(row) is dict and set(row) == REFERENCE_KEYS, 'unexpected case reference fields')
        _require(type(row['name']) is str and row['name'] == name, 'case file path or order differs')
        _require(type(row['bytes']) is int and row['bytes'] > 0 and _hex(row['sha256'], 64), 'case byte identity is missing')
        _require(all(type(row[key]) is int for key in ('viewport', 'fontScale'))
                 and (row['viewport'], row['fontScale']) == cohort, 'reference cohort or order differs')
        _require(_hex(row['runNonce'], 32) and row['runNonce'] not in nonces, 'duplicate or invalid case invocation')
        nonces.add(row['runNonce'])
    return CASE_FILES


def store_auto_collapse_cases(report, directory, source, apk_sha):
    """Store already oracle-validated complete cases without changing their values.

    The returned report is an archive index, not an acceptance result. Existing
    originals may only be reused when their bytes are identical; they are never
    overwritten with a different invocation.
    """
    _require(type(report) is dict and not STORAGE_KEYS.intersection(report), 'an original inline report is required')
    identity = _identity(report, source, apk_sha)
    cases = report.get('cases')
    _require(type(cases) is list and len(cases) == len(COHORTS), 'all three complete cases are required')
    directory = _directory(directory)
    limit, scan = _privacy()
    references, originals, nonces = [], [], set()
    for case, name, cohort in zip(cases, CASE_FILES, COHORTS):
        nonce = _owned_case(case, identity, cohort, navigation_contract=report['navigationContract'])
        _require(nonce not in nonces, 'duplicate case invocation')
        nonces.add(nonce)
        raw = _encoded(case)
        _require(0 < len(raw) <= limit, 'case exceeds the unchanged diagnostic bound')
        scan(directory / name, raw)
        originals.append((name, raw))
        references.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                               runNonce=nonce, viewport=cohort[0], fontScale=cohort[1]))
    for name, raw in originals:
        path = directory / name
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        except FileExistsError:
            _require(_read(directory, name) == raw, 'refusing to replace another invocation or changed case')
        else:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
    result = copy.deepcopy(report)
    del result['cases']
    result.update(caseStorageVersion=1, caseFiles=references)
    case_file_names(result)
    return result


def load_auto_collapse_cases(report, directory, source, apk_sha):
    """Resolve complete originals; callers then apply the original full oracle."""
    names = case_file_names(report)
    if not names:
        # No metadata rewriting and no new dependency for retained inline data.
        return report
    identity = _identity(report, source, apk_sha)
    directory = _directory(directory)
    cases = []
    for reference, name, cohort in zip(report['caseFiles'], names, COHORTS):
        raw = _read(directory, name)
        _require(len(raw) == reference['bytes'] and hashlib.sha256(raw).hexdigest() == reference['sha256'],
                 'case original size or digest differs from its reference')
        case = _decode(raw)
        _owned_case(case, identity, cohort, reference['runNonce'], navigation_contract=report['navigationContract'])
        cases.append(case)
    result = copy.deepcopy(report)
    for key in STORAGE_KEYS:
        del result[key]
    result['cases'] = cases
    return result
