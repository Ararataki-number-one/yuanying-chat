"""Diagnostic enum boundaries only; no Android or native gate acceptance."""
import copy,importlib.util,json,os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'tools/browser'))
from run_gecko_ip_timezone_integration import extension_debug
NONCE='c'*32
SCRIPTS=['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js']
def payload():
 return dict(schema=1,diagnosticOnly=True,releaseAcceptance=False,requestNonce=NONCE,runtimeManifest=dict(available=True,version='2.1.2.104',id='browser@pocketchat.local',scriptCount=5,scripts=SCRIPTS),helperPresence=dict(bootstrap='object',headers='object',identity='object',timezone='object'),events=[dict(sequence=1,stage='before-request',urlClass='geo-host-variant',exactGeo=False,get=True,origin='own',document='absent',requestIdPresent=True,result='none',errorName='none')],omitted=0,invalid=0,bootstrapObject=True,bootstrapCreate=True,headersObject=True)
def changed():
 changes=[lambda d:d.update(requestNonce='d'*32),lambda d:d.update(rawUrl='https://secret.invalid'),lambda d:d.update(diagnosticOnly=False),lambda d:d.update(releaseAcceptance=True),lambda d:d.update(omitted=True),lambda d:d.update(events=d['events']*33),lambda d:d['events'][0].update(stage='secret'),lambda d:d['events'][0].update(errorName='private message'),lambda d:d['events'][0].update(origin='https://secret.invalid'),lambda d:d['events'][0].update(requestIdPresent=1),lambda d:d['events'][0].update(sequence=2),lambda d:d['runtimeManifest'].update(scripts=['/private/file']),lambda d:d['helperPresence'].update(identity='secret'),lambda d:d['events'][0].update(rawHeader='secret')]
 for change in changes:
  d=copy.deepcopy(payload());change(d);yield d
class Controls(unittest.TestCase):
 def test_independent_python_boundary_rejects_private_unknown_wrong_nonce_and_typed_overflow(self):
  self.assertEqual(extension_debug(dict(registered=True,accepted=1,rejected=0,latest=payload()),NONCE)['accepted'],1)
  for d in changed():
   with self.subTest(d=d):
    with self.assertRaises((ValueError,TypeError)):extension_debug(dict(registered=True,accepted=1,rejected=0,latest=d),NONCE)
 def test_actual_java_payload_validator_both_supplied_json_parsers(self):
  java=pathlib.Path(os.environ['PROFILE_JAVA']);jars=[pathlib.Path(os.environ[n]) for n in ('PROFILE_JSON_JAR','PROFILE_ANDROID_JSON_JAR')];self.assertTrue((java/'bin/javac').is_file() and all(p.is_file() for p in jars),'Real dependencies required; no skip')
  source=(ROOT/'tests/gecko/GeckoIpTimeZoneIntegrationActivity.java').read_text()
  def method(name):
   start=source.index('  static boolean '+name+'(');a=source.index('{',start);depth=1;i=a+1;quote=None;escape=False
   while depth:
    c=source[i]
    if quote:
     if escape:escape=False
     elif c=='\\':escape=True
     elif c==quote:quote=None
    elif c in ('"',"'"):quote=c
    elif c=='{':depth+=1
    elif c=='}':depth-=1
    i+=1
   return source[start:i]
  actual=method('diagnosticKeys')+'\n'+method('extensionDiagnosticPayload');values=[payload(),*changed()]
  with tempfile.TemporaryDirectory(prefix='ip-diagnostic-java-') as tmp:
   p=pathlib.Path(tmp);cases=p/'cases.json';cases.write_text(json.dumps(values));host=p/'Host.java';host.write_text('import org.json.*;import java.util.*;public final class Host {\n'+actual+'\npublic static void main(String[]a)throws Exception{JSONArray cases=new JSONArray(new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(a[0])),java.nio.charset.StandardCharsets.UTF_8));for(int i=0;i<cases.length();i++)if(extensionDiagnosticPayload(cases.getJSONObject(i),"'+NONCE+'")!=(i==0))throw new AssertionError("case"+i);System.out.println("actualJavaPayloadControls="+cases.length());}}')
   for index,jar in enumerate(jars):
    out=p/str(index);out.mkdir();subprocess.run([str(java/'bin/javac'),'-cp',str(jar),'-d',str(out),str(host)],check=True,capture_output=True);r=subprocess.run([str(java/'bin/java'),'-cp',str(out)+os.pathsep+str(jar),'Host',str(cases)],check=True,capture_output=True,text=True);self.assertIn('actualJavaPayloadControls=15',r.stdout)
