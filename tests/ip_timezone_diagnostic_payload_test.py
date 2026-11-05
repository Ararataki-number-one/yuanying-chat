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
if __name__=='__main__':unittest.main()
