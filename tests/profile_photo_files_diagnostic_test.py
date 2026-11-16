"""The independent photo runner executes the original files workload only.

These host controls execute the actual diagnostic identity scripts in a new
Git repository. They do not compile, run Android, or qualify a release.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = '.github/workflows/photo-files-diagnostic.yml'
WORKFLOW = 'NONQUALIFYING photo and complete files diagnostics'
BEGIN = 'Bind independent diagnostic source and run identity'
END = 'Record original diagnostic outcomes without qualifying a release'
FILES = 'Verify production environments and file transfers'
BUILD_STEPS = ('Prepare locked toolchain', 'Compile release and native regression package',
               'Prepare synthetic signed upgrade archives')
DEVICE_STEPS = ('Prepare Android runtime only', 'Boot Android for native acceptance',
                'Record bounded native setup endpoint diagnostics', FILES,
                'Preserve emulator and runner health')


def require(value, message):
    if not value:
        raise AssertionError(message)


def by_name(workflow, job, name):
    values = [step for step in workflow['jobs'][job]['steps'] if step.get('name') == name]
    require(len(values) == 1, 'Exactly one '+name+' step is required')
    return values[0]


def validate(workflow):
    original = yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
    require(workflow['name'] == WORKFLOW, 'The actual diagnostic workflow identity must be retained')
    require(workflow['on'] == {'push': {'branches': ['diagnostic/photo-files-2.1.6']},
                               'workflow_dispatch': None}, 'Only the independent diagnostic trigger is allowed')
    require(workflow['permissions'] == {'contents': 'read', 'actions': 'read'}, 'Diagnostics must be read only')
    require(set(workflow['jobs']) == {'android'}, 'Only the independent Android job is allowed')
    job = workflow['jobs']['android']
    require(job['runs-on'] == 'ubuntu-24.04' and job['timeout-minutes'] == 40, 'Original files runner and budget are required')
    require(job['strategy'] == {'fail-fast': False, 'matrix': {'phase': ['files']}}, 'One complete files phase is required')
    require('needs' not in job and 'env' not in job and not job.get('continue-on-error'), 'Diagnostics cannot feed release qualification or override identity')
    require(workflow['env'] == original['env'], 'Original capacity preflight and environment must remain exact')
    for owner, names in (('build', BUILD_STEPS), ('android', DEVICE_STEPS)):
        for name in names:
            expected = by_name(original, owner, name)
            actual = by_name(workflow, 'android', name)
            require(actual['run'] == expected['run'], 'Original executable step changed: '+name)
            require(actual.get('if') == expected.get('if'), 'Original condition changed: '+name)
            require(actual.get('env') == expected.get('env'), 'Original environment changed: '+name)
    steps = job['steps']
    names = [step.get('name') for step in steps]
    for earlier, later in zip(BUILD_STEPS+DEVICE_STEPS, (BUILD_STEPS+DEVICE_STEPS)[1:]):
        require(names.index(earlier) < names.index(later), 'Actual files dependency order changed')
    source_step = by_name(workflow, 'android', 'Require exact integration source stamps and release isolation')
    require(names.index(BUILD_STEPS[1]) < names.index(source_step['name']) < names.index(DEVICE_STEPS[0]), 'Same-source stamps must precede the device')
    require('if' not in source_step and "len(integration)==2 and len(release)==2" in source_step['run']
            and 'runner.expected_build(apk,source,tree,version,code)' in source_step['run']
            and 'runner.STAMP not in archive.namelist()' in source_step['run'], 'Both ABI source stamps and release isolation are mandatory')
    combined = '\n'.join(step.get('run', '') for step in steps)
    require(combined.count('python3 tests/gecko/run_device.py ') == 1
            and combined.count('python3 tests/gecko/run_update_route.py ') == 1, 'The complete original workload must execute exactly once')
    require(not re.search(r'publish_ci|publish-gecko-release|ci_bundle|git\s+push|gh\s+release', combined), 'Diagnostics cannot publish or seal release evidence')
    for step in steps:
        require(not step.get('continue-on-error'), 'Diagnostic failures must remain visible')
        require(not any(key.startswith('GITHUB_') for key in step.get('env', {})), 'Actual GitHub identity must not be overridden')
        require(not re.search(r'(?:export\s+)?GITHUB_(?:WORKFLOW|REF|SHA|RUN_ID|RUN_ATTEMPT|JOB)\s*=', step.get('run', '')), 'Actual GitHub identity must not be spoofed')
    uploads = [step for step in steps if step.get('uses', '').startswith('actions/upload-artifact@')]
    require(len(uploads) == 2, 'Only original diagnostic evidence and APK uploads are expected')
    require({step['with']['name'].split('-${{', 1)[0] for step in uploads}
            == {'photo-files-diagnostic-evidence', 'photo-files-diagnostic-apks'}, 'Diagnostic artifacts cannot masquerade as release artifacts')
    for step in uploads:
        require(step.get('if') == 'always()', 'Failure evidence must be preserved')
        paths = step['with']['path'].splitlines()
        require(not any('**' in path or re.search(r'\.(?:jks|pem|key)$', path) for path in paths), 'Only explicit non-key diagnostic paths may be uploaded')
    evidence = next(step for step in uploads if '-evidence-' in step['with']['name'])['with']['path']
    require(all(path in evidence.splitlines() for path in ('work/photo-files-diagnostic/*.json',
                'work/gecko-integration/*.json', 'work/gecko-integration/*.png',
                'work/gecko-integration/*.txt', 'work/gecko-integration/*.log')), 'Original photos, events, identity and failures must be retained')
    return steps


def python_block(step):
    match = re.fullmatch(r"set -euo pipefail\npython3 - <<'PYCODE'\n([\s\S]*)\nPYCODE\n?", step['run'])
    require(match is not None, 'Actual diagnostic Python block is required')
    return match.group(1)


class PhotoFilesDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load((ROOT/PATH).read_text())

    def test_actual_dependency_commands_are_complete_once_and_shell_valid(self):
        for step in validate(self.workflow):
            if 'run' in step:
                subprocess.run(['bash', '-n'], input=step['run'], text=True, check=True, capture_output=True)
        for name, mutate in (
            ('missing update archives', lambda value: value['jobs']['android']['steps'].remove(by_name(value, 'android', BUILD_STEPS[2]))),
            ('duplicate device workload', lambda value: by_name(value, 'android', FILES).__setitem__('run', by_name(value, 'android', FILES)['run']+'python3 tests/gecko/run_device.py\n')),
            ('reduced CPU capacity', lambda value: by_name(value, 'android', DEVICE_STEPS[1]).__setitem__('run', by_name(value, 'android', DEVICE_STEPS[1])['run'].replace('-cores 4', '-cores 2'))),
        ):
            with self.subTest(name=name):
                value = copy.deepcopy(self.workflow)
                mutate(value)
                with self.assertRaises(AssertionError):
                    validate(value)

    def test_diagnostic_scope_cannot_publish_or_impersonate_release_identity(self):
        validate(self.workflow)
        for name, mutate in (
            ('publisher', lambda value: value['jobs']['android']['steps'].append({'name': 'forbidden', 'run': 'python3 tools/gecko/publish_ci.py'})),
            ('identity override', lambda value: by_name(value, 'android', FILES).__setitem__('env', {'GITHUB_WORKFLOW': 'Production acceptance'})),
            ('release artifact', lambda value: next(step for step in value['jobs']['android']['steps'] if step.get('uses', '').startswith('actions/upload-artifact@'))['with'].__setitem__('name', 'gecko-acceptance-files')),
        ):
            with self.subTest(name=name):
                value = copy.deepcopy(self.workflow)
                mutate(value)
                with self.assertRaises(AssertionError):
                    validate(value)

    def test_actual_envelope_preserves_failure_identity_and_rejects_changed_source(self):
        with tempfile.TemporaryDirectory(prefix='photo-diagnostic-host-') as directory:
            root = Path(directory)
            inputs = [PATH, 'tests/gecko/run_device.py', 'tests/gecko/run_update_route.py',
                      'tests/gecko/GeckoIntegrationTestActivity.java', 'tools/gecko/photo_upload_contract.py']
            for name in inputs:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT/name).read_bytes())
            (root/'.gitignore').write_text('work/\n')
            for command in (['git', 'init', '-q'], ['git', 'add', '.'],
                            ['git', '-c', 'user.name=Controlled Host', '-c', 'user.email=host@example.invalid', 'commit', '-qm', 'diagnostic identity fixture']):
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            env = dict(os.environ, GITHUB_SHA=source, GITHUB_RUN_ID='123456', GITHUB_RUN_ATTEMPT='1',
                       GITHUB_WORKFLOW=WORKFLOW, GITHUB_REF='refs/heads/diagnostic/photo-files-2.1.6',
                       GITHUB_JOB='android', GITHUB_EVENT_NAME='push', DIAGNOSTIC_JOB_STATUS='failure', FILES_STEP_OUTCOME='failure')
            def run(name, environment=env):
                return subprocess.run([os.sys.executable, '-c', python_block(by_name(self.workflow, 'android', name))],
                                      cwd=root, env=environment, capture_output=True, text=True)
            wrong = dict(env, GITHUB_SHA='0'*40)
            self.assertNotEqual(run(BEGIN, wrong).returncode, 0)
            self.assertEqual(run(BEGIN).returncode, 0)
            image = root/'work/gecko-integration/photo-upload-controlled.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'controlled host bytes, not an Android photo')
            complete = run(END)
            self.assertEqual(complete.returncode, 0, complete.stderr)
            result = json.loads((root/'work/photo-files-diagnostic/diagnostic-scope.json').read_text())
            self.assertEqual((result['sourceCommit'], result['runId'], result['workflow'], result['ref']),
                             (source, env['GITHUB_RUN_ID'], WORKFLOW, env['GITHUB_REF']))
            self.assertTrue(result['diagnosticOnly'])
            self.assertFalse(result['releaseAcceptance'])
            self.assertFalse(result['allReleasePhasesComplete'])
            self.assertFalse(result['originalFilesStepPassed'])
            self.assertEqual(result['filesStepOutcome'], 'failure')
            self.assertEqual(result['retainedOriginalFiles'], [{'path': image.relative_to(root).as_posix(),
                             'bytes': image.stat().st_size, 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}])
            (root/inputs[1]).write_text('changed source after execution\n')
            self.assertNotEqual(run(END).returncode, 0)


if __name__ == '__main__':
    unittest.main()
