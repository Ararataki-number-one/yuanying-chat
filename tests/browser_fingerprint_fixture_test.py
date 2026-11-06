"""Trust/transport scope checks only. These do not replace Android TLS execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


class BrowserFingerprintFixtureTests(unittest.TestCase):
    def test_actual_address_visibility_navigation_and_hidden_menu_controls(self):
        production=ROOT/'app/src/main/java/local/pocketchat';source=(production/'GeckoAddressUi.java').read_text();main=(production/'MainActivity.java').read_text()
        spec=importlib.util.spec_from_file_location('navigation_member_parser',ROOT/'tests/gecko-navigation-host/run.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
        needles=['String target(','String current(','static boolean visibleFor(','void refresh(','static boolean available(','static void home(']
        members='\n'.join(parser.member_at(source,source.index(needle)) for needle in needles)
        chat=parser.member_at(main,main.index('static boolean chatUrl('))
        self.assertIn('row.setVisibility(View.GONE)',source[:source.index('String target(')])
        for button in ('address','home'):self.assertIn(button+'.setSingleLine(true)',source)
        self.assertNotIn('setMinHeight(0)',source);self.assertNotIn('setMinimumHeight(0)',source)
        self.assertIn('option(d,"打开网址或搜索",()->GeckoAddressUi.show(this));',main)
        self.assertIn('if(geckoAddress!=null)geckoAddress.refresh();',parser.member_at(main,main.index('void applySession(')))
        show=parser.member_at(source,source.index('static void show('));self.assertNotIn('isShown(',show);self.assertNotIn('getVisibility(',show)
        self.assertIn('owner.refresh();',show);self.assertIn('if(a.geckoAddress!=null)a.geckoAddress.refresh();',parser.member_at(source,source.index('static void closeSites(')))
        program=r'''
package local.pocketchat;
import java.net.URI;
public final class AddressVisibilityHost {
  static int checks;
  static void check(String id,boolean value){if(!value)throw new AssertionError(id);checks++;}
  // Explicit JVM presentation/session/URI boundaries; no Android classes or SDK execution.
  static final class View {static final int VISIBLE=0,GONE=8;}
  static final class Row {int visibility=View.GONE,writes;int getVisibility(){return visibility;}void setVisibility(int v){visibility=v;writes++;}}
  static final class Label {String text="",description="";int writes;void setText(String s){text=s;writes++;}void setContentDescription(String s){description=s;}}
  static final class Web {String url="about:blank";String getUrl(){return url;}}
  static final class Session {boolean navigating;String navigationTarget="",resume="https://resume.example/";final Web web=new Web();String resumeUrl(){return resume;}void browse(String url,String label){navigating=true;navigationTarget=url;}}
  static final class BrowserPreferences {static String selected="https://chatgpt.com/";static String home(MainActivity a){return selected;}}
  static final class Uri {final URI uri;Uri(String s){uri=URI.create(s);}static Uri parse(String s){return new Uri(s);}String getScheme(){return uri.getScheme();}String getHost(){return uri.getHost();}String getUserInfo(){return uri.getUserInfo();}int getPort(){return uri.getPort();}}
  static final class MainActivity {Session session=new Session();Object remote=new Object();boolean destroyed,finishing;int reveals;GeckoAddressUi geckoAddress;boolean isFinishing(){return finishing;}void showPage(boolean b){reveals++;}@CHAT@}
  static final class GeckoAddressUi {final MainActivity a;final Row row=new Row();final Label address=new Label();String shown="";GeckoAddressUi(MainActivity a){this.a=a;a.geckoAddress=this;}@MEMBERS@}
  public static void main(String[] args){
    MainActivity a=new MainActivity();GeckoAddressUi ui=new GeckoAddressUi(a);
    check("Default presentation consumes no row",ui.row.getVisibility()==View.GONE);ui.refresh();check("About blank stays hidden",ui.row.getVisibility()==View.GONE);
    for(String url:new String[]{"https://chatgpt.com/","https://chatgpt.com:443/c/test#fragment","https://chatgpt.com/c/test?q=1#frag"}){a.session.web.url=url;ui.refresh();check("Official origin omitted",ui.row.getVisibility()==View.GONE);check("Hidden native row does not disable menu",GeckoAddressUi.available(a));check("Menu uses current official address",ui.current().equals(url));}
    for(String url:new String[]{"http://public.example/","https://public.example/path#fragment","http://chatgpt.com/","https://chatgpt.com.other.example/"}){a.session.web.url=url;ui.refresh();check("Ordinary public origin visible",ui.row.getVisibility()==View.VISIBLE);check("Visible address is actual current target",ui.address.text.endsWith(url));}
    check("HTTP warning stays meaningful",GeckoAddressUi.visibleFor("http://public.example/"));
    a.session.web.url="https://public.example/";ui.refresh();a.session.navigating=true;a.session.navigationTarget="https://chatgpt.com:443/c/new#frag";ui.refresh();check("Navigating public to ChatGPT hides in same event",ui.row.getVisibility()==View.GONE);check("Menu sees new target before native URL changes",ui.current().equals(a.session.navigationTarget));
    a.session.navigationTarget="http://next.example/";ui.refresh();check("Navigating back to public shows in same event",ui.row.getVisibility()==View.VISIBLE);check("HTTP target shows warning",ui.address.text.startsWith("HTTP 未加密 · "));
    int layouts=ui.row.writes,texts=ui.address.writes;for(int i=0;i<100;i++)ui.refresh();check("Repeated frame refresh avoids layout churn",ui.row.writes==layouts&&ui.address.writes==texts);
    a.session.navigating=false;for(String url:new String[]{"", "about:blank","javascript:void(0)","http://127.0.0.1/private","file:///private"}){a.session.web.url=url;ui.refresh();check("Empty live URL does not borrow public menu fallback",ui.row.getVisibility()==View.GONE);}
    check("Null target is hidden",!GeckoAddressUi.visibleFor(null));a.session.web.url=null;ui.refresh();check("Null native URL stays hidden",ui.row.getVisibility()==View.GONE);check("Empty live URL keeps menu resume prefill",ui.current().equals(a.session.resume));a.session.web.url="https://public.example/";a.session.navigating=true;a.session.navigationTarget="";ui.refresh();check("Empty pending target does not show stale public page",ui.row.getVisibility()==View.GONE);a.session=null;BrowserPreferences.selected="https://homepage.example/";ui.refresh();check("No-session startup remains hidden",ui.row.getVisibility()==View.GONE);check("Menu keeps homepage prefill",ui.current().equals(BrowserPreferences.selected));
    a.session=new Session();a.session.web.url="https://public.example/";ui.refresh();BrowserPreferences.selected="https://chatgpt.com/";GeckoAddressUi.home(a);check("Native home action synchronously hides ordinary address",ui.row.getVisibility()==View.GONE&&a.reveals==1&&a.session.navigationTarget.equals(BrowserPreferences.selected));
    a.destroyed=true;check("Destroyed owner cannot open menu",!GeckoAddressUi.available(a));a.destroyed=false;a.finishing=true;check("Finishing owner cannot open menu",!GeckoAddressUi.available(a));a.finishing=false;a.remote=null;check("Absent surface cannot open menu",!GeckoAddressUi.available(a));
    System.out.println("{\"checks\":"+checks+",\"actualAndroidExecution\":false,\"menuAvailableWhileHidden\":true}");
  }
}
'''.replace('@CHAT@',chat).replace('@MEMBERS@',members)
        java_home=Path(os.environ.get('JAVA_HOME',str(ROOT/'work/browser-ci-jdk/jdk-17.0.21+9')));javac=str(java_home/'bin/javac');java=str(java_home/'bin/java')
        with tempfile.TemporaryDirectory(prefix='address-visibility-host-') as folder:
            folder=Path(folder);path=folder/'AddressVisibilityHost.java';classes=folder/'classes'
            def execute(body):
                path.write_text(body);built=subprocess.run([javac,'--release','17','-encoding','UTF-8','-d',str(classes),str(path),str(production/'BrowserAddressPolicy.java'),str(production/'GeckoNavigationPolicy.java')],capture_output=True,text=True,timeout=30);self.assertEqual(built.returncode,0,built.stderr);return subprocess.run([java,'-cp',str(classes),'local.pocketchat.AddressVisibilityHost'],capture_output=True,text=True,timeout=20)
            passed=execute(program);self.assertEqual(passed.returncode,0,passed.stderr);result=json.loads(passed.stdout);self.assertGreaterEqual(result['checks'],40)
            mutations=[('&&!MainActivity.chatUrl(url)','', 'Official origin omitted'),('a.session.navigating?a.session.navigationTarget:a.session.web.getUrl()','a.session.web.getUrl()','Navigating public to ChatGPT hides in same event'),('String url=target();int visibility=','String url=current();int visibility=','Empty live URL does not borrow public menu fallback')]
            for before,after,failure in mutations:
                self.assertEqual(program.count(before),1);mutant=execute(program.replace(before,after,1));self.assertNotEqual(mutant.returncode,0);self.assertIn('AssertionError: '+failure,mutant.stderr)
            print(json.dumps(dict(scope='Extracted exact production target/current/visibility/refresh/home/availability and chatUrl methods on explicit JVM view/session/URI boundaries; real address policy sources, no Android or Gecko execution',**result,mutationControls=len(mutations))))

    def test_runner_pins_all_required_source_inputs_that_actually_exist(self):
        def load(name,path):
            spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        runner=load('fingerprint_runner_inputs','tools/browser/run_fingerprint_integration.py');checker=load('fingerprint_checker_inputs','tools/browser/check_fingerprint_evidence.py')
        paths=runner.source_inputs();self.assertEqual(paths,sorted(set(paths)))
        self.assertTrue(all(path.is_file() and path.is_relative_to(ROOT) for path in paths))
        self.assertLessEqual(checker.SOURCE_INPUTS,{str(path.relative_to(ROOT)) for path in paths})

    def test_release_resources_do_not_trust_synthetic_ca(self):
        production=ROOT/'app/src/main/res';config=(production/'xml/network_security.xml').read_text()
        self.assertNotIn('browser_fingerprint',config);self.assertNotIn('pocketchat.test',config)
        self.assertNotIn('src="user"',config)
        for path in production.rglob('*'):
            if path.is_file():self.assertNotIn(b'PUBLIC synthetic browser fixture CA',path.read_bytes())
        build=(ROOT/'app/build.gradle').read_text();self.assertRegex(build,r"integration\s*\{[^\n]*res.srcDirs\s*=\s*\['../tests/gecko/res'\]")
        self.assertNotRegex(build,r"main\s*\{[^\n]*(?:tests/gecko|browser-fingerprint-trust)")

    def test_integration_ca_only_trusts_exact_reserved_synthetic_hosts(self):
        root=ET.parse(ROOT/'tests/gecko/res/xml/network_security.xml').getroot();trusted=[]
        self.assertEqual(root.find('base-config').attrib,{'cleartextTrafficPermitted':'true'})
        self.assertIsNone(root.find('debug-overrides'));self.assertIsNone(root.find('base-config/trust-anchors'))
        for config in root.findall('domain-config'):
            anchors=config.find('trust-anchors')
            if anchors is not None:
                self.assertEqual(config.attrib,{'cleartextTrafficPermitted':'true'})
                self.assertEqual([c.attrib for c in anchors], [{'src':'system'},{'src':'user'}])
                for domain in config.findall('domain'):self.assertEqual(domain.attrib,{'includeSubdomains':'false'});trusted.append(domain.text)
        self.assertEqual(set(trusted),{'fp-a.pocketchat.test','fp-b.pocketchat.test'});self.assertEqual(len(trusted),2)

    def test_no_bundled_fingerprint_key_or_fixed_trust_material(self):
        java=(ROOT/'tests/gecko/BrowserFingerprintFixture.java').read_text()
        self.assertFalse(list((ROOT/'tests/gecko/assets/browser-fingerprint-trust').glob('*')))
        self.assertFalse((ROOT/'tests/gecko/res/raw/browser_fingerprint_ca.pem').exists())
        for forbidden in ('PKCS12','KeyManagerFactory','SSLContext','server.p12','CA_SHA','LEAF_SHA','ServerSocket'):
            self.assertNotIn(forbidden,java)
        self.assertIn('expectedLeafSha256',java);self.assertIn('publicCaPemSha256',java)
        self.assertIn('Current host fixture binding required',java)

    def test_no_tls_exception_or_public_forwarding_path(self):
        java=(ROOT/'tests/gecko/BrowserFingerprintFixture.java').read_text();activity=(ROOT/'tests/gecko/BrowserFingerprintIntegrationActivity.java').read_text();host=(ROOT/'tools/browser/fingerprint_fixture_server.py').read_text()
        self.assertNotRegex(java+activity,r'\.proceed\s*\(|setHostnameVerifier|setDefaultSSLSocketFactory|ALLOW_ALL_HOSTNAME|TrustAll|X509TrustManager')
        self.assertNotIn('new Socket(',java);self.assertIn('openConnection(Proxy.NO_PROXY)',java)
        self.assertIn('http://127.0.0.1:',java);self.assertIn("bind(('127.0.0.1',0))",host)
        self.assertNotIn('create_connection(',host);self.assertNotIn('.connect(',host)
        self.assertIn("target in tuple(host+':443' for host in HOSTS)",host)
        self.assertIn('threading.BoundedSemaphore(12)',host)
        self.assertIn("TemporaryDirectory(prefix='pocketchat-fingerprint-tls-',dir='/tmp')",host)
        self.assertNotIn("CERT_NONE",host);self.assertNotIn('check_hostname=False',host)

    def test_shell_report_is_allowlisted_and_no_screenshot_transport(self):
        provider=(ROOT/'tests/gecko/BrowserFingerprintEvidenceProvider.java').read_text();runner=(ROOT/'tools/browser/run_fingerprint_integration.py').read_text()
        self.assertIn('Binder.getCallingUid()!=2000',provider);self.assertIn('file.length()>1024*1024',provider);self.assertIn('"/chromium".equals(uri.getPath())',provider);self.assertIn('"/gecko".equals(uri.getPath())',provider)
        for forbidden in ('screencap','logcat','getCookie','pageSource','localStorage','sessionStorage','attachments/'):
            self.assertNotIn(forbidden,runner)
        self.assertNotIn("/'results.json'",runner);self.assertIn("/'browser-fingerprint-results.json'",runner)
        self.assertIn("re.search(r\"versionName '([^']+)'\",settings)",runner)

    def test_components_are_integration_only_and_names_are_valid(self):
        integration=(ROOT/'tests/gecko/AndroidManifest.xml').read_text();main=(ROOT/'app/src/main/AndroidManifest.xml').read_text()
        for name in ('BrowserFingerprintIntegrationActivity','BrowserFingerprintEvidenceProvider'):
            self.assertIn(name,integration);self.assertNotIn(name,main)
        for affinity in re.findall(r'android:taskAffinity="([^"]+)"',integration):self.assertRegex(affinity,r'^[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)+$')


if __name__=='__main__':unittest.main(verbosity=2)
