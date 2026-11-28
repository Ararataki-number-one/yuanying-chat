"""The base and on-demand feature must agree on the phone orientation policy."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = "{http://schemas.android.com/apk/res/android}"
TOOLS = "{http://schemas.android.com/tools}"
RESOLUTION = "com.google.android.gms.common.api.GoogleApiActivity"


def activities(module):
    manifest = ET.parse(ROOT / module / "src/main/AndroidManifest.xml")
    return {a.get(ANDROID + "name"): a for a in manifest.findall("application/activity")
            if a.get(TOOLS + "node") != "remove"}


class PortraitOrientationTest(unittest.TestCase):
    def test_all_app_screens_and_engine_profiles_request_portrait(self):
        base, feature = activities("app"), activities("chromium")
        expected = {"local.pocketchat." + name for name in
                    ("BrandLaunchActivity", "WindowHomeActivity", "DownloadCenterActivity",
                     "AppSettingsActivity", "MainActivity", "BrowserActivity", "ChromiumModuleInstallActivity")}
        expected.update(f"local.pocketchat.ProfileActivity{n}" for n in range(1, 8))
        expected.update(f"local.pocketchat.BrowserActivity$Profile{n}" for n in range(1, 8))
        self.assertLessEqual(expected, set(base))
        self.assertIn("local.pocketchat.CefriumBrowserActivity", feature)
        for name, activity in {**base, **feature}.items():
            if name != RESOLUTION:
                with self.subTest(component=name):
                    self.assertEqual(activity.get(ANDROID + "screenOrientation"), "portrait")

    def test_translucent_sdk_resolution_follows_its_caller_on_oreo(self):
        resources = ROOT / "app/src/main/res"
        attr = activities("app")[RESOLUTION].get(ANDROID + "screenOrientation")
        self.assertEqual(attr, "@integer/transparent_activity_orientation")
        # API 26 cannot request a fixed orientation for a translucent activity.
        for folder, orientation in (("values", 3), ("values-v27", 1)):
            with self.subTest(folder=folder):
                xml = ET.parse(resources / folder / "window_orientation.xml")
                value = xml.findtext("integer[@name='transparent_activity_orientation']")
                self.assertEqual(int(value), orientation)


if __name__ == "__main__":
    unittest.main()
