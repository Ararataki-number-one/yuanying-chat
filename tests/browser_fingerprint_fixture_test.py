"""Trust/transport scope checks only. These do not replace Android TLS execution."""
import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


class BrowserFingerprintFixtureTests(unittest.TestCase):
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
