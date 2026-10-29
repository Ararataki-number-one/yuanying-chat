"""Production filesystem root admission and destructive-delete ordering checks.

These are JVM/source checks, not Android deletion or phone acceptance evidence.
The original 39 lifecycle host controls and device producer remain unchanged.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/src/main/java/local/pocketchat"


def remove_body():
    text = (SOURCE / "EnvironmentDeleteActivity.java").read_text()
    start = text.index("private static void performRemove(Context c,int slot,EnvironmentSpec.Identity expected)throws Exception{")
    end = text.index("  static void erase(File f)", start)
    return text[start:end]


class EnvironmentDeleteRootGuardTest(unittest.TestCase):
    def test_actual_root_policy_on_real_filesystem(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17+ with jdk.compiler is required")
        with tempfile.TemporaryDirectory(prefix="environment-delete-root-classes-") as output:
            subprocess.run([
                java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-encoding", "UTF-8",
                "-source", "8", "-target", "8", "-d", output,
                str(SOURCE / "EnvironmentBrowserData.java"),
                str(ROOT / "tests/browser-runtime/EnvironmentDeleteRootPolicyTest.java"),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            execution = subprocess.run([
                java, "-cp", output, "local.pocketchat.EnvironmentDeleteRootPolicyTest",
            ], cwd=ROOT, check=True, capture_output=True, text=True)
        result = json.loads(execution.stdout)
        self.assertEqual(result, dict(status="passed", passed=8,
            actualAndroidExecution=False, actualProductionRootPolicyExecution=True))

    def test_first_guard_precedes_all_delete_side_effects(self):
        body = remove_body()
        first_statement = body[body.index("{") + 1:].lstrip()
        self.assertTrue(first_statement.startswith("EnvironmentResetActivity.verifyRoots(c,slot);"))
        first_guard = body.index("EnvironmentResetActivity.verifyRoots(c,slot);")
        for side_effect in ["ProfileCatalog.get(c)", "Profiles.context(c,slot)",
                "DownloadLibrary.get(c).migrate()", "new NetworkCatalog(c)",
                '"stopForDelete"']:
            self.assertLess(first_guard, body.index(side_effect), side_effect)

    def test_second_guard_follows_writer_exit_and_precedes_enumeration(self):
        body = remove_body()
        guards = list(re.finditer(re.escape("EnvironmentResetActivity.verifyRoots(c,slot);"), body))
        self.assertEqual(len(guards), 2)
        second = guards[1].start()
        # The guard must follow the entire bounded stop/kill loop, including
        # its successful !alive exit, not just its first kill attempt.
        self.assertLess(body.index('"stopForDelete"'), second)
        self.assertLess(body.index("android.os.Process.killProcess(p.pid)"), second)
        self.assertLess(body.index("Thread.sleep(100);}while(true);"), second)
        for destructive_step in ["NotificationManager notices=", "files.listFiles()",
                'erase(new File(data,"cache/profiles/env"+slot))',
                'erase(new File(profile.getNoBackupFilesDir(),name))',
                'profile.deleteDatabase(name)', "catalog.completeDelete(expected)"]:
            self.assertLess(second, body.index(destructive_step), destructive_step)


if __name__ == "__main__":
    unittest.main()
