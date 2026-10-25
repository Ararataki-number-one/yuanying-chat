"""Parser/transport controls with explicitly synthetic receipts; no Android evidence."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('release_host_transport',ROOT/'tools/gecko/run_profile_host_checks.py')
HOST=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(HOST)
CONTRACT=runpy.run_path(str(ROOT/'tests/network-transport-client-host/run.py'))
SOURCE='a'*40;TREE='b'*40
FILES={'app/src/main/java/local/pocketchat/J.java':'c'*64,'app/src/main/java/local/pocketchat/NetworkTransportClient.java':'d'*64}


def client_fixture():
    """Synthetic complete parser fixture; timeout number is not a measured result."""
    value=dict(status='passed',passed=92,sourceIdentity=dict(sourceCommit=SOURCE,sourceTree=TREE,sourceDirty=False,sourceFiles=FILES),
        oldFailuresReproduced=True,executionInputsUnchanged=True,fullSelectedClass=True,beforeRef=CONTRACT['BEFORE'],
        beforeClientSha256=CONTRACT['BEFORE_CLIENT_SHA256'],sharedWholeJsonHelperSha256=FILES['app/src/main/java/local/pocketchat/J.java'],
        actualAndroidExecution=False,actualBinderExecution=False,actualServiceExecution=False,jsonJarSha256=HOST.ANDROID_JSON_SHA256,
        validationErrors=[],beforeFailuresRequired=sorted(CONTRACT['KNOWN_OLD_FAILURES']),runs=[])
    names=sorted(CONTRACT['KNOWN_OLD_FAILURES'])+['synthetic-parser-control-%d'%i for i in range(84)]
    for name in ('before','current'):
        failed=8 if name=='before' else 0
        report=dict(status='failed' if failed else 'passed',checkCount=92,failedCount=failed,
            checks=[dict(name=n,**{'pass':i>=failed}) for i,n in enumerate(names)],
            cases=[dict(case=n,failedChecks=failed if i==0 else 0) for i,n in enumerate(sorted(CONTRACT['CASE_NAMES']))],
            replyTimeoutObservation=dict(configuredTimeoutSeconds=15,observedElapsedNanos=15000000000,
                exceptionClass='java.util.concurrent.TimeoutException',requestId='0'*8+'-'+ '0'*4+'-'+ '0'*4+'-'+ '0'*4+'-'+ '0'*12),
            actualAndroidExecution=False,actualBinderExecution=False,actualServiceExecution=False)
        row=dict(name=name,sourceCommit=SOURCE if name=='current' else CONTRACT['BEFORE'],
            clientSha256=FILES['app/src/main/java/local/pocketchat/NetworkTransportClient.java'] if name=='current' else CONTRACT['BEFORE_CLIENT_SHA256'],
            compileExitCode=0,exitCode=1 if failed else 0,report=report,
            rawCompileStdout='',rawCompileStderr='',rawStdout=json.dumps(report),rawStderr='')
        row['rawStreamMetadata']={k:dict(utf8Bytes=len(row[k].encode()),sha256=hashlib.sha256(row[k].encode()).hexdigest())
            for k in ('rawCompileStdout','rawCompileStderr','rawStdout','rawStderr')}
        value['runs'].append(row)
    return value


class ReleaseHostTransportTest(unittest.TestCase):
    def verify(self,value):
        return HOST.verify_client_json_run(value,SOURCE,TREE,False,FILES,HOST.ANDROID_JSON_SHA256,CONTRACT)

    def test_complete_receipt_retains_both_original_streams(self):
        value=client_fixture();self.assertIs(self.verify(value),value)
        self.assertEqual([r['name'] for r in value['runs']],['before','current'])

    def test_source_jar_scope_count_and_old_failure_mutations_are_rejected(self):
        for change in (
            lambda v:v.update(passed=True),lambda v:v.update(jsonJarSha256='0'*64),
            lambda v:v.update(actualAndroidExecution=True),lambda v:v.update(beforeFailuresRequired=[]),
            lambda v:v.update(oldFailuresReproduced=False),lambda v:v.update(runs=v['runs'][1:]),
            lambda v:v['sourceIdentity'].update(sourceDirty=0),lambda v:v['sourceIdentity'].update(sourceCommit='0'*40),
            lambda v:v['sourceIdentity'].update(sourceFiles={}),lambda v:v['runs'][1].update(sourceCommit='0'*40),
            lambda v:v['runs'][0].update(clientSha256='0'*64),lambda v:v['runs'][1].update(rawStdout='{}'),
            lambda v:v['runs'][1].update(rawStderr='changed'),lambda v:v['runs'][1].update(exitCode=1)):
            value=copy.deepcopy(client_fixture());change(value)
            with self.subTest(change=change),self.assertRaises(ValueError):self.verify(value)

    def test_raw_boolean_integer_alias_is_rejected_after_valid_stream_hash(self):
        value=client_fixture();row=value['runs'][1];raw=copy.deepcopy(row['report']);raw['actualAndroidExecution']=0
        row['rawStdout']=json.dumps(raw);data=row['rawStdout'].encode()
        row['rawStreamMetadata']['rawStdout']=dict(utf8Bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        with self.assertRaises(ValueError):self.verify(value)

    def test_stability_full_before_candidate_raw_roundtrip_and_missing_streams(self):
        value={}
        for key,count in (('candidate',25),('before',2)):
            row=dict(checkCount=count,checks=[{'name':key+str(i),'pass':True} for i in range(count)],actualAndroidExecution=False)
            value[key]=dict(row,runtimeStdout=json.dumps(row),runtimeStderr='',compileStdout='',compileStderr='')
        self.assertIs(HOST.verify_stability_raw(value),value)
        for variant in value:
            for stream in ('runtimeStdout','runtimeStderr','compileStdout','compileStderr'):
                mutated=copy.deepcopy(value);del mutated[variant][stream]
                with self.subTest(variant=variant,stream=stream),self.assertRaises(ValueError):HOST.verify_stability_raw(mutated)
            mutated=copy.deepcopy(value);mutated[variant]['actualAndroidExecution']=0
            with self.assertRaises(ValueError):HOST.verify_stability_raw(mutated)

    def optional(self,root):
        return HOST.run_optional_android_client(root,root/'out','/jdk/bin/java',root/'actual-runner.py',SOURCE,TREE,False,FILES,CONTRACT)

    def test_absent_android_dependency_is_explicit_not_run_without_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(HOST.subprocess,'run') as run:
            result=self.optional(Path(tmp));self.assertEqual(result['status'],'not-run');run.assert_not_called()
            self.assertIs(result['actualAndroidExecution'],False);self.assertNotIn('evidence',result)

    def test_invalid_and_dangling_android_dependency_cannot_claim_not_run_or_pass(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(HOST.subprocess,'run') as run:
            root=Path(tmp);jar=root/'work/gecko-integration/sharing-android-json.jar';jar.parent.mkdir(parents=True)
            jar.write_bytes(b'wrong jar')
            with self.assertRaises(ValueError):self.optional(root)
            jar.unlink();jar.symlink_to(root/'missing')
            with self.assertRaises(ValueError):self.optional(root)
            run.assert_not_called()

    def test_optional_branch_keeps_raw_report_and_fails_execution_or_post_run_jar_change(self):
        # The subprocess is a controlled parser fixture here. A separate recorded
        # integration run executes the real before/current JVM producer.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=root/'work/gecko-integration/sharing-android-json.jar';jar.parent.mkdir(parents=True)
            raw=b'synthetic jar for branch plumbing';jar.write_bytes(raw);(root/'out').mkdir()
            digest=hashlib.sha256(raw).hexdigest();value=client_fixture();value['jsonJarSha256']=digest
            (root/'out/network-transport-client-android-host-results.json').write_text(json.dumps(value))
            with patch.object(HOST,'ANDROID_JSON_SHA256',digest),patch.object(HOST.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'raw stdout','raw stderr')) as run:
                result=self.optional(root);self.assertEqual(result['evidence'],value);self.assertEqual(result['output'],'raw stdoutraw stderr')
                self.assertEqual(run.call_args.args[0][-4:],['--json-jar',str(jar),'--output',str(root/'out/network-transport-client-android-host-results.json')])
            with patch.object(HOST,'ANDROID_JSON_SHA256',digest),patch.object(HOST.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'original failure','original stderr')):
                with self.assertRaisesRegex(ValueError,'original failureoriginal stderr'):self.optional(root)
            def changed(*args,**kwargs):
                jar.write_bytes(b'changed during execution');return subprocess.CompletedProcess([],0,'','')
            with patch.object(HOST,'ANDROID_JSON_SHA256',digest),patch.object(HOST.subprocess,'run',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'changed during paired execution'):self.optional(root)

    def test_actual_profile_group_keeps_complete_evidence_and_original_counts(self):
        tree=ast.parse((ROOT/'tools/gecko/run_profile_host_checks.py').read_text())
        groups={}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict':
                kw={k.arg:k.value for k in node.keywords}
                if isinstance(kw.get('test'),ast.Constant):groups[kw['test'].value]=kw
        self.assertEqual(ast.literal_eval(groups['local-draft-restoration-stability-host']['passed']),27)
        self.assertEqual(ast.dump(groups['local-draft-restoration-stability-host']['evidence']),ast.dump(ast.Name(id='draft_stability',ctx=ast.Load())))
        self.assertEqual(ast.literal_eval(groups['network-transport-client-host']['passed']),92)
        self.assertEqual(ast.dump(groups['network-transport-client-host']['androidJson']),ast.dump(ast.Name(id='android_client',ctx=ast.Load())))


if __name__=='__main__':unittest.main()
