"""Trust/transport scope checks only. These do not replace Android TLS execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


class BrowserFingerprintFixtureTests(unittest.TestCase):
    def test_actual_browser_address_navigation_and_history_controls(self):
        production=ROOT/'app/src/main/java/local/pocketchat';source=(production/'GeckoAddressUi.java').read_text();main=(production/'MainActivity.java').read_text()
        spec=importlib.util.spec_from_file_location('navigation_member_parser',ROOT/'tests/gecko-navigation-host/run.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
        needles=['String target(','String current(','static boolean visibleFor(','void refresh(','static boolean available(','static void home(','private void submitAddress(']
        members='\n'.join(parser.member_at(source,source.index(needle)) for needle in needles)
        chat=parser.member_at(main,main.index('static boolean chatUrl('))
        session_source=(production/'ChatSession.java').read_text()
        display='\n'.join(parser.member_at(session_source,session_source.index(needle)) for needle in ['boolean validBrowserTarget(','String browserDisplayUrl('])
        diagnostic_source=(production/'RequestIdentityAudit.java').read_text()
        diagnostic='\n'.join(parser.member_at(diagnostic_source,diagnostic_source.index(needle)) for needle in ['static final String PATH=','static boolean namespace(','static boolean diagnosticUrl('])
        self.assertIn('address.setSingleLine(true)',source)
        self.assertNotIn('setMinHeight(0)',source);self.assertNotIn('setMinimumHeight(0)',source)
        self.assertIn('option(d,"打开网址或搜索",()->GeckoAddressUi.show(this));',main)
        self.assertIn('if(geckoAddress!=null)geckoAddress.refresh();',parser.member_at(main,main.index('void applySession(')))
        show=parser.member_at(source,source.index('static void show('));self.assertNotIn('isShown(',show);self.assertNotIn('getVisibility(',show)
        self.assertIn('owner.submitAddress(dialog,input,notice)',show)
        program=r'''
package local.pocketchat;
import java.net.URI;
import java.net.URLDecoder;
import java.util.Locale;
public final class AddressVisibilityHost {
  static int checks;
  static void check(String id,boolean value){if(!value)throw new AssertionError(id);checks++;}
  // Explicit JVM presentation/session/URI boundaries; no Android classes or SDK execution.
  static final class View {static final int VISIBLE=0,GONE=8;}
  static final class Row {int visibility=View.GONE,writes;int getVisibility(){return visibility;}void setVisibility(int v){visibility=v;writes++;}}
  static final class Label {String text="",description="",tooltip="",glyph="";boolean enabled;int writes;void setText(String s){text=s;writes++;}void setContentDescription(String s){description=s;}void setTooltipText(String s){tooltip=s;}}
  static final class Web {String url="about:blank";boolean back,forward,visible;String getUrl(){return url;}boolean canGoBack(){return back;}boolean canGoForward(){return forward;}boolean hasVisibleDocument(){return visible;}}
  static final class RequestIdentityAudit {@DIAGNOSTIC@}
  static final class Session {boolean navigating,navigationFailed,browserNavigationChosen,browserNavigationStopped,accept=true,startLoading=true;int browseCalls;String status="环境已关闭",navigationTarget="",browsingUrl="",resume="https://resume.example/";final Web web=new Web();String resumeUrl(){return resume;}@DISPLAY@ boolean browse(String url,String label){browseCalls++;if(!accept)return false;navigating=startLoading;navigationFailed=!startLoading;browserNavigationChosen=true;browserNavigationStopped=false;browsingUrl=url;navigationTarget=url;return true;}}
  static final class AlertDialog {boolean showing=true;boolean isShowing(){return showing;}void dismiss(){showing=false;}}
  static final class EditText {String value,error="";EditText(String value){this.value=value;}String getText(){return value;}void setError(String error){this.error=error;}}
  static final class TextView {String text="";int visibility=View.GONE;void setText(String text){this.text=text;}void setVisibility(int visibility){this.visibility=visibility;}}
  static final class BrowserToolbarUi {static void enabled(Label button,boolean value){button.enabled=value;}static void action(Label button,String glyph,String label){button.glyph=glyph;button.description=label;}}
  static final class BrowserPreferences {static String selected="https://chatgpt.com/";static String home(MainActivity a){return selected;}}
  static final class Uri {final URI uri;Uri(String s){uri=URI.create(s);}static Uri parse(String s){return new Uri(s);}String getScheme(){return uri.getScheme();}String getHost(){return uri.getHost();}String getUserInfo(){return uri.getUserInfo();}int getPort(){return uri.getPort();}}
  static final class MainActivity {Session session=new Session();Web remote=session.web;boolean destroyed,finishing;int reveals;GeckoAddressUi geckoAddress;boolean isFinishing(){return finishing;}void showPage(boolean b){reveals++;}@CHAT@}
  static final class GeckoAddressUi {final MainActivity a;final Row row=new Row();final Label address=new Label(),back=new Label(),forward=new Label(),reload=new Label();String shown="";AlertDialog dialog;GeckoAddressUi(MainActivity a){this.a=a;a.geckoAddress=this;}@MEMBERS@}
  public static void main(String[] args){
    MainActivity a=new MainActivity();GeckoAddressUi ui=new GeckoAddressUi(a);
    ui.refresh();check("Blank page keeps browser controls",ui.row.getVisibility()==View.VISIBLE);check("Initial history is disabled",!ui.back.enabled&&!ui.forward.enabled);
    check("Cold blank uses the existing resume destination",ui.current().equals(a.session.resume)&&ui.address.description.contains(a.session.resume));
    a.session.web.visible=true;ui.refresh();check("Visible blank popup keeps its real address",ui.current().equals("about:blank")&&ui.address.text.equals("about:blank"));
    a.session.web.visible=false;a.session.resume="";ui.refresh();check("Cold blank without resume uses selected home",ui.current().equals(BrowserPreferences.selected));
    a.session.resume="about:blank";ui.refresh();check("Blank resume cannot hide the home destination",ui.current().equals(BrowserPreferences.selected));
    a.session.resume="https://resume.example/";
    for(String url:new String[]{"https://chatgpt.com/","https://chatgpt.com:443/c/test#fragment","https://chatgpt.com/c/test?q=1#frag"}){a.session.web.url=url;ui.refresh();check("ChatGPT keeps the browser toolbar",ui.row.getVisibility()==View.VISIBLE);check("Official page remains editable",GeckoAddressUi.available(a));check("Menu uses current official address",ui.current().equals(url));check("Full official URL stays accessible",ui.address.description.contains(url));}
    for(String url:new String[]{"http://public.example/","https://public.example/path#fragment","http://chatgpt.com/","https://chatgpt.com.other.example/"}){a.session.web.url=url;ui.refresh();check("Ordinary public origin visible",ui.row.getVisibility()==View.VISIBLE);check("Visible address is current target",ui.address.description.contains(url));check("Tooltip retains full URL",ui.address.tooltip.equals(url));}
    check("HTTP scheme stays explicit",GeckoAddressUi.visibleFor("http://public.example/"));
    a.session.web.url="https://public.example/";ui.refresh();a.session.navigating=true;a.session.navigationTarget="https://chatgpt.com:443/c/new#frag";ui.refresh();check("Pending target replaces old address",ui.current().equals(a.session.navigationTarget));check("Pending target is visibly identified",ui.address.description.contains(a.session.navigationTarget));check("Loading has stop action",ui.reload.glyph.equals("close")&&ui.reload.description.equals("停止加载"));
    a.session.navigationTarget="http://next.example/";ui.refresh();check("HTTP target stays explicit",ui.address.text.startsWith("http://"));
    int layouts=ui.row.writes,texts=ui.address.writes;for(int i=0;i<100;i++)ui.refresh();check("Repeated frame refresh avoids layout churn",ui.row.writes==layouts&&ui.address.writes==texts);
    a.session.navigating=false;a.remote.back=true;a.remote.forward=false;ui.refresh();check("History reflects native back state",ui.back.enabled&&!ui.forward.enabled);a.remote.forward=true;ui.refresh();check("History reflects native forward state",ui.forward.enabled);check("Ready page has reload action",ui.reload.glyph.equals("refresh")&&ui.reload.description.equals("刷新网页"));
    for(String url:new String[]{"", "about:blank","javascript:void(0)","http://127.0.0.1/private","file:///private"}){a.session.web.url=url;ui.refresh();check("Displayed URL never hides navigation controls",ui.row.getVisibility()==View.VISIBLE);}
    a.session.web.url=null;ui.refresh();check("Empty live URL uses saved resume prefill",ui.current().equals(a.session.resume));a.session.web.url="https://public.example/";a.session.navigating=true;a.session.navigationTarget="";ui.refresh();check("Unknown history target keeps current address",ui.current().equals(a.session.web.url));a.session=null;BrowserPreferences.selected="https://homepage.example/";ui.refresh();check("No-session startup keeps home address",ui.current().equals(BrowserPreferences.selected));check("No-session menu unavailable",!GeckoAddressUi.available(a));
    a.session=new Session();a.remote=a.session.web;a.session.web.url="https://public.example/";ui.refresh();BrowserPreferences.selected="https://chatgpt.com/";GeckoAddressUi.home(a);check("Home retains normal browser toolbar",ui.row.getVisibility()==View.VISIBLE&&a.reveals==1&&a.session.navigationTarget.equals(BrowserPreferences.selected));check("Home immediately updates visible target",ui.address.description.contains(BrowserPreferences.selected));
    for(boolean loading:new boolean[]{true,false}){
      a.session.startLoading=loading;ui.dialog=new AlertDialog();EditText input=new EditText("example.org/path");TextView notice=new TextView();int reveals=a.reveals;
      ui.submitAddress(ui.dialog,input,notice);
      check("Accepted address closes form even before loading starts",!ui.dialog.showing&&a.reveals==reveals+1&&a.session.navigationTarget.equals("https://example.org/path"));
      check("Accepted address does not display stale session status",notice.visibility==View.GONE&&input.error.isEmpty());
      check("Accepted offline destination stays editable",ui.current().equals("https://example.org/path")&&ui.address.description.contains("https://example.org/path"));
    }
    a.session.browserNavigationStopped=true;ui.refresh();check("Stop displays the retained page",ui.current().equals(a.session.web.url));a.session.browserNavigationStopped=false;
    a.session.navigating=false;a.session.navigationFailed=false;a.session.web.url="https://redirect.example/complete";a.session.browsingUrl=a.session.web.url;ui.refresh();check("Committed redirect replaces the entered address",ui.current().equals(a.session.web.url));
    a.session.navigating=true;a.session.navigationTarget="https://audit.example/pocketchat-identity/v1/document?nonce=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";a.session.web.url=a.session.navigationTarget;ui.refresh();check("Diagnostic page keeps its actual address",ui.current().equals(a.session.web.url));
    a.session.navigationFailed=true;a.session.navigating=false;a.session.navigationTarget="https://old.example/";a.session.browsingUrl="https://new.example/";ui.refresh();check("An old failed target cannot hide the current document",ui.current().equals(a.session.web.url));
    ui.dialog=new AlertDialog();TextView notice=new TextView();ui.submitAddress(ui.dialog,new EditText("   "),notice);check("Empty address uses configured homepage",!ui.dialog.showing&&a.session.navigationTarget.equals(BrowserPreferences.selected));
    ui.dialog=new AlertDialog();EditText invalid=new EditText("javascript:alert(1)");int attempts=a.session.browseCalls;notice=new TextView();ui.submitAddress(ui.dialog,invalid,notice);
    check("Invalid explicit scheme is still rejected",ui.dialog.showing&&a.session.browseCalls==attempts&&notice.visibility==View.VISIBLE&&!invalid.error.isEmpty());
    a.session.accept=false;ui.dialog=new AlertDialog();notice=new TextView();ui.submitAddress(ui.dialog,new EditText("example.org"),notice);check("Unavailable session retains form and actual reason",ui.dialog.showing&&notice.text.equals(a.session.status));a.session.accept=true;
    AlertDialog replaced=new AlertDialog();ui.dialog=new AlertDialog();attempts=a.session.browseCalls;ui.submitAddress(replaced,new EditText("example.org"),new TextView());check("Replaced dialog cannot navigate",a.session.browseCalls==attempts&&replaced.showing);
    a.destroyed=true;ui.submitAddress(ui.dialog,new EditText("example.org"),new TextView());check("Destroyed address owner cannot navigate",a.session.browseCalls==attempts);a.destroyed=false;
    a.destroyed=true;check("Destroyed owner cannot open menu",!GeckoAddressUi.available(a));a.destroyed=false;a.finishing=true;check("Finishing owner cannot open menu",!GeckoAddressUi.available(a));a.finishing=false;a.remote=null;check("Absent surface cannot open menu",!GeckoAddressUi.available(a));
    System.out.println("{\"checks\":"+checks+",\"actualAndroidExecution\":false,\"persistentBrowserControls\":true}");
  }
}
'''.replace('@CHAT@',chat).replace('@MEMBERS@',members).replace('@DISPLAY@',display).replace('@DIAGNOSTIC@',diagnostic)
        java_home=Path(os.environ.get('JAVA_HOME',str(ROOT/'work/browser-ci-jdk/jdk-17.0.21+9')));javac=str(java_home/'bin/javac');java=str(java_home/'bin/java')
        with tempfile.TemporaryDirectory(prefix='address-visibility-host-') as folder:
            folder=Path(folder);path=folder/'AddressVisibilityHost.java';classes=folder/'classes'
            def execute(body):
                path.write_text(body);built=subprocess.run([javac,'--release','17','-encoding','UTF-8','-d',str(classes),str(path),str(production/'BrowserAddressPolicy.java'),str(production/'GeckoNavigationPolicy.java')],capture_output=True,text=True,timeout=30);self.assertEqual(built.returncode,0,built.stderr);return subprocess.run([java,'-cp',str(classes),'local.pocketchat.AddressVisibilityHost'],capture_output=True,text=True,timeout=20)
            passed=execute(program);self.assertEqual(passed.returncode,0,passed.stderr);result=json.loads(passed.stdout);self.assertGreaterEqual(result['checks'],40)
            mutations=[('row.setVisibility(View.VISIBLE)','row.setVisibility(View.GONE)','Blank page keeps browser controls'),('a.session.browserDisplayUrl()','a.session.web.getUrl()','Pending target replaces old address'),('a.remote!=null&&a.remote.canGoForward()','false','History reflects native forward state'),('a.session!=null&&a.session.navigating','false','Loading has stop action'),('!a.session.web.hasVisibleDocument()','true','Visible blank popup keeps its real address'),('"about:blank".equals(url)&&a.session!=null&&!a.session.web.hasVisibleDocument()','false','Cold blank uses the existing resume destination')]
            mutations.append(('if(a.session.browse(url,"正在打开网页…")){','if(a.session.browse(url,"正在打开网页…")&&a.session.navigating){','Accepted address closes form even before loading starts'))
            mutations.append(('browserNavigationChosen&&navigationFailed&&navigationTarget.equals(browsingUrl)','false','Accepted offline destination stays editable'))
            for before,after,failure in mutations:
                self.assertEqual(program.count(before),1);mutant=execute(program.replace(before,after,1));self.assertNotEqual(mutant.returncode,0);self.assertIn('AssertionError: '+failure,mutant.stderr)
            self.assertEqual((production/'GeckoAddressUi.java').read_text(),source)
            self.assertEqual((production/'ChatSession.java').read_text(),session_source)
            self.assertEqual((production/'RequestIdentityAudit.java').read_text(),diagnostic_source)
            print(json.dumps(dict(scope='Exact current address presentation and submission methods on explicit JVM boundaries; real address policies; no Android or Gecko execution',**result,mutationControls=len(mutations))))

    def test_actual_browser_address_row_reflows_without_recreating_controls(self):
        source=(ROOT/'app/src/main/java/local/pocketchat/GeckoAddressUi.java').read_text()
        spec=importlib.util.spec_from_file_location('address_row_parser',ROOT/'tests/gecko-navigation-host/run.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
        row=parser.member_at(source,source.index('static final class BrowserAddressRow'))
        template=(ROOT/'tests/browser-address-host/BrowserAddressLayoutHost.java.in').read_text()
        program=template.replace('/* PRODUCTION_ROW */',row)
        java_home=Path(os.environ.get('JAVA_HOME',str(ROOT/'work/browser-ci-jdk/jdk-17.0.21+9')))
        with tempfile.TemporaryDirectory(prefix='browser-address-layout-') as directory:
            directory=Path(directory);path=directory/'BrowserAddressLayoutHost.java';classes=directory/'classes'
            def execute(body):
                path.write_text(body)
                result=subprocess.run([str(java_home/'bin/javac'),'--release','17','-encoding','UTF-8','-d',str(classes),str(path)],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                return subprocess.run([str(java_home/'bin/java'),'-cp',str(classes),'local.pocketchat.BrowserAddressLayoutHost'],capture_output=True,text=True,timeout=20)
            passed=execute(program);self.assertEqual(passed.returncode,0,passed.stderr)
            report=json.loads(passed.stdout);self.assertGreaterEqual(report['checks'],180)
            mutations=[('stacked=available-4*action<minimum;','stacked=false;'),
                       ('text.substring(0,end)+"…"','"chatgpt.com…"'),
                       ('int action=dp(48),minimum=readableAddressWidth();','int action=dp(44),minimum=readableAddressWidth();'),
                       ('setMeasuredDimension(width,resolveSize(getPaddingTop()+content+getPaddingBottom(),heightSpec));','setMeasuredDimension(width,resolveSize(getPaddingTop()+content+getPaddingBottom(),heightSpec));requestLayout();')]
            for before,after in mutations:
                self.assertEqual(program.count(before),1)
                failed=execute(program.replace(before,after,1));self.assertNotEqual(failed.returncode,0);self.assertIn('AssertionError:',failed.stderr)
            self.assertEqual((ROOT/'app/src/main/java/local/pocketchat/GeckoAddressUi.java').read_text(),source)
            print(json.dumps(dict(scope='Exact production BrowserAddressRow measure/layout against explicit JVM text and View boundaries; native font rendering remains device evidence',**report,mutationControls=len(mutations))))

    def test_native_browser_toolbar_geometry_requires_complete_inline_or_stacked_rows(self):
        sys.path.insert(0,str(ROOT/'tools/gecko'))
        try:
            spec=importlib.util.spec_from_file_location('browser_toolbar_capture',ROOT/'tools/gecko/capture_glass_navigation.py')
            capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
        finally:sys.path.pop(0)
        descriptions={'back':'后退','forward':'前进','reload':'刷新网页','home':'打开当前环境主页',
                      'address':'当前网址 https://chatgpt.com/c/example，点击输入网址或搜索'}
        def fixture(stacked=False,density=1):
            capture.set_display((320 if stacked else 412)*density,892*density,160*density)
            boxes={'back':[16,100,64,148],'forward':[64,100,112,148],
                   'address':[112,100,300,148],'reload':[300,100,348,148],'home':[348,100,396,148]}
            if stacked:boxes.update(back=[16,152,64,200],forward=[64,152,112,200],address=[16,100,304,148],reload=[208,152,256,200],home=[256,152,304,200])
            tree=ET.Element('hierarchy')
            for name,box in boxes.items():
                box=[value*density for value in box]
                ET.SubElement(tree,'node',{'package':capture.PACKAGE,'class':'android.widget.Button','content-desc':descriptions[name],
                    'clickable':'true','enabled':'false' if name in ('back','forward') else 'true',
                    'text':'chatgpt.com/c/example' if name=='address' else '',
                    'bounds':f'[{box[0]},{box[1]}][{box[2]},{box[3]}]'})
            return tree
        def observed(tree):return capture.browser_toolbar_geometry(ET.tostring(tree,encoding='unicode'))
        def node(tree,name):return next(item for item in tree if item.get('content-desc')==descriptions[name])
        for density in (1,3):
            for stacked in (False,True):
                report=observed(fixture(stacked,density));self.assertIsNotNone(report)
                self.assertEqual(report['layoutMode'],'stacked' if stacked else 'inline')
                self.assertEqual(report['singleHorizontalRow'],not stacked);self.assertEqual(report['addressOwnRow'],stacked)
                self.assertFalse(report['actions']['back']['enabled']);self.assertFalse(report['nativeGlyphVisibilityClaimed'])
        broken=fixture(False);capture.set_display(320,892,160)
        node(broken,'address').set('bounds','[112,100][208,148]');node(broken,'reload').set('bounds','[208,100][256,148]');node(broken,'home').set('bounds','[256,100][304,148]')
        self.assertIsNone(observed(broken),'The old narrow 96dp address slot must fail')
        for name,box in [('back','[16,152][62,200]'),('forward','[63,152][111,200]'),
                         ('reload','[208,154][256,202]'),('home','[208,152][256,200]'),
                         ('address','[18,100][302,148]'),('address','[16,105][304,153]'),
                         ('address','[16,100][321,148]')]:
            broken=fixture(True);node(broken,name).set('bounds',box)
            self.assertIsNone(observed(broken),(name,box))
        broken=fixture(True);node(broken,'address').set('text','');self.assertIsNone(observed(broken))
        broken=fixture(True);node(broken,'back').set('enabled','unknown');self.assertIsNone(observed(broken))
        broken=fixture(True);broken.append(ET.fromstring(ET.tostring(node(broken,'address'))));self.assertIsNone(observed(broken))

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
