"""Replay original API32 hierarchy cropping without changing either old outcome.

Native receipts bind the same screen geometry in two separate real CI runs.
These host checks do not claim a successful current device capture.
"""
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
import capture_glass_navigation as G
from historical_source_inputs import browser_v3_bytes, browser_v3_identity
from profile_navigation_v4_test import browser_xml as synthetic_v4_browser_xml

FIXTURE=ROOT/'tests/ui-hierarchy-driver/api32-safearea-original-crop.json'
FIXTURE_SHA='3c3bad0de637de650e7d97f9b3835b496c41969a150cbc49a4bfee5bad7e873f'
HISTORICAL_CAPTURE='tools/gecko/capture_glass_navigation.py'
HISTORICAL_CAPTURE_SHA='2cd0099d5bc054f41e6cbef694f7d041e0fe6ec2e0b0bfb107794a6d6da97c4e'

def digest(raw):return hashlib.sha256(raw).hexdigest()

class ObservedHierarchyCropTest(unittest.TestCase):
    def historical_capture(self):
        source=browser_v3_bytes(HISTORICAL_CAPTURE)
        identity=browser_v3_identity(HISTORICAL_CAPTURE)
        self.assertEqual(digest(source),HISTORICAL_CAPTURE_SHA)
        self.assertEqual(identity['sha256'],HISTORICAL_CAPTURE_SHA)
        self.assertIs(identity['historicalProofOnly'],True)
        self.assertIs(identity['currentSourceReplacement'],False)
        module=types.ModuleType('observed_crop_capture_v3')
        module.__file__=str(ROOT/HISTORICAL_CAPTURE)
        exec(compile(source,HISTORICAL_CAPTURE+'@'+identity['commit'],'exec'),module.__dict__)
        return module

    def evidence(self):
        raw=FIXTURE.read_bytes();self.assertEqual(digest(raw),FIXTURE_SHA)
        value=json.loads(raw)
        self.assertIs(value['recordedComparisonOnly'],True)
        self.assertIs(value['currentAndroidAcceptance'],False)
        self.assertEqual([row['label'] for row in value['cases']],['C6','C8'])
        for row in value['cases']:
            self.assertEqual(row['caseStatus'],'failed')
            for name in ('hierarchy','displayViewport'):
                item=row[name];raw=item['rawUtf8'].encode()
                self.assertEqual(len(raw),item['bytes']);self.assertEqual(digest(raw),item['sha256'])
            event=row['nativeReady'];raw=event['rawUtf8'].encode();receipt=event['receipt'];payload=json.loads(raw)
            self.assertEqual(len(raw),receipt['payloadBytes']);self.assertEqual(digest(raw),receipt['payloadSha256'])
            self.assertEqual(payload['sourceCommit'],row['sourceCommit'])
            identity=payload['buildIdentity']
            for name in ('sourceCommit','sourceTree','apkSha256'):self.assertEqual(identity[name],row[name])
            for name in ('runId','runAttempt'):self.assertEqual(identity['sdkBuildIdentity'][name],row[name])
            self.assertIs(identity['dirtySource'],False)
            for name in ('runNonce','fixtureAction','command','sequence','nativeContext','processSlot'):
                self.assertEqual(payload[name],receipt[name])
            self.assertEqual(payload['event']['kind'],receipt['eventKind'])
        return value['cases']

    def test_original_native_screen_geometry_is_equal_and_old_cases_remain_failed(self):
        earlier,later=self.evidence()
        self.assertTrue(earlier['initialChatObserved']);self.assertFalse(later['initialChatObserved'])
        self.assertIn('could not get idle state',earlier['error'])
        self.assertEqual(later['error'],'Actual native screen did not become ready: safearea-light-chat')
        snapshots=[json.loads(row['nativeReady']['rawUtf8'])['event']['result'] for row in (earlier,later)]
        for snapshot in snapshots:
            self.assertEqual(snapshot['command'],'ready')
            self.assertEqual(snapshot['browserToolbarBounds'],[0,2346,1236,2532])
            self.assertEqual(snapshot['browserAddressTap'],[618,2436])
            self.assertEqual((snapshot['webWidth'],snapshot['webY'],snapshot['webHeight']),(1236,312,2034))
        for row in (earlier,later):
            viewport=G.window_display_viewport(row['displayViewport']['rawUtf8'])
            self.assertEqual(viewport,dict(widthPx=1236,heightPx=2676,densityDpi=480))

    def test_historical_v3_geometry_gate_rejects_clipped_buttons_without_relaxing_48dp(self):
        earlier,later=self.evidence()
        historical=self.historical_capture()
        historical.set_display(1236,2676,480)
        prior=(G.WIDTH,G.HEIGHT,G.DENSITY,G.DISPLAY_REQUEST)
        G.set_display(1236,2676,480)
        try:
            original=historical.browser_toolbar_geometry(earlier['hierarchy']['rawUtf8'])
            self.assertIsNotNone(original)
            self.assertEqual(original['navigationContract'],3)
            self.assertEqual(original['minimumActionTouchDp'],48)
            self.assertEqual(original['addressBounds'],[312,2364,924,2508])
            self.assertIsNone(historical.browser_toolbar_geometry(later['hierarchy']['rawUtf8']))
            for row,clip in ((earlier,2676),(later,2388)):
                self.assertIsNone(G.browser_toolbar_geometry(row['hierarchy']['rawUtf8']))
                tree=ET.fromstring(row['hierarchy']['rawUtf8'])
                self.assertEqual(tree.find('node').get('bounds'),f'[0,0][1236,{clip}]')
                buttons=[node for node in tree.iter('node') if node.get('class')=='android.widget.Button'
                         and (node.get('content-desc') in ('后退','打开当前环境主页','刷新网页','浏览器菜单')
                              or node.get('content-desc','').startswith('当前网址 '))]
                self.assertEqual(len(buttons),5)
                for node in buttons:
                    box=G.bounds(node);self.assertEqual(box[1],2364)
                    self.assertEqual(box[3],min(2508,clip))
                    self.assertEqual(box[3]-box[1],144 if row is earlier else 24)
        finally:G.set_display(*prior[:3],requested=prior[3])

    def test_current_v4_synthetic_geometry_keeps_48dp_and_rejects_clipping(self):
        # This independent generated v4 tree is not a rewrite of either receipt.
        tree=ET.fromstring(synthetic_v4_browser_xml(width=412))
        address=next(node for node in tree.iter('node')
                     if node.get('content-desc','').startswith('当前网址 '))
        address.set('text','example.test/photo')
        prior=(G.WIDTH,G.HEIGHT,G.DENSITY,G.DISPLAY_REQUEST)
        G.set_display(1236,1920,480)
        try:
            current=G.browser_toolbar_geometry(ET.tostring(tree,encoding='unicode'))
            self.assertIsNotNone(current)
            self.assertEqual(current['navigationContract'],4)
            self.assertEqual(current['minimumActionTouchDp'],48)
            self.assertEqual(tuple(current['actions']),('home','windows','tools','menu'))
            tools=next(node for node in tree.iter('node') if node.get('content-desc')=='网页工具')
            left,top,right,bottom=G.bounds(tools)
            self.assertEqual(bottom-top,144)
            tools.set('bounds',f'[{left},{top}][{right},{top+24}]')
            self.assertIsNone(G.browser_toolbar_geometry(ET.tostring(tree,encoding='unicode')))
        finally:G.set_display(*prior[:3],requested=prior[3])

if __name__=='__main__':unittest.main()
