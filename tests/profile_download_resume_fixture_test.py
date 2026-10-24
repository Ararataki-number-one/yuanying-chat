#!/usr/bin/env python3
"""Exact production Cookie/download methods and fixture callbacks; JVM/loopback only."""
import ast,copy,hashlib,importlib.util,json,os,pathlib,shutil,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/gecko/DownloadResumeIntegrationActivity.java'
HERE=ROOT/'tests/download-resume-fixture-host'
spec=importlib.util.spec_from_file_location('f06_exact_members',ROOT/'tests/download-resume-host/run.py')
member_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(member_module)
member=member_module.member
sha=lambda raw:hashlib.sha256(raw).hexdigest()
OLD_VIEW='''static final class OldFixtureView extends GeckoWebView {
    OldFixtureView(Context context,ChatSession owner){super(context,owner);}
    @Override public String getUrl(){return PAGE;}
    @Override protected boolean allowedUrl(String url){return false;}
  }'''

def undo_fixture(text):
    rules=json.loads((HERE/'fixture-preservation.json').read_text())
    for row in reversed(rules['changes']):
        if text.count(row['after'])!=1:raise ValueError('Exact unique fixture change missing')
        text=text.replace(row['after'],row['before'],1)
    if sha(text.encode())!=rules['originalSha256']:raise ValueError('Original fixture changed outside approved adapter/observation')
    return text

