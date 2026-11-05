"""Actual shallow Git/object restoration with a declared offline fetch boundary.

No public network request, source projection, original assertion substitution,
Android, native runtime, APK construction or signing occurs in these controls.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('explicit_public_source_history',ROOT/'tools/browser/source_history.py')
history=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(history)
E21='e21b4fd6698074310ee36f85f980b16ad643c934'

class PublicHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='public-history-setup-');self.addCleanup(self.temporary.cleanup)
        self.repo=Path(self.temporary.name)/'repo';self.repo.mkdir();self.real=history.git;self.fetches=[]
        self.git_run('init','-q');self.git_run('config','user.name','Source input control');self.git_run('config','user.email','source-control@example.invalid')
        (self.repo/'anchor.txt').write_text('current source remains unchanged\n');self.git_run('add','anchor.txt');self.git_run('commit','-qm','Independent current source fixture')
        self.git_run('remote','add','origin',history.ORIGINS[0]);target=self.repo/history.MANIFEST;target.parent.mkdir(parents=True);target.write_bytes((ROOT/history.MANIFEST).read_bytes())
        self.head=self.git_run('rev-parse','HEAD').decode().strip()
        self.environment=dict(CI='true',GITHUB_ACTIONS='true',GITHUB_SERVER_URL='https://github.com',GITHUB_REPOSITORY=history.REPOSITORY,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA=self.head)
    def git_run(self,*args):
        value=subprocess.run(['git','--no-replace-objects',*args],cwd=self.repo,capture_output=True,check=True)
        return value.stdout
    def seed(self,commit):
        self.git_run('fetch','--no-tags','--depth=1','--no-write-fetch-head',str(ROOT),commit)
    def transport(self,root,*args):
        if args[:1]==('fetch',):
            self.assertEqual(args[:5],('fetch','--no-tags','--depth=1','--no-write-fetch-head','origin'))
            self.assertEqual(len(args),6);self.assertIn(args[5],{g['commit']for g in history.manifest(root)})
            self.fetches.append(args)
            # Only the transport boundary is local. Verification executes real
            # Git against the fetched original commit/tree/blob/source bytes.
            return self.real(root,*args[:4],str(ROOT),args[5])
        return self.real(root,*args)
    def prepare(self,environment=None,transport=None):
        with patch.object(history,'git',side_effect=transport or self.transport):
            return history.prepare_public_history(self.repo,self.environment if environment is None else environment)
    def test_exact_missing_e21_and_all_declared_objects_restore_in_real_shallow_repo(self):
        self.assertNotEqual(subprocess.run(['git','cat-file','-e',E21+'^{commit}'],cwd=self.repo,capture_output=True).returncode,0)
        before=history.checkout_state(self.repo);report=self.prepare();self.assertEqual(report['status'],'passed');self.assertTrue(report['checkoutUnchanged'])
        self.assertEqual(history.checkout_state(self.repo),before);self.assertEqual(self.git_run('rev-parse','HEAD').decode().strip(),self.head)
        self.assertTrue((self.repo/'.git/shallow').is_file());self.assertFalse((self.repo/'.git/FETCH_HEAD').exists())
        self.assertEqual(len(self.fetches),len(history.manifest(self.repo)));self.assertIn(E21,report['fetchedCommits'])
        for group in history.manifest(self.repo):self.assertEqual(history.verify_group(self.repo,group)['tree'],group['tree'])
        self.assertFalse(report['testsExecuted']);self.assertFalse(report['actualAndroidExecution'])
    def test_prepared_objects_require_no_fetch_or_ci_identity(self):
        for group in history.manifest(self.repo):self.seed(group['commit'])
        def no_fetch(root,*args):
            self.assertNotEqual(args[:1],('fetch',));return self.real(root,*args)
        report=self.prepare({},no_fetch);self.assertEqual(report['fetchedCommits'],[])
    def test_prepared_readonly_inputs_preserve_dirty_source_but_missing_inputs_cannot_fetch(self):
        (self.repo/'anchor.txt').write_text('Unrelated existing local change\n')
        with self.assertRaises(RuntimeError):self.prepare()
        self.assertEqual(self.fetches,[])
        for group in history.manifest(self.repo):self.seed(group['commit'])
        before=history.checkout_state(self.repo);report=self.prepare({})
        self.assertEqual(report['fetchedCommits'],[]);self.assertEqual(history.checkout_state(self.repo),before)

    def test_missing_objects_never_fetch_for_unowned_source_origin_or_run(self):
        for key,value in [('CI','false'),('GITHUB_REPOSITORY','foreign/repository'),('GITHUB_SHA','f'*40),('GITHUB_RUN_ID','0'),('GITHUB_RUN_ATTEMPT','not-a-number')]:
            env=dict(self.environment);env[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.prepare(env)
        self.git_run('remote','set-url','origin','https://example.invalid/foreign/repository')
        with self.assertRaises(RuntimeError):self.prepare()
        self.assertEqual(self.fetches,[])
    def test_changed_missing_and_symlink_manifests_fail_before_fetch(self):
        path=self.repo/history.MANIFEST;raw=path.read_bytes()
        path.write_bytes(raw+b'\n')
        with self.assertRaises(RuntimeError):self.prepare()
        path.unlink()
        with self.assertRaises(RuntimeError):self.prepare()
        target=self.repo/'different.json';target.write_bytes(raw);path.symlink_to(target)
        with self.assertRaises(RuntimeError):self.prepare()
        self.assertEqual(self.fetches,[])
    def test_a_successful_fetch_without_exact_objects_is_rejected(self):
        def incomplete(root,*args):
            if args[:1]==('fetch',):return subprocess.CompletedProcess(args,0,b'',b'')
            return self.real(root,*args)
        with self.assertRaises(history.MissingHistoricalObject):self.prepare(transport=incomplete)
    def test_actual_source_mutation_during_fetch_is_rejected(self):
        def mutation(root,*args):
            result=self.transport(root,*args)
            if args[:1]==('fetch',):(self.repo/'anchor.txt').write_text('changed source\n')
            return result
        with self.assertRaises(RuntimeError):self.prepare(transport=mutation)
    def test_counterfeit_object_bytes_never_trigger_an_accepting_fallback(self):
        for group in history.manifest(self.repo):self.seed(group['commit'])
        blob=next(iter(history.manifest(self.repo)[0]['files'].values()))['blob']
        def counterfeit(root,*args):
            result=self.real(root,*args)
            if args==('cat-file','blob',blob):return subprocess.CompletedProcess(args,0,result.stdout+b'counterfeit',b'')
            return result
        with self.assertRaises(RuntimeError):self.prepare(transport=counterfeit)
        self.assertEqual(self.fetches,[])
    def test_cli_and_workflow_disable_implicit_fetch_before_original_git_reads(self):
        environment=dict(os.environ);environment.pop('GIT_NO_LAZY_FETCH',None)
        code="import os,sys;sys.path.insert(0,sys.argv[1]);import prepare_baselines;print(os.environ.get('GIT_NO_LAZY_FETCH'))"
        value=subprocess.run([__import__('sys').executable,'-c',code,str(ROOT/'tools/browser')],capture_output=True,text=True,check=True,env=environment)
        self.assertEqual(value.stdout.strip(),'1')
        workflow=(ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text()
        self.assertIn("  GIT_NO_LAZY_FETCH: '1'\njobs:\n",workflow)

    def test_every_actual_git_process_has_lazy_fetch_disabled(self):
        real_run=subprocess.run;observed=[]
        def probe(*args,**kwargs):
            observed.append(kwargs['env'].get('GIT_NO_LAZY_FETCH'));return real_run(*args,**kwargs)
        with patch.object(history.subprocess,'run',side_effect=probe):
            history.git(self.repo,'cat-file','commit',self.head)
        self.assertEqual(observed,['1'])

if __name__=='__main__':unittest.main(verbosity=2)
