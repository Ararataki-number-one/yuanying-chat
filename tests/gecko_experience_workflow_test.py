"""Exercise input selection and the actual workflow shell; never run a device/build."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('workflow_comparison', ROOT/'tools/gecko/run_experience_comparison.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def declaration(mode='baseline'):
    value = dict(schema=1, mode=mode, baseline_source='a'*40, baseline_run='123',
                 baseline_attempt='1', scenario='download-history-1000', repetitions=3)
    if mode == 'compare':
        value.update(candidate_source='b'*40, candidate_run='124', candidate_attempt='1')
    return value


class WorkflowTests(unittest.TestCase):
    def invoke(self, directory, env):
        args = SimpleNamespace(output=directory/'outputs', report=directory/'selection.json')
        with mock.patch.dict(os.environ, env, clear=True):
            M.select_inputs(args)
        output = dict(line.split('=', 1) for line in args.output.read_text().splitlines())
        return output, json.loads(args.report.read_text())

    def test_dispatch_scenario_reaches_actual_workflow_prepare_command(self):
        workflow = (ROOT/'.github/workflows/gecko-experience.yml').read_text()
        part = workflow.split('    - name: Restore unchanged build bundles and seal ABBA plan\n', 1)[1].split('\n    - ', 1)[0]
        shell = textwrap.dedent(part.split('      run: |\n', 1)[1])
        self.assertIn('SCENARIO: ${{ inputs.scenario }}', workflow)
        self.assertIn('SCENARIO: ${{ steps.inputs.outputs.scenario }}', part)
        self.assertIn('options: ['+', '.join(M.scenarios.NAMES)+']', workflow)
        for mode in ('baseline', 'compare'):
            for scenario in M.scenarios.NAMES:
                with self.subTest(mode=mode, scenario=scenario), tempfile.TemporaryDirectory() as folder:
                    directory = Path(folder)
                    env = {key.upper(): str(value) for key, value in declaration(mode).items() if key != 'schema'}
                    env.update(GITHUB_EVENT_NAME='workflow_dispatch', SCENARIO=scenario)
                    selected, receipt = self.invoke(directory, env)
                    self.assertEqual(selected['scenario'], scenario)
                    expected = M.scenarios.manifest(scenario)
                    self.assertEqual(receipt['scenarioManifest'], expected)
                    self.assertEqual(receipt['scenarioManifestSha256'], M.scenarios.digest(expected))
                    # Run the actual bash argument construction, replacing only
                    # Python execution with an argv recorder, not a fake build.
                    binary = directory/'bin';binary.mkdir()
                    executable = binary/'python3'
                    executable.write_text('#!'+sys.executable+'\nimport json,os,sys\njson.dump(sys.argv[1:],open(os.environ["ARGV_CAPTURE"],"w"))\n')
                    executable.chmod(0o755)
                    captured = directory/'argv.json'
                    shell_env = dict(os.environ, **{key.upper(): value for key, value in selected.items()})
                    shell_env.update(PATH=str(binary)+os.pathsep+os.environ['PATH'], ARGV_CAPTURE=str(captured))
                    subprocess.run(['bash', '-c', shell], cwd=directory, env=shell_env, check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    argv = json.loads(captured.read_text())
                    self.assertEqual(argv[:2], ['tools/gecko/run_experience_comparison.py', 'prepare'])
                    self.assertEqual(argv[argv.index('--scenario')+1], scenario)
                    self.assertEqual(argv[argv.index('--baseline-source')+1], 'a'*40)
                    self.assertEqual(argv[argv.index('--baseline-run')+1], '123')
                    self.assertEqual(argv[argv.index('--repetitions')+1], '3')
                    self.assertEqual('--candidate-source' in argv, mode == 'compare')
                    if mode == 'compare': self.assertEqual(argv[argv.index('--candidate-source')+1], 'b'*40)

    def test_invalid_dispatch_fails_before_outputs_or_device_setup(self):
        for scenario, repetitions in [('idle-120', '5'), ('core\nmode=compare', '3'),
                                      ('unsupported', '3'), ('core', '0')]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                env = {key.upper(): str(value) for key, value in declaration().items() if key != 'schema'}
                env.update(GITHUB_EVENT_NAME='workflow_dispatch', SCENARIO=scenario, REPETITIONS=repetitions)
                with self.assertRaises(ValueError): self.invoke(directory, env)
                self.assertFalse((directory/'outputs').exists())
                self.assertEqual(json.loads((directory/'selection.json').read_text())['status'], 'failed')

    def test_declared_push_uses_exact_refs_and_never_discovers_a_run(self):
        for mode in ('baseline', 'compare'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder);path = directory/M.REQUEST_PATH;path.parent.mkdir()
                value = declaration(mode);raw = json.dumps(value).encode();path.write_bytes(raw)
                env = dict(GITHUB_EVENT_NAME='push', GITHUB_SHA='c'*40,
                           GITHUB_REF_NAME='benchmark/experience-p01-fixed', MODE='wrong', BASELINE_RUN='999')
                with mock.patch.object(M, 'ROOT', directory), mock.patch.object(M.urllib.request, 'urlopen', side_effect=AssertionError('No build discovery allowed')):
                    selected, receipt = self.invoke(directory, env)
                self.assertEqual(selected['baseline_run'], '123')
                self.assertEqual(selected['mode'], mode)
                self.assertEqual(receipt['request']['value'], value)
                self.assertEqual(receipt['request']['sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(receipt['request']['orchestrationSource'], 'c'*40)
                self.assertTrue(receipt['buildSelectionFrozen'])

    def test_declared_push_rejects_unknown_duplicate_stale_and_unbounded_inputs(self):
        base = declaration()
        invalid = [dict(base, schema=True), dict(base, repetitions=True), dict(base, repetitions=11),
                   dict(base, baseline_run=123), dict(base, baseline_source='main'),
                   dict(base, baseline_attempt='1\nmode=compare'), dict(base, candidate_run='124'),
                   dict(base, extra='not sealed'), dict(base, mode='compare'),
                   dict(base, scenario='idle-120', repetitions=5)]
        raw_cases = [json.dumps(value) for value in invalid]
        raw_cases += [json.dumps(base)[:-1]+',"mode":"baseline"}', ' '*16385, '[]', 'null']
        for raw in raw_cases:
            with self.subTest(raw=raw[:80]), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder);path = directory/M.REQUEST_PATH;path.parent.mkdir();path.write_text(raw)
                env = dict(GITHUB_EVENT_NAME='push', GITHUB_SHA='c'*40, GITHUB_REF_NAME='benchmark/experience-invalid')
                with mock.patch.object(M, 'ROOT', directory), self.assertRaises(ValueError): self.invoke(directory, env)
                self.assertFalse((directory/'outputs').exists())
                self.assertEqual(json.loads((directory/'selection.json').read_text())['status'], 'failed')

    def test_push_request_requires_fixed_regular_file_and_dedicated_branch(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder);path = directory/M.REQUEST_PATH;path.parent.mkdir()
            with self.assertRaises(ValueError): M.declared_inputs(directory, 'c'*40, 'benchmark/experience-missing')
            target = directory/'elsewhere.json';target.write_text(json.dumps(declaration()));path.symlink_to(target)
            with self.assertRaises(ValueError): M.declared_inputs(directory, 'c'*40, 'benchmark/experience-link')
            path.unlink();path.write_text(target.read_text())
            with self.assertRaises(ValueError): M.declared_inputs(directory, 'c'*40, 'release/gecko-anything')
            with self.assertRaises(ValueError): M.declared_inputs(directory, 'main', 'benchmark/experience-source')

    def test_legacy_push_keeps_one_original_build_and_core_default(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(GITHUB_EVENT_NAME='push', GITHUB_SHA='a'*40,
                       GITHUB_REF_NAME='release/gecko-2.0.16-experience', GITHUB_REPOSITORY='owner/repo',
                       GH_TOKEN='synthetic-test-only', SCENARIO='idle-120')
            run = dict(id=123, run_attempt=1, head_sha='a'*40, event='push',
                       head_branch=env['GITHUB_REF_NAME'], status='in_progress')
            responses = [dict(workflow_runs=[run]), run,
                         dict(artifacts=[dict(id=456, name='gecko-123-1-build', expired=False)])]
            with mock.patch.object(M.urllib.request, 'urlopen', side_effect=[io.StringIO(json.dumps(r)) for r in responses]) as network:
                selected, receipt = self.invoke(Path(folder), env)
            self.assertEqual(network.call_count, 3)
            self.assertEqual(selected['scenario'], 'core')
            self.assertEqual(selected['baseline_run'], '123')
            self.assertEqual(receipt['artifactId'], 456)
            self.assertNotIn('request', receipt)


if __name__ == '__main__':
    unittest.main()
