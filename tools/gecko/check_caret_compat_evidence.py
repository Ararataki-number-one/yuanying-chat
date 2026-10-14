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


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_native_geometry(geometry, owner):
    require(isinstance(geometry, dict) and all(type(geometry.get(key)) is type(wanted) and geometry[key] == wanted
            for key, wanted in owner.items()), 'native geometry source/run/document owner differs')
    for field in ['nativeSession', 'attachedSession', 'nativePort']:
        require(type(geometry.get(field)) is int and geometry[field] != 0, 'actual native geometry session/port missing')
    require(geometry['nativeSession'] == geometry['attachedSession'] and geometry.get('shown') is True
            and geometry.get('committedUrl') == owner['documentUrl'], 'native geometry is not the visible committed session')
    for field in ['surfaceWidth', 'surfaceHeight', 'webWidth', 'webHeight']:
        require(integer(geometry.get(field), 1), 'native geometry dimension missing: ' + field)
    for field in ['originX', 'originY']:
        require(type(geometry.get(field)) is int and -(2**31) <= geometry[field] < 2**31, 'actual native surface origin missing')
    layout, matrix = geometry.get('readingLayout'), geometry.get('clientToSurfaceMatrix')
    require(finite_number(layout) and 0 < layout <= 1 and isinstance(matrix, list) and len(matrix) == 9
            and all(finite_number(value) for value in matrix), 'finite actual native matrix and layout required')
    require(matrix[0] > 0 and matrix[4] > 0 and abs(matrix[0] - matrix[4]) <= .001
            and matrix[1] == matrix[3] == matrix[6] == matrix[7] == 0 and matrix[8] == 1,
            'native client matrix must have positive isotropic affine scales')
    return matrix, layout


def verify_viewport(viewport):
    require(isinstance(viewport, dict) and all(finite_number(viewport.get(field)) for field in
            ['width', 'height', 'scale', 'offsetLeft', 'offsetTop', 'pageLeft', 'pageTop'])
            and viewport['width'] > 0 and viewport['height'] > 0 and viewport['scale'] > 0,
            'actual document visual viewport missing or invalid')


def verify_measured_points(snapshot):
    points = snapshot.get('points')
    require(snapshot.get('ready') is True and isinstance(points, list)
            and len(points) == utf16_length(snapshot.get('draft')) + 1,
            'complete actual UTF16 measured caret points missing')
    require(all(isinstance(point, dict) and set(point) == {'x', 'y'}
                and finite_number(point['x']) and finite_number(point['y']) for point in points),
            'actual measured caret points must contain finite coordinates')
    return points