class ConsoleControls(unittest.TestCase):
 def test_only_bound_native_pid_and_whitelisted_enum_json_are_exported(self):
  from run_gecko_ip_timezone_integration import console_debug
  binding=dict(runNonce=NONCE,sourceCommit='a'*40,integrationApkSha256='b'*64)
  process=b'PID UID NAME\n120 10200 local.pocketchat.test:profile6\n121 10200 local.pocketchat.test:gecko_env6_tab0_disable_art_image_\n999 10201 foreign.app\n'
  event=payload()['events'][0];value=dict(schema=1,diagnosticOnly=True,releaseAcceptance=False,event=event)
  def line(pid,v):return ('11-05 17:00:00.000 '+str(pid)+' 122 I GeckoConsole: POCKET_IP_TZ_DIAG4 '+json.dumps(v)+'\n').encode()
  raw=line(120,value)+line(999,value)+line(121,dict(value,rawHeader='private secret'))+b'Unrelated secret log\n'
  result=console_debug(raw,process,binding,dict(processPid=120,processUid=10200));self.assertEqual(len(result['events']),1);self.assertEqual(result['rejectedOrOmitted'],2);self.assertFalse(result['wholeLogcatExported']);self.assertNotIn('private secret',json.dumps(result));self.assertNotIn('Unrelated',json.dumps(result));self.assertEqual(result['binding'],binding)
  for identity in (dict(processPid=121,processUid=10200),dict(processPid=120,processUid=10201)):
   with self.assertRaises(ValueError):console_debug(raw,process,binding,identity)
 def test_isolated_gecko_child_requires_actual_native_package_association(self):
  from run_gecko_ip_timezone_integration import console_debug
  binding=dict(runNonce=NONCE);ps=b'PID UID NAME\n120 10200 local.pocketchat.test:profile6\n121 99001 local.pocketchat.test:gecko_env6_tab0_disable_art_image_\n122 99002 local.pocketchat.test:gecko_env5_tab0_disable_art_image_\n'
  value=dict(schema=1,diagnosticOnly=True,releaseAcceptance=False,event=payload()['events'][0]);raw=('11-05 17:00:00.000 121 122 I GeckoConsole: POCKET_IP_TZ_DIAG4 '+json.dumps(value)+'\n').encode();owner=dict(processPid=120,processUid=10200)
  absent=console_debug(raw,ps,binding,owner);self.assertEqual(absent['events'],[]);self.assertEqual(absent['unverifiedProcessCount'],1)
  proof=dict(pid=121,uid=99001,role='gecko-env6');present=console_debug(raw,ps,binding,owner,[proof]);self.assertEqual(len(present['events']),1);self.assertEqual(present['events'][0]['pid'],121)
  for bad in (dict(proof,pid=122),dict(proof,uid=99002),dict(proof,role='profile6')):
   self.assertEqual(console_debug(raw,ps,binding,owner,[bad])['events'],[])
 def test_poll_and_sdk_reflection_are_typed_and_unavailable_is_explicit(self):
  v=dict(registered=True,accepted=0,rejected=0,latest={},hello=0,poll=dict(count=1,ineligible=1,eligible=False,portPresent=False,extensionSame=False,runtimeSame=False,attempted=0,returned=0,threw=0,consoleEnabled=False,processPid=120,processUid=10200),port=dict(present=False,id=None,disconnected=None,listenersRegistered=None,dispatcherPresent=False,dispatcherAttached=None,pendingMessages=None))
  self.assertEqual(extension_debug(v,NONCE),v)
  for mutate in (lambda x:x['poll'].update(rawError='secret'),lambda x:x['port'].update(disconnected=0),lambda x:x['poll'].update(returned=True),lambda x:x['port'].update(pendingMessages=10001)):
   bad=copy.deepcopy(v);mutate(bad)
   with self.assertRaises(ValueError):extension_debug(bad,NONCE)
if __name__=='__main__':unittest.main()
