"""Execute the actual CI publisher against isolated local Git repositories.

Binary/APK-path bytes are synthetic inputs. These controls cover bounded Git
fetch, ancestry, and publication byte identity; no APK or Android validation.
No external remote or user checkout is written by these tests.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / 'tools/gecko/publish_ci.py'
BRANCH = 'apk/gecko-integration-build-20261003'
REF = 'refs/heads/' + BRANCH
GIT = shutil.which('git')

GIT_WRAPPER = r'''
import json,os,subprocess,sys
args=sys.argv[1:]
with open(os.environ['PUBLISH_TEST_GIT_LOG'],'a',encoding='utf-8') as stream:
    stream.write(json.dumps(args)+'\n')
real=os.environ['PUBLISH_TEST_REAL_GIT']
if os.environ.get('PUBLISH_TEST_MODE')=='fetch-failure' and args and args[0]=='fetch':
    sys.stderr.write('Synthetic local artifact fetch failure\n')
    sys.exit(91)
result=subprocess.run([real,*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
observation=dict(arguments=args,returnCode=result.returncode,stdoutHex=result.stdout.hex(),stderrHex=result.stderr.hex())
if (result.returncode==0 and os.environ.get('PUBLISH_TEST_MODE')=='drift'
    and args==['ls-remote','origin',os.environ['PUBLISH_TEST_ARTIFACT_REF']]
    and result.stdout.decode().split()==[os.environ['PUBLISH_TEST_PREVIOUS_SHA'],os.environ['PUBLISH_TEST_ARTIFACT_REF']]):
    # Advance only the observation of the original tip. The retry observes
    # the new tip and must not repeat a stale compare-and-swap in this fixture.
    changed=subprocess.run([real,'--git-dir',os.environ['PUBLISH_TEST_REMOTE'],'update-ref',
        os.environ['PUBLISH_TEST_ARTIFACT_REF'],os.environ['PUBLISH_TEST_RACE_SHA'],
        os.environ['PUBLISH_TEST_PREVIOUS_SHA']],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if changed.returncode:
        sys.stderr.buffer.write(changed.stderr);sys.exit(changed.returncode)
    observation['injectedRemoteAdvance']=dict(previous=os.environ['PUBLISH_TEST_PREVIOUS_SHA'],current=os.environ['PUBLISH_TEST_RACE_SHA'])
if result.returncode==0 and args and args[0]=='fetch':
    observation['fetchedHeadBeforeFault']=subprocess.check_output([real,'rev-parse','FETCH_HEAD']).decode().strip()
    if os.environ.get('PUBLISH_TEST_MODE')=='fetch-head-mismatch':
        # A real local FETCH_HEAD modification after the real fixed-SHA fetch,
        # not fabricated rev-parse output and not a production fetch retry.
        path=subprocess.check_output([real,'rev-parse','--git-path','FETCH_HEAD']).decode().strip()
        with open(path,'rb') as stream:before=stream.read()
        source=subprocess.check_output([real,'rev-parse','HEAD']).strip()
        after=source+b'\t\tSynthetic test-only concurrent FETCH_HEAD modification\n'
        with open(path,'wb') as stream:stream.write(after)
        observation['injectedFetchHeadChange']=dict(beforeHex=before.hex(),afterHex=after.hex())
    observation['fetchedHeadAfterFault']=subprocess.check_output([real,'rev-parse','FETCH_HEAD']).decode().strip()
with open(os.environ['PUBLISH_TEST_GIT_LOG']+'.results','a',encoding='utf-8') as stream:
    stream.write(json.dumps(observation)+'\n')
sys.stdout.buffer.write(result.stdout);sys.stderr.buffer.write(result.stderr)
sys.exit(result.returncode)
'''


class BoundedPublisherTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(GIT,'Git is required for local publication controls')
        self.temporary = tempfile.TemporaryDirectory(prefix='publish-bounded-history-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.seed,self.remote,self.client = self.base/'seed',self.base/'remote.git',self.base/'client'
        self.environment = dict(os.environ,GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME='Synthetic publisher test',GIT_AUTHOR_EMAIL='publisher-test@example.invalid',
            GIT_COMMITTER_NAME='Synthetic publisher test',GIT_COMMITTER_EMAIL='publisher-test@example.invalid')
        for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE'):
            self.environment.pop(key,None)
        self.git('init','--initial-branch=main',str(self.seed))
        self.git('init','--bare','--initial-branch=main',str(self.remote))
        (self.seed/'tools/gecko').mkdir(parents=True)
        shutil.copy2(PUBLISHER,self.seed/'tools/gecko/publish_ci.py')
        shutil.copy2(PUBLISHER.with_name('ci_git_publish.py'),self.seed/'tools/gecko/ci_git_publish.py')
        shutil.copy2(PUBLISHER.with_name('network_scope_artifacts.py'),self.seed/'tools/gecko/network_scope_artifacts.py')
        (self.seed/'app').mkdir()
        (self.seed/'app/build.gradle').write_text("android { defaultConfig { versionName '2.0.0'; versionCode 53 } }\n")
        (self.seed/'.gitignore').write_text('work/\napp/build/\n')
        self.source_bytes = b'Selected synthetic source evidence; preserve exact bytes.\n'
        (self.seed/'source-evidence.txt').write_bytes(self.source_bytes)
        self.git('add','.',cwd=self.seed)
        self.git('commit','-m','Synthetic selected source',cwd=self.seed)
        self.source = self.git('rev-parse','HEAD',cwd=self.seed).stdout.strip()
        self.git('remote','add','origin',str(self.remote),cwd=self.seed)
        self.git('push','origin','HEAD:refs/heads/main',cwd=self.seed)
        self.wrapper_dir = self.base/'git-bin'
        self.wrapper_dir.mkdir()
        wrapper = self.wrapper_dir/'git'
        wrapper.write_text('#!'+sys.executable+'\n'+GIT_WRAPPER)
        wrapper.chmod(0o755)
        self.command_log = self.base/'publisher-git-commands.jsonl'
        self.command_log.write_text('')
        self.previous = self.old = self.old_blob = self.current_blob = None

    def git(self,*arguments,cwd=None,check=True,env=None,input=None):
        return subprocess.run([GIT,*arguments],cwd=cwd,env=env or self.environment,input=input,
                              text=True,capture_output=True,check=check,timeout=30)

    def remote_git(self,*arguments,check=True):
        return self.git('--git-dir',str(self.remote),*arguments,check=check)

    def history_commit(self,files,parents):
        work = self.base/'history-tree'
        if work.exists():
            shutil.rmtree(work)
        work.mkdir()
        for name,body in files.items():
            (work/name).write_bytes(body)
        environment = dict(self.environment,GIT_INDEX_FILE=str(self.base/'history-index'),GIT_WORK_TREE=str(work))
        self.git('read-tree','--empty',cwd=self.seed,env=environment)
        self.git('add','-f','--',*files,cwd=self.seed,env=environment)
        tree = self.git('write-tree',cwd=self.seed,env=environment).stdout.strip()
        parent_args = [argument for parent in parents for argument in ('-p',parent)]
        return self.git('commit-tree',tree,*parent_args,'-m','Synthetic historical artifact',cwd=self.seed,env=environment).stdout.strip()

    def prepare(self,history=True):
        if history:
            old_bytes = hashlib.sha256(b'obsolete synthetic binary seed').digest()*8192
            self.old = self.history_commit({'obsolete-fixture-binary.bin':old_bytes,'manifest.json':b'{"synthetic":"old"}\n'},[self.source])
            self.old_blob = self.git('rev-parse',self.old+':obsolete-fixture-binary.bin',cwd=self.seed).stdout.strip()
            self.previous = self.history_commit({'current-artifact-fixture.bin':b'Current prior artifact bytes\n',
                'manifest.json':b'{"synthetic":"previous"}\n'},[self.source,self.old])
            self.current_blob = self.git('rev-parse',self.previous+':current-artifact-fixture.bin',cwd=self.seed).stdout.strip()
            self.git('push','origin',self.previous+':'+REF,cwd=self.seed)
            self.git('tag','obsolete-artifact-tag',self.old,cwd=self.seed)
            self.git('tag','current-artifact-tag',self.previous,cwd=self.seed)
            self.git('push','origin','--tags',cwd=self.seed)
        # file:// and --no-local enforce real depth semantics rather than the
        # object hardlinks used by Git's optimized local-path clone.
        self.git('clone','--no-local','--single-branch','--branch','main','--depth=1','--no-tags',
                 self.remote.as_uri(),str(self.client))
        # Remove clone's persistent tag policy so the publisher's own --no-tags
        # must prevent auto-following the tag on the fetched artifact tip.
        self.git('config','--unset','remote.origin.tagOpt',cwd=self.client)
        apk = self.client/'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk'
        apk.parent.mkdir(parents=True)
        self.apk_bytes = b'SYNTHETIC-NOT-AN-APK\0'+bytes(range(256))*37
        apk.write_bytes(self.apk_bytes)
        output = self.client/'work/gecko-integration'
        (output/'caret-compat').mkdir(parents=True)
        self.evidence_bytes = (json.dumps(dict(sourceCommit=self.source,scope='synthetic local publisher control',
            actualAndroidExecution=False,text='Exact Unicode evidence 中文🙂'),ensure_ascii=False,indent=2)+'\n').encode()
        (output/'gecko-performance-results.json').write_bytes(self.evidence_bytes)
        self.caret_bytes = b'{"status":"synthetic-host-control","actualAndroidExecution":false}\n'
        (output/'caret-compat/gecko-caret-compat-results.json').write_bytes(self.caret_bytes)
        self.diagnostic_bytes = {}
        for name,folder in [('installed-apk-read-performance-before.json',output),
                            ('installed-apk-read-performance-after.json',output),
                            ('editing-phase-environment.json',output),
                            ('installed-apk-read-caret.json',output/'caret-compat')]:
            body = (json.dumps(dict(status='failed',sourceCommit=self.source,
                scope='Synthetic localhost provider-read control',origin='http://127.0.0.1:8771',
                diagnosticFile=name,error='Synthetic provider read 失败🙂',
                stdout='原始 stdout 中文🙂\nsecond line\n',stderr='Exact synthetic diagnostic error\n',
                hostSpace=dict(availableBytes=0,totalBytes=131072,path='/tmp/synthetic localhost read host'),
                actualAndroidExecution=False,actualGeckoExecution=False,applicationAcceptance=False,
                controlledCaretCompatibilityAcceptance=False,releaseAcceptance=False,physicalPhoneAcceptance=False),
                ensure_ascii=False,indent=3)+'\n\n').encode('utf-8')
            self.diagnostic_bytes[name] = body
            (folder/name).write_bytes(body)
        self.failure_bytes = {
            'gecko-caret-compat-failure-window.txt':
                'Synthetic localhost window diagnostic; no actual Android focus\n原始窗口🙂\n\n'.encode('utf-8'),
            'gecko-caret-compat-failure-activity.txt':
                'Synthetic localhost activity diagnostic; no actual Android process\r\n原始 activity🙂\r\n'.encode('utf-8'),
            'gecko-caret-compat-failure-screen.png':
                b'SYNTHETIC-PNG-PATH-BYTES-NOT-AN-IMAGE\x00'+bytes(range(256)),
            'gecko-caret-compat-failure-ui.xml':
                ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<synthetic-host-control origin="http://127.0.0.1:8771" actualAndroidExecution="false" '
                 'applicationAcceptance="false">原始 UI🙂</synthetic-host-control>\n').encode('utf-8')}
        for name,body in self.failure_bytes.items():
            (output/'caret-compat'/name).write_bytes(body)

    def publish(self,mode=None,race=None):
        environment = dict(self.environment,PATH=str(self.wrapper_dir)+os.pathsep+os.environ.get('PATH',''),
            GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='2',PUBLISH_TEST_GIT_LOG=str(self.command_log),
            PUBLISH_TEST_REAL_GIT=GIT,PUBLISH_TEST_REMOTE=str(self.remote),PUBLISH_TEST_ARTIFACT_REF=REF)
        if mode:
            environment['PUBLISH_TEST_MODE'] = mode
        if race:
            environment.update(PUBLISH_TEST_RACE_SHA=race,PUBLISH_TEST_PREVIOUS_SHA=self.previous)
        return subprocess.run([sys.executable,str(self.client/'tools/gecko/publish_ci.py')],cwd=self.client,
                              env=environment,text=True,capture_output=True,timeout=60)

    def commands(self):
        return [json.loads(line) for line in self.command_log.read_text().splitlines()]

    def published(self):
        return self.remote_git('rev-parse',REF).stdout.strip()

    def assert_source_preserved(self):
        self.assertEqual(self.git('rev-parse','HEAD',cwd=self.client).stdout.strip(),self.source)
        self.assertEqual(self.git('show',self.source+':source-evidence.txt',cwd=self.client).stdout.encode(),self.source_bytes)
        self.assertEqual(self.git('status','--porcelain',cwd=self.client).stdout,'')

    def test_existing_artifact_history_fetch_is_bounded_and_remote_ancestry_is_preserved(self):
        self.prepare()
        result = self.publish()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        current = self.published()
        self.assertEqual(self.remote_git('show','-s','--format=%P',current).stdout.strip().split(),[self.source,self.previous])
        self.assertEqual(self.git('cat-file','-e',self.old,cwd=self.client,check=False).returncode,1)
        self.assertEqual(self.git('cat-file','-e',self.old_blob,cwd=self.client,check=False).returncode,1)
        self.assertEqual(self.git('cat-file','-e',self.current_blob,cwd=self.client,check=False).returncode,0)
        self.assertEqual(self.git('show-ref','--tags',cwd=self.client,check=False).returncode,1)
        self.assertEqual(self.remote_git('merge-base','--is-ancestor',self.old,current,check=False).returncode,0)
        self.assertEqual(self.remote_git('merge-base','--is-ancestor',self.previous,current,check=False).returncode,0)
        self.assertEqual(self.remote_git('cat-file','-e',self.old_blob,check=False).returncode,0)
        self.assertEqual(self.remote_git('rev-parse','refs/tags/obsolete-artifact-tag').stdout.strip(),self.old)
        self.assertEqual(self.remote_git('rev-parse','refs/tags/current-artifact-tag').stdout.strip(),self.previous)
        self.assert_source_preserved()

    def test_current_manifest_chunks_and_source_evidence_keep_exact_byte_identity(self):
        self.prepare()
        result = self.publish()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        current = self.published()
        stage = self.client/'work/gecko-integration/public'
        remote_manifest = subprocess.check_output([GIT,'--git-dir',str(self.remote),'show',current+':manifest.json'],env=self.environment)
        self.assertEqual(remote_manifest,(stage/'manifest.json').read_bytes())
        manifest = json.loads(remote_manifest)
        self.assertEqual({key:manifest[key] for key in ('sourceCommit','runId','runAttempt','version','versionCode','googleLogin')},
            dict(sourceCommit=self.source,runId='12345',runAttempt='2',version='2.0.0',versionCode=53,googleLogin='not-tested'))
        self.assertEqual(len(manifest['artifacts']),1)
        artifact = manifest['artifacts'][0]
        self.assertEqual({key:artifact[key] for key in ('abi','bytes','sha256','signing')},dict(abi='arm64-v8a',
            bytes=len(self.apk_bytes),sha256=hashlib.sha256(self.apk_bytes).hexdigest(),signing='unsigned'))
        joined = b''
        for part in artifact['chunks']:
            body = subprocess.check_output([GIT,'--git-dir',str(self.remote),'show',current+':'+part['file']],env=self.environment)
            self.assertEqual(body,(stage/part['file']).read_bytes())
            self.assertEqual(len(body),part['bytes']);self.assertEqual(hashlib.sha256(body).hexdigest(),part['sha256'])
            joined += body
        self.assertEqual(joined,self.apk_bytes)
        for name,body in [('gecko-performance-results.json',self.evidence_bytes),('gecko-caret-compat-results.json',self.caret_bytes)]:
            published = subprocess.check_output([GIT,'--git-dir',str(self.remote),'show',current+':'+name],env=self.environment)
            self.assertEqual(published,body)
        self.assertEqual(self.remote_git('show',current+'^1:source-evidence.txt').stdout.encode(),self.source_bytes)
        self.assert_source_preserved()

    def test_first_publication_has_only_source_parent_and_never_fetches_artifact_history(self):
        self.prepare(history=False)
        result = self.publish()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.remote_git('show','-s','--format=%P',self.published()).stdout.strip(),self.source)
        self.assertFalse(any(command and command[0]=='fetch' for command in self.commands()))
        self.assert_source_preserved()

    def test_failed_read_diagnostics_are_published_flat_with_exact_original_bytes(self):
        self.prepare()
        result = self.publish()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        current = self.published()
        stage = self.client/'work/gecko-integration/public'
        paths = self.remote_git('ls-tree','-r','--name-only',current).stdout.splitlines()
        for name,expected in self.diagnostic_bytes.items():
            with self.subTest(name=name):
                self.assertIn(name,paths)
                self.assertNotIn('caret-compat/'+name,paths)
                raw = subprocess.check_output([GIT,'--git-dir',str(self.remote),'show',current+':'+name],env=self.environment)
                self.assertEqual(raw,expected)
                self.assertEqual((stage/name).read_bytes(),expected)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),hashlib.sha256(expected).hexdigest())
                value = json.loads(raw)
                self.assertEqual(value['status'],'failed')
                self.assertEqual(value['stdout'],'原始 stdout 中文🙂\nsecond line\n')
                self.assertEqual(value['hostSpace']['availableBytes'],0)
                for flag in ('actualAndroidExecution','actualGeckoExecution','applicationAcceptance',
                             'controlledCaretCompatibilityAcceptance','releaseAcceptance','physicalPhoneAcceptance'):
                    self.assertIs(value[flag],False)
        for name,expected in self.failure_bytes.items():
            with self.subTest(name=name):
                self.assertIn(name,paths)
                self.assertNotIn('caret-compat/'+name,paths)
                raw = subprocess.check_output([GIT,'--git-dir',str(self.remote),'show',current+':'+name],env=self.environment)
                self.assertEqual(raw,expected)
                self.assertEqual((stage/name).read_bytes(),expected)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),hashlib.sha256(expected).hexdigest())
        self.assert_source_preserved()

    def test_branch_advance_keeps_immutable_fetch_and_retries_same_tree_without_losing_history(self):
        self.prepare()
        prior_tree = self.git('rev-parse',self.previous+'^{tree}',cwd=self.seed).stdout.strip()
        race = self.git('commit-tree',prior_tree,'-p',self.source,'-p',self.previous,'-m','Synthetic concurrent artifact publication',cwd=self.seed).stdout.strip()
        self.git('push','origin',race+':refs/heads/race-object-holder',cwd=self.seed)
        result = self.publish(mode='drift',race=race)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.git('rev-parse','FETCH_HEAD',cwd=self.client).stdout.strip(),race)
        current = self.published()
        commands = self.commands()
        observations = [json.loads(line) for line in Path(str(self.command_log)+'.results').read_text().splitlines()]
        fetches = [row for row in observations if row['arguments'][0]=='fetch']
        pushes = [row for row in observations if 'push' in row['arguments']]
        commits = [row for row in observations if row['arguments'][0]=='commit-tree']
        self.assertEqual([row['arguments'] for row in fetches],
            [['fetch','--depth=1','--no-tags','origin',tip] for tip in (self.previous,race)])
        self.assertEqual([row['fetchedHeadBeforeFault'] for row in fetches],[self.previous,race])
        self.assertEqual([row['fetchedHeadAfterFault'] for row in fetches],[self.previous,race])
        self.assertEqual(sum('injectedRemoteAdvance' in row for row in observations),1)
        self.assertEqual(len(pushes),2);self.assertLessEqual(len(pushes),3)
        self.assertNotEqual(pushes[0]['returnCode'],0);self.assertEqual(pushes[1]['returnCode'],0)
        rejection=bytes.fromhex(pushes[0]['stderrHex']).decode()
        self.assertIn('[rejected]',rejection)
        self.assertTrue(any(marker in rejection for marker in ('fetch first','non-fast-forward')),rejection)
        self.assertEqual(len(commits),2)
        committed = [bytes.fromhex(row['stdoutHex']).decode().strip() for row in commits]
        self.assertEqual(current,committed[-1])
        trees = [self.git('rev-parse',commit+'^{tree}',cwd=self.client).stdout.strip() for commit in committed]
        self.assertEqual(trees[0],trees[1])
        self.assertEqual(sum(command[0]=='write-tree' for command in commands),1)
        self.assertEqual(sum(command[0]=='add' for command in commands),1)
        for commit,tip,row in zip(committed,(self.previous,race),commits):
            self.assertEqual(row['arguments'][1],trees[0])
            self.assertEqual(row['arguments'][2:6],['-p',self.source,'-p',tip])
            self.assertEqual(self.git('show','-s','--format=%P',commit,cwd=self.client).stdout.strip().split(),[self.source,tip])
        self.assertTrue(all(not any(value.startswith('--force') or value.startswith('+') for value in command) for command in commands))
        stage=self.client/'work/gecko-integration/public'
        self.assertEqual(set(self.remote_git('ls-tree','-r','--name-only',current).stdout.splitlines()),{path.name for path in stage.iterdir()})
        for path in stage.iterdir():
            published=subprocess.check_output([GIT,'--git-dir',str(self.remote),'show',current+':'+path.name],env=self.environment)
            self.assertEqual(published,path.read_bytes(),path.name)
        manifest=json.loads((stage/'manifest.json').read_bytes())
        self.assertEqual(manifest['sourceCommit'],self.source)
        self.assertEqual(b''.join((stage/part['file']).read_bytes() for part in manifest['artifacts'][0]['chunks']),self.apk_bytes)
        for tip in (self.source,self.old,self.previous,race):
            self.assertEqual(self.remote_git('merge-base','--is-ancestor',tip,current,check=False).returncode,0)
        self.assertEqual(self.git('cat-file','-e',self.old,cwd=self.client,check=False).returncode,1)
        self.assertEqual(self.git('cat-file','-e',self.old_blob,cwd=self.client,check=False).returncode,1)
        self.assertEqual(self.git('cat-file','-e',self.current_blob,cwd=self.client,check=False).returncode,0)
        self.assertEqual(self.git('show-ref','--tags',cwd=self.client,check=False).returncode,1)
        self.assertEqual(self.remote_git('cat-file','-e',self.old_blob,check=False).returncode,0)
        self.assertEqual(self.remote_git('rev-parse','refs/tags/obsolete-artifact-tag').stdout.strip(),self.old)
        self.assertEqual(self.remote_git('rev-parse','refs/tags/current-artifact-tag').stdout.strip(),self.previous)
        self.assert_source_preserved()

    def test_real_fetch_head_change_after_immutable_fetch_fails_before_any_commit_or_push(self):
        self.prepare()
        result=self.publish(mode='fetch-head-mismatch')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Fetched artifact commit differs from its immutable identity',result.stderr)
        self.assertEqual(self.published(),self.previous)
        self.assertEqual(self.git('rev-parse','FETCH_HEAD',cwd=self.client).stdout.strip(),self.source)
        commands=self.commands()
        self.assertEqual([row for row in commands if row[0]=='fetch'],
                         [['fetch','--depth=1','--no-tags','origin',self.previous]])
        self.assertEqual(sum(row[0]=='ls-remote' for row in commands),1)
        self.assertFalse(any('push' in command or 'commit-tree' in command for command in commands))
        observations=[json.loads(line) for line in Path(str(self.command_log)+'.results').read_text().splitlines()]
        fetched=[row for row in observations if row['arguments'][0]=='fetch']
        self.assertEqual(len(fetched),1)
        self.assertEqual(fetched[0]['fetchedHeadBeforeFault'],self.previous)
        self.assertEqual(fetched[0]['fetchedHeadAfterFault'],self.source)
        self.assertTrue(bytes.fromhex(fetched[0]['injectedFetchHeadChange']['beforeHex']).startswith(self.previous.encode()+b'\t'))
        self.assertEqual(bytes.fromhex(fetched[0]['injectedFetchHeadChange']['afterHex']),
                         (self.client/'.git/FETCH_HEAD').read_bytes())
        self.assertEqual(self.remote_git('merge-base','--is-ancestor',self.old,self.previous,check=False).returncode,0)
        self.assert_source_preserved()

    def test_failed_previous_fetch_cannot_publish_or_rewrite_remote_history(self):
        self.prepare()
        result = self.publish(mode='fetch-failure')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Synthetic local artifact fetch failure',result.stderr)
        self.assertEqual(self.published(),self.previous)
        self.assertFalse(any('push' in command or 'commit-tree' in command for command in self.commands()))
        self.assertEqual(self.remote_git('merge-base','--is-ancestor',self.old,self.previous,check=False).returncode,0)
        self.assert_source_preserved()


if __name__ == '__main__':
    unittest.main()
