"""Replay the real 420 dpi files failure, without relabelling it as a pass.

The original artifact has complete dumpsys and XML bytes, but no `wm density`
receipt. That command's host-model response below is explicitly constructed
from independently observed native configuration, never claimed as device IO.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import workspace_navigation_contract_v3 as navigation

FIXTURE = ROOT/'tests/fixtures/browser-navigation-original-density.json'
FIXTURE_SHA = 'e592b1835934351d0398aa55efc984c2d5a3a1c14b13720981e066c9b8403e0c'
PACKAGE = 'local.pocketchat.test'
ACTION_NAMES = ('后退', '打开当前环境主页', '刷新网页', '浏览器菜单')


class ObservedNativeDensityTest(unittest.TestCase):
    def original(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), FIXTURE_SHA)
        value = json.loads(raw)
        self.assertIs(value['recordedComparisonOnly'], True)
        self.assertIs(value['currentAndroidAcceptance'], False)
        self.assertEqual(value['caseStatus'], 'failed')
        self.assertEqual(value['artifactId'], 14213987314)
        self.assertEqual(value['artifactSha256'],
                         '079e40257129de3f4e623d4bb26388231f067334d18bc50939867ef249f08d39')
        for item in value['originals'].values():
            data = item['rawUtf8'].encode('utf-8')
            self.assertEqual(len(data), item['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
        runtime = json.loads(value['originals']['device-failure-runtime.json']['rawUtf8'])
        self.assertIs(runtime['diagnosticOnly'], True)
        self.assertIs(runtime['acceptance'], False)
        self.assertEqual(runtime['originalError'],
                         'AssertionError: Native browser action must retain the actual 48 dp target')
        self.assertEqual(runtime['sourceCommit'], value['sourceCommit'])
        identity = runtime['buildIdentity']
        for key in ('sourceCommit', 'sourceTree', 'apkSha256'):
            self.assertEqual(identity[key], value[key])
        self.assertIs(identity['dirtySource'], False)
        self.assertEqual((identity['version'], identity['versionCode']), ('2.1.6', 108))
        self.assertEqual(identity['package'], PACKAGE)
        for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt'):
            self.assertEqual(identity['sdkBuildIdentity'][key], value[key])
        return runtime, value['originals']['production-ui.xml']['rawUtf8']

    def actual_density_dpi(self, runtime):
        observations = {tuple(row['command']): row for row in runtime['observations']}
        activity = observations['dumpsys', 'activity', 'activities']
        window = observations['dumpsys', 'window', 'windows']
        for item in (activity, window):
            self.assertEqual(item['returnCode'], 0)
            self.assertIs(item['truncated'], False)
        component = PACKAGE+'/local.pocketchat.MainActivity'
        activity_block = activity['stdout'].split('mActivityComponent='+component, 1)[1]
        activity_block = activity_block.split('\n    * Hist', 1)[0]
        densities = re.findall(r'^\s+CurrentConfiguration=\{[^\n]*?\b(\d+)dpi\b',
                               activity_block, re.M)
        self.assertEqual(densities, ['420'])
        window_blocks = re.split(r'\n  Window #\d+ ', window['stdout'])
        owned = [block for block in window_blocks
                 if component in block.split('\n', 1)[0]]
        self.assertEqual(len(owned), 1)
        self.assertEqual(re.findall(r'^\s+mFullConfiguration=\{[^\n]*?\b(\d+)dpi\b',
                                    owned[0], re.M), ['420'])
        global_density = re.findall(r'^\s+mGlobalConfiguration=\{[^\n]*?\b(\d+)dpi\b',
                                    window['stdout'], re.M)
        self.assertEqual(global_density, ['420'])
        return int(densities[0])

    def modeled_wm_evidence(self, dpi):
        # Explicit host response; this is not an original captured command.
        return navigation.display_density_evidence(
            f'Physical density: 160\nOverride density: {dpi}\n')

    def test_original_android_configuration_and_buttons_prove_48dp(self):
        runtime, xml = self.original()
        dpi = self.actual_density_dpi(runtime)
        buttons = [node for node in ET.fromstring(xml).iter('node')
                   if node.get('package') == PACKAGE and node.get('content-desc') in ACTION_NAMES]
        self.assertEqual(len(buttons), 4)
        for node in buttons:
            left, top, right, bottom = navigation.bounds(node)
            self.assertEqual((right-left, bottom-top), (126, 126))
            self.assertEqual((right-left)/(dpi/160), 48)

    def test_original_xml_requires_independent_density_instead_of_fixed_480dpi(self):
        runtime, xml = self.original()
        with self.assertRaises(AssertionError):
            navigation.navigation(xml, PACKAGE, conversation=True, browser=True)
        evidence = self.modeled_wm_evidence(self.actual_density_dpi(runtime))
        result = navigation.navigation(xml, PACKAGE, conversation=True, browser=True,
                                       density_evidence=evidence)
        self.assertEqual(result['density'], 2.625)
        self.assertEqual(result['addressLayout'], 'inline')
        self.assertEqual([row['name'] for row in result['controls']],
                         ['back', 'home', 'address', 'reload', 'menu'])
        with self.assertRaises(AssertionError):
            navigation.navigation(xml, PACKAGE, conversation=True, browser=True,
                                  density_evidence=self.modeled_wm_evidence(480))

    def test_smaller_square_buttons_cannot_self_certify_their_density(self):
        runtime, xml = self.original()
        evidence = self.modeled_wm_evidence(self.actual_density_dpi(runtime))
        tree = ET.fromstring(xml)
        for node in tree.iter('node'):
            if node.get('package') == PACKAGE and node.get('content-desc') in ACTION_NAMES:
                left, top, right, bottom = navigation.bounds(node)
                node.set('bounds', f'[{left},{top}][{right-1},{bottom-1}]')
        with self.assertRaises(AssertionError):
            navigation.navigation(ET.tostring(tree, encoding='unicode'), PACKAGE,
                                  conversation=True, browser=True, density_evidence=evidence)


if __name__ == '__main__':
    unittest.main()
