"""Compile the new adapters against real Android APIs, with declared app edges.

This is not an APK build, Android execution, Gecko integration or UI acceptance.
The application and Gecko boundary signatures are supplied by one local double;
the actual Android framework classes come only from android.jar.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "app/src/main/java/local/pocketchat"
PINS = {
    "desktop": "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796",
    "android-json": "dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def android_jar():
    configured = os.environ.get("PROFILE_ANDROID_JAR")
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise AssertionError("PROFILE_ANDROID_JAR does not name a real Android platform JAR")
        return path
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if sdk:
        for version in ("android-37.1", "android-37", "android-35"):
            path = Path(sdk) / "platforms" / version / "android.jar"
            if path.is_file():
                return path
    raise AssertionError("Set PROFILE_ANDROID_JAR or ANDROID_HOME to an installed Android SDK")


class FirstFiveUiCompileTest(unittest.TestCase):
    def test_actual_ui_adapters_compile_on_android_with_both_json_runtimes(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17 with jdk.compiler is required")
        framework = android_jar()
        identity_only = os.environ.get("FIRST_FIVE_UI_IDENTITY_ONLY") == "1"
        names = [
            "EnvironmentIdentityUi", "EnvironmentIdentityStatus", "EnvironmentSpec",
            "BrowserIdentitySpec", "GeckoSettings", "FingerprintObservationHistory", "J",
        ]
        if not identity_only:
            names += [
                "ProtectionTemplateUi", "FingerprintComparisonUi", "ProtectionTemplateAssessment", "NativeCapabilityManifest",
                "FingerprintDeepBaseline", "FingerprintContextBaselines",
                "FingerprintReportComparison", "AuditReport",
            ]
            # AuditReport may use the newly added finite public-field comparator.
            if (PRODUCTION / "MobileIdentityConsistency.java").is_file():
                names.append("MobileIdentityConsistency")
        sources = [PRODUCTION / (name + ".java") for name in names]
        sources += [ROOT / "tests/first-five-ui-compile/BoundaryDoubles.java"]
        for source in sources:
            self.assertTrue(source.is_file(), "Required production UI source missing: " + str(source))
        self.assertNotIn("package android.", sources[-1].read_text())
        inputs = [*sources, Path(__file__)]
        before = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
        jars = {
            "desktop": Path(os.environ.get("PROFILE_JSON_JAR", ROOT / "work/profile-host/json.jar")),
            "android-json": Path(os.environ.get("PROFILE_ANDROID_JSON_JAR", ROOT / "work/profile-host/android-json.jar")),
        }
        runs = []
        for runtime, dependency in jars.items():
            self.assertTrue(dependency.is_file(), "Pinned JSON dependency missing: " + str(dependency))
            self.assertEqual(digest(dependency), PINS[runtime], "JSON dependency differs from the pinned input")
            with tempfile.TemporaryDirectory(prefix="first-five-ui-compile-") as temp:
                result = subprocess.run([
                    java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "--release", "8",
                    "-encoding", "UTF-8", "-cp", os.pathsep.join((str(dependency), str(framework))),
                    "-d", temp, *map(str, sources),
                ], capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, runtime + "\n" + result.stdout + result.stderr)
                runs.append({"runtime": runtime, "jsonSha256": digest(dependency),
                             "compileStdout": result.stdout, "compileStderr": result.stderr,
                             "compiledAdapters": ["EnvironmentIdentityUi"] if identity_only else
                                 ["EnvironmentIdentityUi", "ProtectionTemplateUi", "FingerprintComparisonUi"]})
        self.assertEqual(before, {str(path.relative_to(ROOT)): digest(path) for path in inputs})
        report = {
            "schema": 1, "status": "passed", "androidFrameworkJarSha256": digest(framework),
            "actualAndroidFrameworkClasses": True, "applicationAndGeckoBoundaryDoubles": True,
            "actualAndroidExecution": False, "actualGeckoExecution": False,
            "fullApplicationCompilation": False, "apkBuilt": False,
            "physicalPhoneAcceptance": False, "identityOnlyDevelopmentCheck": identity_only,
            "sourceSha256": before, "runs": runs,
            "scope": "Real production UI adapters and pure models compile against an installed Android platform JAR. "
                     "Local app/Gecko doubles do not establish actual integration or runtime UI behavior.",
        }
        target = ROOT / "work/first-five-ui/compile-results.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