class DownloadResumeFixtureControls(unittest.TestCase):
    host_report=None
    def test_exact_production_cookie_wait_and_http_download_with_owned_callbacks(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java');self.assertTrue(java,'Java17 required')
        candidates=[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')]
        jar=next((pathlib.Path(p) for p in candidates if p and pathlib.Path(p).is_file()),None);self.assertIsNotNone(jar,'Existing host JSON dependency required')
        production=ROOT/'app/src/main/java/local/pocketchat'
        source=(production/'GeckoWebView.java').read_text();download=(production/'FileDownloads.java').read_text();fixture=FIXTURE.read_text()
        selected={'READ_COOKIES':member(source,'void readCookies('),'DOWNLOAD_COOKIES':member(source,'String downloadCookies('),
                  'VALID':member(download,'boolean valid('),'DOWNLOAD':member(download,'void download('),
                  'FIXTURE_VIEW':member(fixture,'static final class FixtureView'), 'ENDPOINT':member(fixture,'static final class Endpoint'), 'OLD_FIXTURE_VIEW':OLD_VIEW, 'SHA':member(fixture,'static String sha('), 'OBSERVE_FAILURE':member(fixture,'void observeRangeFailure(')}
        files=[production/n for n in ('GeckoWebView.java','FileDownloads.java','J.java','DownloadRange.java','SealedFileIo.java')]
        files += [FIXTURE,HERE/'CookieFixtureHost.java.in',HERE/'fixture-preservation.json',pathlib.Path(__file__),ROOT/'tests/download-resume-host/run.py',ROOT/'tests/sealed-file-host/android/util/AtomicFile.java',ROOT/'tests/download-recovery-host/android/os/Handler.java',ROOT/'tests/download-recovery-host/android/os/Looper.java',ROOT/'tests/download-recovery-host/android/net/Uri.java',ROOT/'tests/download-resume-host/stubs/android/util/Base64.java',ROOT/'tests/download-resume-host/stubs/android/os/SystemClock.java']
        hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in files}
        with tempfile.TemporaryDirectory(prefix='f06-cookie-controls-') as temporary:
            out=pathlib.Path(temporary);pkg=out/'local/pocketchat';pkg.mkdir(parents=True)
            raw=(HERE/'CookieFixtureHost.java.in').read_text()
            for key,value in selected.items():raw=raw.replace('/* '+key+' */',value)
            (pkg/'CookieFixtureHost.java').write_text(raw)
            for name in ('J.java','DownloadRange.java','SealedFileIo.java'):(pkg/name).write_bytes((production/name).read_bytes())
            stub=out/'android/webkit/ValueCallback.java';stub.parent.mkdir(parents=True);stub.write_text('package android.webkit;public interface ValueCallback<T>{void onReceiveValue(T value);}')
            inputs=list(pkg.glob('*.java'))+[stub]+files[-6:]
            compiled=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-cp',str(jar),'-d',str(out),*map(str,inputs)],text=True,capture_output=True,timeout=40)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            ran=subprocess.run([java,'-cp',str(out)+os.pathsep+str(jar),'local.pocketchat.CookieFixtureHost'],text=True,capture_output=True,timeout=45)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            value=json.loads(ran.stdout);self.assertEqual(value['status'],'passed');self.assertEqual(value['checkCount'],57)
            self.assertEqual(value['checkCount'],len(value['checks']));self.assertTrue(all(r['pass'] is True for r in value['checks']))
            self.assertIs(value['actualAndroidExecution'],False);self.assertIs(value['actualGeckoExecution'],False)
            value.update(sourceFiles=hashes,selectedMethodsSha256={k:sha(v.encode()) for k,v in selected.items()},jsonJarSha256=sha(jar.read_bytes()),compileStdout=compiled.stdout,compileStderr=compiled.stderr,runtimeStdout=ran.stdout,runtimeStderr=ran.stderr,
                sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
                scope='Exact production readCookies/downloadCookies/valid/download, real DownloadRange/SealedFileIo/J, actual fixture callback and endpoint on host JVM. Controlled Android/owner/publication adapters; real loopback HTTP. No Android, Gecko Cookie bridge, TLS/WAN or MediaStore acceptance.')
            self.assertTrue(all(sha((ROOT/p).read_bytes())==h for p,h in hashes.items()));value['inputsUnchanged']=True
            type(self).host_report=value
            report=os.environ.get('F06_COOKIE_HOST_REPORT')
            if report:pathlib.Path(report).parent.mkdir(parents=True,exist_ok=True);pathlib.Path(report).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

    def test_exact_inverse_retains_original_fixture_checks_actions_and_timeouts(self):
        current=FIXTURE.read_text();old=undo_fixture(current)
        for needle in ('void exercise(', 'void retirement(', 'void oldWriter(', 'void protectedRows(', 'void runDriver(', 'void cleanup('):
            # exercise only appends a new truthful callback report field.
            selected=member(current,needle)
            if needle=='void exercise(':selected=selected.replace('.put("syntheticCookieReads",syntheticCookieReads)','')
            self.assertEqual(selected,member(old,needle),needle)
        self.assertEqual(current.count('10000'),old.count('10000'));self.assertEqual(current.count('done.get(10,TimeUnit.SECONDS)'),1)
        self.assertEqual(member(current,'void download(') if 'void download(' in current else None,None,'Production transfer must not be overridden by fixture')

    def test_old_guards_and_success_mutations_are_rejected(self):
        current=FIXTURE.read_text()
        for a,b in [('socket.setSoTimeout(10000)','socket.setSoTimeout(10001)'),('client.setSoTimeout(10000)','client.setSoTimeout(10001)'),('endpoint.done.get(10,TimeUnit.SECONDS)','endpoint.done.get(11,TimeUnit.SECONDS)'),('Arrays.equals(expected,actual)','true'),('range(206);range(200);','range(200);'),('d.valid(d.ticket)','true'),('callback.onReceiveValue("")','callback.onReceiveValue("secret")'),('"ownedCleanupCompleted",true','"ownedCleanupCompleted",false')]:
            self.assertIn(a,current)
            with self.subTest(mutation=a),self.assertRaises(ValueError):undo_fixture(current.replace(a,b,1))

    def test_embedded_profile_guard_rejects_incomplete_or_forged_host_receipts(self):
        source=(ROOT/'tools/gecko/run_profile_host_checks.py').read_text()
        main=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='main')
        start=next(i for i,node in enumerate(main.body) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='resume_fixture' for t in node.targets))
        group=ast.Module(body=main.body[start:start+4],type_ignores=[])
        self.assertIsInstance(group.body[-1],ast.If)
        code=compile(ast.fix_missing_locations(group),'<exact profile F06 guard>','exec')
        with tempfile.TemporaryDirectory() as directory:
            base=pathlib.Path(directory);jar=base/'json.jar';jar.write_bytes(b'explicit synthetic parser fixture')
            owned=base/'fixture.java';owned.write_bytes(b'explicit synthetic source input')
            report=base/'report.json';checks=[dict(name='synthetic-'+str(i),**{'pass':True}) for i in range(57)]
            raw=dict(status='passed',checkCount=57,checks=checks,actualAndroidExecution=False,actualGeckoExecution=False,actualLoopbackHttp=True)
            value=dict(raw,inputsUnchanged=True,sourceCommit='a'*40,jsonJarSha256=sha(jar.read_bytes()),sourceFiles={'fixture.java':sha(owned.read_bytes())},runtimeStdout=json.dumps(raw))
            def verify(candidate):
                report.write_text(json.dumps(candidate));exec(code,dict(json=json,hashlib=hashlib,ROOT=base,resume_fixture_receipt=report,
                    json_jar=jar,source_id='a'*40,resume_fixture_inputs={owned},before_hashes={owned:sha(owned.read_bytes())}))
            verify(value)
            changes=[lambda v:v.update(checkCount=56),lambda v:v['checks'].pop(),lambda v:v['checks'][0].update({'pass':False}),
                lambda v:v['checks'][0].update({'pass':1}),lambda v:v['checks'][1].update(name=v['checks'][0]['name']),
                lambda v:v.update(actualAndroidExecution=True),lambda v:v.update(actualGeckoExecution=True),
                lambda v:v.update(actualLoopbackHttp=False),lambda v:v.update(inputsUnchanged=False),
                lambda v:v.update(sourceCommit='b'*40),lambda v:v.update(sourceFiles={}),lambda v:v.update(jsonJarSha256='0'*64),
                lambda v:v.update(runtimeStdout='{}'),lambda v:v.update(runtimeStdout=v['runtimeStdout'].replace('true','1'))]
            for change in changes:
                candidate=copy.deepcopy(value);change(candidate)
                with self.assertRaises((ValueError,KeyError)):verify(candidate)

if __name__=='__main__':unittest.main()
