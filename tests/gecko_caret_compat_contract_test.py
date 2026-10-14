#!/usr/bin/env python3
"""Synthetic adversarial evidence controls. No Android/Gecko execution claim."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('caret_contract', Path(__file__).resolve().parents[1] / 'tools/gecko/check_caret_compat_evidence.py')
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
SOURCE, RUN, ATTEMPT = 'a' * 40, '12345', '1'


def raw(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')


def event(events, kind, draft, start, end=None, *, key='', data='', input_type='', ctrl=False):
    events.append(dict(index=len(events), time=len(events) * 10.0, type=kind, key=key, data=data,
                       inputType=input_type, trusted=True, ctrl=ctrl, shift=False,
                       composing=kind.startswith('composition'), start=start, end=start if end is None else end,
                       draft=draft, prevented=False))


def snap(number, draft, start, events, end=None, *, focused=True, direction='none'):
    return dict(ready=True, case=number, draft=draft, start=start, end=start if end is None else end,
                direction=direction, focused=focused, otherDraft='untouched independent draft',
                sendCount=0, cookie='session=synthetic-caret', allTrusted=True, overflow=False,
                **C.counts(events))


def typed(events, old, new, before, after, char, *, end=None, reject=False):
    event(events, 'keydown', old, before, end, key=char)
    event(events, 'beforeinput', old, before, end, data=char, input_type='insertText')
    if reject:
        events[-1]['prevented'] = True
    if not reject:
        event(events, 'input', new, after, data=char, input_type='insertText')
    event(events, 'keyup', old if reject else new, before if reject else after, key=char)


def inserted(events, old, new, before, after, data, *, input_type='insertText'):
    event(events, 'beforeinput', old, before, data=data, input_type=input_type)
    event(events, 'input', new, after, data=data, input_type=input_type)


def case_events(number):
    """Meaningful fictional records for parser controls, never a runner substitute."""
    events = []
    seed, caret = C.SEEDS[number], C.CARETS[number]
    event(events, 'focus', seed, caret)
    stages = []
    def stage(draft, start, end=None, direction='none'):
        stages.append(snap(number, draft, start, events, end, direction=direction))
    if number == 0:
        typed(events, seed, 'abcdefghiQj', 9, 10, 'Q'); stage('abcdefghiQj', 10)
    elif number == 1:
        event(events, 'select', seed, 2, 5); stage(seed, 2, 5)
        typed(events, seed, 'abZfghij', 2, 3, 'Z', end=5); stage('abZfghij', 3)
    elif number == 2:
        event(events, 'keydown', seed, 3, key='ArrowLeft'); event(events, 'keyup', seed, 2, key='ArrowLeft')
        event(events, 'keydown', seed, 2, key='Backspace')
        inserted(events, seed, 'acdef', 2, 1, '', input_type='deleteContentBackward')
        event(events, 'keyup', 'acdef', 1, key='Backspace'); event(events, 'keydown', 'acdef', 1, key='Delete')
        inserted(events, 'acdef', 'adef', 1, 1, '', input_type='deleteContentForward')
        event(events, 'keyup', 'adef', 1, key='Delete'); stage('adef', 1)
    elif number == 3:
        typed(events, seed, 'undoX draft', 4, 5, 'X'); stage('undoX draft', 5)
        event(events, 'keydown', 'undoX draft', 5, key='Control', ctrl=True)
        event(events, 'keydown', 'undoX draft', 5, key='z', ctrl=True)
        inserted(events, 'undoX draft', seed, 5, 4, '', input_type='historyUndo')
        event(events, 'keyup', seed, 4, key='z', ctrl=True); event(events, 'keyup', seed, 4, key='Control')
        stage(seed, 4)
    elif number == 4:
        inserted(events, seed, 'left-many wordsright', 5, 15, 'many words'); stage('left-many wordsright', 15)
    elif number == 5:
        inserted(events, seed, 'clipboard paste tail', 9, 15, ' paste', input_type='insertFromPaste')
        stage('clipboard paste tail', 15)
        typed(events, 'clipboard paste tail', 'clipboard pasteQ tail', 15, 16, 'Q'); stage('clipboard pasteQ tail', 16)
        inserted(events, 'clipboard pasteQ tail', 'clipboard pasteQ😀 tail', 16, 18, '😀', input_type='insertFromPaste')
        stage('clipboard pasteQ😀 tail', 18)
    elif number == 6:
        event(events, 'compositionstart', seed, 4)
        event(events, 'compositionupdate', seed, 4, data='ni')
        inserted(events, seed, 'seedni tail', 4, 6, 'ni', input_type='insertCompositionText'); stage('seedni tail', 6)
        event(events, 'compositionupdate', 'seedni tail', 6, data='你')
        inserted(events, 'seedni tail', 'seed你 tail', 6, 5, '你', input_type='insertCompositionText'); stage('seed你 tail', 5)
        event(events, 'compositionupdate', 'seed你 tail', 5, data='你好')
        inserted(events, 'seed你 tail', 'seed你好 tail', 5, 6, '你好', input_type='insertCompositionText')
        event(events, 'compositionend', 'seed你好 tail', 6, data='你好'); stage('seed你好 tail', 6); stage('seed你好 tail', 6)
    elif number == 7:
        event(events, 'compositionstart', seed, 4); event(events, 'compositionupdate', seed, 4, data='中')
        inserted(events, seed, 'seed中 tail', 4, 5, '中', input_type='insertCompositionText'); stage('seed中 tail', 5)
        event(events, 'compositionend', 'seed中 tail', 5, data='中'); stage('seed中 tail', 5)
    elif number == 8:
        inserted(events, seed, 'batch one two tail', 5, 13, ' one two'); stage('batch one two tail', 13)
    elif number == 9:
        event(events, 'select', seed, 2, 5); stage(seed, 2, 5, 'backward')
        inserted(events, seed, 'abQQf', 2, 4, 'QQ'); stage('abQQf', 4)
    elif number == 10:
        typed(events, seed, seed, 4, 4, 'Q', reject=True); stage(seed, 4)
    elif number == 11:
        typed(events, seed, 'softQ tail', 4, 5, 'Q'); stage('softQ tail', 5)
    elif number == 12:
        inserted(events, seed, 'AB', 3, 1, '', input_type='deleteContentBackward'); stage('AB', 1)
    elif number == 13:
        stage(seed, 4); typed(events, seed, 'noopQ tail', 4, 5, 'Q'); stage('noopQ tail', 5)
    return events, stages


def fixture(directory):
    patch = directory / 'source.patch'; patch.write_text('// synthetic parser-control patch\n')
    recipe = directory / 'compile.py'; recipe.write_text('# synthetic parser-control recipe\n')
    protected = directory / 'tests/gecko'; protected.mkdir(parents=True)
    (protected / 'run_gecko_performance.py').write_text('# synthetic protected runner source control\n')
    (protected / 'GeckoPerformanceIntegrationActivity.java').write_text('// synthetic protected activity source control\n')
    def record(path):
        return dict(path=path.name, bytes=path.stat().st_size, sha256=C.digest(path.read_bytes()))
    manifest = dict(schema=1, sdkBuildKind='source-derived-java', sdkCoordinate=C._sdk.SDK_COORDINATE,
        sdkInputCoordinate=C._sdk.SDK_COORDINATE, sdkRuntimeCoordinate=C._sdk.SDK_RUNTIME_COORDINATE,
        sdkInputAarSha256=C._sdk.SDK_AAR_SHA256, upstreamRevision=C._sdk.UPSTREAM_REVISION,
        sdkAarSha256='1' * 64, sdkClassesJarSha256='2' * 64,
        sdkGeckoEditableClassSha256=C._sdk.DERIVED_EDITABLE_SHA256, sdkAarBytes=12345,
        sourcePatch=record(patch), sourceRecipe=record(recipe), **copy.deepcopy(C._sdk.DERIVED_FLAGS))
    manifest_path = directory / C._sdk.DERIVED_MANIFEST
    manifest_path.parent.mkdir(parents=True); manifest_path.write_bytes(raw(manifest))
    def source_reader(commit, path):
        C.require(commit == SOURCE, 'synthetic selected-source ownership')
        return (directory / path).read_bytes()
    sdk = dict(manifest, sourceCommit=SOURCE, sourceTree='b' * 40, runId=RUN, runAttempt=ATTEMPT,
               sdkManifestSha256=C.digest(manifest_path.read_bytes()))
    sdk_raw = raw(sdk); sdk_hash = C.digest(sdk_raw)
    build = dict(schema=1, sourceCommit=SOURCE, runId=RUN, runAttempt=ATTEMPT,
        integrationApkSha256='4' * 64, releaseApkSha256='5' * 64, sdkReceiptSha256=sdk_hash,
        sdkManifestSha256=sdk['sdkManifestSha256'],
        sdkAarSha256=sdk['sdkAarSha256'], sdkClassJarSha256=sdk['sdkClassesJarSha256'],
        sdkEditableClassSha256=sdk['sdkGeckoEditableClassSha256'], embeddedIdentityAssetSha256='6' * 64,
        normalMode=True, sdkObserverIncluded=False)
    embedded = {field: build[field] for field in C.IDENTITY_FIELDS}
    audit = dict(schema=1, apkSha256=build['integrationApkSha256'], package=C.PACKAGE, component=C.COMPONENT,
        definitionCount=3, observerDefinitions=[], editableDefinitionCount=1, fixtureDefinitionCount=1, caretHelperDefinitionCount=1,
        sdkManifestSha256=build['sdkManifestSha256'],
        embeddedIdentityAssetSha256=build['embeddedIdentityAssetSha256'], embeddedBuildIdentity=embedded,
        dex=[dict(entry='classes.dex', bytes=400, sha256='7' * 64, classDefinitionCount=3, classDefinitions=[
            'Lorg/mozilla/geckoview/GeckoEditable;', 'Llocal/pocketchat/GeckoCaretCompatibilityIntegrationActivity;',
            'Llocal/pocketchat/CaretCompatibilityBuildIdentity;'])])
    audit_hash, build_hash = C.digest(raw(audit)), C.digest(raw(build))
    identity = dict(embedded, integrationApkSha256=build['integrationApkSha256'], releaseApkSha256=build['releaseApkSha256'],
                    embeddedIdentityAssetSha256=build['embeddedIdentityAssetSha256'])
    installed = dict(apkSha256=build['integrationApkSha256'], package=C.PACKAGE, component=C.COMPONENT,
        observerDefinitions=[], apkDefinitionAuditSha256=audit_hash, sdkManifestSha256=build['sdkManifestSha256'],
        embeddedIdentityAssetSha256=build['embeddedIdentityAssetSha256'])
    check_specs, api_specs, hardware_specs, action_specs, clipboard = C.expected_layout()
    checks = [dict(index=i, scenario=case_id, name=name, **{'pass': True}) for i, (case_id, name) in enumerate(check_specs)]
    apis = [dict(row, origin='original-sdk-inputconnection', accepted=True, thread=42, connectionIdentity=100 + C.IDS.index(row['scenario'])) for row in api_specs]
    hardware = []
    for row in hardware_specs:
        commands = []
        for op, value in row['commands']:
            if op == 'tap':
                commands.append(dict(op=op, x=100 + value, y=200, expectedCaret=value))
            else:
                commands.append(dict(op=op, **{{'text': 'text', 'key': 'code', 'combination': 'codes'}[op]: value}))
        hardware.append(dict(id=row['id'], scenario=row['scenario'], origin='adb-input-keyboard-and-touch', commands=commands,
            executions=[dict(commandIndex=i, op=command['op'], completed=True, invocationCount=1) for i, command in enumerate(commands)]))
    scenarios, checkpoints, chunks, flat, projections = [], [], [], {}, {}
    for number, case_id in enumerate(C.IDS):
        events, states = case_events(number); flat[case_id] = events; projections[case_id] = C.vectors(events)
        case_checkpoints = []
        for expected, actual in zip(C.CHECKPOINTS[number], states):
            row = dict(index=len(checkpoints), scenario=case_id, expected=copy.deepcopy(expected), actual=actual)
            checkpoints.append(row); case_checkpoints.append(row)
        actions = []
        for kind, wanted in action_specs[number]:
            rows = hardware if kind == 'hw' else clipboard if kind == 'clipboard' else apis
            field = 'id' if kind == 'hw' else 'index'
            row = next(row for row in rows if row[field] == wanted[field])
            actions.append({k: v for k, v in row.items() if k != 'executions'})
        scenarios.append(dict(id=case_id, initialDraft=C.SEEDS[number],
            initialSnapshot=snap(number, C.SEEDS[number], 0, [], focused=False),
            focusedInitial=snap(number, C.SEEDS[number], C.CARETS[number], events[:1]),
            actual=states[-1], actions=actions, checkpoints=case_checkpoints))
        chunks.extend(dict(id=case_id, offset=offset, events=events[offset:offset + 4]) for offset in range(0, len(events), 4))
    common_sdk = C._sdk.identity_from_receipt(sdk_raw, manifest, build['sdkManifestSha256'], SOURCE, 'b' * 40)
    common_identity = dict(common_sdk, package=C.PACKAGE, dirtySource=False,
                           apkSha256=build['integrationApkSha256'], sdkBuildIdentity=copy.deepcopy(common_sdk))
    common_identity.pop('runId'); common_identity.pop('runAttempt')
    report = dict(schema=1, sourceCommit=SOURCE, runId=RUN, runAttempt=ATTEMPT, mode='normal', status='passed',
        commonInstalledIdentity=common_identity,
        diagnosticOnly=False, releaseAcceptance=False, physicalPhoneAcceptance=False, vendorKeyboardUiAcceptance=False,
        controlledCaretCompatibilityAcceptance=True, actualAndroidExecution=True, actualGeckoExecution=True,
        sdkObserverEnabled=False, sdkObserverAbsenceChecked=True, sdkObserverClassNamesChecked=C.OBSERVERS,
        domTextWrites=0, error='', buildReceiptSha256=build_hash, sdkReceiptSha256=sdk_hash,
        apkDefinitionAuditSha256=audit_hash, buildIdentity=identity, installedBuild=installed, embeddedBuildIdentity=embedded,
        checkCount=len(checks), checks=checks, apiCount=len(apis), actualInputConnectionCalls=apis,
        actualAndroidActions=hardware, actualClipboardCalls=clipboard, scenarioCount=14, scenarios=scenarios,
        checkpointCount=len(checkpoints), checkpoints=checkpoints, trustedEventChunks=chunks,
        actualTrustedEvents=flat, eventVectors=projections,
        fixtureRequests=[dict(case=i, id=case_id, method='GET', path='/caret') for i, case_id in enumerate(C.IDS)],
        controlledProxyRoutes=[dict(host='127.0.0.1', port=8771, addressType=1, accepted=True)])
    return dict(report=report, build=build, sdk=sdk, audit=audit, source=SOURCE, run_id=RUN, run_attempt=ATTEMPT,
                build_hash=build_hash, sdk_hash=sdk_hash, audit_hash=audit_hash, sdk_raw=sdk_raw,
                source_reader=source_reader, artifact_root=directory)


def burst(identity):
    names = ['Actual Android input waits for visible IME and unchanged viewport, composer and caret',
        'Actual Android tap and keyboard input preserve the existing composer draft',
        'The single Android input burst delivers exact ordered trusted keys and real input events',
        'Actual user input neither sends a message nor changes the synthetic login']
    checks = [dict(name=name, **{'pass': True}) for name in names + [f'Synthetic existing performance assertion {i}' for i in range(151)]]
    events = []; draft = 'original unsent draft'
    for char in '-user-typed':
        current = draft + char
        typed(events, draft, current, C.utf16_length(draft), C.utf16_length(current), char)
        draft = current
    return dict(sourceCommit=SOURCE, status='passed',
        diagnosticOnly=False, inputDiagnosticsEnabled=False, inputNativeDiagnosticsEnabled=False,
        actualAndroidExecution=True, actualGeckoExecution=True, actualAndroidTouchExecution=True,
        actualGeckoBindingRegressionExecution=True, actualInputImeSettled=True, actualSingleInputBurst=True,
        actualInputEvaluationTrace=[], actualNativeInputTrace=[], checkCount=155, checks=checks,
        actualAndroidTextInputs=[dict(id='current-input', text='-user-typed', composerFocused=True, nativeFocused=True,
            acceptingText=True, imeVisible=True, stableFocusSamples=3, settledMs=600, start=21, end=21, draft='original unsent draft')],
        actualTrustedInputEvents=events)


def burst_bundle(data, report=None):
    report = burst(None) if report is None else report
    identity = data['report']['commonInstalledIdentity']; raw_report = raw(report)
    frame = dict(apkSha256=identity['apkSha256'], installedApkPath='/data/app/synthetic-control/base.apk',
                 apkDefinitionAudit=copy.deepcopy(data['audit']), commonInstalledIdentity=copy.deepcopy(identity))
    sidecar = dict(schema=1, sourceCommit=SOURCE, sourceTree=identity['sourceTree'], runId=RUN, runAttempt=ATTEMPT,
        sdkManifestSha256=identity['sdkManifestSha256'], sdkReceiptSha256=identity['sdkBuildReceiptSha256'],
        integrationApkSha256=identity['apkSha256'], buildReceiptSha256=data['build_hash'],
        rawReportSha256=C.digest(raw_report), rawReportBytes=len(raw_report),
        runnerSha256=C.digest(data['source_reader'](SOURCE, 'tests/gecko/run_gecko_performance.py')),
        activitySha256=C.digest(data['source_reader'](SOURCE, 'tests/gecko/GeckoPerformanceIntegrationActivity.java')),
        invocationCount=1, invocationRepositoryRoot=str(data['artifact_root']),
        command=['python3', str(data['artifact_root'] / 'tests/gecko/run_gecko_performance.py'),
                                  '--adb', '/synthetic/adb', '--serial', 'synthetic-5554'],
        before=frame, after=copy.deepcopy(frame), runnerExitCode=0, actualInstalledApkRead=True,
        rawReportUnmodified=True, diagnosticOnly=False, actualAndroidExecution=True)
    return dict(report=report, source=SOURCE, run_id=RUN, run_attempt=ATTEMPT, identity=identity,
                sidecar=sidecar, raw_report=raw_report, build=data['build'], build_hash=data['build_hash'],
                sdk_raw=data['sdk_raw'], artifact_root=data['artifact_root'], source_reader=data['source_reader'])


class ContractControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='caret-contract-controls-')
        self.addCleanup(self.temp.cleanup)
        self.data = fixture(Path(self.temp.name))

    def verify(self, data=None):
        data = self.data if data is None else data
        return C.verify_report(**data)

    def verify_burst(self, value=None):
        return C.verify_original_burst(**burst_bundle(self.data, value))

    def staged_evidence(self):
        directory = Path(self.temp.name) / 'staged-artifacts'
        directory.mkdir()
        original = burst_bundle(self.data)
        values = {
            'installed-apk-definition-audit.json': raw(self.data['audit']),
            'sdk-build-receipt.json': self.data['sdk_raw'],
            'caret-apk-build-receipt.json': raw(self.data['build']),
            'gecko-caret-compat-results.json': (json.dumps(self.data['report'], ensure_ascii=False) + '\n').encode('utf-8'),
            'gecko-performance-results.json': original['raw_report'],
            'gecko-performance-build-identity.json': raw(original['sidecar']),
        }
        for name, content in values.items():
            (directory / name).write_bytes(content)
        return directory

    def verify_staged(self, directory, source=SOURCE):
        return C.verify_caret_evidence(directory, source, artifact_root=self.data['artifact_root'],
                                       source_reader=self.data['source_reader'])

    def test_aggregate_validates_both_fixtures_and_hashes_actual_artifact_bytes(self):
        directory = self.staged_evidence()
        result = self.verify_staged(directory)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['sourceCommit'], SOURCE)
        self.assertEqual((result['runId'], result['runAttempt']), (RUN, ATTEMPT))
        self.assertEqual((result['scenarios'], result['checkpoints'], result['checks']), (14, 24, 129))
        self.assertEqual(result['originalBurst']['fullPerformanceChecks'], 155)
        self.assertFalse(result['releaseAcceptance'])
        self.assertEqual(result['artifactSha256'], {name: C.digest((directory / name).read_bytes())
                                                   for name in C.EVIDENCE_FILES})

    def test_aggregate_rejects_every_missing_required_artifact(self):
        directory = self.staged_evidence()
        for name in C.EVIDENCE_FILES:
            with self.subTest(artifact=name):
                path = directory / name; content = path.read_bytes(); path.unlink()
                with self.assertRaises(ValueError): self.verify_staged(directory)
                path.write_bytes(content)

    def test_aggregate_rejects_each_tampered_artifact(self):
        directory = self.staged_evidence()
        mutations = {
            'installed-apk-definition-audit.json': lambda v: v['dex'][0].__setitem__('sha256', 'f' * 64),
            'sdk-build-receipt.json': lambda v: v.__setitem__('runAttempt', '9'),
            'caret-apk-build-receipt.json': lambda v: v.__setitem__('integrationApkSha256', 'f' * 64),
            'gecko-caret-compat-results.json': lambda v: v.__setitem__('status', 'failed'),
            'gecko-performance-results.json': lambda v: v.__setitem__('status', 'failed'),
            'gecko-performance-build-identity.json': lambda v: v.__setitem__('invocationCount', 2),
        }
        for name, mutate in mutations.items():
            with self.subTest(artifact=name):
                path = directory / name; content = path.read_bytes()
                value = json.loads(content); mutate(value); path.write_bytes(raw(value))
                with self.assertRaises(ValueError): self.verify_staged(directory)
                path.write_bytes(content)

    def test_aggregate_rejects_source_conflict_and_conflicting_installed_audit(self):
        directory = self.staged_evidence()
        with self.assertRaises(ValueError): self.verify_staged(directory, 'f' * 40)
        path = directory / 'gecko-performance-build-identity.json'
        sidecar = json.loads(path.read_bytes())
        for frame in ['before', 'after']:
            sidecar[frame]['apkDefinitionAudit']['dex'][0]['sha256'] = 'f' * 64
        path.write_bytes(raw(sidecar))
        with self.assertRaises(ValueError): self.verify_staged(directory)

    def test_original_absolute_invocation_path_is_independent_of_staged_checkout(self):
        data = burst_bundle(self.data)
        data['sidecar']['invocationRepositoryRoot'] = '/actual-ci-runner/selected-checkout'
        data['sidecar']['command'][1] = '/actual-ci-runner/selected-checkout/tests/gecko/run_gecko_performance.py'
        self.assertTrue(C.verify_original_burst(**data)['originalSingleBurst'])
        data['sidecar']['command'][1] = '/actual-ci-runner/selected-checkout/tests/gecko/alternate.py'
        with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_missing_or_invalid_invocation_root_is_rejected(self):
        for root in [None, '', 'relative-root', '/recorded/../other-root']:
            data = burst_bundle(self.data); data['sidecar']['invocationRepositoryRoot'] = root
            with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_gate_module_imports_in_staged_checkout_without_application_directory(self):
        staged = Path(self.temp.name) / 'release-client-checkout'
        destination = staged / 'tools/gecko'; destination.mkdir(parents=True)
        for name in ['check_caret_compat_evidence.py', 'sdk_identity_contract.py']:
            (destination / name).write_bytes((C.ROOT / 'tools/gecko' / name).read_bytes())
        spec = importlib.util.spec_from_file_location('staged_caret_contract', destination / 'check_caret_compat_evidence.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(module.ROOT, staged)
        self.assertFalse((staged / 'app').exists())

    def rejected(self, mutate):
        data = copy.deepcopy(self.data); mutate(data)
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.verify(data)

    def test_complete_synthetic_record_validates_only_contract(self):
        result = self.verify()
        self.assertEqual(result['scenarios'], 14); self.assertEqual(result['checkpoints'], 24)
        self.assertEqual(result['checks'], 129); self.assertFalse(result['releaseAcceptance'])

    def test_tampered_external_receipt_hash(self):
        self.rejected(lambda d: d['report'].__setitem__('sdkReceiptSha256', 'f' * 64))

    def test_wrong_source_run_attempt_and_build_hash(self):
        for key, value in [('sourceCommit', 'b' * 40), ('runId', '999'), ('runAttempt', '2'), ('buildReceiptSha256', 'f' * 64)]:
            with self.subTest(key=key): self.rejected(lambda d, key=key, value=value: d['report'].__setitem__(key, value))

    def test_missing_or_duplicate_or_reordered_case(self):
        for mutate in [lambda d: d['report']['scenarios'].pop(),
                       lambda d: d['report']['scenarios'].__setitem__(1, d['report']['scenarios'][0]),
                       lambda d: d['report']['scenarios'].reverse()]:
            self.rejected(mutate)

    def test_missing_and_invented_expected_checkpoint(self):
        self.rejected(lambda d: d['report']['checkpoints'].pop(10))
        self.rejected(lambda d: d['report']['checkpoints'][0]['expected'].__setitem__('draft', 'invented'))
        self.rejected(lambda d: d['report']['checkpoints'][0]['actual'].__setitem__('start', 9))

    def test_duplicate_missing_and_reordered_raw_event_chunks(self):
        self.rejected(lambda d: d['report']['trustedEventChunks'].insert(1, d['report']['trustedEventChunks'][0]))
        self.rejected(lambda d: d['report']['trustedEventChunks'].pop(1))
        self.rejected(lambda d: d['report']['trustedEventChunks'].reverse())

    def test_untrusted_duplicate_index_and_nonfinite_event(self):
        for key, value in [('trusted', False), ('index', 8), ('time', float('nan'))]:
            with self.subTest(key=key):
                self.rejected(lambda d, key=key, value=value: d['report']['trustedEventChunks'][0]['events'][0].__setitem__(key, value))

    def test_forged_vectors_and_snapshot_counts(self):
        self.rejected(lambda d: d['report']['eventVectors']['rapid-taps']['characterKeys'].append('Q'))
        self.rejected(lambda d: d['report']['scenarios'][0]['actual'].__setitem__('keyCount', 99))
        self.rejected(lambda d: d['report']['scenarios'][0]['actual'].__setitem__('allTrusted', False))

    def test_extra_trusted_character_key_even_when_claimed_in_vector(self):
        def mutate(d):
            item = d['report']['actualTrustedEvents']['rapid-taps'][1]; item['key'] = 'W'
            d['report']['eventVectors']['rapid-taps'] = C.vectors(d['report']['actualTrustedEvents']['rapid-taps'])
        self.rejected(mutate)

    def test_inconsistent_ic_thread_connection_and_rejected_api(self):
        for key, value in [('thread', 999), ('connectionIdentity', 999), ('accepted', False), ('arguments', ['wrong', 1])]:
            with self.subTest(key=key):
                self.rejected(lambda d, key=key, value=value: d['report']['actualInputConnectionCalls'][5].__setitem__(key, value))

    def test_skipped_duplicated_and_wrong_android_commands(self):
        for key, value in [('completed', False), ('invocationCount', 2), ('commandIndex', 9)]:
            with self.subTest(key=key):
                self.rejected(lambda d, key=key, value=value: d['report']['actualAndroidActions'][0]['executions'][0].__setitem__(key, value))
        self.rejected(lambda d: d['report']['actualAndroidActions'][1]['commands'][2].__setitem__('text', 'QQ'))

    def test_missing_real_clipboard_and_wrong_single_character_payload(self):
        self.rejected(lambda d: d['report']['actualClipboardCalls'].pop())
        self.rejected(lambda d: d['report']['actualClipboardCalls'][1].__setitem__('text', 'QQ'))

    def test_utf16_unicode_checkpoint_cannot_use_codepoint_offset(self):
        self.rejected(lambda d: d['report']['scenarios'][5]['checkpoints'][2]['expected'].__setitem__('start', 17))
        self.assertEqual(C.utf16_length('clipboard pasteQ😀'), 18)

    def test_missing_composition_and_backward_selection(self):
        self.rejected(lambda d: d['report']['scenarios'][7]['actual'].__setitem__('compositionEndCount', 0))
        self.rejected(lambda d: d['report']['scenarios'][9]['checkpoints'][0]['actual'].__setitem__('direction', 'forward'))

    def test_noop_progress_rejected_input_and_preserved_cookie(self):
        self.rejected(lambda d: d['report']['scenarios'][13]['checkpoints'][0]['actual'].__setitem__('inputCount', 1))
        self.rejected(lambda d: d['report']['scenarios'][10]['actual'].__setitem__('inputCount', 1))
        self.rejected(lambda d: d['report']['scenarios'][0]['actual'].__setitem__('cookie', 'changed'))
        self.rejected(lambda d: d['report']['actualTrustedEvents']['rejected-input'][2].__setitem__('prevented', False))

    def test_diagnostic_observer_skipped_and_overclaimed_report(self):
        for key, value in [('diagnosticOnly', True), ('mode', 'diagnostic'), ('sdkObserverEnabled', True),
                           ('physicalPhoneAcceptance', True), ('releaseAcceptance', True), ('skipped', True)]:
            with self.subTest(key=key): self.rejected(lambda d, key=key, value=value: d['report'].__setitem__(key, value))

    def test_sdk_requires_source_compile_without_asm_or_extra_changes(self):
        self.rejected(lambda d: d['sdk'].__setitem__('asmTransformApplied', True))
        self.rejected(lambda d: d['sdk'].__setitem__('sourceCompileApplied', False))
        self.rejected(lambda d: d['sdk'].__setitem__('sdkClassTransformApplied', False))
        self.rejected(lambda d: d['sdk'].__setitem__('patchMethod', 'asm-bytecode-transform'))
        self.rejected(lambda d: d['sdk']['changedClassEntries'].append('org/mozilla/geckoview/Other.class'))
        self.rejected(lambda d: d['sdk'].__setitem__('allNativeAndResourceEntriesUnchanged', False))

    def test_prototype_or_uncommitted_recipe_cannot_certify_normal_execution(self):
        self.rejected(lambda d: d['sdk'].__setitem__('prototypeOnly', True))
        self.rejected(lambda d: d['sdk'].__setitem__('recipeInputsCommitted', False))

    def test_rehashed_noncanonical_adapter_body_still_rejected(self):
        data = copy.deepcopy(self.data)
        data['sdk']['compiler'] = {'version': 'invented-adapter', 'args': ['javac']}
        data['sdk_raw'] = raw(data['sdk']); data['sdk_hash'] = C.digest(data['sdk_raw'])
        data['build']['sdkReceiptSha256'] = data['sdk_hash']
        with self.assertRaisesRegex(ValueError, 'runtime receipt fields differ'):
            self.verify(data)

    def test_rehashed_asm_claim_conflicts_with_selected_source(self):
        data = copy.deepcopy(self.data)
        data['sdk']['asmTransformApplied'] = True
        data['sdk_raw'] = raw(data['sdk']); data['sdk_hash'] = C.digest(data['sdk_raw'])
        data['build']['sdkReceiptSha256'] = data['sdk_hash']
        with self.assertRaisesRegex(ValueError, 'runtime receipt differs from selected source: asmTransformApplied'):
            self.verify(data)

    def test_missing_selected_source_manifest_has_no_prototype_fallback(self):
        data = copy.deepcopy(self.data)
        def unavailable(commit, path):
            raise FileNotFoundError('no committed manifest at selected source')
        data['source_reader'] = unavailable
        with self.assertRaises(FileNotFoundError):
            self.verify(data)

    def test_sdk_manifest_digest_bound_through_every_identity(self):
        for section in ['sdk', 'build', 'audit']:
            with self.subTest(section=section):
                self.rejected(lambda d, section=section: d[section].__setitem__('sdkManifestSha256', 'f' * 64))
        for section in ['embeddedBuildIdentity', 'buildIdentity', 'installedBuild']:
            with self.subTest(section=section):
                self.rejected(lambda d, section=section: d['report'][section].__setitem__('sdkManifestSha256', 'f' * 64))
        manifest = Path(self.data['artifact_root']) / C._sdk.DERIVED_MANIFEST
        manifest.write_text('{"changed":true}\n')
        with self.assertRaises(ValueError): self.verify()

    def test_actual_source_or_recipe_artifact_tampering(self):
        (Path(self.data['artifact_root']) / self.data['sdk']['sourceRecipe']['path']).write_text('changed compiler recipe\n')
        with self.assertRaises(ValueError): self.verify()

    def test_dex_definition_observer_and_rawstring_claim_rejected(self):
        def actual_observer(d):
            d['audit']['dex'][0]['classDefinitions'].append('Lorg/mozilla/geckoview/PocketGeckoEditableTrace;')
            d['audit']['dex'][0]['classDefinitionCount'] = d['audit']['definitionCount'] = 4
        self.rejected(actual_observer)
        self.rejected(lambda d: d['audit']['dex'][0].__setitem__('classDefinitions', 'raw string scan'))
        self.rejected(lambda d: d['audit']['dex'][0]['classDefinitions'].append('Lorg/mozilla/geckoview/GeckoEditable;'))

    def test_installed_embedded_source_and_apk_identity_tampering(self):
        self.rejected(lambda d: d['audit']['embeddedBuildIdentity'].__setitem__('sourceCommit', 'b' * 40))
        self.rejected(lambda d: d['report']['installedBuild'].__setitem__('apkSha256', 'f' * 64))

    def test_common_installed_identity_cannot_disagree_with_fixture(self):
        for key, value in [('apkSha256', 'f' * 64), ('sourceCommit', 'c' * 40), ('runId', '999'),
                           ('sdkAarSha256', 'f' * 64), ('sdkClassesJarSha256', 'f' * 64),
                           ('sdkGeckoEditableClassSha256', 'f' * 64), ('sdkManifestSha256', 'f' * 64),
                           ('sdkBuildReceiptSha256', 'f' * 64), ('sdkBuildSource', 'c' * 40)]:
            with self.subTest(key=key):
                self.rejected(lambda d, key=key, value=value: d['report']['commonInstalledIdentity'].__setitem__(key, value))
        self.rejected(lambda d: d['report']['commonInstalledIdentity']['sdkBuildIdentity'].__setitem__('sourceTree', 'c' * 40))
        self.rejected(lambda d: d['report'].pop('commonInstalledIdentity'))

    def test_common_run_identity_is_required_in_actual_nested_sdk_asset(self):
        self.assertNotIn('runId', self.data['report']['commonInstalledIdentity'])
        self.assertNotIn('runAttempt', self.data['report']['commonInstalledIdentity'])
        self.verify()
        for key in ['runId', 'runAttempt']:
            with self.subTest(key=key):
                self.rejected(lambda d, key=key: d['report']['commonInstalledIdentity']['sdkBuildIdentity'].__setitem__(key, '999'))
                self.rejected(lambda d, key=key: d['report']['commonInstalledIdentity']['sdkBuildIdentity'].pop(key))

    def test_shared_common_helper_cannot_substitute_for_caret_helper(self):
        def mutate(d):
            definitions = d['audit']['dex'][0]['classDefinitions']
            definitions[definitions.index('Llocal/pocketchat/CaretCompatibilityBuildIdentity;')] = 'Llocal/pocketchat/IntegrationBuildIdentity;'
            d['audit']['caretHelperDefinitionCount'] = 0
        self.rejected(mutate)

    def test_selectionchange_is_compatibility_only(self):
        events = copy.deepcopy(self.data['report']['actualTrustedEvents']['rapid-taps'])
        item = dict(events[-1], index=len(events), time=events[-1]['time'] + 1, type='selectionchange', key='')
        events.append(item)
        report = copy.deepcopy(self.data['report'])
        report['actualTrustedEvents']['rapid-taps'] = events
        report['trustedEventChunks'] = [row for row in report['trustedEventChunks'] if row['id'] != 'rapid-taps']
        report['trustedEventChunks'] = [dict(id='rapid-taps', offset=i, events=events[i:i + 4]) for i in range(0, len(events), 4)] + report['trustedEventChunks']
        report['eventVectors']['rapid-taps'] = C.vectors(events)
        C.verify_events(report)
        normal = burst(self.data['report']['buildIdentity'])
        normal['actualTrustedInputEvents'].append(item)
        with self.assertRaises(ValueError):
            self.verify_burst(normal)

    def test_duplicate_json_fields_and_nonfinite_json_rejected(self):
        path = Path(self.temp.name) / 'invalid.json'
        for content in ['{"schema":1,"schema":1}', '{"time":NaN}', '{"truncated":']:
            path.write_text(content)
            with self.assertRaises(ValueError): C.read_json(path)

    def test_original_normal_single_burst_contract(self):
        value = burst(self.data['report']['buildIdentity'])
        result = self.verify_burst(value)
        self.assertEqual(result['orderedTrustedKeys'], 11)

    def test_original_burst_matches_shared_installed_identity(self):
        shared = self.data['report']['commonInstalledIdentity']
        value = burst(shared)
        self.verify_burst(value)
        data = burst_bundle(self.data, value); data['identity'] = self.data['report']['buildIdentity']
        with self.assertRaises(ValueError):
            C.verify_original_burst(**data)

    def test_original_raw_report_remains_without_unproduced_build_metadata(self):
        data = burst_bundle(self.data)
        self.assertNotIn('runId', data['report']); self.assertNotIn('runAttempt', data['report'])
        self.assertNotIn('buildIdentity', data['report'])
        original = data['raw_report']
        C.verify_original_burst(**data)
        self.assertEqual(data['raw_report'], original)
        self.assertEqual(data['sidecar']['rawReportSha256'], C.digest(original))

    def test_original_sidecar_rejects_changed_raw_report_bytes_and_claims(self):
        for mutate in [lambda d: d.__setitem__('raw_report', d['raw_report'] + b' '),
                       lambda d: d['sidecar'].__setitem__('rawReportSha256', 'f' * 64),
                       lambda d: d['sidecar'].__setitem__('rawReportBytes', 1),
                       lambda d: d['sidecar'].__setitem__('rawReportUnmodified', False)]:
            data = burst_bundle(self.data); mutate(data)
            with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_sidecar_rejects_foreign_build_source_run_and_sdk(self):
        for key, value in [('sourceCommit', 'c' * 40), ('sourceTree', 'c' * 40), ('runId', '999'),
                           ('runAttempt', '999'), ('integrationApkSha256', 'f' * 64),
                           ('sdkManifestSha256', 'f' * 64), ('sdkReceiptSha256', 'f' * 64),
                           ('buildReceiptSha256', 'f' * 64)]:
            with self.subTest(key=key):
                data = burst_bundle(self.data); data['sidecar'][key] = value
                with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_sidecar_requires_one_successful_unmodified_normal_run(self):
        for key, value in [('invocationCount', 0), ('invocationCount', 2), ('invocationCount', True),
                           ('runnerExitCode', 1), ('actualInstalledApkRead', False),
                           ('actualAndroidExecution', False), ('diagnosticOnly', True)]:
            with self.subTest(key=key, value=value):
                data = burst_bundle(self.data); data['sidecar'][key] = value
                with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_sidecar_rejects_changed_installed_apk_audit_and_metadata(self):
        for mutate in [lambda s: s['after'].__setitem__('apkSha256', 'f' * 64),
                       lambda s: s['after'].__setitem__('installedApkPath', '/data/app/other/base.apk'),
                       lambda s: s['after']['apkDefinitionAudit'].__setitem__('sdkManifestSha256', 'f' * 64),
                       lambda s: s['after']['commonInstalledIdentity'].__setitem__('sdkAarSha256', 'f' * 64),
                       lambda s: s['before']['commonInstalledIdentity']['sdkBuildIdentity'].__setitem__('runAttempt', '999')]:
            data = burst_bundle(self.data); mutate(data['sidecar'])
            with self.assertRaises(ValueError): C.verify_original_burst(**data)
        data = burst_bundle(self.data)
        for frame in ['before', 'after']:
            audit = data['sidecar'][frame]['apkDefinitionAudit']
            audit['dex'][0]['classDefinitions'].append('Lorg/mozilla/geckoview/PocketGeckoEditableTrace;')
            audit['dex'][0]['classDefinitionCount'] = audit['definitionCount'] = 4
        with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_sidecar_rejects_modified_protected_sources_and_extra_arguments(self):
        for key in ['runnerSha256', 'activitySha256']:
            data = burst_bundle(self.data); data['sidecar'][key] = 'f' * 64
            with self.assertRaises(ValueError): C.verify_original_burst(**data)
        for mutate in [lambda s: s['command'].append('--input-diagnostics'),
                       lambda s: s['command'].__setitem__(1, 'tests/gecko/alternate.py'),
                       lambda s: s['command'].__setitem__(2, '--paced-input')]:
            data = burst_bundle(self.data); mutate(data['sidecar'])
            with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_raw_report_without_sidecar_cannot_be_promoted(self):
        data = burst_bundle(self.data); data['sidecar'] = None
        with self.assertRaises(ValueError): C.verify_original_burst(**data)

    def test_original_burst_rejects_pacing_observers_untrusted_and_reordered_keys(self):
        for mutate in [lambda b: b.__setitem__('diagnosticOnly', True),
                       lambda b: b['actualAndroidTextInputs'].append(copy.deepcopy(b['actualAndroidTextInputs'][0])),
                       lambda b: b['actualTrustedInputEvents'][0].__setitem__('trusted', False),
                       lambda b: b['actualTrustedInputEvents'][0].__setitem__('key', 'u'),
                       lambda b: b.__setitem__('actualNativeInputTrace', [{'observer': True}]),
                       lambda b: b.__setitem__('sdkInputWriterDiagnosticsEnabled', True),
                       lambda b: b.__setitem__('actualSdkInputClockTrace', [{'observer': True}]),
                       lambda b: b.__setitem__('sdkInputWriterLogCapture', {'captured': True}),
                       lambda b: b.__setitem__('runAttempt', '9')]:
            value = burst(self.data['report']['buildIdentity']); mutate(value)
            with self.assertRaises(ValueError):
                self.verify_burst(value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
