#!/usr/bin/env python3
"""Replay C10's immutable Android diagnostic through the lossless case archive.

This consumes the original artifact member, never reconstructed device events.
It verifies storage and the retained oracle; it is not a new Android execution
and cannot replace the complete release workflow for the current source.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from caret_ime_guard import PRIVACY_MAX_BYTES, assert_public_diagnostic_text
from chrome_collapse_case_storage import store_auto_collapse_cases, load_auto_collapse_cases, case_file_names
from chrome_collapse_contract import verify_auto_collapse

METADATA = Path(__file__).with_name('c10-observed-aggregate.json')


def compact(value, *, newline=False, sorted_keys=False):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                       sort_keys=sorted_keys, allow_nan=False) + ('\n' if newline else '')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_rejected(callback, message):
    try:
        callback()
    except (AssertionError, ValueError) as error:
        return dict(rejected=True, errorType=type(error).__name__, message=str(error)[:240])
    raise AssertionError(message)


def replay(report_path, output):
    pins = json.loads(METADATA.read_bytes())
    original = report_path.read_bytes()
    require(len(original) == pins['memberBytes'] and sha(original) == pins['memberSha256'],
            'Input is not the original pinned C10 artifact member')
    report = json.loads(original)
    source, apk = pins['sourceCommit'], pins['installedApkSha256']
    require(report['sourceCommit'] == source and report['sourceTree'] == pins['sourceTree'],
            'Original diagnostic source identity differs')
    require(report['status'] == 'passed' and report['diagnosticOnly'] is True
            and report['releaseAcceptance'] is False and report['fullUiAcceptance'] is False,
            'The original independent diagnostic scope changed')
    installed = report['buildIdentity']
    require(installed['apkSha256'] == apk, 'Original installed APK differs')
    require(all(installed['sdkBuildIdentity'][key] == pins[key]
                for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt')),
            'Original same-run installed SDK identity differs')

    inline = report['autoCollapse']
    aggregate = compact(inline)
    require(len(aggregate) == pins['autoCollapseBytes'] and sha(aggregate) == pins['autoCollapseSha256'],
            'Original complete aggregate differs')
    require(PRIVACY_MAX_BYTES == pins['unchangedPrivacyMaxBytes'] == 16 * 1024 * 1024,
            'The diagnostic privacy cap may not change')
    require(len(aggregate) > PRIVACY_MAX_BYTES, 'Original oversized regression no longer represented')
    aggregate_rejection = expect_rejected(
        lambda: assert_public_diagnostic_text(Path('original-auto-collapse.json'), aggregate),
        'Original oversized aggregate unexpectedly passed the unchanged privacy cap')
    require('rejected bounded capture' in aggregate_rejection['message'],
            'Original rejection was not the observed size boundary')

    for case, pin in zip(inline['cases'], pins['cases']):
        raw = compact(case)
        require((case['viewport'], case['fontScale'], case['runNonce']) ==
                (pin['viewport'], pin['fontScale'], pin['runNonce']), 'Original cohort/nonce differs')
        require(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'Original complete case differs')
        require(len(case['observations']) == pin['observations'], 'Original observations are missing')
        events = case['eventTransfer']['events']
        require(len(events) == pin['events'] and
                [sha(event['rawUtf8'].encode()) for event in events] == pin['rawUtf8Sha256'],
                'Original provider payloads are missing or changed')

    # These existing proof readers remain byte-identical to the observed source.
    # Current storage is deliberately kept separate from application validation.
    oracle_sources = {}
    for name in ('tools/gecko/chrome_collapse_contract.py',
                 'tools/gecko/chrome_collapse_contract_v2.py',
                 'tools/gecko/chrome_collapse_contract_v3.py',
                 'tools/gecko/integration_event_contract.py'):
        current = (ROOT / name).read_bytes()
        historical = subprocess.check_output(['git', 'show', source + ':' + name], cwd=ROOT)
        require(current == historical, 'The original oracle changed: ' + name)
        oracle_sources[name] = sha(current)
    before = verify_auto_collapse(inline, source, apk)
    require(before == pins['originalReaderResult'], 'Original native/UI oracle result differs')

    output.mkdir(parents=True, exist_ok=False)
    reference = store_auto_collapse_cases(inline, output, source, apk)
    restored = load_auto_collapse_cases(reference, output, source, apk)
    require(restored == inline and compact(restored, sorted_keys=True) == compact(inline, sorted_keys=True),
            'Hydration changed original fields, types, or values')
    original_files = []
    for old, new, name, pin in zip(inline['cases'], restored['cases'], case_file_names(reference), pins['cases']):
        raw = (output / name).read_bytes()
        require(raw == compact(old, newline=True), 'Complete case file bytes differ from the original case')
        require(len(raw) == pin['bytes'] + 1, 'Case storage changed more than the explicit final newline')
        assert_public_diagnostic_text(output / name, raw)
        require(set(old) == set(new) and compact(old) == compact(new), 'Original case fields or values changed')
        require([row['rawUtf8'].encode() for row in old['eventTransfer']['events']] ==
                [row['rawUtf8'].encode() for row in new['eventTransfer']['events']],
                'A complete provider payload was normalized or omitted')
        original_files.append(dict(name=name, bytes=len(raw), sha256=sha(raw), privacyScan='passed'))
    reference_raw = compact(reference, newline=True)
    assert_public_diagnostic_text(output / 'case-reference.json', reference_raw)
    (output / 'case-reference.json').write_bytes(reference_raw)
    after = verify_auto_collapse(restored, source, apk)
    require(after == before, 'Hydrated original oracle result changed')

    # Storage is not an application oracle. These mutations occur only in
    # isolated in-memory copies, retaining all original artifact/case bytes.
    tampered_raw = copy.deepcopy(restored)
    tampered_raw['cases'][0]['eventTransfer']['events'][0]['rawUtf8'] += ' '
    raw_negative = expect_rejected(
        lambda: verify_auto_collapse(tampered_raw, source, apk),
        'The retained oracle accepted a changed native provider payload')
    tampered_observation = copy.deepcopy(restored)
    first = next(iter(tampered_observation['cases'][0]['observations'].values()))
    first['webHeight'] += 1
    observation_negative = expect_rejected(
        lambda: verify_auto_collapse(tampered_observation, source, apk),
        'The retained oracle accepted a snapshot changed independently of the native receipt')

    implementation = {}
    for name in ('tools/gecko/chrome_collapse_case_storage.py',
                 'tools/gecko/caret_ime_guard.py', 'tests/chrome-collapse-archive/replay_actual.py'):
        implementation[name] = sha((ROOT / name).read_bytes())
    audit = dict(schema=1, status='passed', diagnosticOnly=True,
                 actualAndroidExecution=False, releaseAcceptance=False,
                 fullUiAcceptance=False, currentSourceAcceptance=False,
                 sourceCommit=source, sourceTree=pins['sourceTree'],
                 runId=pins['runId'], runAttempt=pins['runAttempt'],
                 originalArtifactId=pins['artifactId'],
                 originalArtifactZipSha256=pins['artifactZipSha256'],
                 originalReport=dict(path=str(report_path), bytes=len(original), sha256=sha(original)),
                 originalInstalledApkSha256=apk,
                 originalAggregate=dict(bytes=len(aggregate), sha256=sha(aggregate),
                                        privacyRejection=aggregate_rejection),
                 storedCases=original_files, unchangedPrivacyMaxBytes=PRIVACY_MAX_BYTES,
                 caseReference=dict(bytes=len(reference_raw), sha256=sha(reference_raw)),
                 originalOracle=before, hydratedOracle=after,
                 originalPayloadsPreserved=sum(pin['events'] for pin in pins['cases']),
                 allCaseFieldsAndBytesPreserved=True,
                 retainedOracleNegativeControls=dict(nativePayload=raw_negative,
                                                     independentObservation=observation_negative),
                 unchangedOracleSources=oracle_sources, implementationSources=implementation,
                 implementationBaseCommit=subprocess.check_output(
                     ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                 scope='Host replay of one immutable C10 diagnostic through current archive storage. '
                       'No new Android run, full-UI replay, release acceptance, or discarded event evidence.')
    audit_raw = (json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    assert_public_diagnostic_text(output / 'replay-audit.json', audit_raw)
    (output / 'replay-audit.json').write_bytes(audit_raw)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True,
                        help='Original chrome-collapse-diagnostic/results.json from the pinned C10 artifact')
    parser.add_argument('--out', type=Path, required=True,
                        help='New directory for the complete case files and independent audit')
    args = parser.parse_args()
    audit = replay(args.report, args.out)
    print(json.dumps(dict(status=audit['status'], originalAggregateBytes=audit['originalAggregate']['bytes'],
                          completeCaseBytes=[r['bytes'] for r in audit['storedCases']],
                          preservedOriginalPayloads=audit['originalPayloadsPreserved'],
                          oracle=audit['hydratedOracle'], releaseAcceptance=False,
                          audit=str(args.out / 'replay-audit.json')), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
