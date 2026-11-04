"""Restore the actual incremental baseline graph into an isolated shallow repository."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class BaselineBundleTests(unittest.TestCase):
    def test_missing_local_history_restores_without_checkout(self):
        metadata=json.loads((ROOT/'tests/baselines/local-performance-history.json').read_text())
        with tempfile.TemporaryDirectory(prefix='browser-baseline-restore-') as temporary:
            repo=Path(temporary)
            def git(*args):return subprocess.check_output(['git',*args],cwd=repo,stderr=subprocess.PIPE,text=True).strip()
            git('init','-q');git('fetch','--no-tags','--depth=1',str(ROOT),metadata['prerequisite']);git('update-ref','HEAD',metadata['prerequisite'])
            self.assertNotEqual(subprocess.run(['git','cat-file','-e',metadata['requiredCommits']['f43adac']],cwd=repo,capture_output=True).returncode,0)
            (repo/'tools/browser').mkdir(parents=True);(repo/'tests/baselines').mkdir(parents=True)
            shutil.copy2(ROOT/'tools/browser/prepare_baselines.py',repo/'tools/browser/prepare_baselines.py')
            for name in ['local-performance-history.bundle','local-performance-history.json']:shutil.copy2(ROOT/'tests/baselines'/name,repo/'tests/baselines'/name)
            before=git('status','--porcelain');result=repo/'work/result.json'
            subprocess.run(['python3',str(repo/'tools/browser/prepare_baselines.py'),'--output',str(result)],cwd=repo,check=True,capture_output=True)
            report=json.loads(result.read_text());self.assertEqual(report['status'],'passed');self.assertTrue(report['headAndWorkingTreeUnchanged'])
            self.assertEqual(git('rev-parse','HEAD'),metadata['prerequisite'])
            # The report is outside the source comparison; ignore that generated work path.
            after=git('status','--porcelain');self.assertEqual(before,after.replace('?? work/\n','').replace('?? work/','').rstrip())
            for short,commit in metadata['requiredCommits'].items():self.assertEqual(git('rev-parse',short+'^{commit}'),commit)
            self.assertFalse((repo/'app').exists(),'Restoring test objects must not check out baseline sources')

if __name__=='__main__':unittest.main(verbosity=2)