def verify_evidence_collection(report):
    collection = report.get('evidenceCollection')
    phases = [('receiptCaptureStartedAtMonotonicNanos', 'receiptCaptureCompletedAtMonotonicNanos', 'receiptCaptureDurationNanos'),
              ('drainStartedAtMonotonicNanos', 'drainCompletedAtMonotonicNanos', 'drainDurationNanos')]
    fields = {'schema', 'scope', 'activeOperationBudgetMillis', 'readOnlyDrainBudgetMillis'}
    fields.update(field for phase in phases for field in phase)
    require(isinstance(collection, dict) and set(collection) == fields
            and type(collection.get('schema')) is int and collection['schema'] == 1
            and collection.get('scope') == 'host-artifact-io'
            and type(collection.get('activeOperationBudgetMillis')) is int and collection['activeOperationBudgetMillis'] == 300000
            and type(collection.get('readOnlyDrainBudgetMillis')) is int and collection['readOnlyDrainBudgetMillis'] == 600000,
            'host artifact collection scope or operation/drain budget differs')
    for start, end, duration in phases:
        require(integer(collection.get(start), 1) and integer(collection.get(end), 1)
                and integer(collection.get(duration)) and collection[end] >= collection[start]
                and collection[duration] == collection[end] - collection[start],
                'actual host artifact collection phase clocks or duration differ: ' + start)
    require(collection['receiptCaptureCompletedAtMonotonicNanos'] <= collection['drainStartedAtMonotonicNanos'],
            'read-only evidence drain overlaps the active receipt capture phase')
    for action in report['actualAndroidActions']:
        for execution in action['executions']:
            require(collection['receiptCaptureStartedAtMonotonicNanos'] <= execution['adbStartedAtMonotonicNanos']
                    <= execution['adbCompletedAtMonotonicNanos'] <= collection['receiptCaptureCompletedAtMonotonicNanos'],
                    'actual Android input execution lies outside active receipt capture or during read-only drain')


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
            geometry, point = command.get('nativeGeometry'), command.get('clientPoint')
            require(isinstance(geometry, dict) and isinstance(point, dict)
                    and finite_number(point.get('x')) and finite_number(point.get('y')), 'actual SDK matrix/origin/client target missing')
            matrix, layout = verify_native_geometry(geometry, {key: geometry.get(key) for key in
                ['sourceCommit', 'runId', 'runAttempt', 'runNonce', 'case', 'documentUrl', 'timeOrigin']})
            verify_viewport(command.get('viewport'))
            mapped_x = geometry['originX'] + (matrix[0] * point['x'] + matrix[2]) * layout
            mapped_y = geometry['originY'] + (matrix[4] * point['y'] + matrix[5]) * layout
            require(finite_number(mapped_x) and finite_number(mapped_y)
                    and abs(command['x'] - mapped_x) <= .51 and abs(command['y'] - mapped_y) <= .51,
                    'actual tap coordinates differ from the SDK matrix, reading layout and surface origin')
        else:
            field = {'text': 'text', 'key': 'code', 'combination': 'codes'}[wanted[0]]
            require(command.get(field) == wanted[1], 'Android command changed')
        require(isinstance(done, dict) and type(done.get('commandIndex')) is int and done['commandIndex'] == index
                and done.get('op') == wanted[0] and done.get('completed') is True and type(done.get('invocationCount')) is int
                and done['invocationCount'] == 1, 'skipped/duplicated Android execution')
        for start, end in [('adbStartedAtWallTimeMillis', 'adbCompletedAtWallTimeMillis'),
                           ('adbStartedAtMonotonicNanos', 'adbCompletedAtMonotonicNanos')]:
            require(integer(done.get(start), 1) and integer(done.get(end), 1) and done[end] >= done[start],
                    'actual Android execution timestamps missing, malformed or reversed: ' + start)


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


def expected_transport_order(report):
    order = []
    check_index = api_index = hardware_index = checkpoint_index = clipboard_index = 0
    for case_id, flow in zip(IDS, FLOW):
        order += [('check', check_index), ('stepNeeded', f'{case_id}-focus-{hardware_index}'), ('check', check_index + 1)]
        check_index += 2; hardware_index += 1
        for step in flow:
            kind = step[0]
            if kind == 'hw':
                order.append(('stepNeeded', f'{case_id}-{step[1]}-{hardware_index}')); hardware_index += 1
            elif kind == 'api':
                order += [('api', api_index), ('check', check_index)]; api_index += 1; check_index += 1
            elif kind == 'clipboard':
                order.append(('clipboard', clipboard_index)); clipboard_index += 1
            elif kind == 'cp':
                order.append(('checkpoint', checkpoint_index)); checkpoint_index += 1
                order += [('check', check_index + offset) for offset in range(3)]; check_index += 3
            elif kind == 'extra':
                order.append(('check', check_index)); check_index += 1
        order += [('trustedEvents', (row['id'], row['offset'])) for row in report['trustedEventChunks'] if row['id'] == case_id]
        order.append(('scenario', case_id))
    order.append(('report', None))
    return order


