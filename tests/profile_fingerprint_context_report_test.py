"""Actual production AuditReport context model with preserved captured browser values."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'app/src/main/java/local/pocketchat/AuditReport.java'
HOST=ROOT/'tests/fingerprint-context-report-host/FingerprintContextReportHost.java'
FIXTURE=ROOT/'tests/fingerprint-context-report-host/actual-chromium-contexts-v1.json'
STUBS=[ROOT/'tests/browser-runtime/fingerprint-report-stubs/J.java',ROOT/'tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java']
PINS={'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796':'desktop-json','3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed':'desktop-json','dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79':'android-json'}
FIXTURE_SHA256='8f406de1468f05140319b564aa8cd136bded8affe0ab8053d063c0d9288f2073'
COUNT=77
MUTANT_FAILURE='Actual Worker canvas with zero audio font limits remains available'


def jars():
    candidates=[os.environ.get('PROFILE_JSON_JAR'),os.environ.get('PROFILE_ANDROID_JSON_JAR'),ROOT/'work/profile-host/json.jar',ROOT/'work/profile-host/android-json.jar',ROOT/'work/gecko-integration/catalog-json.jar',ROOT/'work/gecko-integration/sharing-android-json.jar']
    selected={}
    for value in candidates:
        if not value or not Path(value).is_file():continue
        path=Path(value);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in PINS:raise AssertionError('Unexpected JSON runtime dependency')
        selected.setdefault(PINS[digest],path)
    if set(selected)!={'desktop-json','android-json'}:raise RuntimeError('Both pinned desktop and Android JSON runtimes are required for these host controls')
    return selected


def compiler_java():
    configured=os.environ.get('PROFILE_JAVA')
    if configured:return configured
    local=Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')
    return str(local) if local.is_file() else shutil.which('java')


class FingerprintContextReportTest(unittest.TestCase):
    def test_real_captured_contexts_and_labelled_boundary_controls(self):
        sources=[MODEL,HOST,FIXTURE,*STUBS,Path(__file__)]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        self.assertEqual(before[str(FIXTURE.relative_to(ROOT))],FIXTURE_SHA256)
        fixture=json.loads(FIXTURE.read_text());self.assertTrue(fixture['capture']['actualChromiumExecution']);self.assertFalse(fixture['capture']['actualGeckoExecution']);self.assertEqual(fixture['sample']['nonce'],'context-browser-case')
        actual=MODEL.read_text();mutant=actual
        for old,new in [('exactNumber(limits.opt("audioFrames"),worker?0:2048)','exactNumber(limits.opt("audioFrames"),2048)'),('exactNumber(limits.opt("fontCandidates"),worker?0:5)','exactNumber(limits.opt("fontCandidates"),5)')]:
            self.assertEqual(mutant.count(old),1,'Model change requires review of the explicitly labelled historical-limit mutant')
            mutant=mutant.replace(old,new)
        self.assertNotEqual(mutant,actual)
        java=compiler_java();self.assertTrue(java,'JDK17+ required for --release8 model compilation');records=[]
        for runtime,jar in jars().items():
            for variant,text in [('current',actual),('historical-worker-limit-mutant',mutant)]:
                with tempfile.TemporaryDirectory(prefix='fingerprint-context-report-') as directory:
                    directory=Path(directory);model=directory/'AuditReport.java';model.write_text(text);classes=directory/'classes';classes.mkdir()
                    command=[java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',str(jar),'-d',str(classes),str(model),*map(str,STUBS),str(HOST)]
                    compile_run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30);self.assertEqual(compile_run.returncode,0,compile_run.stdout+compile_run.stderr)
                    run=subprocess.run([java,'-cp',str(classes)+os.pathsep+str(jar),'local.pocketchat.FingerprintContextReportHost',str(FIXTURE)],cwd=ROOT,capture_output=True,text=True,timeout=15)
                    row=dict(jsonRuntime=runtime,jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(),variant=variant,modelSha256=hashlib.sha256(text.encode()).hexdigest(),compilerRelease=8,compileReturnCode=compile_run.returncode,compileStdout=compile_run.stdout,compileStderr=compile_run.stderr,runtimeReturnCode=run.returncode,runtimeStdout=run.stdout,runtimeStderr=run.stderr)
                    if variant=='current':
                        self.assertEqual(run.returncode,0,run.stdout+run.stderr);report=json.loads(run.stdout);self.assertEqual(report['status'],'passed');self.assertEqual(report['total'],COUNT);self.assertEqual(report['passed'],COUNT);self.assertEqual(len(report['checks']),COUNT);self.assertTrue(all(x['pass'] is True for x in report['checks']));self.assertFalse(report['actualAndroidExecution']);self.assertFalse(report['actualGeckoExecution']);self.assertFalse(report['actualChromiumExecution']);self.assertTrue(report['usesPreviouslyCapturedActualChromiumInput']);row['report']=report
                    else:
                        self.assertNotEqual(run.returncode,0,'Historical wrong Worker operation limits must fail the captured-input positive control');self.assertIn('AssertionError: '+MUTANT_FAILURE,run.stderr);row['expectedFailure']=MUTANT_FAILURE;row['isExplicitSourceMutationNotAnOldCommitExecution']=True
                    records.append(row)
        self.assertEqual(before,{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'Selected model and test inputs changed during controls')
        receipt=dict(schema=1,status='passed',sourceSha256=before,executionInputsUnchanged=True,actualAndroidExecution=False,actualGeckoExecution=False,actualChromiumExecution=False,usesPreviouslyCapturedActualChromiumInput=True,currentControlCountPerJsonRuntime=COUNT,historicalLimitMutantRejectedPerJsonRuntime=True,capture=fixture['capture'],runs=records,scope='Production Java AuditReport on pinned JVM JSON runtimes with captured browser values and labelled input/source mutants. No new browser, native lifecycle freshness or privacy-effectiveness acceptance.')
        output=ROOT/'work/coverage-context-report/results.json';output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():
            old=output.read_bytes();archive=output.parent/'previous-executions'/(hashlib.sha256(old).hexdigest()+'.json');archive.parent.mkdir(exist_ok=True)
            if archive.exists():self.assertEqual(archive.read_bytes(),old)
            else:archive.write_bytes(old)
        output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':unittest.main()
