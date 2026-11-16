"""Execute the current publication readers against controlled native receipts.

The source Git objects, archived driver bytes, XML parsers, workflow Python,
publisher gates and staging writes are real. The Android command records are
declared host fixtures, never replacement Android acceptance evidence. Only
the verifier's repository location points at a disposable real Git repository.
"""
import ast
import copy
from contextlib import contextmanager, ExitStack
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools'), str(ROOT/'tools/gecko'), str(ROOT/'tests')]
import profile_workspace_density_v3_test as fixtures

FULL = ROOT/'.github/workflows/browser-2_1-acceptance.yml'
PUBLISH = ROOT/'.github/workflows/publish-gecko-release.yml'
PUBLISHER = ROOT/'tools/publish-gecko-release.py'
FULL_STEP = 'Require native browser workspace roundtrip at the actual display density'
PUBLISH_STEP = 'Verify original regressions, derived SDK provenance and signed public APK'
PACKAGE = 'local.pocketchat.test'


def one(values, label):
    values = list(values)
    if len(values) != 1:
        raise AssertionError('Exactly one current '+label+' is required')
    return values[0]


def calls(node, name):
    return [child for child in ast.walk(node) if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name) and child.func.id == name]


def execute(nodes, namespace, filename):
    module = nodes if isinstance(nodes, ast.Module) else ast.Module(body=copy.deepcopy(nodes), type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(filename), 'exec'), namespace)


def step_python(workflow, job_name, step_name):
    job = workflow['jobs'][job_name]
    if job.get('continue-on-error', False) is not False:
        raise AssertionError('Workspace qualification job cannot ignore failures')
    step = one((row for row in job['steps'] if row.get('name') == step_name), step_name)
    if 'if' in step or step.get('continue-on-error', False) is not False:
        raise AssertionError('Workspace qualification step must execute unconditionally')
    run = step['run']
    if step.get('shell', 'bash') != 'bash':
        raise AssertionError('Workspace qualification requires its actual bash boundary')
    match = re.fullmatch(r"set -euo pipefail\npython3 - <<'(PY(?:CODE)?)'\n([\s\S]*)\n\1\n?", run)
    if not match:
        raise AssertionError('A failing shell and the actual Python block are required')
    return ast.parse(match.group(2))


@contextmanager
def working_directory(directory):
    previous, previous_path = Path.cwd(), list(sys.path)
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(previous)
        sys.path[:] = previous_path


def reseal_xml(record, phase, xml):
    """Keep all original byte joins consistent so semantic negatives reach XML checks."""
    native = record['nativeUi'][phase]
    raw = xml.encode('utf-8'); digest = hashlib.sha256(raw).hexdigest()
    native.update(rawXml=xml, xmlBytes=len(raw), xmlSha256=digest)
    attempt = one((row for row in record['hierarchyCapture']['attempts']
                   if row['index'] == native['captureIndex']), 'owned capture attempt')
    attempt.update(xmlBytes=len(raw), xmlSha256=digest)
    attempt['commands'][-1]['stdout'] = dict(bytes=len(raw), sha256=digest,
        text=raw[:8192].decode('utf-8', 'replace'), truncated=len(raw) > 8192)


class WorkspaceRoundtripPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='workspace-publication-source-')
        cls.repository = Path(cls.temporary.name)
        cls.source, cls.tree = fixtures.create_source_repository(cls.repository)
        cls.record = fixtures.controlled_roundtrip(cls.repository, cls.source, cls.tree, dpi=420)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.temporary_case = tempfile.TemporaryDirectory(prefix='workspace-publication-input-')
        self.addCleanup(self.temporary_case.cleanup)
        self.base = Path(self.temporary_case.name)
        self.evidence = self.base/'work/gecko-integration/public'
        self.evidence.mkdir(parents=True)
        (self.base/'app').mkdir()
        (self.base/'app/build.gradle').write_text("versionName '2.1.6'\nversionCode 108\n")
        self.device = dict(status='passed', actualAndroidExecution=True, releaseMode=True,
                           sourceCommit=self.source, productionNavigation=copy.deepcopy(self.record))
        driver=self.record['hierarchyCapture']['acquisitionDriver']
        self.device['eventTransport']={'buildIdentity':dict(sourceTree=self.tree,
            sdkBuildIdentity={key:driver[key] for key in ('runId','runAttempt')})}
        self.write(self.device)

    def write(self, device):
        # Deliberately valid noncanonical formatting. The original evidence
        # bytes must survive staging; equivalent re-serialization is rejected.
        raw = (json.dumps(device, ensure_ascii=False, separators=(',', ':'))+'\n\n').encode()
        (self.evidence/'device-results.json').write_bytes(raw)
        return raw

    @contextmanager
    def real_reader(self):
        with ExitStack() as stack:
            observed = []
            for name in ('gecko.workspace_navigation_contract_v3', 'tools.gecko.workspace_navigation_contract_v3'):
                module = importlib.import_module(name)
                original = module.verify_workspace_roundtrip
                def at_repository(record, package, *, source=None, root=None, original=original):
                    self.assertIsNone(root)
                    self.assertEqual(source, self.source)
                    observed.append((package, source))
                    return original(record, package, source=source, root=self.repository)
                stack.enter_context(patch.object(module, 'verify_workspace_roundtrip', side_effect=at_repository))
            yield observed

    def full_gate(self, workflow=None):
        tree = step_python(workflow or yaml.safe_load(FULL.read_text()), 'verify', FULL_STEP)
        one(calls(tree, 'verify_workspace_roundtrip'), 'full native workspace reader')
        with self.real_reader() as observed, patch.dict(os.environ, GITHUB_SHA=self.source), working_directory(self.base):
            execute(tree, {}, FULL)
        self.assertEqual(observed, [(PACKAGE, self.source)])

    def publisher_gate(self, tree=None):
        tree = tree or ast.parse(PUBLISHER.read_text())
        report_at = one((index for index, node in enumerate(tree.body) if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == 'report' for target in node.targets)),
                        'original publisher report read')
        gate = one((node for node in tree.body if isinstance(node, ast.If)
                    and calls(node, 'verify_workspace_roundtrip')), 'publisher native workspace reader')
        self.assertEqual(ast.unparse(gate.test), 'version_code >= 108')
        namespace = dict(args=SimpleNamespace(evidence=self.evidence, source=self.source), version_code=108,
                         production_navigation=None, json=json, hashlib=hashlib)
        with self.real_reader() as observed:
            execute(tree.body[report_at:report_at+3], namespace, PUBLISHER)
            execute([gate], namespace, PUBLISHER)
        self.assertEqual(observed, [(PACKAGE, self.source)])
        raw = (self.evidence/'device-results.json').read_bytes()
        self.assertEqual(namespace['production_navigation']['deviceReportSha256'], hashlib.sha256(raw).hexdigest())
        manifest_gate = one((node for node in tree.body if isinstance(node, ast.If)
                             and ast.unparse(node.test) == 'production_navigation is not None'),
                            'verified navigation manifest binding')
        namespace['manifest'] = {}
        execute([manifest_gate], namespace, PUBLISHER)
        self.assertEqual(namespace['manifest']['productionNavigationRegression'], namespace['production_navigation'])
        return namespace

    def publish_gate(self, workflow=None, manifest=None):
        tree = step_python(workflow or yaml.safe_load(PUBLISH.read_text()), 'publish', PUBLISH_STEP)
        report_at = one((index for index, node in enumerate(tree.body) if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == 'report' for target in node.targets)),
                        'original published report read')
        gate = one((node for node in tree.body if isinstance(node, ast.If)
                    and calls(node, 'verify_workspace_roundtrip')), 'published native workspace reader')
        self.assertEqual(ast.unparse(gate.test), "m['versionCode'] >= 108")
        if manifest is None:
            summary = self.publisher_gate()['production_navigation']
            manifest = dict(versionCode=108, sourceCommit=self.source, productionNavigationRegression=summary)
        namespace = dict(m=manifest, pathlib=importlib.import_module('pathlib'), json=json, hashlib=hashlib)
        with self.real_reader() as observed, working_directory(self.evidence):
            execute(tree.body[report_at:report_at+2], namespace, PUBLISH)
            execute([gate], namespace, PUBLISH)
        self.assertEqual(observed, [(PACKAGE, self.source)])

    def test_all_three_real_readers_accept_bound_originals_and_stage_exact_bytes(self):
        self.full_gate(); namespace = self.publisher_gate(); self.publish_gate()
        summary = namespace['production_navigation']['roundtrip']
        self.assertEqual((summary['densityDpi'], summary['minimumActionTouchDp'],
                          summary['minimumActionTouchPx'], summary['actualAndroidTaps']), (420, 48, 126, 3))
        tree = ast.parse(PUBLISHER.read_text())
        stage = self.base/'signed-public'; stage.mkdir()
        namespace.update(stage=stage)
        write = one((node for node in tree.body if isinstance(node, ast.If)
                     and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                             and child.func.attr == 'write_bytes' and child.args
                             and isinstance(child.args[0], ast.Name) and child.args[0].id == 'navigation_report_raw'
                             for child in ast.walk(node))), 'original device report staging')
        execute([write], namespace, PUBLISHER)
        self.assertEqual((stage/'device-results.json').read_bytes(), (self.evidence/'device-results.json').read_bytes())
        stale = dict(versionCode=108, sourceCommit=self.source,
                     productionNavigationRegression=dict(namespace['production_navigation'], deviceReportSha256='0'*64))
        with self.assertRaises(AssertionError): self.publish_gate(manifest=stale)

    def test_each_consumer_rejects_density_xml_input_menu_and_return_mutations(self):
        def density(record):
            record['densityEvidence']['effectiveDpi'] = 480
        def fabricated_density(record):
            module = importlib.import_module('gecko.workspace_navigation_contract_v3')
            record['densityEvidence'] = module.display_density_evidence('Physical density: 480\n')
        def raw_xml(record):
            record['nativeUi']['initial'].pop('rawXml')
        def tap(record):
            record['inputs'][1]['point'] = [-1, -1]
        def menu(record):
            tree = ET.fromstring(record['nativeUi']['menu']['rawXml'])
            node = one((node for node in tree.iter('node') if node.get('text') == '管理全部环境'
                        and node.get('class') == 'android.widget.Button'), 'actual management menu target')
            l, t, r, b = map(int, re.findall(r'\d+', node.get('bounds')))
            node.set('bounds', f'[{l},{t}][{r},{t+125}]')
            reseal_xml(record, 'menu', ET.tostring(tree, encoding='unicode'))
        def environment(record):
            tree = ET.fromstring(record['nativeUi']['chat']['rawXml'])
            node = one((node for node in tree.iter('node') if node.get('content-desc', '').startswith('当前环境：')),
                       'return environment capsule')
            node.set('content-desc', '当前环境：wrong environment，点按输入网址，长按切换环境')
            reseal_xml(record, 'chat', ET.tostring(tree, encoding='unicode'))
        def outside_menu(record):
            tree = ET.fromstring(record['nativeUi']['menu']['rawXml'])
            node = one((node for node in tree.iter('node') if node.get('text') == '管理全部环境'
                        and node.get('class') == 'android.widget.Button'), 'actual management menu target')
            viewport = one((node for node in tree.iter('node') if node.get('class') == 'android.widget.ScrollView'),
                           'actual menu viewport')
            l, t, r, b = map(int, re.findall(r'\d+', viewport.get('bounds')))
            rectangle = [r+10, t, r+136, t+126]
            node.set('bounds', f'[{rectangle[0]},{rectangle[1]}][{rectangle[2]},{rectangle[3]}]')
            record['inputs'][1].update(bounds=rectangle, point=[r+73,t+63])
            reseal_xml(record, 'menu', ET.tostring(tree, encoding='unicode'))
        def source(record):
            record['sourceCommit'] = 'f'*40
        baseline = self.publisher_gate()['production_navigation']
        manifest = dict(versionCode=108, sourceCommit=self.source, productionNavigationRegression=baseline)
        for mutation in (density, fabricated_density, raw_xml, tap, menu, outside_menu, environment, source):
            device = copy.deepcopy(self.device); mutation(device['productionNavigation']); self.write(device)
            for gate in (self.full_gate, self.publisher_gate, lambda:self.publish_gate(manifest=manifest)):
                with self.subTest(mutation=mutation.__name__, gate=gate.__name__), \
                        self.assertRaises((AssertionError, ValueError, KeyError)):
                    gate()

    def test_outer_original_source_status_and_execution_checks_remain_effective(self):
        baseline = self.publisher_gate()['production_navigation']
        manifest = dict(versionCode=108, sourceCommit=self.source, productionNavigationRegression=baseline)
        for key, value in (('sourceCommit', 'f'*40), ('status', 'failed'),
                           ('actualAndroidExecution', False), ('releaseMode', False)):
            device = copy.deepcopy(self.device); device[key] = value; self.write(device)
            for gate in (self.full_gate, self.publisher_gate, lambda:self.publish_gate(manifest=manifest)):
                with self.subTest(key=key, gate=gate.__name__), self.assertRaises(AssertionError): gate()

    def test_native_capture_must_join_the_installed_build_tree_run_and_attempt(self):
        baseline = self.publisher_gate()['production_navigation']
        manifest = dict(versionCode=108, sourceCommit=self.source, productionNavigationRegression=baseline)
        for key in ('sourceTree', 'runId', 'runAttempt'):
            device = copy.deepcopy(self.device)
            identity = device['eventTransport']['buildIdentity']
            target = identity if key == 'sourceTree' else identity['sdkBuildIdentity']
            target[key] = 'f'*40 if key == 'sourceTree' else '999999'
            self.write(device)
            for gate in (self.full_gate, self.publisher_gate, lambda:self.publish_gate(manifest=manifest)):
                with self.subTest(key=key, gate=gate.__name__), self.assertRaisesRegex(AssertionError, 'differ'):
                    gate()

    def test_removed_skipped_or_ignored_qualification_gate_is_rejected(self):
        original = yaml.safe_load(FULL.read_text())
        for mutation in ('removed', 'conditional', 'ignored', 'removed-reader'):
            changed = copy.deepcopy(original); steps = changed['jobs']['verify']['steps']
            step = one((row for row in steps if row.get('name') == FULL_STEP), FULL_STEP)
            if mutation == 'removed': steps.remove(step)
            elif mutation == 'conditional': step['if'] = 'false'
            elif mutation == 'ignored': step['continue-on-error'] = True
            else: step['run'] = step['run'].replace("navigation=verify_workspace_roundtrip(device['productionNavigation'],'local.pocketchat.test',source=source)", 'pass')
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError): self.full_gate(changed)
        changed = ast.parse(PUBLISHER.read_text())
        changed.body = [node for node in changed.body if not (isinstance(node, ast.If)
                        and calls(node, 'verify_workspace_roundtrip'))]
        with self.assertRaises(AssertionError): self.publisher_gate(changed)
        changed = yaml.safe_load(PUBLISH.read_text())
        step = one((row for row in changed['jobs']['publish']['steps'] if row.get('name') == PUBLISH_STEP), PUBLISH_STEP)
        step['run'] = step['run'].replace("verify_workspace_roundtrip(report['productionNavigation'],'local.pocketchat.test',source=m['sourceCommit'])", '{}')
        with self.assertRaises(AssertionError): self.publish_gate(changed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
