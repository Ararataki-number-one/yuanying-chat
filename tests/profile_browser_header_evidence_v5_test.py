"""Synthetic XML/native cross-check and real-tap receipt rejection controls."""
import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from browser_header_contract_v5 import network_extension
from workspace_browser_header_v5 import conversation_header, native_observation
from compact_chrome_layout_v5 import verify_case
from profile_navigation_v4_test import case as v4_case, browser_xml, layout as v4_layout

SOURCE, NONCE, PACKAGE = 'a'*40, 'b'*32, 'local.pocketchat.test'


def add_delegate(layout):
    layout.update(headerContract=5, actualAndroidLayout=True, density=3)
    row = layout['networkMetrics']
    row.update(touchBounds=row['bounds'].copy(), effectiveTouchRegions=[row['bounds'].copy()])
    return layout


def native():
    complete = add_delegate(v4_layout())
    layout = {key: complete[key] for key in ('headerContract','actualAndroidLayout','density','viewportDp','toolbar','topBounds','webBounds','controls','networkInHeader','networkShown')}
    layout['networkMetrics'] = {key: complete['networkMetrics'][key] for key in ('bounds','touchBounds','effectiveTouchRegions','clickable','focusable')}
    return dict(schema=1, headerContract=5, status='observed', scene='chat', nonce=NONCE,
                sourceCommit=SOURCE, actualAndroidLayout=True, windowFocused=True, layoutRequested=False,
                engine='gecko', activityClass='local.pocketchat.MainActivity', activityIdentity=10,
                delegateIdentity=20, windowBounds=[0,0,1080,1920], startedUptimeMs=1000, observedUptimeMs=3000, density=3, fontScale=1,
                capsuleAccessibilityBounds=layout['controls'][0]['visible'].copy(), layout=layout)


def current_case(width=360, scale=1):
    value = v4_case(width, scale); value['headerContract'] = 5
    for layout in (value['layout'], value['statusObservation']['before'], value['statusObservation']['after']): add_delegate(layout)
    point = network_extension(value['statusObservation']['before'])
    value['actualAndroidTaps'].append(dict(control='network-extension', actualAndroidTap=True, **point))
    value['networkDetails'].append(copy.deepcopy(value['networkDetails'][0]))
    return value


class BrowserHeaderEvidenceV5Tests(unittest.TestCase):
    def test_current_native_observation_and_bottom_navigation_four(self):
        measured = native_observation(json.dumps(native()), NONCE, SOURCE)
        result = conversation_header(browser_xml(), PACKAGE, 360, 640, 1, 'Controlled environment', browser=True, native=measured)
        self.assertEqual((result['headerContract'], result['navigationContract']), (5, 4))

    def test_wrong_source_or_nonce_is_rejected(self):
        for source, nonce in (('c'*40, NONCE), (SOURCE, 'd'*32)):
            with self.subTest(source=source, nonce=nonce), self.assertRaises(AssertionError):
                native_observation(json.dumps(native()), nonce, source)

    def test_focus_and_actual_measurement_required(self):
        for key in ('actualAndroidLayout', 'windowFocused'):
            value = native(); value[key] = False
            with self.subTest(key=key), self.assertRaises(AssertionError): native_observation(json.dumps(value), NONCE, SOURCE)

    def test_duplicate_native_field_rejected(self):
        raw = json.dumps(native()).replace('"schema": 1', '"schema": 1, "schema": 1')
        with self.assertRaises(AssertionError): native_observation(raw, NONCE, SOURCE)

    def test_xml_network_cannot_claim_an_unobserved_geometry(self):
        tree = ET.fromstring(browser_xml())
        row = next(n for n in tree.iter('node') if n.get('content-desc', '').startswith('当前环境网络：'))
        row.set('bounds', '[0,216][1080,300]')
        with self.assertRaises(AssertionError):
            conversation_header(ET.tostring(tree, encoding='unicode'), PACKAGE, 360, 640, 1, 'Controlled environment', browser=True, native=native())

    def test_three_cohorts_require_a_real_third_network_tap_receipt(self):
        for width, scale in ((360, 1), (412, 1), (360, 2)):
            self.assertTrue(verify_case(current_case(width, scale)))

    def test_missing_extension_or_modal_close_receipt_is_rejected(self):
        for field in ('actualAndroidTaps', 'networkDetails'):
            value = current_case(); value[field].pop()
            with self.subTest(field=field), self.assertRaises(AssertionError): verify_case(value)

    def test_extension_tap_cannot_move_into_the_webpage(self):
        value = current_case(); value['actualAndroidTaps'][-1]['point'][1] = value['layout']['webBounds'][1]+1
        with self.assertRaises(AssertionError): verify_case(value)

    def test_old_v4_case_cannot_qualify_as_v5_without_native_regions(self):
        with self.assertRaises(AssertionError): verify_case(v4_case())


if __name__ == '__main__': unittest.main()
