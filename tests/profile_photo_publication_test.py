"""Execute current photo publication gates with disposable counterfeit inputs.

These are host parser/staging controls, never Android qualification evidence.
The PNG decoder, native-event reader, installed-build join, YAML Python blocks,
publisher list/copy statements and final git-add invocation are the real ones.
Only unrelated release inputs and the git-show source boundary are controlled.
"""
import ast
import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools'), str(ROOT/'tests')]
import gecko_photo_upload_contract_test as fixtures

contract = fixtures.contract
FULL = ROOT/'.github/workflows/browser-2_1-acceptance.yml'
PUBLISH = ROOT/'.github/workflows/publish-gecko-release.yml'
PUBLISHER = ROOT/'tools/publish-gecko-release.py'
PHOTO_STEP = 'Require actual photo contents from the same installed Android build'
PUBLISH_STEP = 'Verify original regressions, derived SDK provenance and signed public APK'


def calls(node, name):
    return [child for child in ast.walk(node) if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name) and child.func.id == name]


def one(values, label):
    values = list(values)
    if len(values) != 1:
        raise AssertionError('Exactly one current '+label+' is required')
    return values[0]


def step_python(workflow, job_name, step_name):
    job = workflow['jobs'][job_name]
    if job.get('continue-on-error', False) is not False:
        raise AssertionError('Photo qualification job cannot ignore failures')
    step = one((row for row in job['steps'] if row.get('name') == step_name), step_name)
    if 'if' in step or step.get('continue-on-error', False) is not False:
        raise AssertionError('Photo qualification step must execute unconditionally')
    run = step['run']
    if step.get('shell', 'bash') != 'bash' or not run.startswith('set -euo pipefail\n'):
        raise AssertionError('Photo qualification requires a failing shell boundary')
    match = re.fullmatch(r"set -euo pipefail\npython3 - <<'(PY(?:CODE)?)'\n([\s\S]*)\n\1\n?", run)
    if not match:
        raise AssertionError('Current Python qualification block is required')
    return ast.parse(match.group(2))


def execute(nodes, namespace, filename):
    tree = nodes if isinstance(nodes, ast.Module) else ast.Module(body=copy.deepcopy(nodes), type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(filename), 'exec'), namespace)


@contextmanager
def working_directory(directory):
    previous = Path.cwd()
    previous_path = list(sys.path)
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(previous)
        sys.path[:] = previous_path


class PhotoPublicationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        offline = patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '1'})
        offline.start()
        cls.addClassCleanup(offline.stop)
        cls.original = (ROOT/'tests/gecko/assets/photo-upload-pattern.png').read_bytes()
        cls.solid = fixtures.png(bytes([42, 73, 101, 255])*(contract.WIDTH*contract.HEIGHT))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='photo-publication-host-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.evidence = self.base/'work/gecko-integration/public'
        self.evidence.mkdir(parents=True)
        ledger = contract.PhotoUploadLedger(self.evidence, fixtures.identity())
        for index, (name, slot, level, mode, action) in enumerate(contract.CASES, 1):
            nonce = f'{index:032x}'
            ledger.register(name, nonce, slot, level, mode, action)
            ledger.document(nonce, index, level, mode)
            case = ledger.cases[nonce]
            for phase in contract.phases(mode):
                raw = self.solid if phase in contract.UNSELECTED and level == 2 else self.original
                content_type, body = fixtures.multipart(raw)
                ledger.receive(nonce, index, phase, content_type, body)
            result = fixtures.native(case)
            ledger.complete(nonce, result, fixtures.packets(case, result))
        self.photo = ledger.report()
        self.device = {'eventTransport': {'buildIdentity': fixtures.identity()}}
        self.write('photo-upload-results.json', self.photo)
        self.write('device-results.json', self.device)
        self.summary = contract.verify_photo_upload_evidence(self.evidence, fixtures.identity()['sourceCommit'])
        self.required = ['photo-upload-results.json', *self.summary['files']]
        self.assertEqual(len(self.required), 29)

    def write(self, name, value, directory=None):
        ((directory or self.evidence)/name).write_text(json.dumps(value)+'\n')

    def full_gate(self, workflow=None):
        workflow = workflow or yaml.safe_load(FULL.read_text())
        tree = step_python(workflow, 'verify', PHOTO_STEP)
        for name in ('verify_photo_upload_evidence', 'verify_installed'):
            one(calls(tree, name), 'full-workflow '+name+' call')
        with patch.dict(os.environ, {'GITHUB_SHA': fixtures.identity()['sourceCommit']}), working_directory(self.base):
            execute(tree, {}, FULL)

    def publisher_gate(self, tree=None, device=None):
        tree = tree or ast.parse(PUBLISHER.read_text())
        gate = one((node for node in tree.body if isinstance(node, ast.If)
                    and calls(node, 'verify_photo_upload_evidence')), 'publisher photo gate')
        namespace = dict(version_code=108, photo_upload=None,
                         args=SimpleNamespace(evidence=self.evidence, source=fixtures.identity()['sourceCommit']),
                         report=device or self.device, json=json)
        execute([gate], namespace, PUBLISHER)
        self.assertEqual(namespace['photo_upload'], self.summary)
        return namespace

    def publish_gate(self, workflow=None, manifest=None, device=None):
        tree = step_python(workflow or yaml.safe_load(PUBLISH.read_text()), 'publish', PUBLISH_STEP)
        gate = one((node for node in tree.body if isinstance(node, ast.If)
                    and calls(node, 'verify_photo_upload_evidence')), 'published photo gate')
        self.write('compact-chrome-results.json', {'cases': [{'navigationContract': 3}], 'autoCollapse': {'navigationContract': 3}})
        namespace = dict(m=manifest or {'versionCode': 108, 'sourceCommit': fixtures.identity()['sourceCommit'],
                                       'photoUploadContentRegression': self.summary},
                         report=device or self.device, json=json, pathlib=__import__('pathlib'))
        with working_directory(self.evidence):
            execute([gate], namespace, PUBLISH)

    def stage_and_index(self, tree=None):
        """Run actual list construction/copy/git-add with a real isolated Git index."""
        tree = tree or ast.parse(PUBLISHER.read_text())
        namespace = self.publisher_gate(tree)
        stage = self.base/'stage'
        stage.mkdir(exist_ok=True)
        namespace.update(stage=stage, root=ROOT, shutil=shutil, roadmap_release=False, sdk_build=None,
                         caret=None, template_release=False, resource_release=False, browser_release=False,
                         fingerprint_release=False, worker_timezone_release=False, chain_files=[],
                         chrome={'autoCollapse': {'cases': [], 'scope': 'Unrelated inline staging fixture only'}})
        start = one((index for index, node in enumerate(tree.body) if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'performance_files' for target in node.targets)),
                    'publication file-list initializer')
        end = one((index for index, node in enumerate(tree.body) if isinstance(node, ast.For)
                   and isinstance(node.iter, ast.Name) and node.iter.id == 'performance_files'), 'publication file-copy loop')
        self.assertGreater(end, start)
        execute(tree.body[start:end], namespace, PUBLISHER)
        self.assertTrue(set(self.required).issubset(namespace['performance_files']),
                        'Every original PNG and the complete native-event report must enter performance_files')
        # Unrelated pre-existing reports are only controlled bytes in this temp
        # directory. Nothing produced here is an acceptance or release artifact.
        for name in namespace['performance_files']:
            path = self.evidence/name
            if not path.exists():
                self.assertNotIn(name, self.required, 'A required original photo artifact is missing')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'controlled unrelated host input\n')
        execute([tree.body[end]], namespace, PUBLISHER)
        for name in self.required:
            self.assertEqual((stage/name).read_bytes(), (self.evidence/name).read_bytes())
        for name in ('.github/controlled-host.yml', 'tools/controlled-host.txt'):
            path = stage/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('controlled host boundary\n')
        add = one((node for node in tree.body if isinstance(node, ast.Expr)
                   and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                   and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'subprocess'
                   and node.value.func.attr == 'run' and node.value.args
                   and isinstance(node.value.args[0], ast.List)
                   and [getattr(item, 'value', None) for item in node.value.args[0].elts[:2]] == ['git', 'add']),
                  'publication git-add invocation')
        git_root = self.base/'git-root'
        subprocess.run(['git', 'init', '-q', str(git_root)], check=True, capture_output=True)
        environment = dict(os.environ, GIT_INDEX_FILE=str(self.base/'publication-index'), GIT_WORK_TREE=str(stage))
        # This legacy release does not stage optional Chromium assets.
        namespace.update(root=git_root, env=environment, subprocess=subprocess, manual_raw=None,
                         authorization_raw=None, chromium_release_files=[], manifest={'parts': []})
        arguments = eval(compile(ast.Expression(add.value.args[0]), str(PUBLISHER), 'eval'), namespace)
        for name in arguments[4:]:
            path = stage/name
            if not path.exists():
                self.assertNotIn(name, self.required)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('controlled unrelated staged input\n')
        execute([add], namespace, PUBLISHER)
        tracked = subprocess.check_output(['git', 'ls-files'], cwd=git_root, env=environment, text=True).splitlines()
        self.assertTrue(set(self.required).issubset(tracked), 'The actual release index must retain all 29 photo artifacts')
        for name in self.required:
            retained = subprocess.check_output(['git', 'show', ':'+name], cwd=git_root, env=environment)
            self.assertEqual(retained, (self.evidence/name).read_bytes())

    def test_full_acceptance_executes_decoder_and_installed_build_join(self):
        self.full_gate()
        missing = self.evidence/self.summary['files'][0]
        original = missing.read_bytes()
        missing.unlink()
        with self.assertRaisesRegex(AssertionError, 'Original uploaded image is missing'):
            self.full_gate()
        missing.write_bytes(original)
        mixed = copy.deepcopy(self.device)
        mixed['eventTransport']['buildIdentity']['apkSha256'] = 'f'*64
        self.write('device-results.json', mixed)
        with self.assertRaisesRegex(ValueError, 'apkSha256'):
            self.full_gate()

    def test_removed_conditional_or_ignored_full_gate_is_rejected(self):
        original = yaml.safe_load(FULL.read_text())
        for mutation in ('removed', 'conditional', 'ignored', 'removed-decoder', 'removed-build-join'):
            changed = copy.deepcopy(original)
            steps = changed['jobs']['verify']['steps']
            step = one((row for row in steps if row.get('name') == PHOTO_STEP), PHOTO_STEP)
            if mutation == 'removed':
                steps.remove(step)
            elif mutation == 'conditional':
                step['if'] = 'false'
            elif mutation == 'ignored':
                step['continue-on-error'] = True
            elif mutation == 'removed-decoder':
                step['run'] = step['run'].replace('verify_photo_upload_evidence(directory,source)', 'pass')
            else:
                step['run'] = step['run'].replace("verify_installed(photo['buildIdentity'],device['eventTransport']['buildIdentity'])", 'pass')
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.full_gate(changed)

    def test_current_publisher_gate_and_actual_index_preserve_every_original(self):
        self.stage_and_index()

    def test_removing_staging_list_or_final_git_add_expansion_is_observable(self):
        for mutation in ('file-list', 'git-add'):
            changed = ast.parse(PUBLISHER.read_text())
            if mutation == 'file-list':
                changed.body = [node for node in changed.body if not (isinstance(node, ast.If)
                                and ast.unparse(node.test) == 'photo_upload is not None'
                                and any(isinstance(child, ast.Attribute) and child.attr == 'extend' for child in ast.walk(node)))]
            else:
                for node in ast.walk(changed):
                    if isinstance(node, ast.List) and [getattr(item, 'value', None) for item in node.elts[:2]] == ['git', 'add']:
                        node.elts = [item for item in node.elts if not (isinstance(item, ast.Starred)
                                     and isinstance(item.value, ast.Name) and item.value.id == 'performance_files')]
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.stage_and_index(changed)

    def test_publisher_and_published_workflow_reject_missing_images_mixed_builds_and_manifest_drift(self):
        self.publisher_gate()
        self.publish_gate()
        missing = self.evidence/self.summary['files'][-1]
        raw = missing.read_bytes()
        missing.unlink()
        for gate in (self.publisher_gate, self.publish_gate):
            with self.subTest(gate=gate.__name__, mutation='missing-png'), self.assertRaisesRegex(AssertionError, 'Original uploaded image is missing'):
                gate()
        missing.write_bytes(raw)
        mixed = copy.deepcopy(self.device)
        mixed['eventTransport']['buildIdentity']['buildStampSha256'] = 'f'*64
        for gate in (self.publisher_gate, self.publish_gate):
            with self.subTest(gate=gate.__name__, mutation='mixed-build'), self.assertRaisesRegex(ValueError, 'buildStampSha256'):
                gate(device=mixed)
        manifest = {'versionCode': 108, 'sourceCommit': fixtures.identity()['sourceCommit'],
                    'photoUploadContentRegression': dict(self.summary, images=27)}
        with self.assertRaises(AssertionError):
            self.publish_gate(manifest=manifest)
        changed = yaml.safe_load(PUBLISH.read_text())
        step = one((row for row in changed['jobs']['publish']['steps'] if row.get('name') == PUBLISH_STEP), PUBLISH_STEP)
        step['run'] = step['run'].replace("assert verify_photo_upload_evidence(pathlib.Path('.'),m['sourceCommit'])==m['photoUploadContentRegression']", 'pass')
        with self.assertRaises(AssertionError):
            self.publish_gate(workflow=changed)

    def test_published_checker_must_equal_the_selected_source_bytes(self):
        tree = step_python(yaml.safe_load(PUBLISH.read_text()), 'publish', PUBLISH_STEP)
        gate = one((node for node in tree.body if isinstance(node, ast.If)
                    and any(isinstance(child, ast.Constant) and child.value == 'tools/gecko/photo_upload_contract.py'
                            for child in ast.walk(node))), 'photo checker source binding')
        # This boundary returns actual source-file bytes from this checkout for
        # the exact git-show argv. It does not claim a real source commit exists.
        def selected_source(arguments):
            self.assertEqual(arguments[:2], ['git', 'show'])
            self.assertTrue(arguments[2].startswith(fixtures.identity()['sourceCommit']+':tools/gecko/'))
            return (ROOT/arguments[2].split(':', 1)[1]).read_bytes()
        for node in ast.walk(gate):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith('tools/gecko/'):
                path = self.base/node.value
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/node.value, path)
        namespace = dict(m={'versionCode': 108, 'sourceCommit': fixtures.identity()['sourceCommit']},
                         pathlib=__import__('pathlib'), subprocess=SimpleNamespace(check_output=selected_source))
        with working_directory(self.base):
            execute([gate], namespace, PUBLISH)
            altered = self.base/'tools/gecko/photo_upload_contract.py'
            altered.write_bytes(altered.read_bytes()+b'\n# counterfeit staged checker\n')
            with self.assertRaisesRegex(AssertionError, 'differs from tested source'):
                execute([gate], namespace, PUBLISH)


if __name__ == '__main__':
    unittest.main(verbosity=2)
