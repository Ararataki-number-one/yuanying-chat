#!/usr/bin/env python3
"""Offline graph/inverse controls. No Android, network, or release acceptance."""
import ast
import contextlib
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
import unittest
from unittest import mock
import yaml

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source11_targeted_generator_frontend',ROOT/'tests/gecko/source11_targeted_generator_compat.py')
frontend=importlib.util.module_from_spec(spec);spec.loader.exec_module(frontend)
g=frontend.load_generator()

def restore_job(case,key,job):
    """Independent narrow inverse; every unacknowledged field must still match."""
    old=g.base()['jobs'][key];job=copy.deepcopy(job)
    case.assertEqual(job['steps'][-2:],g.scope_steps(key));job['steps']=job['steps'][:-2]
    steps=[];current=iter(job['steps'])
    for original in old['steps']:
        if original.get('run')==g.PUBLISH.rstrip('\n'):
            case.assertEqual(key,'build');steps.append(copy.deepcopy(original));continue
        step=next(current)
        if original.get('name') in g.STEP_IDS:
            case.assertEqual(step.pop('id'),g.STEP_IDS[original['name']])
        if original.get('uses') in (g.UPLOAD,g.DOWNLOAD):
            case.assertTrue(step['with']['name'].startswith(g.PREFIX))
            step['with']['name']=step['with']['name'][len(g.PREFIX):]
        if original.get('uses','').startswith('actions/checkout@'):
            case.assertIs(step['with'].pop('persist-credentials'),False)
            if not step['with'] and 'with' not in original:step.pop('with')
        if 'run' in original:
            run=step['run']
            if original.get('name')=='Verify network performance and compact chrome':
                case.assertEqual(run.count(g.UI_DIAGNOSTIC_LINE),1)
                run=run.replace(g.UI_DIAGNOSTIC_LINE,g.UI_LINE)
            if original.get('name')=='Verify production environments and file transfers':
                case.assertEqual(run.count(g.FILES_DIAGNOSTIC_LINE),1)
                run=run.replace(g.FILES_DIAGNOSTIC_LINE,g.FILES_LINE)
            lines=run.splitlines(keepends=True)
            for index,line in enumerate(original['run'].splitlines(keepends=True)):
                if line==g.PUBLISH:lines.insert(index,line)
            step['run']=''.join(lines)
        case.assertEqual(step,original)
        steps.append(step)
    with case.assertRaises(StopIteration):next(current)
    job['steps']=steps
    for field in ('name','permissions','if'):
        if field in old:job[field]=copy.deepcopy(old[field])
        else:job.pop(field)
    if key=='android':job['strategy']['matrix']['phase']=copy.deepcopy(old['strategy']['matrix']['phase'])
    case.assertEqual(job,old)
    return job

