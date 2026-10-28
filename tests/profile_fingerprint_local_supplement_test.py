"""Fail-closed reader controls; synthetic reports are not Android executions."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / 'tests/gecko/FingerprintFollowupIntegrationActivity.java'
RUNNER = ROOT / 'tests/gecko/run_fingerprint_followups.py'
spec = importlib.util.spec_from_file_location('fingerprint_local_reader', RUNNER)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def inverse_activity(source):
    source, count = re.subn(r'  static final String\[\] LOCAL_COMPARISON_CHECK_IDS=\{[^{}]*\};\n', '', source)
    assert count == 1
    for line in ('  final JSONArray localComparisonChecks=new JSONArray();\n',
                 '  final JSONObject localComparisonEvidence=new JSONObject();\n',
                 '    localContextBaselineChecks();\n',
                 '    localCrossOriginBaselineChecks(report);\n',
                 '    if(error==null&&localComparisonChecks.length()!=LOCAL_COMPARISON_CHECK_IDS.length)error=new IOException("Local comparison supplement incomplete");\n'):
        assert source.count(line) == 1
        source = source.replace(line, '')
    for start, end in [('  void localCheck(', '  void event('),
                       ('  JSONObject reference(JSONObject pins,', '  void faultMode('),
                       ('  void localCrossOriginBaselineChecks(', '  JSONObject auditSnapshot(')]:
        assert source.count(start) == source.count(end) == 1
        first, last = source.index(start), source.index(end)
        assert first < last
        source = source[:first] + source[last:]
    suffix = '.put("localComparisonChecks",copyArray(localComparisonChecks)).put("localComparisonCheckCount",localComparisonChecks.length()).put("localComparisonExpectedCount",LOCAL_COMPARISON_CHECK_IDS.length).put("localComparisonEvidence",localComparisonEvidence)'
    assert source.count(suffix) == 1
    return source.replace(suffix, '')


def synthetic_native():
    owner = '12345678-1234-4234-8234-123456789abc'
    semantic, actual = 'https://chatgpt.com', reader.ORIGIN + '/chat'

    def pin(source, origin, top):
        return dict(observation=dict(source=source, sourceOrigin=origin, topLevelOrigin=top,
                                     environmentId=owner, environmentGeneration=3),
                    protectionVerified=False, leakVerdict=False)

    contexts, raw = {}, dict(schema=1, requested=True)
    for name, source in [('worker', 'dedicated-worker'), ('frame', 'same-origin-srcdoc')]:
        raw[name] = dict(source=source, probes=dict(canvas=dict(state='available')))
        contexts[name] = dict(source=source, eligible=True, admissionIssue='', captureIssue='',
                              reference=pin(source, semantic, semantic))
    detector = reader.ORIGIN + reader.BASE + 'document?nonce=' + 'a' * 32 + '&frame=1'
    frame = dict(origin=reader.FRAME_ORIGIN, apiChecks=dict(probes=dict(canvas=dict(state='available'))))
    local = dict(actualSourceUrl=actual, semanticSourceAlias=semantic + '/c/local',
                 observationMetadata=dict(environmentId=owner, environmentGeneration=3, sourceOrigin=semantic),
                 mainReference=pin('page-main-world', semantic, semantic), contexts=contexts, apiContexts=raw,
                 mainApiChecks=dict(probes=dict(canvas=dict(state='available'))),
                 migration=dict(legacyMigrated=True, canonicalEmptyAuthoritative=True, storePayloadRestored=True),
                 persistenceRefusal=dict(pinRollback=True, clearRollback=True, saveCalls=2,
                     payloadUnchanged=True, ciphertextUnchanged=True,
                     payloadBeforeSha256='b' * 64, payloadAfterSha256='b' * 64,
                     ciphertextBeforeSha256='c' * 64, ciphertextAfterSha256='c' * 64),
                 pairModeCoordinatorAcceptance=False, physicalPhoneAcceptance=False,
                 fullFingerprintProtectionAcceptance=False)
    cross = dict(actualDetectorUrl=detector, actualFrameOrigin=reader.FRAME_ORIGIN, eligible=True,
                 admissionIssue='', captureIssue='', restoredCaptureIssue='',
                 reference=pin('controlled-cross-origin-iframe', reader.FRAME_ORIGIN, reader.ORIGIN),
                 changedEndpoint=dict(configurationSaved=True, pinRefused=True, liveDocumentStillCurrent=True,
                                      selectedOriginDiffers=True, referencesUnchanged=True),
                 physicalPhoneAcceptance=False, fullFingerprintProtectionAcceptance=False)
    return dict(actualSourceChat=actual, semanticSourceAlias=semantic + '/c/local', origin=reader.ORIGIN,
                frameOrigin=reader.FRAME_ORIGIN, checks=[{'pass': True} for _ in range(99)],
                localComparisonExpectedCount=32, localComparisonCheckCount=32,
                localComparisonChecks=[dict(id=name, **{'pass': True}) for name in reader.local_comparison_check_ids()],
                localComparisonEvidence=dict(local=local, cross=cross),
                cases=[dict(case='controlled-cross-origin-frame', actualDetectorUrl=detector,
                            report=dict(requestIdentity=dict(browser=dict(crossOriginFrame=frame))))])


class FingerprintLocalSupplementTest(unittest.TestCase):
    def test_original_native_activity_and_two_receivers_are_preserved(self):
        original = inverse_activity(JAVA.read_text())
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),
                         '40eb7acd2ff1f1ed4eb528077c0005fd14a917c5d5f28074c093182e74403906')
        source = RUNNER.read_text()
        functions = {node.name: ast.get_source_segment(source, node) for node in ast.parse(source).body
                     if isinstance(node, ast.FunctionDef)}
        for name, digest in [('reconcile', 'fb377551e9953e51e28aba693a3abe07be931c2d2c278c7d3a7fd6c7c42d4624'),
                             ('reconcile_coverage', 'c0e8cae74e7bcfc7aec8280acc9485c5f4a62db2c42488ebcbfa492f9965e979')]:
            self.assertEqual(hashlib.sha256(functions[name].encode()).hexdigest(), digest)
        self.assertEqual(reader.CASES, ['standard-source-control', 'manual-api-checks',
            'credential-and-redirect-controls', 'top-level-request-identity',
            'controlled-diagnostic-page-recovery', 'nonempty-draft-refusal',
            'late-registration-cancellation', 'synthetic-epoch-preflight-invalidation',
            'browser-policy-preflight-invalidation', 'strict-native-receipt-loss-control',
            'bounded-context-api-checks', 'pinned-deep-reference-lifecycle',
            'manual-service-capability-controls', 'controlled-cross-origin-frame'])

    def test_complete_supplement_and_unavailable_contexts_do_not_attest_protection(self):
        value = synthetic_native()
        result = reader.reconcile_local_comparison(value)
        self.assertEqual(result['checks'], 32)
        self.assertFalse(result['physicalPhoneAcceptance'])
        self.assertFalse(result['pairActualModeCoordinatorAcceptance'])
        self.assertFalse(result['fullFingerprintProtectionAcceptance'])
        unavailable = copy.deepcopy(value)
        raw = unavailable['localComparisonEvidence']['local']['apiContexts']['worker']
        raw.update(source='unavailable', probes=dict(canvas=dict(state='uncovered')))
        unavailable['localComparisonEvidence']['local']['contexts']['worker'].update(
            source='unavailable', eligible=False, admissionIssue='not covered', captureIssue='not covered', reference={})
        self.assertFalse(reader.reconcile_local_comparison(unavailable)['contexts']['worker']['referenceCaptured'])

        mutants = []
        def mutate(label, action):
            item = copy.deepcopy(value); action(item); mutants.append((label, item))
        mutate('missing supplement', lambda n: n.pop('localComparisonChecks'))
        mutate('short supplement', lambda n: n['localComparisonChecks'].pop())
        mutate('reordered supplement', lambda n: n['localComparisonChecks'].reverse())
        mutate('invented id', lambda n: n['localComparisonChecks'][0].update(id='invented'))
        mutate('false check', lambda n: n['localComparisonChecks'][0].update({'pass': False}))
        mutate('truthy integer check', lambda n: n['localComparisonChecks'][0].update({'pass': 1}))
        mutate('boolean count', lambda n: n.update(localComparisonExpectedCount=True))
        mutate('wrong completed count', lambda n: n.update(localComparisonCheckCount=31))
        mutate('original check removed', lambda n: n['checks'].pop())
        mutate('original check failed', lambda n: n['checks'][0].update({'pass': False}))
        mutate('missing local evidence', lambda n: n['localComparisonEvidence'].pop('local'))
        mutate('actual source relabelled', lambda n: n['localComparisonEvidence']['local'].update(actualSourceUrl='https://foreign.example'))
        mutate('foreign saved owner', lambda n: n['localComparisonEvidence']['local']['mainReference']['observation'].update(environmentId='foreign'))
        mutate('capturable context silently unavailable', lambda n: n['localComparisonEvidence']['local']['contexts']['worker'].update(eligible=False))
        mutate('meaningful context missing reference', lambda n: n['localComparisonEvidence']['local']['contexts']['frame'].update(reference={}))
        mutate('cross-context equality invented', lambda n: n['localComparisonEvidence']['local']['contexts']['worker']['reference']['observation'].update(source='page-main-world'))
        mutate('migration not restored', lambda n: n['localComparisonEvidence']['local']['migration'].update(storePayloadRestored=False))
        mutate('cleared baseline resurrected', lambda n: n['localComparisonEvidence']['local']['migration'].update(canonicalEmptyAuthoritative=False))
        mutate('pin rollback absent', lambda n: n['localComparisonEvidence']['local']['persistenceRefusal'].update(pinRollback=False))
        mutate('no actual save attempt', lambda n: n['localComparisonEvidence']['local']['persistenceRefusal'].update(saveCalls=0))
        mutate('ciphertext changed', lambda n: n['localComparisonEvidence']['local']['persistenceRefusal'].update(ciphertextAfterSha256='d'*64))
        mutate('mode coordinator falsely accepted', lambda n: n['localComparisonEvidence']['local'].update(pairModeCoordinatorAcceptance=True))
        mutate('phone falsely accepted', lambda n: n['localComparisonEvidence']['local'].update(physicalPhoneAcceptance=True))
        mutate('cross detector missing', lambda n: n['localComparisonEvidence']['cross'].update(actualDetectorUrl=''))
        mutate('cross origin relabelled', lambda n: n['localComparisonEvidence']['cross']['reference']['observation'].update(sourceOrigin=reader.ORIGIN))
        mutate('frame config change accepted', lambda n: n['localComparisonEvidence']['cross']['changedEndpoint'].update(pinRefused=False))
        for name, item in mutants:
            with self.subTest(name=name), self.assertRaises(ValueError):
                reader.reconcile_local_comparison(item)
        source = JAVA.read_text()
        for changed in ('', source + source,
                        source.replace('"local.main.pin"', '"local.main.current-deep"', 1),
                        source.replace('"local.main.pin",', '', 1)):
            with self.assertRaises(ValueError):reader.local_comparison_check_ids(changed)
        target = ROOT / 'work/compile-setup/local-supplement-reader-controls.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(status='passed-host-reader-controls', positiveControls=2,
            negativeControls=len(mutants)+4, exactSupplementChecks=32, originalNativeChecksPreserved=99,
            originalCasesPreserved=14, actualAndroidExecution=False, actualGeckoExecution=False,
            physicalPhoneAcceptance=False, fullFingerprintProtectionAcceptance=False,
            scope='Synthetic Python reader controls and byte-exact inverse of original Java activity; new Java native actions still require the current actual Android CI invocation.'), indent=2)+'\n')


if __name__ == '__main__':unittest.main()
