"""Exercise the browser network check with JVM-only connection boundaries."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from profile_gecko_window_selection_test import member


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app/src/main/java/local/pocketchat"
CHROMIUM = ROOT / "chromium/src/main/java/local/pocketchat"


class BrowserNetworkCheckTests(unittest.TestCase):
    def test_live_chromium_check_uses_exact_route_and_is_read_only(self):
        java = Path(os.environ.get("PROFILE_JAVA") or shutil.which("java") or "")
        javac = java.with_name("javac.exe" if os.name == "nt" else "javac")
        self.assertTrue(java.is_file() and javac.is_file(), "A JDK is required")
        route = (CHROMIUM / "CefriumRoute.java").read_text(encoding="utf-8")
        methods = "\n".join(member(route, signature) for signature in (
            "private boolean ready(Grant selected)", "private boolean evidenceUsable(Grant selected)",
            "String networkCheckSummary()", "private boolean baseCurrent(Grant selected)",
        ))
        template = (ROOT / "tests/browser-runtime/CefriumNetworkCheckHost.java.in").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="cefrium-network-check-") as folder:
            path = Path(folder) / "CefriumNetworkCheckHost.java"
            path.write_text(template.replace("/* PRODUCTION_METHODS */", methods), encoding="utf-8")
            build = subprocess.run([str(javac), "-encoding", "UTF-8", "-d", folder, str(path),
                                    str(APP / "CefriumRoutePolicy.java")], capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(java), "-cp", folder, "local.pocketchat.CefriumNetworkCheckHost"],
                                 capture_output=True, text=True, timeout=25)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), "Cefrium local network check passed")

    def test_entry_opens_this_engine_and_keeps_network_settings_bound(self):
        browser = (CHROMIUM / "CefriumBrowserActivity.java").read_text(encoding="utf-8")
        self.assertIn('"网络环境检查",false,this::showNetworkCheck', member(browser, "private void createScreen("))
        entry = member(browser, "private void showNetworkCheck()")
        self.assertIn("selected.networkCheckSummary()", entry)
        self.assertIn('openWorkspace("network")', entry)
        self.assertNotIn("EnvironmentAuditUi", entry)
        workspace = member(browser, "private void openWorkspace(")
        for guard in ("files.busy()", "stillSelected()", "Profiles.activity(identity.slot)"):
            self.assertIn(guard, workspace)


if __name__ == "__main__":
    unittest.main()