def verify_caret_transport(report, *, source, run_id, run_attempt):
    """Reconstruct the actual provider records; never accept a partial log payload."""
    transport = report.get('eventTransport')
    require(isinstance(transport, dict) and type(transport.get('schema')) is int and transport['schema'] == 1,
            'complete owned caret event transport missing')
    nonce = transport.get('runNonce')
    require(hex_value(nonce, 32) and report.get('runNonce') == nonce
            and transport.get('fixtureAction') == 'caretCompatibility'
            and type(transport.get('processSlot')) is int and transport['processSlot'] == 0
            and type(transport.get('command')) is int and transport['command'] == 1,
            'caret transport invocation/slot/action/command differs')
    common = report['commonInstalledIdentity']
    require(transport.get('buildIdentity') == common, 'caret transport differs from actual installed identity')
    records = transport.get('records')
    require(isinstance(records, list) and 1 <= len(records) <= 4096, 'complete ordered provider records missing')
    collected = {kind: [] for kind in ['check', 'checkpoint', 'scenario', 'api', 'clipboard', 'stepNeeded', 'trustedEvents']}
    terminal, observed_order = None, []
    for sequence, row in enumerate(records, 1):
        require(isinstance(row, dict) and set(row) == {'receipt', 'rawUtf8'} and isinstance(row['rawUtf8'], str),
                'original provider receipt and complete UTF8 payload required')
        raw = row['rawUtf8'].encode('utf-8', errors='strict')
        receipt = row['receipt']
        require(isinstance(receipt, dict) and receipt.get('kind') == 'eventReceipt'
                and type(receipt.get('schema')) is int and receipt['schema'] == 1
                and type(receipt.get('payloadBytes')) is int and receipt['payloadBytes'] == len(raw)
                and 0 < len(raw) <= 2 * 1024 * 1024 and receipt.get('payloadSha256') == digest(raw),
                'provider payload UTF8 byte bound/length/hash differs')
        envelope = _sdk.strict_json(raw)
        expected = dict(runNonce=nonce, fixtureAction='caretCompatibility', command=1, sequence=sequence,
                        nativeContext='environment-1', processSlot=0)
        for key, wanted in expected.items():
            require(type(receipt.get(key)) is type(wanted) and receipt[key] == wanted
                    and type(envelope.get(key)) is type(wanted) and envelope[key] == wanted,
                    'provider source/run/ordered sequence fence differs: ' + key)
        require(type(envelope.get('schema')) is int and envelope['schema'] == 1
                and envelope.get('sourceCommit') == source and envelope.get('buildIdentity') == common
                and integer(envelope.get('observedAtElapsedRealtime')),
                'provider envelope source/build/observation identity differs')
        event = envelope.get('event')
        require(isinstance(event, dict) and event.get('kind') == receipt.get('eventKind')
                and event.get('nativeContext') == 'environment-1' and type(event.get('processSlot')) is int
                and event['processSlot'] == 0 and isinstance(event.get('result'), dict),
                'complete original provider event/result differs')
        kind, value = event['kind'], event['result']
        require(terminal is None and kind in set(collected) | {'report'}, 'unexpected, failed or post-terminal provider event')
        key = None if kind == 'report' else ((value.get('id'), value.get('offset')) if kind == 'trustedEvents'
              else value.get('id') if kind in ['stepNeeded', 'scenario'] else value.get('index'))
        observed_order.append((kind, key))
        if kind == 'report':
            require(sequence == len(records), 'terminal provider report is not the final event')
            terminal = value
        else:
            collected[kind].append(value)
    require(isinstance(terminal, dict) and terminal.get('status') == 'passed'
            and terminal.get('error') == '' and all(report.get(key) == value for key, value in terminal.items()),
            'full native terminal report missing, failed or mutated')
    require(observed_order == expected_transport_order(report), 'provider event order differs from the actual fixture flow')
    require(isinstance(transport.get('receiptLedger'), list)
            and _sdk._typed_equal(transport['receiptLedger'], [row['receipt'] for row in records]),
            'complete native receipt ledger differs from ordered original provider records')
    for kind, field in [('check', 'checks'), ('checkpoint', 'checkpoints'), ('scenario', 'scenarios'),
                        ('api', 'actualInputConnectionCalls'), ('clipboard', 'actualClipboardCalls'),
                        ('trustedEvents', 'trustedEventChunks')]:
        require(collected[kind] == report.get(field), 'provider raw events differ from reconstructed ' + field)
    actions = report.get('actualAndroidActions')
    require(isinstance(actions, list) and collected['stepNeeded'] ==
            [{key: value for key, value in action.items() if key != 'executions'} for action in actions],
            'provider original Android requests differ from executed actions')
    for number, case in enumerate(report.get('scenarios', [])):
        snapshots = [case.get('initialSnapshot'), case.get('focusedInitial'), case.get('actual')]
        snapshots += [checkpoint.get('actual') for checkpoint in case.get('checkpoints', [])]
        time_origin = None
        for value in snapshots:
            require(isinstance(value, dict), 'actual isolated observation snapshot missing')
            expected = dict(sourceCommit=source, runId=run_id, runAttempt=run_attempt, runNonce=nonce,
                            case=number, documentUrl='http://127.0.0.1:8771/caret?case=' + str(number))
            require(all(type(value.get(key)) is type(wanted) and value[key] == wanted for key, wanted in expected.items())
                    and value.get('observerWorld') == 'extension-isolated-world'
                    and type(value.get('listenerInstallCount')) is int and value['listenerInstallCount'] == 1,
                    'isolated observer source/run/nonce/case/document/listener owner differs')
            observed = value.get('timeOrigin')
            require(type(observed) in (int, float) and math.isfinite(observed) and observed > 0
                    and (time_origin is None or observed == time_origin), 'observer document time origin changed within case')
            time_origin = observed
            owner = dict(expected, timeOrigin=observed)
            matrix, layout = verify_native_geometry(value.get('nativeGeometry'), owner)
            verify_viewport(value.get('viewport'))
            verify_measured_points(value)
        initial = case['initialSnapshot']
        preparation = initial.get('geometryPreparation')
        require(isinstance(preparation, dict) and integer(preparation.get('stableSamples'), 3)
                and integer(preparation.get('stableMillis'), 600) and isinstance(preparation.get('transitions'), list)
                and 1 <= len(preparation['transitions']) <= 16, 'initial geometry preparation was skipped or unbounded')
        require(integer(preparation.get('startedAt'), 1) and integer(preparation.get('completedAt'), 1)
                and integer(preparation.get('preparationStartedAt'), 1)
                and preparation['preparationStartedAt'] <= preparation['startedAt'] <= preparation['completedAt']
                and preparation['completedAt'] - preparation['preparationStartedAt'] <= 25000
                and preparation['completedAt'] - preparation['startedAt'] == preparation['stableMillis'],
                'actual geometry preparation timestamps differ from settled duration')
        first = preparation.get('firstStableSnapshot')
        stable_fields = ['sourceCommit', 'runId', 'runAttempt', 'runNonce', 'case', 'documentUrl', 'timeOrigin',
                         'nativeGeometry', 'viewport', 'bounds', 'points', 'draft', 'start', 'end',
                         'readyState', 'documentFontsLoaded']
        require(isinstance(first, dict) and all(_sdk._typed_equal(first.get(key), initial.get(key)) for key in stable_fields),
                'prepared geometry changed between first and final stable observations')
        last_transition = preparation['preparationStartedAt']
        for transition in preparation['transitions']:
            require(isinstance(transition, dict) and integer(transition.get('observedAt'), 1)
                    and last_transition <= transition['observedAt'] <= preparation['startedAt']
                    and type(transition.get('ready')) is bool and isinstance(transition.get('snapshot'), dict),
                    'bounded actual geometry transitions malformed or out of order')
            last_transition = transition['observedAt']
            observed_snapshot = transition['snapshot']
            require(transition['ready'] is not True or observed_snapshot.get('ready') is True,
                    'native geometry transition claims readiness before document readiness')
            if observed_snapshot.get('ready') is True:
                owner = dict(sourceCommit=source, runId=run_id, runAttempt=run_attempt, runNonce=nonce,
                    case=number, documentUrl=initial['documentUrl'], timeOrigin=initial['timeOrigin'])
                require(all(observed_snapshot.get(key) == wanted for key, wanted in owner.items()),
                        'geometry transition belongs to another observer document')
                pending_native = observed_snapshot.get('nativeGeometry')
                require(isinstance(pending_native, dict) and all(pending_native.get(key) == wanted for key, wanted in owner.items()),
                        'pending native geometry transition belongs to another document')
                if transition['ready'] is True:
                    transition_matrix, transition_layout = verify_native_geometry(pending_native, owner)
                    verify_viewport(observed_snapshot.get('viewport'))
                    verify_measured_points(observed_snapshot)
                    require(observed_snapshot.get('readyState') == 'complete' and observed_snapshot.get('documentFontsLoaded') is True
                            and abs(pending_native['webWidth'] - observed_snapshot['viewport']['width'] * transition_matrix[0] * transition_layout) < 8,
                            'ready native geometry transition is not coherent with its document')
            if transition['observedAt'] == preparation['startedAt']:
                require(transition['ready'] is True and all(_sdk._typed_equal(observed_snapshot.get(key), first.get(key))
                        for key in stable_fields), 'final stable transition differs from its first stable observation')
        # The producer retains only the first 16 transitions. When there is room,
        # it must have recorded the final stable epoch; a full prefix can end
        # earlier, with the separately retained firstStableSnapshot proving it.
        require(len(preparation['transitions']) == 16 or last_transition == preparation['startedAt'],
                'final stable transition missing before the retained prefix was full')
        require(initial.get('readyState') == 'complete' and initial.get('documentFontsLoaded') is True,
                'initial document layout/font preparation incomplete')
        native = initial['nativeGeometry']; viewport = initial['viewport']
        require(abs(native['webWidth'] - viewport['width'] * native['clientToSurfaceMatrix'][0] * native['readingLayout']) < 8,
                'initial document/native viewport geometry incoherent')
        focus_action = next((action for action in actions if action.get('scenario') == case['id']
                             and '-focus-' in action.get('id', '')), None)
        require(isinstance(focus_action, dict) and len(focus_action['commands']) == 1
                and focus_action['commands'][0].get('nativeGeometry') == native
                and focus_action['commands'][0].get('viewport') == viewport,
                'sole initial tap differs from the prepared actual geometry')
    for action in actions:
        number = IDS.index(action['scenario'])
        case = report['scenarios'][number]
        initial = case['initialSnapshot']
        owner = dict(sourceCommit=source, runId=run_id, runAttempt=run_attempt, runNonce=nonce,
                     case=number, documentUrl=initial['documentUrl'], timeOrigin=initial['timeOrigin'])
        for command in action['commands']:
            if command['op'] == 'tap':
                verify_native_geometry(command.get('nativeGeometry'), owner)
                target = initial if '-focus-' in action['id'] else case['focusedInitial']
                require('-focus-' in action['id'] or number == 0 and '-two-rapid-taps-and-type-' in action['id'],
                        'tap has no canonical captured target observation')
                points = verify_measured_points(target)
                index = command.get('expectedCaret')
                require(integer(index) and index < len(points)
                        and _sdk._typed_equal(command.get('clientPoint'), points[index]),
                        'tap does not use the measured point for its advertised caret')
                require(_sdk._typed_equal(command.get('nativeGeometry'), target['nativeGeometry'])
                        and _sdk._typed_equal(command.get('viewport'), target['viewport']),
                        'tap geometry differs from its canonical captured target observation')
    return len(records)


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
    observer_hash = digest(source_reader(source, 'tests/gecko/assets/caret-document-observer.js'))
    require(report.get('observerScriptSha256') == audit.get('observerScriptSha256') == observer_hash,
            'actual isolated observer asset differs from installed APK or selected source')
    events = verify_events(report)
    transport_count = verify_caret_transport(report, source=source, run_id=run_id, run_attempt=run_attempt)
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
    verify_evidence_collection(report)
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
                actualAndroidActions=len(hardware), trustedDomEvents=sum(map(len, events.values())),
                completeProviderEvents=transport_count)


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
