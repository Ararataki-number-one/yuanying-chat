"""Static contracts: diagnostic isolation and unchanged original CI commands.

No workflow, Android runtime, gesture or trace collection is executed here.
"""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('scheduler_workflow_generator',
    ROOT / 'tools/gecko/generate_input_scheduler_diagnostic_workflow.py')
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)


class SchedulerDiagnosticWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = yaml.safe_load(GEN.BASE.read_bytes())
        cls.flow = yaml.safe_load(GEN.TARGET.read_bytes())
        cls.build = cls.flow['jobs']['build']
        cls.samples = cls.flow['jobs']['editing-trace']

    def test_generated_file_is_reproducible_from_pinned_formal_source(self):
        self.assertEqual(hashlib.sha256(GEN.BASE.read_bytes()).hexdigest(), GEN.BASE_SHA256)
        self.assertEqual(GEN.TARGET.read_text(), GEN.render())

    def test_only_one_exact_diagnostic_branch_and_explicit_files_can_push_trigger(self):
        trigger = self.flow['on']
        self.assertEqual(set(trigger), {'push', 'workflow_dispatch'})
        self.assertEqual(trigger['push']['branches'], ['diagnostic/gecko-input-scheduler-20261028'])
        self.assertEqual(trigger['push']['paths'], [
            '.github/workflows/gecko-input-scheduler-diagnostic.yml',
            'tools/gecko/trace_input_scheduler.py',
            'tools/gecko/generate_input_scheduler_diagnostic_workflow.py',
            'tests/gecko_scheduler_diagnostic_workflow_test.py',
            'tests/gecko_scheduler_trace_input_test.py'])
        self.assertIsNone(trigger['workflow_dispatch'])

    def test_graph_is_one_build_and_three_fixed_once_only_original_workloads(self):
        self.assertEqual(set(self.flow['jobs']), {'build', 'editing-trace'})
        self.assertEqual(self.samples['needs'], 'build')
        self.assertEqual(self.samples['strategy']['matrix'], {'sample': ['1', '2', '3']})
        self.assertFalse(self.samples['strategy']['fail-fast'])
        self.assertFalse(self.flow['concurrency']['cancel-in-progress'])
        phase = [s for s in self.samples['steps'] if s.get('id') == 'trace_workload']
        self.assertEqual(len(phase), 1)
        self.assertNotIn('continue-on-error', phase[0])

    def test_repository_permissions_and_artifact_names_cannot_publish_production(self):
        self.assertEqual(self.flow['permissions'], {'contents': 'read', 'actions': 'read'})
        for job in self.flow['jobs'].values():
            self.assertNotIn('permissions', job)
            for step in job['steps']:
                if step.get('uses') == GEN.UPLOAD:
                    self.assertTrue(step['with']['name'].startswith('scheduler-diagnostic-'))
                if step.get('uses', '').startswith('actions/checkout@'):
                    self.assertIs(step['with']['persist-credentials'], False)
                    self.assertEqual(step['with']['fetch-depth'], 4)
                run = step.get('run', '')
                for forbidden in ('tools/gecko/publish_ci.py', 'tools/publish-gecko-release.py',
                                  'tools/publish-update-feed.py', 'git push ', 'gh release '):
                    self.assertNotIn(forbidden, run)

    def test_all_original_build_commands_remain_exact_except_the_publisher(self):
        original = [s['run'] for s in self.source['jobs']['build']['steps']
                    if 'run' in s and s.get('name') != 'Publish unsigned build for local original signing']
        actual = [s['run'] for s in self.build['steps']
                  if 'run' in s and s.get('name') != 'Declare this compiled bundle diagnostic only']
        self.assertEqual(actual, original)
        transfer = next(s for s in self.build['steps'] if s.get('name') == 'Transfer exact compiled APKs and SDK inputs')
        restore = next(s for s in self.samples['steps'] if s.get('uses') == GEN.DOWNLOAD)
        self.assertEqual(restore['with']['name'], transfer['with']['name'])

    def test_original_boot_capacity_and_workload_body_are_not_changed(self):
        old = self.source['jobs']['editing-samples']['steps']
        for name in ('Prepare Android runtime only', 'Boot Android for native acceptance',
                     'Restore exact build and verify its source/run/byte hashes'):
            self.assertEqual(next(s['run'] for s in self.samples['steps'] if s.get('name') == name),
                             next(s['run'] for s in old if s.get('name') == name))
        self.assertEqual(self.flow['env'], self.source['env'])
        original = next(s['run'] for s in old if s.get('name') == 'Run one original workload on this independent Android device')
        wrapped = next(s['run'] for s in self.samples['steps'] if s.get('id') == 'trace_workload')
        marker = "<<'POCKETCHAT_ORIGINAL_EDITING'\n"
        body = wrapped.split(marker, 1)[1].split('POCKETCHAT_ORIGINAL_EDITING\n', 1)[0]
        self.assertEqual(body, original)
        self.assertEqual(body.count('python3 tools/gecko/run_caret_editing_phase.py '), 1)
        self.assertIn('trace_input_scheduler.py run ', wrapped)
        self.assertNotIn('key_order_samples.py', wrapped)

    def test_perfetto_binary_and_analysis_are_only_after_the_original_phase(self):
        steps = self.samples['steps']
        phase = next(i for i, s in enumerate(steps) if s.get('id') == 'trace_workload')
        analysis = next(i for i, s in enumerate(steps) if s.get('id') == 'trace_analysis')
        self.assertGreater(analysis, phase)
        self.assertEqual(steps[analysis]['if'], 'always()')
        run = steps[analysis]['run']
        self.assertIn('https://github.com/google/perfetto/releases/download/v54.0/linux-amd64.zip', run)
        self.assertIn('2066ad35f7f56baf622f88506ded9cc07e2bc569417e7cd22e057126c06da382', run)
        self.assertIn('trace_input_scheduler.py analyze ', run)
        for step in steps:
            if step.get('uses') == GEN.UPLOAD:
                self.assertNotIn('work/input-scheduler-tools', step['with']['path'])

    def test_wrapper_is_unconditionally_diagnostic_and_preserves_failed_raw_bytes(self):
        scope = next(s for s in self.samples['steps'] if s.get('name') == 'Declare diagnostic scope regardless of workload outcome')
        self.assertEqual(scope['if'], 'always()')
        self.assertIn('diagnosticOnly=True,applicationAcceptance=False,releaseAcceptance=False', scope['run'])
        self.assertIn('analysisStepOutcome=', scope['run'])
        pack = next(s for s in self.samples['steps'] if s.get('name') == 'Seal original phase bytes without an acceptance collector')
        self.assertEqual(pack['if'], 'always()')
        self.assertEqual(pack['run'], 'python3 tools/gecko/ci_bundle.py pack --kind phase --phase editing --bundle work/input-scheduler-diagnostic/original-phase.tar.gz')
        upload = next(s for s in self.samples['steps'] if s.get('name') == 'Preserve diagnostic trace and unchanged phase evidence')
        self.assertEqual(upload['if'], 'always()')
        self.assertEqual(upload['with']['path'], 'work/input-scheduler-diagnostic/')
        self.assertEqual(upload['with']['compression-level'], 6)
        steps = self.samples['steps']
        phase = next(s for s in steps if s.get('id') == 'trace_workload')
        analysis = next(s for s in steps if s.get('id') == 'trace_analysis')
        self.assertGreater(steps.index(upload), steps.index(phase))
        self.assertGreater(steps.index(upload), steps.index(analysis))
        self.assertGreater(steps.index(upload), steps.index(pack))

    def test_generated_run_shells_parse_without_executing_any_workload(self):
        for job in self.flow['jobs'].values():
            for step in job['steps']:
                if 'run' not in step:
                    continue
                result = subprocess.run(['bash', '-n'], input=step['run'], text=True,
                                        capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, step.get('name', '') + result.stderr)


if __name__ == '__main__':
    unittest.main()
