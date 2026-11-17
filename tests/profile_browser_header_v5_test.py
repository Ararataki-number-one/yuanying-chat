"""Synthetic negative controls for the new reader; never Android evidence."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from browser_header_contract_v5 import verify_header


def fixture(width=360, density=3, row_dp=28):
    px = lambda n: int(n*density+.5)
    w, y, target, capsule_width = px(width), px(24), px(48), px(192)
    top = [px(16), y, w-px(16), y+target]
    left = (w-capsule_width)//2
    capsule = [left, y, left+capsule_width, top[3]]
    row = [px(16), top[3], w-px(16), top[3]+px(row_dp)]
    touch = [row[0], min(row[1], row[3]-target), row[2], row[3]]
    if touch[1] >= capsule[3]:
        regions = [touch.copy()]
    else:
        regions = [[touch[0], touch[1], capsule[0], capsule[3]],
                   [capsule[2], touch[1], touch[2], capsule[3]],
                   [touch[0], capsule[3], touch[2], touch[3]]]
    return dict(headerContract=5, actualAndroidLayout=True, density=density, viewportDp=w/density,
                toolbar=[0, y, w, row[3]+1], topBounds=top, webBounds=[0, row[3]+1, w, px(600)],
                controls=[dict(name='environment', touch=capsule,
                               visible=[left, y+px(2), left+capsule_width, y+px(38)])],
                networkInHeader=True, networkShown=True,
                networkMetrics=dict(bounds=row, touchBounds=touch, effectiveTouchRegions=regions,
                                    clickable=True, focusable=True))


class HeaderV5Test(unittest.TestCase):
    def test_compact_normal_phone_retains_side_target(self):
        current = fixture()
        result = verify_header(current)
        self.assertEqual((current['toolbar'][3]-current['toolbar'][1]-1)/3, 76)
        point = result['networkExtension']['point']
        self.assertLess(point[1], current['networkMetrics']['bounds'][1])
        self.assertTrue(result['effectiveRegionsDisjoint'])

    def test_density_and_width_cases(self):
        for density in (1, 1.33125, 2, 2.625, 3, 4):
            for width in (280, 300, 320, 360, 412, 720):
                for row_dp in ((48, 64) if width < 320 else (28, 48, 64)):
                    with self.subTest(density=density, width=width, row=row_dp):
                        verify_header(fixture(width, density, row_dp))

    def test_rejects_old_header_and_missing_native_measurement(self):
        for key in ('headerContract', 'actualAndroidLayout'):
            value = fixture(); value.pop(key)
            with self.assertRaises(AssertionError): verify_header(value)
        value = fixture(); value['headerContract'] = 4
        with self.assertRaises(AssertionError): verify_header(value)

    def test_capsule_pixels_cannot_be_network_targets(self):
        value = fixture(); value['networkMetrics']['effectiveTouchRegions'] = [value['networkMetrics']['touchBounds']]
        with self.assertRaises(AssertionError): verify_header(value)

    def test_extension_cannot_enter_webpage(self):
        value = fixture(); value['networkMetrics']['touchBounds'][3] = value['webBounds'][1]+1
        with self.assertRaises(AssertionError): verify_header(value)

    def test_compact_strip_needs_full_side_target(self):
        with self.assertRaises(AssertionError): verify_header(fixture(width=300, row_dp=28))

    def test_native_regions_must_cover_the_whole_effective_target(self):
        value = fixture(); value['networkMetrics']['effectiveTouchRegions'].pop(0)
        with self.assertRaises(AssertionError): verify_header(value)

    def test_duplicate_native_regions_are_rejected(self):
        value = fixture(); regions = value['networkMetrics']['effectiveTouchRegions']; regions.append(copy.deepcopy(regions[0]))
        with self.assertRaises(AssertionError): verify_header(value)

    def test_capsule_target_cannot_shrink(self):
        value = fixture(); value['controls'][0]['touch'][3] -= 4
        with self.assertRaises(AssertionError): verify_header(value)

    def test_network_target_cannot_shrink(self):
        value = fixture(); value['networkMetrics']['touchBounds'][1] += 4
        with self.assertRaises(AssertionError): verify_header(value)

    def test_visual_strip_cannot_become_unreadably_short(self):
        with self.assertRaises(AssertionError): verify_header(fixture(row_dp=20))


if __name__ == '__main__':
    unittest.main()
