#!/usr/bin/env python3
"""Strict controlled Android caret evidence contract; host controls are not execution.

This additional contract never replaces the original performance/release gates.
External receipts must describe actual source compilation and installed APK bytes.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
_sdk_spec = importlib.util.spec_from_file_location('caret_shared_sdk_contract', ROOT / 'tools/gecko/sdk_identity_contract.py')
_sdk = importlib.util.module_from_spec(_sdk_spec)
_sdk_spec.loader.exec_module(_sdk)

OFFICIAL_AAR = '15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268'
OFFICIAL_SOURCE = '6a4e6774de38930f9a741ad20df1baa6d4edc58264162118f5a3d7c8fd3fd78b'
OFFICIAL_EDITABLE_CLASS = '608461e22cae3ed19572aa43a0dc38d4926d48709bd456c91853935462f5fa54'
PACKAGE = 'local.pocketchat.test'
COMPONENT = 'local.pocketchat.GeckoCaretCompatibilityIntegrationActivity'
OBSERVERS = ['org.mozilla.geckoview.PocketGeckoEditableTrace',
             'org.mozilla.geckoview.PocketGeckoInputTrace',
             'org.mozilla.geckoview.PocketInputWriterTrace']
IDS = ['rapid-taps', 'selected-replace', 'arrow-delete', 'undo', 'ime-multiword',
       'clipboard-paste', 'chinese-composition', 'finish-composition', 'batch-commit',
       'reversed-selection', 'rejected-input', 'soft-single-char', 'codepoint-delete',
       'noop-composition']
SEEDS = ['abcdefghij', 'abcdefghij', 'abcdef', 'undo draft', 'left-right',
         'clipboard tail', 'seed tail', 'seed tail', 'batch tail', 'abcdef',
         'rejected draft', 'soft tail', 'A😀B', 'noop tail']
CARETS = [5, 8, 3, 4, 5, 9, 4, 4, 5, 5, 4, 4, 3, 4]
EVENT_TYPES = {'keydown', 'keyup', 'beforeinput', 'input', 'compositionstart',
               'compositionupdate', 'compositionend', 'focus', 'blur', 'select'}
COMPAT_EVENT_TYPES = EVENT_TYPES | {'selectionchange'}


def require(condition, message):
    if not condition:
        raise ValueError('Caret compatibility: ' + message)


def integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**63 - 1


def hex_value(value, size=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(size) + '}', value) is not None


def utf16_length(value):
    require(isinstance(value, str), 'text value missing')
    return len(value.encode('utf-16-le', errors='surrogatepass')) // 2


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON field ' + key)
        value[key] = item
    return value


def read_json(path):
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=unique_object,
                           parse_constant=lambda item: require(False, 'nonfinite JSON ' + item))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Caret compatibility: invalid UTF-8 or JSON') from error
    require(isinstance(value, dict), 'JSON root must be an object')
    return value, digest(raw)


def checkpoint(draft, start, end, keys, inputs, before):
    return dict(draft=draft, start=start, end=end, minimumKeys=keys,
                minimumInputs=inputs, minimumBefore=before)


CHECKPOINTS = [
    [checkpoint('abcdefghiQj', 10, 10, 1, 1, 1)],
    [checkpoint('abcdefghij', 2, 5, 0, 0, 0), checkpoint('abZfghij', 3, 3, 1, 1, 1)],
    [checkpoint('adef', 1, 1, 3, 2, 2)],
    [checkpoint('undoX draft', 5, 5, 1, 1, 1), checkpoint('undo draft', 4, 4, 2, 2, 1)],
    [checkpoint('left-many wordsright', 15, 15, 0, 1, 1)],
    [checkpoint('clipboard paste tail', 15, 15, 0, 1, 1),
     checkpoint('clipboard pasteQ tail', 16, 16, 0, 2, 2),
     checkpoint('clipboard pasteQ😀 tail', 18, 18, 0, 3, 3)],
    [checkpoint('seedni tail', 6, 6, 0, 1, 1), checkpoint('seed你 tail', 5, 5, 0, 2, 2),
     checkpoint('seed你好 tail', 6, 6, 0, 3, 3), checkpoint('seed你好 tail', 6, 6, 0, 3, 3)],
    [checkpoint('seed中 tail', 5, 5, 0, 1, 1), checkpoint('seed中 tail', 5, 5, 0, 1, 1)],
    [checkpoint('batch one two tail', 13, 13, 0, 1, 1)],
    [checkpoint('abcdef', 2, 5, 0, 0, 0), checkpoint('abQQf', 4, 4, 0, 1, 1)],
    [checkpoint('rejected draft', 4, 4, 1, 0, 1)],
    [checkpoint('softQ tail', 5, 5, 0, 1, 1)],
    [checkpoint('AB', 1, 1, 0, 1, 1)],
    [checkpoint('noop tail', 4, 4, 0, 0, 0), checkpoint('noopQ tail', 5, 5, 1, 1, 1)],
]

# The order is the actual Java fixture's order, including intermediate checkpoints.
# cp entries refer to each case's exact checkpoint vector above.
FLOW = [
    [('hw', 'two-rapid-taps-and-type', [('tap', 2), ('tap', 9), ('text', 'Q')]), ('cp', 0)],
    [('api', 'setSelection', [2, 5]), ('cp', 0), ('hw', 'replace-selection', [('text', 'Z')]), ('cp', 1)],
    [('hw', 'arrow-backspace-delete', [('key', 21), ('key', 67), ('key', 112)]), ('cp', 0)],
    [('hw', 'insert-for-undo', [('text', 'X')]), ('cp', 0), ('hw', 'ctrl-z', [('combination', [113, 54])]), ('cp', 1)],
    [('api', 'commitText', ['many words', 1]), ('cp', 0)],
    [('clipboard', ' paste'), ('api', 'performContextMenuAction', [16908322]), ('cp', 0),
     ('clipboard', 'Q'), ('api', 'performContextMenuAction', [16908322]), ('cp', 1),
     ('clipboard', '😀'), ('api', 'performContextMenuAction', [16908322]), ('cp', 2)],
    [('api', 'setComposingText', ['ni', 1]), ('cp', 0), ('api', 'setComposingText', ['你', 1]), ('cp', 1),
     ('api', 'commitText', ['你好', 1]), ('cp', 2), ('extra', 'Chinese composition produced real composition events'),
     ('api', 'finishComposingText', []), ('cp', 3)],
    [('api', 'setComposingText', ['中', 1]), ('cp', 0), ('api', 'finishComposingText', []), ('cp', 1),
     ('extra', 'Finish composition delivers a real composition end')],
    [('api', 'beginBatchEdit', []), ('api', 'commitText', [' one', 1]), ('api', 'commitText', [' two', 1]),
     ('api', 'endBatchEdit', []), ('cp', 0)],
    [('api', 'setSelection', [5, 2]), ('cp', 0), ('extra', 'Reversed selection preserves backward direction'),
     ('api', 'commitText', ['QQ', 1]), ('cp', 1)],
    [('hw', 'rejected-one-key', [('text', 'Q')]), ('cp', 0),
     ('extra', 'Rejected beforeinput does not modify the draft'), ('extra', 'Rejected key is sent exactly once')],
    [('api', 'commitText', ['Q', 1]), ('cp', 0)],
    [('api', 'deleteSurroundingTextInCodePoints', [1, 0]), ('cp', 0)],
    [('api', 'beginBatchEdit', []), ('api', 'setComposingText', ['', 1]), ('api', 'finishComposingText', []),
     ('api', 'endBatchEdit', []), ('cp', 0), ('extra', 'No-op composition preserves text without fabricated input'),
     ('hw', 'progress-after-noop', [('text', 'Q')]), ('cp', 1)],
]
CHARACTER_KEYS = [['Q'], ['Z'], [], ['X', 'z'], [], ['Q'], [], [], [], [], ['Q'], ['Q'], [], ['Q']]


def expected_layout():
    checks, apis, hardware, actions, clipboard = [], [], [], [], []
    api_index = cp_index = hw_index = 0
    for number, case_id in enumerate(IDS):
        case_actions = []
        for name in ['Controlled initial draft is intact', 'Real tap establishes the exact caret and visible IME']:
            checks.append((case_id, name))
        for step in [('hw', 'focus', [('tap', CARETS[number])])] + FLOW[number]:
            if step[0] == 'hw':
                row = dict(id=f'{case_id}-{step[1]}-{hw_index}', scenario=case_id,
                           commands=step[2])
                hardware.append(row); case_actions.append(('hw', row)); hw_index += 1
            elif step[0] == 'api':
                row = dict(index=api_index, scenario=case_id, api=step[1], arguments=step[2])
                apis.append(row); case_actions.append(('api', row))
                checks.append((case_id, f'Original InputConnection accepts {step[1]} #{api_index}'))
                api_index += 1
            elif step[0] == 'cp':
                checks.extend((case_id, name) for name in [f'Exact draft and selection after original input #{cp_index}',
                    'Preserved other draft, synthetic cookie and no send', 'Input events are trusted and bounded'])
                cp_index += 1
            elif step[0] == 'clipboard':
                row = dict(index=len(clipboard), scenario=case_id, api='setPrimaryClip',
                           origin='original-android-clipboardmanager', text=step[1])
                clipboard.append(row); case_actions.append(('clipboard', row))
            else:
                checks.append((case_id, step[1]))
        actions.append(case_actions)
    return checks, apis, hardware, actions, clipboard


IDENTITY_FIELDS = ['schema', 'sourceCommit', 'runId', 'runAttempt', 'sdkReceiptSha256',
                   'sdkManifestSha256', 'sdkAarSha256', 'sdkClassJarSha256', 'sdkEditableClassSha256',
                   'normalMode', 'sdkObserverIncluded']


def verify_receipts(build, sdk, audit, *, source, run_id, run_attempt, sdk_hash, audit_hash, artifact_root=ROOT,
                    sdk_raw=None, source_reader=None):
    require(hex_value(source, 40) and isinstance(run_id, str) and re.fullmatch('[1-9][0-9]*', run_id)
            and isinstance(run_attempt, str) and re.fullmatch('[1-9][0-9]*', run_attempt), 'expected invocation identity')
    for value, label in [(build, 'build receipt'), (sdk, 'SDK receipt')]:
        require(type(value.get('schema')) is int and value['schema'] == 1, label + ' schema')
        require(all(value.get(key) == wanted for key, wanted in [('sourceCommit', source), ('runId', run_id),
                ('runAttempt', run_attempt)]), label + ' source/run/attempt mismatch')
    require(build.get('normalMode') is True and build.get('sdkObserverIncluded') is False, 'normal observer-free build required')
    for field in ['integrationApkSha256', 'releaseApkSha256', 'sdkReceiptSha256', 'sdkManifestSha256', 'sdkAarSha256',
                  'sdkClassJarSha256', 'sdkEditableClassSha256', 'embeddedIdentityAssetSha256']:
        require(hex_value(build.get(field)), 'build receipt ' + field)
    require(build['sdkReceiptSha256'] == sdk_hash, 'SDK receipt bytes differ from build receipt')
    require(type(sdk_raw) is bytes and digest(sdk_raw) == sdk_hash and _sdk.strict_json(sdk_raw) == sdk,
            'canonical raw SDK receipt bytes missing or differ from decoded receipt')
    if source_reader is None:
        def source_reader(commit, path):
            return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=artifact_root, stderr=subprocess.PIPE)
    manifest, manifest_hash = _sdk.selected_manifest(source, source_reader)
    require(hex_value(sdk.get('sourceTree'), 40), 'SDK receipt committed source tree missing')
    _sdk.validate_receipt(sdk_raw, manifest, manifest_hash, source, sdk['sourceTree'])
    require(hex_value(sdk.get('sdkManifestSha256')) and sdk['sdkManifestSha256'] == build['sdkManifestSha256'],
            'SDK manifest digest differs from build receipt')
    require([build['sdkAarSha256'], build['sdkClassJarSha256'], build['sdkEditableClassSha256']] ==
            [sdk['sdkAarSha256'], sdk['sdkClassesJarSha256'], sdk['sdkGeckoEditableClassSha256']], 'build SDK hashes differ')
    embedded = {field: build[field] for field in IDENTITY_FIELDS}
    require(type(audit.get('schema')) is int and audit['schema'] == 1 and audit.get('apkSha256') == build['integrationApkSha256']
            and audit.get('package') == PACKAGE and audit.get('component') == COMPONENT, 'installed definition audit identity')
    require(audit.get('sdkManifestSha256') == build['sdkManifestSha256']
            and audit.get('embeddedIdentityAssetSha256') == build['embeddedIdentityAssetSha256']
            and audit.get('embeddedBuildIdentity') == embedded, 'installed embedded source/SDK asset mismatch')
    require(audit.get('observerDefinitions') == [] and audit.get('editableDefinitionCount') == 1
            and audit.get('fixtureDefinitionCount') == 1 and audit.get('caretHelperDefinitionCount') == 1,
            'installed definitions contain observers or missing/duplicate fixture/caret helper/Editable')
    dex = audit.get('dex')
    require(isinstance(dex, list) and dex, 'actual DEX definition audit missing')
    definitions, entries = [], []
    for row in dex:
        require(isinstance(row, dict) and isinstance(row.get('entry'), str)
                and re.fullmatch(r'classes(?:[2-9]|[1-9][0-9]+)?\.dex', row['entry']), 'invalid DEX entry')
        require(integer(row.get('bytes'), 1) and hex_value(row.get('sha256')), 'actual DEX bytes/digest missing')
        names = row.get('classDefinitions')
        require(isinstance(names, list) and names and all(isinstance(x, str) and re.fullmatch(r'L[^;\s]+;', x)
                for x in names), 'actual class_def descriptors required, not raw string matches')
        require(type(row.get('classDefinitionCount')) is int and row['classDefinitionCount'] == len(names), 'DEX class_def count mismatch')
        entries.append(row['entry']); definitions.extend(names)
    require(len(entries) == len(set(entries)) and len(definitions) == len(set(definitions)), 'duplicate DEX/class definitions')
    require(integer(audit.get('definitionCount'), 1) and audit['definitionCount'] == len(definitions), 'DEX definition count mismatch')
    require(definitions.count('Lorg/mozilla/geckoview/GeckoEditable;') == 1
            and definitions.count('Llocal/pocketchat/GeckoCaretCompatibilityIntegrationActivity;') == 1
            and definitions.count('Llocal/pocketchat/CaretCompatibilityBuildIdentity;') == 1,
            'required actual DEX definitions missing')
    observer_descriptors = {'L' + name.replace('.', '/') + ';' for name in OBSERVERS}
    require(not any(name in observer_descriptors or name.startswith('Lorg/mozilla/geckoview/Pocket') for name in definitions),
            'SDK observer class definition present')
    identity = dict(embedded, integrationApkSha256=build['integrationApkSha256'], releaseApkSha256=build['releaseApkSha256'],
                    embeddedIdentityAssetSha256=build['embeddedIdentityAssetSha256'])
    installed = dict(apkSha256=build['integrationApkSha256'], package=PACKAGE, component=COMPONENT,
                     observerDefinitions=[], apkDefinitionAuditSha256=audit_hash, sdkManifestSha256=build['sdkManifestSha256'],
                     embeddedIdentityAssetSha256=build['embeddedIdentityAssetSha256'])
    return embedded, identity, installed


def counts(events):
    return dict(eventCount=len(events), keyCount=sum(e['type'] == 'keydown' for e in events),
                characterKeyCount=sum(e['type'] == 'keydown' and utf16_length(e['key']) == 1 for e in events),
                qKeyCount=sum(e['type'] == 'keydown' and e['key'] == 'Q' for e in events),
                inputCount=sum(e['type'] == 'input' for e in events), beforeCount=sum(e['type'] == 'beforeinput' for e in events),
                compositionCount=sum(e['type'] == 'compositionstart' for e in events),
                compositionEndCount=sum(e['type'] == 'compositionend' for e in events))


def vectors(events):
    return dict(characterKeys=[e['key'] for e in events if e['type'] == 'keydown' and utf16_length(e['key']) == 1],
                beforeInputTypes=[e['inputType'] for e in events if e['type'] == 'beforeinput'],
                inputTypes=[e['inputType'] for e in events if e['type'] == 'input'],
                compositionTypes=[e['type'] for e in events if e['type'].startswith('composition')])


def verify_events(report):
    chunks = report.get('trustedEventChunks'); flat = report.get('actualTrustedEvents')
    require(isinstance(chunks, list) and isinstance(flat, dict) and list(flat) == IDS, 'complete ordered raw event maps required')
    observed = {case_id: [] for case_id in IDS}
    last_case = -1
    for chunk in chunks:
        require(isinstance(chunk, dict) and chunk.get('id') in IDS, 'event chunk case ownership')
        number = IDS.index(chunk['id'])
        require(number >= last_case, 'event chunks reorder cases'); last_case = number
        events = chunk.get('events')
        require(integer(chunk.get('offset')) and chunk['offset'] == len(observed[chunk['id']]), 'missing/duplicate/out-of-order event chunk')
        require(isinstance(events, list) and 1 <= len(events) <= 4, 'bounded nonempty event chunk required')
        observed[chunk['id']].extend(events)
    require(flat == observed, 'flattened events differ from raw chunks')
    for case_id, events in observed.items():
        require(len(events) <= 512, 'event overflow')
        previous_time = -1
        for index, event in enumerate(events):
            require(isinstance(event, dict) and type(event.get('index')) is int and event['index'] == index,
                    'missing/duplicate/out-of-order DOM event index')
            require(event.get('type') in COMPAT_EVENT_TYPES and event.get('trusted') is True, 'unexpected or untrusted DOM event')
            require(all(type(event.get(field)) is bool for field in ['ctrl', 'shift', 'composing', 'prevented']), 'event modifier/composition/default prevention flags')
            require(all(isinstance(event.get(field), str) for field in ['key', 'data', 'inputType', 'draft']), 'complete raw DOM event text')
            time = event.get('time')
            require(type(time) in (int, float) and math.isfinite(time) and time >= previous_time, 'DOM event time order'); previous_time = time
            length = utf16_length(event['draft'])
            require(integer(event.get('start')) and integer(event.get('end')) and event['start'] <= event['end'] <= length,
                    'DOM event selection bounds')
            if event['type'] in ['input', 'beforeinput']:
                require(bool(event['inputType']), 'actual input type missing')
        require(vectors(events)['characterKeys'] == CHARACTER_KEYS[IDS.index(case_id)], 'extra/missing/reordered trusted character key')
    require(report.get('eventVectors') == {case_id: vectors(observed[case_id]) for case_id in IDS}, 'declared DOM vectors differ from actual chunks')
    return observed


def snapshot(value, number, events, *, focused=None):
    require(isinstance(value, dict) and value.get('ready') is True and type(value.get('case')) is int
            and value['case'] == number, 'snapshot case identity')
    require(isinstance(value.get('draft'), str), 'snapshot draft missing')
    require(integer(value.get('start')) and integer(value.get('end'))
            and value['start'] <= value['end'] <= utf16_length(value['draft']), 'snapshot selection bounds')
    require(value.get('direction') in ['none', 'forward', 'backward'] and type(value.get('focused')) is bool, 'snapshot focus/direction')
    if focused is not None:
        require(value['focused'] is focused, 'snapshot focus mismatch')
    require(value.get('otherDraft') == 'untouched independent draft' and integer(value.get('sendCount')) and value['sendCount'] == 0,
            'other draft changed or a message was sent')
    require(isinstance(value.get('cookie'), str) and 'session=synthetic-caret' in value['cookie'], 'synthetic login cookie changed')
    require(value.get('allTrusted') is True and value.get('overflow') is False, 'snapshot trust/overflow flags')
    for field, actual in counts(events).items():
        require(type(value.get(field)) is int and value[field] == actual, 'snapshot counter differs from raw events: ' + field)


def verify_hardware(actual, expected):
    require(isinstance(actual, dict) and actual.get('id') == expected['id'] and actual.get('scenario') == expected['scenario']
            and actual.get('origin') == 'adb-input-keyboard-and-touch', 'Android action identity')
    commands, executions = actual.get('commands'), actual.get('executions')
    require(isinstance(commands, list) and len(commands) == len(expected['commands']), 'missing/extra Android command')
    require(isinstance(executions, list) and len(executions) == len(commands), 'actual Android command completion missing')
    for index, (command, wanted, done) in enumerate(zip(commands, expected['commands'], executions)):
        require(isinstance(command, dict) and command.get('op') == wanted[0], 'Android command order')
        if wanted[0] == 'tap':
            require(command.get('expectedCaret') == wanted[1] and integer(command.get('x')) and integer(command.get('y')), 'real tap caret/geometry missing')
        else:
            field = {'text': 'text', 'key': 'code', 'combination': 'codes'}[wanted[0]]
            require(command.get(field) == wanted[1], 'Android command changed')
        require(isinstance(done, dict) and type(done.get('commandIndex')) is int and done['commandIndex'] == index
                and done.get('op') == wanted[0] and done.get('completed') is True and type(done.get('invocationCount')) is int
                and done['invocationCount'] == 1, 'skipped/duplicated Android execution')


def verify_common_identity(common, build, *, source, run_id, run_attempt):
    require(isinstance(common, dict) and type(common.get('schema')) is int and common['schema'] == 1
            and common.get('package') == PACKAGE and common.get('dirtySource') is False,
            'actual common installed identity missing or dirty')
    expected = dict(sourceCommit=source, runId=run_id, runAttempt=run_attempt,
                    apkSha256=build['integrationApkSha256'], sdkBuildSource=source,
                    sdkAarSha256=build['sdkAarSha256'], sdkClassesJarSha256=build['sdkClassJarSha256'],
                    sdkGeckoEditableClassSha256=build['sdkEditableClassSha256'],
                    sdkManifestSha256=build['sdkManifestSha256'], sdkBuildReceiptSha256=build['sdkReceiptSha256'])
    require(all(common.get(key) == value for key, value in expected.items() if key not in ['runId', 'runAttempt']),
            'common installed APK/source/SDK identity differs from caret fixture identity')
    for key in ['runId', 'runAttempt']:
        require(key not in common or common[key] == expected[key], 'optional outer common run identity conflicts: ' + key)
    nested = common.get('sdkBuildIdentity')
    require(isinstance(nested, dict) and type(nested.get('schema')) is int and nested['schema'] == 1
            and hex_value(common.get('sourceTree'), 40) and nested.get('sourceTree') == common['sourceTree'],
            'common SDK identity has missing/inconsistent committed source tree')
    for key in ['sourceCommit', 'runId', 'runAttempt', 'sdkBuildSource', 'sdkAarSha256', 'sdkClassesJarSha256',
                'sdkGeckoEditableClassSha256', 'sdkManifestSha256', 'sdkBuildReceiptSha256']:
        require(nested.get(key) == expected[key], 'common nested SDK identity differs: ' + key)
    return common


def verify_report(report, *, build, sdk, audit, source, run_id, run_attempt, build_hash, sdk_hash, audit_hash,
                  artifact_root=ROOT, sdk_raw=None, source_reader=None):
    embedded, identity, installed = verify_receipts(build, sdk, audit, source=source, run_id=run_id, run_attempt=run_attempt,
                                                  sdk_hash=sdk_hash, audit_hash=audit_hash, artifact_root=artifact_root,
                                                  sdk_raw=sdk_raw, source_reader=source_reader)
    require(type(report.get('schema')) is int and report['schema'] == 1 and report.get('status') == 'passed'
            and report.get('mode') == 'normal' and report.get('diagnosticOnly') is False, 'actual normal passed report required')
    for field in ['actualAndroidExecution', 'actualGeckoExecution', 'sdkObserverAbsenceChecked', 'controlledCaretCompatibilityAcceptance']:
        require(report.get(field) is True, 'required actual scope missing ' + field)
    for field in ['releaseAcceptance', 'physicalPhoneAcceptance', 'vendorKeyboardUiAcceptance', 'sdkObserverEnabled']:
        require(report.get(field) is False, 'unsupported acceptance or SDK observer ' + field)
    require(type(report.get('domTextWrites')) is int and report['domTextWrites'] == 0 and not report.get('error')
            and not report.get('runnerError') and not report.get('failureType') and not report.get('skipped'), 'failure/skip/DOM text writes present')
    require(report.get('sdkObserverClassNamesChecked') == OBSERVERS, 'observer absence checks incomplete')
    require(all(report.get(field) == wanted for field, wanted in [('sourceCommit', source), ('runId', run_id), ('runAttempt', run_attempt),
            ('buildReceiptSha256', build_hash), ('sdkReceiptSha256', sdk_hash), ('apkDefinitionAuditSha256', audit_hash)]), 'report invocation or receipt hash mismatch')
    require(report.get('embeddedBuildIdentity') == embedded and report.get('buildIdentity') == identity
            and report.get('installedBuild') == installed, 'report differs from actual installed source/SDK/APK identity')
    verify_common_identity(report.get('commonInstalledIdentity'), build, source=source, run_id=run_id, run_attempt=run_attempt)
    if source_reader is None:
        def source_reader(commit, path):
            return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=artifact_root, stderr=subprocess.PIPE)
    _sdk.verify_sdk_identity(report['commonInstalledIdentity'], source, sdk['sourceTree'], sdk_raw, source_reader)
    events = verify_events(report)
    wanted_checks, wanted_apis, wanted_hardware, wanted_actions, wanted_clipboard = expected_layout()
    checks = report.get('checks')
    require(isinstance(checks, list) and type(report.get('checkCount')) is int and report['checkCount'] == len(wanted_checks) == len(checks), 'missing/extra checks')
    for index, (actual, expected) in enumerate(zip(checks, wanted_checks)):
        require(isinstance(actual, dict) and type(actual.get('index')) is int and actual['index'] == index
                and actual.get('scenario') == expected[0] and actual.get('name') == expected[1]
                and actual.get('pass') is True, 'check order/result differs from fixture')
    apis = report.get('actualInputConnectionCalls')
    require(isinstance(apis, list) and type(report.get('apiCount')) is int and report['apiCount'] == len(wanted_apis) == len(apis), 'missing/extra original InputConnection calls')
    for actual, expected in zip(apis, wanted_apis):
        require(isinstance(actual, dict) and all(actual.get(k) == v for k, v in expected.items())
                and actual.get('origin') == 'original-sdk-inputconnection' and actual.get('accepted') is True
                and integer(actual.get('thread'), 1) and type(actual.get('connectionIdentity')) is int
                and actual['connectionIdentity'] != 0, 'InputConnection arguments/acceptance/thread identity')
    require(len({row['thread'] for row in apis}) == 1, 'original InputConnection calls changed IC thread')
    for case_id in IDS:
        require(len({row['connectionIdentity'] for row in apis if row['scenario'] == case_id}) <= 1,
                'original InputConnection identity changed within a case')
    hardware = report.get('actualAndroidActions')
    require(isinstance(hardware, list) and len(hardware) == len(wanted_hardware), 'missing/extra Android actions')
    for actual, expected in zip(hardware, wanted_hardware):
        verify_hardware(actual, expected)
    clipboard = report.get('actualClipboardCalls')
    require(clipboard == wanted_clipboard, 'missing/extra/reordered actual ClipboardManager calls')
    cases, checkpoints = report.get('scenarios'), report.get('checkpoints')
    require(isinstance(cases, list) and [case.get('id') for case in cases] == IDS
            and type(report.get('scenarioCount')) is int and report['scenarioCount'] == len(IDS), 'missing/duplicate/reordered case')
    require(isinstance(checkpoints, list) and type(report.get('checkpointCount')) is int
            and report['checkpointCount'] == len(checkpoints) == sum(map(len, CHECKPOINTS)), 'missing/extra checkpoint')
    cp_index = 0
    for number, case in enumerate(cases):
        case_id = IDS[number]; raw = events[case_id]
        require(case.get('initialDraft') == SEEDS[number], 'initial HTML seed changed')
        initial, focus = case.get('initialSnapshot'), case.get('focusedInitial')
        require(isinstance(initial, dict) and isinstance(focus, dict) and integer(initial.get('eventCount'))
                and integer(focus.get('eventCount')) and initial['eventCount'] <= focus['eventCount'] <= len(raw),
                'initial/focus raw event prefix bounds')
        snapshot(initial, number, raw[:initial['eventCount']], focused=False)
        snapshot(focus, number, raw[:focus['eventCount']], focused=True)
        require(all(counts(raw[:focus['eventCount']])[field] == 0 for field in ['keyCount', 'inputCount', 'beforeCount',
                'compositionCount', 'compositionEndCount']), 'edits occurred before the initial real focus')
        require(initial['draft'] == focus['draft'] == SEEDS[number] and focus['start'] == focus['end'] == CARETS[number], 'initial exact real-tap caret missing')
        require(case.get('checkpoints') == checkpoints[cp_index:cp_index + len(CHECKPOINTS[number])], 'case checkpoints differ from global actual checkpoints')
        previous_count = focus['eventCount']
        for expected in CHECKPOINTS[number]:
            actual = checkpoints[cp_index]
            require(isinstance(actual, dict) and type(actual.get('index')) is int and actual['index'] == cp_index
                    and actual.get('scenario') == case_id and actual.get('expected') == expected, 'missing/invented expected checkpoint')
            value = actual.get('actual'); count = value.get('eventCount') if isinstance(value, dict) else None
            require(integer(count) and previous_count <= count <= len(raw), 'checkpoint event prefix order')
            snapshot(value, number, raw[:count], focused=True)
            require(all(value.get(field) == expected[field] for field in ['draft', 'start', 'end']), 'actual checkpoint draft/caret differs')
            require(value['keyCount'] >= expected['minimumKeys'] and value['inputCount'] >= expected['minimumInputs']
                    and value['beforeCount'] >= expected['minimumBefore'], 'actual checkpoint input minima missing')
            if raw[:count]:
                latest = raw[count - 1]
                require(latest['draft'] == value['draft'] and latest['start'] == value['start'] and latest['end'] == value['end'],
                        'checkpoint is not the latest actual event state')
            if case_id == 'reversed-selection' and actual['expected'] == CHECKPOINTS[number][0]:
                require(value['direction'] == 'backward', 'reversed selection lost its direction')
            if case_id == 'noop-composition' and actual['expected'] == CHECKPOINTS[number][0]:
                require(value['inputCount'] == 0, 'no-op composition fabricated an input')
            previous_count = count; cp_index += 1
        require(previous_count == len(raw) and case.get('actual') == checkpoints[cp_index - 1]['actual'], 'final snapshot omits actual events/checkpoint')
        expected_case_actions = []
        for kind, wanted in wanted_actions[number]:
            rows = hardware if kind == 'hw' else (clipboard if kind == 'clipboard' else apis)
            row = next(row for row in rows if row.get('id' if kind == 'hw' else 'index') == wanted['id' if kind == 'hw' else 'index'])
            expected_case_actions.append({key: value for key, value in row.items() if key != 'executions'})
        require(case.get('actions') == expected_case_actions, 'case actions omit/reorder actual hardware or IC calls')
    rejected = cases[10]['actual']
    require(rejected['characterKeyCount'] == rejected['qKeyCount'] == rejected['beforeCount'] == 1 and rejected['inputCount'] == 0,
            'rejected key must be submitted once and produce no input')
    rejected_before = [event for event in events['rejected-input'] if event['type'] == 'beforeinput']
    require(len(rejected_before) == 1 and rejected_before[0]['prevented'] is True,
            'rejected input lacks actual beforeinput prevention')
    require(cases[6]['actual']['compositionCount'] > 0 and cases[6]['actual']['compositionEndCount'] > 0
            and cases[7]['actual']['compositionEndCount'] > 0, 'actual composition protocol events missing')
    requests = report.get('fixtureRequests')
    require(isinstance(requests, list) and requests == [dict(case=i, id=case_id, method='GET', path='/caret') for i, case_id in enumerate(IDS)],
            'actual immutable fixture requests missing/duplicated/reordered')
    routes = report.get('controlledProxyRoutes')
    require(isinstance(routes, list) and routes and all(isinstance(row, dict) and row.get('accepted') is True
            and row.get('host') == '127.0.0.1' and row.get('port') == 8771 and row.get('addressType') in [1, 3] for row in routes), 'controlled proxy route changed')
    return dict(controlledCaretCompatibilityAcceptance=True, releaseAcceptance=False,
                physicalPhoneAcceptance=False, vendorKeyboardUiAcceptance=False, scenarios=14,
                checkpoints=len(checkpoints), checks=len(checks), originalInputConnectionCalls=len(apis),
                actualAndroidActions=len(hardware), trustedDomEvents=sum(map(len, events.values())))


def verify_original_burst(report, *, source, run_id, run_attempt, identity, sidecar, raw_report, build,
                          build_hash, sdk_raw, artifact_root=ROOT, source_reader=None):
    """Extra strict burst checks; all existing full performance gates still apply."""
    require(isinstance(identity, dict) and hex_value(identity.get('sourceTree'), 40)
            and all(hex_value(identity.get(key)) for key in ['sdkManifestSha256', 'sdkBuildReceiptSha256', 'apkSha256']),
            'actual common installed identity required for original performance sidecar')
    require(type(raw_report) is bytes and _sdk.strict_json(raw_report) == report,
            'original performance raw bytes missing or decoded report differs')
    require(isinstance(sidecar, dict) and type(sidecar.get('schema')) is int and sidecar['schema'] == 1,
            'separate original performance build identity sidecar required')
    expected_sidecar = dict(sourceCommit=source, sourceTree=identity['sourceTree'], runId=run_id, runAttempt=run_attempt,
        sdkManifestSha256=identity['sdkManifestSha256'], sdkReceiptSha256=identity['sdkBuildReceiptSha256'],
        integrationApkSha256=identity['apkSha256'], buildReceiptSha256=build_hash,
        rawReportSha256=digest(raw_report), rawReportBytes=len(raw_report))
    require(all(type(sidecar.get(key)) is type(value) and sidecar[key] == value for key, value in expected_sidecar.items()),
            'original performance sidecar source/run/APK/SDK/raw report binding mismatch')
    require(type(sidecar.get('invocationCount')) is int and sidecar['invocationCount'] == 1
            and type(sidecar.get('runnerExitCode')) is int and sidecar['runnerExitCode'] == 0,
            'original performance runner skipped, repeated or failed')
    require(all(sidecar.get(key) is True for key in ['actualInstalledApkRead', 'rawReportUnmodified', 'actualAndroidExecution'])
            and sidecar.get('diagnosticOnly') is False, 'actual unchanged normal performance sidecar missing')
    if source_reader is None:
        def source_reader(commit, path):
            return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=artifact_root, stderr=subprocess.PIPE)
    protected = {'runnerSha256': 'tests/gecko/run_gecko_performance.py',
                 'activitySha256': 'tests/gecko/GeckoPerformanceIntegrationActivity.java'}
    for field, path in protected.items():
        require(sidecar.get(field) == digest(source_reader(source, path)),
                'original protected performance source bytes differ: ' + field)
    command = sidecar.get('command')
    invocation_root = sidecar.get('invocationRepositoryRoot')
    require(isinstance(invocation_root, str) and bool(invocation_root)
            and Path(invocation_root).is_absolute()
            and '..' not in Path(invocation_root).parts,
            'actual original runner repository root missing or invalid')
    require(isinstance(command, list) and len(command) == 6 and all(isinstance(part, str) and part for part in command)
            and Path(command[0]).name.startswith('python')
            and command[1] == str(Path(invocation_root) / protected['runnerSha256'])
            and command[2] == '--adb' and command[4] == '--serial',
            'original normal runner invocation changed or added diagnostic/pacing arguments')
    before, after = sidecar.get('before'), sidecar.get('after')
    require(isinstance(before, dict) and isinstance(after, dict) and before.get('apkSha256') == after.get('apkSha256') == identity['apkSha256'],
            'installed APK changed across original performance execution')
    require(isinstance(before.get('installedApkPath'), str) and before['installedApkPath'].startswith('/data/app/')
            and before['installedApkPath'].endswith('/base.apk') and after.get('installedApkPath') == before['installedApkPath'],
            'actual installed APK path missing or changed across original execution')
    require(before.get('apkDefinitionAudit') == after.get('apkDefinitionAudit'), 'actual installed definitions changed across original execution')
    sdk = _sdk.strict_json(sdk_raw)
    for frame in [before, after]:
        audit = frame.get('apkDefinitionAudit'); common = frame.get('commonInstalledIdentity')
        require(isinstance(audit, dict), 'actual original performance installed definition audit missing')
        verify_receipts(build, sdk, audit, source=source, run_id=run_id, run_attempt=run_attempt,
                        sdk_hash=digest(sdk_raw), audit_hash=digest(json.dumps(audit, sort_keys=True).encode('utf-8')),
                        artifact_root=artifact_root, sdk_raw=sdk_raw, source_reader=source_reader)
        verify_common_identity(common, build, source=source, run_id=run_id, run_attempt=run_attempt)
        _sdk.verify_sdk_identity(common, source, identity['sourceTree'], sdk_raw, source_reader)
        require(common['sourceTree'] == identity['sourceTree'] and common['apkSha256'] == identity['apkSha256'],
                'original and caret fixtures do not share installed source/APK identity')
        for key in _sdk.SDK_FIELDS:
            require(common.get(key) == identity.get(key), 'original and caret fixtures use different SDK metadata: ' + key)
    require(report.get('status') == 'passed' and report.get('diagnosticOnly') is False
            and report.get('inputDiagnosticsEnabled') is False and report.get('inputNativeDiagnosticsEnabled') is False,
            'original strict burst must pass in normal mode')
    for field in ['sdkInputWriterDiagnosticsEnabled', 'sdkObserverEnabled']:
        require(field not in report or report[field] is False, 'original burst has SDK diagnostic mode: ' + field)
    for field in ['actualSdkInputClockTrace', 'sdkInputWriterLogCapture']:
        require(not report.get(field), 'original burst includes SDK diagnostic observations: ' + field)
    require(all(report.get(key) is True for key in ['actualAndroidExecution', 'actualGeckoExecution',
            'actualAndroidTouchExecution', 'actualGeckoBindingRegressionExecution', 'actualInputImeSettled', 'actualSingleInputBurst']),
            'actual original strict burst execution missing')
    require(report.get('sourceCommit') == source, 'original raw performance report source mismatch')
    for field, expected in [('runId', run_id), ('runAttempt', run_attempt)]:
        require(field not in report or report[field] == expected, 'existing original report identity conflicts: ' + field)
    require(report.get('actualInputEvaluationTrace') == [] and report.get('actualNativeInputTrace') == [], 'normal burst contains additional observers')
    checks = report.get('checks')
    require(isinstance(checks, list) and type(report.get('checkCount')) is int and report['checkCount'] == len(checks) >= 155
            and all(isinstance(row, dict) and row.get('pass') is True for row in checks)
            and len({row.get('name') for row in checks}) == len(checks), 'original full performance checks incomplete')
    required_names = ['Actual Android input waits for visible IME and unchanged viewport, composer and caret',
        'Actual Android tap and keyboard input preserve the existing composer draft',
        'The single Android input burst delivers exact ordered trusted keys and real input events',
        'Actual user input neither sends a message nor changes the synthetic login']
    require(all(name in {row['name'] for row in checks} for name in required_names), 'original strict burst assertions removed')
    inputs = report.get('actualAndroidTextInputs')
    require(isinstance(inputs, list) and len(inputs) == 1 and inputs[0].get('id') == 'current-input'
            and inputs[0].get('text') == '-user-typed', 'original single unpaced Android text burst changed')
    request = inputs[0]
    require(all(request.get(key) is True for key in ['composerFocused', 'nativeFocused', 'acceptingText', 'imeVisible'])
            and integer(request.get('stableFocusSamples'), 3) and type(request.get('settledMs')) in (int, float)
            and request['settledMs'] >= 600 and request.get('start') == request.get('end')
            and integer(request.get('start')) and isinstance(request.get('draft'), str), 'original burst readiness handshake missing')
    events = report.get('actualTrustedInputEvents')
    require(isinstance(events, list) and 1 <= len(events) < 256 and all(isinstance(e, dict)
            and e.get('type') in EVENT_TYPES | {'focus', 'blur', 'select'} and e.get('trusted') is True for e in events),
            'original burst events incomplete/untrusted/diagnostic')
    keys = [e.get('key') for e in events if e['type'] == 'keydown' and isinstance(e.get('key'), str) and utf16_length(e['key']) == 1]
    require(keys == list('-user-typed'), 'original eleven trusted keys missing/reordered/duplicated')
    actual_inputs = [e for e in events if e['type'] == 'input']
    require(actual_inputs, 'original burst produced no actual input')
    final = actual_inputs[-1]; draft = final.get('draft')
    require(isinstance(draft, str) and draft.count('-user-typed') == 1
            and draft.replace('-user-typed', '', 1) == request['draft'], 'original burst changed the existing draft')
    return dict(originalSingleBurst=True, orderedTrustedKeys=11, fullPerformanceChecks=len(checks))


EVIDENCE_FILES = ('installed-apk-definition-audit.json', 'sdk-build-receipt.json',
                  'caret-apk-build-receipt.json', 'gecko-caret-compat-results.json',
                  'gecko-performance-results.json', 'gecko-performance-build-identity.json')


def verify_caret_evidence(directory, source, *, artifact_root=ROOT, source_reader=None):
    """Validate both actual normal fixtures and their shared byte/source/run binding.

    Selected source bytes come from artifact_root's Git object, independently of
    the directory containing staged artifacts and the recorded CI invocation path.
    source_reader is injectable only for synthetic contract controls.
    """
    require(hex_value(source, 40), 'selected evidence source commit missing')
    directory = Path(directory)
    raw, values, hashes = {}, {}, {}
    for name in EVIDENCE_FILES:
        path = directory / name
        require(path.is_file(), 'required evidence artifact missing: ' + name)
        raw[name] = path.read_bytes()
        values[name] = _sdk.strict_json(raw[name])
        hashes[name] = digest(raw[name])
    sdk = values['sdk-build-receipt.json']
    require(sdk.get('sourceCommit') == source, 'SDK evidence belongs to another selected source')
    run_id, run_attempt = sdk.get('runId'), sdk.get('runAttempt')
    build = values['caret-apk-build-receipt.json']
    audit = values['installed-apk-definition-audit.json']
    report = values['gecko-caret-compat-results.json']
    sidecar = values['gecko-performance-build-identity.json']
    result = verify_report(report, build=build, sdk=sdk, audit=audit, source=source,
        run_id=run_id, run_attempt=run_attempt, build_hash=hashes['caret-apk-build-receipt.json'],
        sdk_hash=hashes['sdk-build-receipt.json'], audit_hash=hashes['installed-apk-definition-audit.json'],
        artifact_root=artifact_root, sdk_raw=raw['sdk-build-receipt.json'], source_reader=source_reader)
    for position in ['before', 'after']:
        frame = sidecar.get(position)
        require(isinstance(frame, dict) and frame.get('apkDefinitionAudit') == audit,
                'original and caret installed definition audits differ: ' + position)
    result['originalBurst'] = verify_original_burst(values['gecko-performance-results.json'],
        source=source, run_id=run_id, run_attempt=run_attempt, identity=report['commonInstalledIdentity'],
        sidecar=sidecar, raw_report=raw['gecko-performance-results.json'], build=build,
        build_hash=hashes['caret-apk-build-receipt.json'], sdk_raw=raw['sdk-build-receipt.json'],
        artifact_root=artifact_root, source_reader=source_reader)
    common = report['commonInstalledIdentity']
    return dict(result, status='passed', sourceCommit=source, sourceTree=common['sourceTree'],
        runId=run_id, runAttempt=run_attempt, integrationApkSha256=build['integrationApkSha256'],
        releaseApkSha256=build['releaseApkSha256'], sdkManifestSha256=build['sdkManifestSha256'],
        sdkBuildReceiptSha256=hashes['sdk-build-receipt.json'], sdkAarSha256=build['sdkAarSha256'],
        sdkClassesJarSha256=build['sdkClassJarSha256'], sdkGeckoEditableClassSha256=build['sdkEditableClassSha256'],
        artifactSha256=hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['report', 'build-receipt', 'sdk-receipt', 'install-definition-audit', 'source', 'run-id', 'run-attempt']:
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--performance-report', help='Also require the unchanged original strict normal burst')
    parser.add_argument('--performance-build-identity', help='Immutable installed-build sidecar for the untouched original report')
    parser.add_argument('--artifact-root', type=Path, default=ROOT, help='Root for SDK source/recipe artifact rows')
    args = parser.parse_args()
    require(bool(args.performance_report) == bool(args.performance_build_identity), 'performance report and build sidecar must be supplied together')
    report, _ = read_json(args.report); build, build_hash = read_json(args.build_receipt)
    sdk, sdk_hash = read_json(args.sdk_receipt); audit, audit_hash = read_json(args.install_definition_audit)
    result = verify_report(report, build=build, sdk=sdk, audit=audit, source=args.source, run_id=args.run_id,
                           run_attempt=args.run_attempt, build_hash=build_hash, sdk_hash=sdk_hash, audit_hash=audit_hash,
                           artifact_root=args.artifact_root, sdk_raw=Path(args.sdk_receipt).read_bytes())
    if args.performance_report:
        performance, _ = read_json(args.performance_report)
        sidecar, _ = read_json(args.performance_build_identity)
        result['originalBurst'] = verify_original_burst(performance, source=args.source, run_id=args.run_id,
            run_attempt=args.run_attempt, identity=report['commonInstalledIdentity'], sidecar=sidecar,
            raw_report=Path(args.performance_report).read_bytes(), build=build, build_hash=build_hash,
            sdk_raw=Path(args.sdk_receipt).read_bytes(), artifact_root=args.artifact_root)
    print(json.dumps(dict(status='passed', **result), sort_keys=True))


if __name__ == '__main__':
    main()
