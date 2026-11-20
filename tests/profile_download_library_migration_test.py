"""Exercise production download migration across a controlled write failure and restart."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DownloadLibraryMigrationTest(unittest.TestCase):
    def test_retries_without_overwriting_or_restoring_removed_records(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17+ required")
        deps = ROOT / "work/profile-host"
        pins = (
            ("PROFILE_JSON_JAR", deps / "json.jar",
             "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796"),
            ("PROFILE_ANDROID_JSON_JAR", deps / "android-json.jar",
             "dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79"),
        )
        command = [sys.executable, "-B", str(ROOT / "tests/download-persistence-host/migration.py"),
                   "--java-home", str(Path(java).resolve().parents[1])]
        for variable, path, sha in pins:
            jar = Path(os.environ.get(variable, path))
            self.assertTrue(jar.is_file(), "Pinned JSON jar required: " + str(jar))
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), sha)
            command.extend(("--json-jar", str(jar)))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reset_migrates_target_before_erasing_download_state(self):
        path = ROOT / "app/src/main/java/local/pocketchat/EnvironmentResetActivity.java"
        source = path.read_text()
        reset = source[source.index("private static void performReset("):]
        migration = reset.index("DownloadLibrary.get(c).migrateBeforeRemoval(slot)")
        self.assertLess(reset.index("terminate(c,slot)"), migration)
        self.assertLess(reset.index("catalog.withReset(plan.next,()->null)"), migration)
        for action in ("ChromiumProfileCleanup.clearRetired", "EnvironmentBrowserData.clear(",
                       "removeEnvironmentTasks(slot)", 'getSharedPreferences("download-tasks",0).edit().clear()',
                       "repository.finishLoginReset(plan)"):
            self.assertLess(migration, reset.index(action), action)


if __name__ == "__main__":
    unittest.main()