class Targeted(unittest.TestCase):
    def setUp(self):self.base=g.base();self.doc=g.derive()
    def test01_reference_and_generation_are_byte_reproducible(self):
        self.assertEqual(hashlib.sha256(g.reviewed_base_bytes(g.BASE.read_bytes())).hexdigest(),g.BASE_SHA256)
        self.assertEqual(g.TARGET.read_text(),g.render())
        self.assertEqual(yaml.safe_load(g.TARGET.read_text()),self.doc)
    def test02_exact_one_build_and_four_vm_graph(self):
        self.assertEqual(set(self.doc['jobs']),{'build','android','chrome-diagnostic'})
        self.assertEqual(self.doc['jobs']['android']['strategy']['matrix'],{'phase':['ui','files']})
        self.assertEqual(self.doc['jobs']['chrome-diagnostic']['strategy']['matrix'],{'scenario':['cold','after-reload']})
        self.assertEqual(self.doc['jobs']['android']['needs'],'build')
        self.assertEqual(self.doc['jobs']['chrome-diagnostic']['needs'],'build')
        self.assertNotIn('editing-samples',self.doc['jobs']);self.assertNotIn('verify',self.doc['jobs'])
    def test03_exact_push_branch_first_attempt_and_read_permissions(self):
        self.assertEqual(self.doc['on'],{'push':{'branches':[g.BRANCH],'paths':g.PUSH_PATHS}})
        self.assertEqual(self.doc['permissions'],g.READ)
        self.assertIs(self.doc['concurrency']['cancel-in-progress'],False)
        for job in self.doc['jobs'].values():
            self.assertEqual(job['permissions'],g.READ)
            self.assertEqual(job['if'],"github.ref == 'refs/heads/"+g.BRANCH+"' && github.run_attempt == 1")
            self.assertTrue(job['name'].startswith('Diagnostic experience'))
    def test04_every_original_command_condition_and_job_field_restores(self):
        for key,job in self.doc['jobs'].items():restore_job(self,key,job)
    def test05_inverse_rejects_unreviewed_device_or_condition_changes(self):
        for mutation in ('cpu','condition','extra-env'):
            job=copy.deepcopy(self.doc['jobs']['android'])
            if mutation=='cpu':
                boot=next(s for s in job['steps'] if s.get('id')=='android_boot')
                self.assertIn('-cores 4',boot['run']);boot['run']=boot['run'].replace('-cores 4','-cores 2')
            elif mutation=='condition':
                next(s for s in job['steps'] if s.get('id')=='diagnostic_ui')['if']='false'
            else:job['env']={'SKIP_REAL_CHECK':'true'}
            with self.assertRaises(AssertionError):restore_job(self,'android',job)
    def test06_no_publication_command_or_refwrite_in_generated_commands(self):
        for job in self.doc['jobs'].values():
            for step in job['steps']:
                run=step.get('run','')
                self.assertNotIn('publish_ci.py',run);self.assertNotIn('git push',run)
                self.assertNotIn('publish-gecko-release.py',run);self.assertNotIn('publish-update-feed.py',run)
                if step.get('uses','').startswith('actions/checkout@'):
                    self.assertIs(step['with']['persist-credentials'],False)
    def test07_single_opt_in_trace_and_publication_only_ui_override(self):
        scripts=[s.get('run','') for j in self.doc['jobs'].values() for s in j['steps']]
        self.assertEqual(sum(s.count('--reading-zoom-trace') for s in scripts),1)
        self.assertEqual(sum(s.count('GITHUB_ACTIONS=false') for s in scripts),1)
        self.assertEqual(sum(s.count(g.FILES_DIAGNOSTIC_LINE) for s in scripts),1)
        self.assertFalse(any('--reading-only' in s for s in scripts))
        self.assertFalse(any('--update-transfers-only' in s for s in scripts))
        self.assertEqual(self.doc['env'],self.base['env'])
        g.verify_ui_checkpoint_only()
    def test08_ui_override_rejects_another_github_actions_use(self):
        original=(ROOT/'tests/gecko/run_ui_visuals.py').read_text()
        with mock.patch.object(Path,'read_text',return_value=original+"\nextra=os.environ.get('GITHUB_ACTIONS')\n"):
            with self.assertRaises(AssertionError):g.verify_ui_checkpoint_only()
    def test09_all_upload_and_download_names_are_namespaced(self):
        for job in self.doc['jobs'].values():
            for step in job['steps']:
                if step.get('uses') in (g.UPLOAD,g.DOWNLOAD):
                    self.assertTrue(step['with']['name'].startswith(g.PREFIX))
                    self.assertFalse(step['with']['name'].startswith(g.PREFIX+g.PREFIX))
    def test10_original_sealed_build_and_phase_bundle_commands_unchanged(self):
        for key in self.doc['jobs']:
            original=self.base['jobs'][key]
            for old in original['steps']:
                if 'ci_bundle.py' in old.get('run',''):
                    actual=next(s for s in self.doc['jobs'][key]['steps'] if s.get('name')==old.get('name'))
                    self.assertEqual(actual['run'],old['run'])
            for field in ('runs-on','timeout-minutes','continue-on-error'):
                self.assertEqual(self.doc['jobs'][key].get(field),original.get(field))
    def test11_original_chrome_failure_semantics_retained(self):
        self.assertIs(self.doc['jobs']['chrome-diagnostic']['continue-on-error'],True)
        self.assertIn('Workflow success does not establish all four VM outcomes',g.render())
        for key in self.doc['jobs']:
            for step in self.doc['jobs'][key]['steps'][-2:]:self.assertEqual(step['if'],'always()')
    def test12_all_generated_shells_parse_without_execution(self):
        count=0
        for job in self.doc['jobs'].values():
            for step in job['steps']:
                if 'run' in step:
                    subprocess.run(['bash','-n'],input=step['run'],text=True,check=True,capture_output=True);count+=1
        self.assertGreater(count,30)
    def test13_trace_interface_requires_single_default_false_store_true(self):
        g.reading_interface_ready("p.add_argument('--reading-zoom-trace',action='store_true')")
        g.reading_interface_ready("p.add_argument('--reading-zoom-trace',action='store_true',default=False)")
        for value in ("p.add_argument('--different',action='store_true')",
            "p.add_argument('--reading-zoom-trace',action='store_true',default=True)",
            "p.add_argument('--reading-zoom-trace',action='store_false')",
            "p.add_argument('--reading-zoom-trace',action='store_true')\np.add_argument('--reading-zoom-trace',action='store_true')"):
            with self.assertRaises(AssertionError):g.reading_interface_ready(value)
    def test14_scope_never_promotes_success_to_acceptance(self):
        for key,phase in [('build','build'),('android','ui'),('android','files'),('chrome-diagnostic','cold'),('chrome-diagnostic','after-reload')]:
            marker=g.scope_steps(key)[0];python=marker['run'].split("python3 - <<'TARGETED_SCOPE'\n",1)[1].rsplit('\nTARGETED_SCOPE\n',1)[0]
            ast.parse(python)
            with tempfile.TemporaryDirectory() as t:
                temp=Path(t);path=temp/'.github/workflows';path.mkdir(parents=True);(path/'gecko-experience-targeted.yml').write_text('synthetic marker test only')
                env={k:'success' for k in marker['env']};env.update(TARGETED_PHASE=phase,GITHUB_SHA='a'*40,GITHUB_REF='refs/heads/'+g.BRANCH,GITHUB_RUN_ID='49999999999',GITHUB_RUN_ATTEMPT='1')
                def git(cmd,**kwargs):
                    self.assertEqual(cmd[0],'git')
                    return {'HEAD':'a'*40+'\n','HEAD^{tree}':'b'*40+'\n','--porcelain':''}[cmd[-1]]
                out=io.StringIO()
                with mock.patch.object(Path,'cwd',return_value=temp),mock.patch.dict(os.environ,env,clear=True),mock.patch('subprocess.check_output',side_effect=git),contextlib.redirect_stdout(out):
                    exec(compile(python,'<diagnostic-scope>','exec'),{})
                record=json.loads(out.getvalue())
                for field in ('applicationAcceptance','releaseAcceptance','physicalPhoneAcceptance','protectionEffectivenessAcceptance','qualification'):
                    self.assertIs(record[field],False)
                self.assertTrue(record['diagnosticOnly']);self.assertEqual(record['maximumOriginalWorkloadInvocations'],1)
                self.assertEqual(record['readingZoomTraceRequested'],key=='android' and phase=='files')

    def test15_history_checkout_inverse_rejects_unreviewed_preparation(self):
        raw=g.BASE.read_bytes();inserted=b'      with:\n        fetch-depth: 16\n'
        self.assertEqual(raw.count(inserted),1)
        restored=g.reviewed_base_bytes(raw)
        self.assertEqual(hashlib.sha256(restored).hexdigest(),g.BASE_SHA256)
        mutants=[raw.replace(inserted,b'',1),raw.replace(inserted,inserted*2,1)]
        mutants.extend(raw.replace(b'fetch-depth: 16',b'fetch-depth: '+value,1) for value in (b'0',b'1',b'17',b'128'))
        checkout=b'    - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262\n'
        second=raw.index(checkout,raw.index(checkout)+len(checkout))+len(checkout)
        moved=raw[:second]+inserted+raw[second:]
        mutants.extend((moved,moved.replace(inserted,b'',1),raw.replace(b'    timeout-minutes: 40\n',b'    timeout-minutes: 41\n',1)))
        for value in mutants:
            with self.subTest(mutationSha256=hashlib.sha256(value).hexdigest()):
                with self.assertRaises(AssertionError):g.reviewed_base_bytes(value)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Targeted))
    out=ROOT/'work/experience-targeted';out.mkdir(parents=True,exist_ok=True)
    (out/'workflow-static-controls.json').write_text(json.dumps(dict(status='passed' if result.wasSuccessful() else 'failed',
        testsRun=result.testsRun,failures=len(result.failures),errors=len(result.errors),actualAndroidExecution=False,
        releaseAcceptance=False,scope='Offline graph, exact inverse, shell syntax and synthetic marker controls only.'),indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
