#!/usr/bin/env python3
"""Run the complete blank-preparation helper on a JVM; never Android evidence."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/gecko/GeckoLocalDraftIntegration.java'
HELPER=ROOT/'tests/gecko/GeckoLocalDraftBlankBarrier.java'
HOST=ROOT/'tests/local-draft-blank-host'
BASE_SOURCE='509336d2bd42b4d2346854a4f9da2c016d150a1a'
BASE_FIXTURE_SHA='8a3e31921ebe063dc65e8d681c4378688b4088168c8b35dcdee6668f0afaeea9'
spec=importlib.util.spec_from_file_location('f04_blank_member',ROOT/'tests/page-recovery-host/run.py')
members=importlib.util.module_from_spec(spec);spec.loader.exec_module(members)
NEW_MEMBERS={
    'void startBlank(':'e78aa83ab76e4024d51b07fa9d3c5ccbafa0b3012f72177cff712002c1adb858',
    'void closeBlank(':'632061783be465c5352e3d0d7bcdb33b63c96406e6c19c5e66c2d396aa4e3070',
    'void observeFailure(':'91b717bacb13f04e4cf9717f741a828b2a6c1328e79913344fca0be8aa23e426',
}
UNCHANGED_MEMBERS={
    'GeckoLocalDraftIntegration(GeckoIntegrationTestActivity activity,long command)':'8eaffd6112c0f2e299374d73e58e654714a4d5553e2df512b2a4dc74423f0e39',
    'void probe(java.util.function.Consumer<JSONObject> done)':'4c2cf887398ff6263c0db4ba0dbaa3a8c68ace1159a68028663c88a5f14cf0e4',
    'void waitSeed(boolean fresh)':'bc6b74516a7e2136956e8cca35fdb7c73a7200e5b33141e540434fa92680e2b7',
    'void awaitCaptured(boolean fresh)':'0834c1db675234553eb41e0f5a0228290595747aec26766829019b864246ed7f',
    'void storeCaptured(String payload,JSONObject source,JSONObject dom,boolean fresh)':'2bc12ef4d4bb83a713c4d7b1ee96ab93f696ec19a903a87eb12a71db22202dec',
    'void awaitRestored(boolean fresh)':'6350f73e7922a795a39faf4a5e55e739e253ddff7bb2b6846aa8d5d57379cec8',
    'static JSONObject restoreChecks(':'03f127fd3ccb5d53e48a0a1c0c331b9bb181956b5289b657f7e367d152110c09',
    'static String canonical(Object value)':'066b96a326b5bfffc887ad23fd354ee24217342105d6d82e5cbacafc298ecdb8',
}

def digest(raw):return hashlib.sha256(raw).hexdigest()

def undo_blank_preparation(text):
    """Invert only this exact reviewed preparation; preserve the entire 509 fixture."""
    def replace_once(current,new,old):
        if current.count(new)!=1:raise ValueError('Exact unique F04 insertion missing: '+new[:80])
        return current.replace(new,old,1)
    for needle,expected in NEW_MEMBERS.items():
        if text.count(needle)!=1:raise ValueError('Exact unique F04 helper missing: '+needle)
        body=members.member(text,needle)
        if digest(body.encode('utf-8'))!=expected:raise ValueError('F04 preparation helper changed: '+needle)
        text=replace_once(text,'  '+body+'\n','')
    changes=(
        ('  GeckoLocalDraftBlankBarrier blankBarrier;\n',''),
        ('s.handler.postDelayed(()->{if(!current())closeBlank();if(current())try{task.run();}',
         's.handler.postDelayed(()->{if(current())try{task.run();}'),
        ('store.io.shutdown();post(()->{observeRestoreRead(filtered);startBlank(restored,fresh);});',
         'store.io.shutdown();post(()->{observeRestoreRead(filtered);observeStage("restore-load-blank");s.web.loadUrl("about:blank");waitBlank(restored,fresh);});'),
        ('    if(blankBarrier==null||!blankBarrier.ready()){if(current())later(()->waitBlank(state,fresh));return;}\n',
         '    if(!"about:blank".equals(s.web.getUrl())){later(()->waitBlank(state,fresh));return;}\n'),
        ('    JSONObject proof=blankBarrier.proof();NetworkCatalog.put(result,"blankBarrier",proof);retainPartial("restoreBarrier",proof.toString());closeBlank();\n',''),
        ('result.put("status","passed").put("actualGeckoSessionState",true);closeBlank();finished=true;',
         'result.put("status","passed").put("actualGeckoSessionState",true);finished=true;'),
        ('"restoreReadiness","restoreBarrier","sdkCurrent","sdkCurrentOwner"','"restoreReadiness"'),
        ('void fail(Throwable error){if(!current())return;observeFailure();closeBlank();finished=true;',
         'void fail(Throwable error){if(!current())return;finished=true;'),
    )
    for new,old in changes:text=replace_once(text,new,old)
    if digest(text.encode('utf-8'))!=BASE_FIXTURE_SHA:raise ValueError('Original 509 F04 fixture changed outside exact preparation')
    return text


class BlankBarrierControls(unittest.TestCase):
    host_report=None

    def test_complete_helper_runs_all_owned_and_foreign_callback_controls(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java,'JDK17 compiler/runtime is required for actual helper controls')
        jar=Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/gecko-integration/catalog-json.jar'))
        self.assertTrue(jar.is_file(),'PROFILE_JSON_JAR or the existing CI catalog-json.jar is required')
        files=[HELPER,ROOT/'app/src/main/java/local/pocketchat/J.java',*sorted(HOST.rglob('*.java'))]
        hashes={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in files}
        with tempfile.TemporaryDirectory(prefix='f04-blank-helper-') as temporary:
            compile_run=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8',
                '-cp',str(jar.resolve()),'-d',temporary,*map(str,files)],capture_output=True,text=True)
            self.assertEqual(compile_run.returncode,0,compile_run.stdout+compile_run.stderr)
            executed=subprocess.run([java,'-cp',temporary+os.pathsep+str(jar.resolve()),'local.pocketchat.BlankBarrierHost'],capture_output=True,text=True)
            self.assertEqual(executed.returncode,0,executed.stdout+executed.stderr)
        value=json.loads(executed.stdout)
        self.assertEqual(value['status'],'passed');self.assertEqual(value['checks'],96)
        self.assertEqual(len(value['results']),96)
        self.assertTrue(all(row['pass'] is True for row in value['results']))
        self.assertEqual(len({row['name'] for row in value['results']}),96)
        self.assertIs(value['actualAndroidExecution'],False);self.assertIs(value['actualGeckoExecution'],False)
        self.assertTrue(all(digest((ROOT/p).read_bytes())==h for p,h in hashes.items()))
        value.update(sourceFiles=hashes,jsonJarSha256=digest(jar.read_bytes()),
                     compileStdout=compile_run.stdout,compileStderr=compile_run.stderr,
                     runtimeStdout=executed.stdout,runtimeStderr=executed.stderr,
                     executionInputsUnchanged=True)
        type(self).host_report=value

    def test_exact_inverse_retains_entire_original_fixture_and_original_waits(self):
        current=FIXTURE.read_text(encoding='utf-8');restored=undo_blank_preparation(current)
        self.assertEqual(digest(restored.encode()),BASE_FIXTURE_SHA)
        for needle,expected in UNCHANGED_MEMBERS.items():
            self.assertEqual(digest(members.member(current,needle).encode()),expected,needle)
        for original in ('elapsedRealtime()+40000','}},100);','stableSamples<5','now-stableAt<1000',
                         'dom.optInt("history",-1)==prefs.getInt(name+"History",-2)',
                         's.web.restoreCheckpoint(s.web.current,state,prefs.getString(name+"Url",""),readRevision);'):
            self.assertEqual(current.count(original),restored.count(original),original)
            self.assertGreater(current.count(original),0)

    def test_original_readiness_payload_deadline_and_poll_mutations_are_rejected(self):
        original=FIXTURE.read_text(encoding='utf-8')
        changes=[('elapsedRealtime()+40000','elapsedRealtime()+41000'),('}},100);','}},101);'),
                 ('stableSamples<5','stableSamples<4'),('now-stableAt<1000','now-stableAt<999'),
                 ('dom.optBoolean("ok")&&','true&&'),('==prefs.getInt(name+"History",-2)','>=0'),
                 ('&&sameCookies(dom.optString("cookie"),prefs.getString(name+"Cookie",""))',''),
                 ('&&s.web.painted.contains(s.web.current)',''),('&&!s.web.failed',''),
                 ('if(!fresh)expected.remove("formdata");','expected.remove("formdata");'),
                 ('if(fresh?!payload.equals(filtered):safe.has("formdata"))','if(false)'),
                 ('s.web.restoreCheckpoint(s.web.current,state,prefs.getString(name+"Url",""),readRevision);',
                  's.web.loadUrl(target);')]
        for old,new in changes:
            with self.subTest(old=old):
                self.assertIn(old,original)
                with self.assertRaises(ValueError):undo_blank_preparation(original.replace(old,new,1))

    def test_inverse_rejects_owner_shortcuts_duplicate_calls_and_hidden_actions(self):
        original=FIXTURE.read_text(encoding='utf-8')
        changes=[('&&s.connectionEpoch==connection',''),
                 ('&&nonce.equals(a.getIntent().getStringExtra("eventNonce"))',''),
                 ('&&!s.web.pendingLoads.contains(owned)',''),
                 ('},SystemClock::elapsedRealtime,this::fail);','},SystemClock::elapsedRealtime,error->{});'),
                 ('startBlank(restored,fresh);','startBlank(restored,fresh);startBlank(restored,fresh);'),
                 ('!blankBarrier.ready()','false'),
                 ('closeBlank();finished=true;','finished=true;'),
                 ('    observeRestored(fresh,dom,ready,now);','    observeRestored(fresh,dom,ready,now);ready=true;'),
                 ('void observeFailure(){try{','void observeFailure(){try{s.web.checkpointState();'),
                 ('    s.web.loadUrl(blankBarrier.uri);waitBlank(state,fresh);','    s.web.loadUrl(blankBarrier.uri);s.web.loadUrl(target);waitBlank(state,fresh);')]
        for old,new in changes:
            with self.subTest(old=old):
                self.assertIn(old,original)
                with self.assertRaises(ValueError):undo_blank_preparation(original.replace(old,new,1))

    def test_failure_snapshot_is_cache_only_and_cannot_restore_reload_or_flush(self):
        text=FIXTURE.read_text(encoding='utf-8');body=members.member(text,'void observeFailure(')
        self.assertIn('s.web.states.get(current)',body)
        self.assertIn('new GeckoSession.SessionState(cached).toString()',body)
        for forbidden in ('evaluateJavascript(','.loadUrl(','.restoreCheckpoint(','.flushSessionState(','.checkpointState(',
                          '.post(','.postDelayed(','.edit(','.apply(','.commit(','.setActive('):
            self.assertNotIn(forbidden,body)
        self.assertIn('"cacheOnly",true,"diagnosticOnly",true,"acceptance",false',body)


if __name__=='__main__':
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--json-jar',type=Path)
    parser.add_argument('--output',type=Path)
    arguments,remaining=parser.parse_known_args()
    if arguments.json_jar:os.environ['PROFILE_JSON_JAR']=str(arguments.json_jar.resolve())
    program=unittest.main(argv=[sys.argv[0],*remaining],exit=False)
    if arguments.output:
        inputs=[Path(__file__).resolve(),FIXTURE,ROOT/'tests/page-recovery-host/run.py',HELPER,
                ROOT/'app/src/main/java/local/pocketchat/J.java',*sorted(HOST.rglob('*.java'))]
        result=dict(schema=1,status='passed' if program.result.wasSuccessful() else 'failed',
                    pythonControls=program.result.testsRun,helper=BlankBarrierControls.host_report,
                    sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
                    sourceFiles={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs},
                    originalFixtureSource=BASE_SOURCE,originalFixtureSha256=BASE_FIXTURE_SHA,
                    actualAndroidExecution=False,actualGeckoExecution=False,releaseAcceptance=False,
                    scope='Complete helper JVM behavior and exact original-fixture preservation controls only')
        arguments.output.parent.mkdir(parents=True,exist_ok=True)
        arguments.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
