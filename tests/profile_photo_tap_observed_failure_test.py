"""Retain the actual missed photo tap without relabeling it as acceptance.

The native Java helper has separate executable geometry/ownership controls.
This file checks the original Android receipts and the exact scope of the
current photo call-site change. It does not fabricate a successful device tap.
"""
import hashlib
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/photo-tap-host/c6-missed-enhanced-tap.json'
FIXTURE_SHA = 'd82945ac6fd0a9b53eb2ef07cee686b912e802dc3dbc574ed99e2ad3f0b58906'
ACTIVITY = ROOT/'tests/gecko/GeckoIntegrationTestActivity.java'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class ObservedPhotoTapFailure(unittest.TestCase):
    def evidence(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(digest(raw), FIXTURE_SHA)
        value = json.loads(raw)
        self.assertIs(value['recordedFailureOnly'], True)
        self.assertIs(value['currentAndroidAcceptance'], False)
        self.assertEqual(value['originalStatus'], 'failed')
        return value

    def event(self, evidence, record):
        raw = record['rawUtf8'].encode('utf-8')
        receipt, payload = record['receipt'], json.loads(raw)
        self.assertEqual(len(raw), receipt['payloadBytes'])
        self.assertEqual(digest(raw), receipt['payloadSha256'])
        self.assertEqual(payload['sourceCommit'], evidence['sourceCommit'])
        identity = payload['buildIdentity']
        self.assertEqual(identity['sourceCommit'], evidence['sourceCommit'])
        self.assertEqual(identity['sourceTree'], evidence['sourceTree'])
        self.assertIs(identity['dirtySource'], False)
        self.assertEqual(identity['sdkBuildIdentity']['runId'], evidence['runId'])
        self.assertEqual(identity['sdkBuildIdentity']['runAttempt'], evidence['runAttempt'])
        for name in ('runNonce', 'fixtureAction', 'command', 'sequence', 'nativeContext', 'processSlot'):
            self.assertEqual(payload[name], receipt[name])
        self.assertEqual(payload['event']['kind'], receipt['eventKind'])
        return payload['event']['result']

    def test_original_enhanced_tap_misses_the_native_button_and_stays_failed(self):
        evidence = self.evidence()
        hierarchy = evidence['failureHierarchy']
        raw = hierarchy['rawUtf8'].encode('utf-8')
        self.assertEqual(len(raw), hierarchy['bytes'])
        self.assertEqual(digest(raw), hierarchy['sha256'])
        nodes = [node for node in ET.fromstring(raw).iter('node')
                 if node.get('resource-id') == 'upload']
        self.assertEqual(len(nodes), 1)
        node = nodes[0]
        self.assertEqual(node.get('package'), 'local.pocketchat.test')
        self.assertEqual(node.get('class'), 'android.widget.Button')
        self.assertEqual(node.get('enabled'), 'true')
        self.assertEqual(node.get('clickable'), 'true')
        bounds = tuple(map(int, re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds')).groups()))
        self.assertEqual(bounds, (21, 457, 621, 518))
        rows = {row['name']: row for row in evidence['cases']}
        taps = {name: self.event(evidence, row['tap']) for name, row in rows.items()}
        protected = taps['protected-external']
        self.assertEqual((protected['x'], protected['y']), (246, 403))
        self.assertAlmostEqual(protected['scale'], 2.6086957)
        inside = lambda point: bounds[0] < point['x'] < bounds[2] and bounds[1] < point['y'] < bounds[3]
        self.assertFalse(inside(protected))
        # These are observed earlier standard-mode points compared with the
        # later protected hierarchy, not invented standard-mode XML captures.
        for name in ('standard-external', 'standard-own'):
            self.assertEqual((taps[name]['x'], taps[name]['y']), (321, 487))
            self.assertTrue(inside(taps[name]))
        failed = self.event(evidence, rows['protected-external']['terminal'])
        self.assertEqual(failed['error'], 'desktop image chooser/upload failed')
        self.assertIs(failed['chooser'], False)
        page = json.loads(failed['result'])
        self.assertIs(page['ready'], True)
        self.assertEqual(page['value'], '')
        self.assertEqual([row['phase'] for row in page['photoEvidence']['receipts']],
                         ['unselected-to-blob', 'unselected-to-data-url'])
        self.assertTrue(all(row['exactPixels'] is False for row in page['photoEvidence']['receipts']))

    def test_only_photo_tap_dispatch_changes_and_old_flows_and_budgets_remain(self):
        evidence = self.evidence()
        source = ACTIVITY.read_text()
        def section(first, last):
            self.assertEqual(source.count(first), 1)
            self.assertEqual(source.count(last), 1)
            return source[source.index(first):source.index(last)]
        methods = evidence['originalMethods']['sha256']
        old_tap = section('  void tapElement(long serial,String id){',
                          '  void waitWindow(long serial,String step,long deadline,Runnable done){')
        self.assertEqual(digest(old_tap.encode()), methods['tapElement'])
        chooser = section('  void desktopImage(long serial,boolean ownProvider){',
                          '  void desktopImageReady(long serial,long deadline,')
        self.assertEqual(digest(chooser.encode()), methods['desktopImage'])
        self.assertIn('SystemClock.elapsedRealtime()+25000', chooser)
        readiness = section('  void desktopImageReady(long serial,long deadline,',
                            '  void finishDesktopImageHost(MainActivity host){')
        dispatch = 'GeckoPhotoTap.begin(this,serial,target,deadline);'
        self.assertEqual(source.count(dispatch), 1)
        self.assertEqual(readiness.count(dispatch), 1)
        restored = readiness.replace(dispatch, 'tapElement(serial,"upload");', 1)
        self.assertEqual(digest(restored.encode()), methods['desktopImageReady'])


if __name__ == '__main__':
    unittest.main()
