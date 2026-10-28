"""Compile the 2.0.26 identity adapter against real Android APIs, with declared app edges.

This is not an APK build, Android execution, Gecko integration or UI acceptance.
The application and Gecko boundary signatures are supplied by one local double;
the actual Android framework classes come only from android.jar. A labelled JVM
adapter host also exercises the production runtime projection with app doubles;
it does not execute Android framework or Gecko methods.
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

ADMISSION_HOST = r'''
package local.pocketchat;
import org.json.JSONObject;
public final class EnvironmentIdentityUiAdmissionHost {
    private static void check(String name, boolean pass) {
        if (!pass) throw new AssertionError(name);
    }
    public static void main(String[] args) throws Exception {
        ChatSession session = new ChatSession();
        session.environmentId = "70208cc2-508b-43c3-95c0-01d6d84fa0b5";
        session.environmentGeneration = 1;
        session.web = new GeckoWebView();
        session.audit = new EnvironmentAudit();
        session.guard = new BrowserNetworkGuard();
        session.identity = new IdentityTemplateController();
        session.networkReady = true;
        session.guard.routeAllowed = true;
        session.web.networkAllowed = true;
        session.identity.routeAdmitted = true;
        check("A currently admitted route is displayed as admitted",
            EnvironmentIdentityUi.runtime(session).getBoolean("routeAdmitted"));

        // Revocation can precede the asynchronous ready/guard UI update.
        session.identity.routeAdmitted = false;
        check("With legacy readiness retained, revoked authoritative admission is not displayed as admitted",
            session.networkReady && session.guard.allowed()
                && !EnvironmentIdentityUi.runtime(session).getBoolean("routeAdmitted"));

        session.identity.routeAdmitted = true;
        session.web.networkAllowed = false;
        check("Native protection still blocks the displayed admission",
            !EnvironmentIdentityUi.runtime(session).getBoolean("routeAdmitted"));
        System.out.println(new JSONObject().put("status", "passed").put("passed", 3)
            .put("adapterHost", true).put("applicationAndGeckoBoundaryDoubles", true)
            .put("actualAndroidExecution", false).put("actualGeckoExecution", false));
    }
}
'''


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


class EnvironmentIdentityUiTest(unittest.TestCase):
    def test_identity_adapter_compiles_and_projects_authoritative_admission(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17 with jdk.compiler is required")
        framework = android_jar()
        names = [
            "EnvironmentIdentityUi", "EnvironmentIdentityStatus", "EnvironmentSpec",
            "BrowserIdentitySpec", "GeckoSettings", "FingerprintObservationHistory", "J",
        ]
        sources = [PRODUCTION / (name + ".java") for name in names]
        sources += [ROOT / "tests/environment-identity-ui-host/BoundaryDoubles.java"]
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
            with tempfile.TemporaryDirectory(prefix="environment-identity-ui-") as temp:
                host = Path(temp) / "EnvironmentIdentityUiAdmissionHost.java"
                host.write_text(ADMISSION_HOST, encoding="utf-8")
                result = subprocess.run([
                    java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "--release", "8",
                    "-encoding", "UTF-8", "-cp", os.pathsep.join((str(dependency), str(framework))),
                    "-d", temp, *map(str, sources), str(host),
                ], capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, runtime + "\n" + result.stdout + result.stderr)
                host_run = subprocess.run([
                    java, "-cp", os.pathsep.join((temp, str(dependency), str(framework))),
                    "local.pocketchat.EnvironmentIdentityUiAdmissionHost",
                ], capture_output=True, text=True, timeout=15)
                self.assertEqual(host_run.returncode, 0, runtime + "\n" + host_run.stdout + host_run.stderr)
                host_report = json.loads(host_run.stdout)
                self.assertEqual(host_report["status"], "passed")
                self.assertEqual(host_report["passed"], 3)
                runs.append({"runtime": runtime, "jsonSha256": digest(dependency),
                             "compileStdout": result.stdout, "compileStderr": result.stderr,
                             "runtimeAdmissionAdapterHost": host_report,
                             "compiledAdapters": ["EnvironmentIdentityUi"]})
        self.assertEqual(before, {str(path.relative_to(ROOT)): digest(path) for path in inputs})
        report = {
            "schema": 1, "status": "passed", "androidFrameworkJarSha256": digest(framework),
            "actualAndroidFrameworkClasses": True, "applicationAndGeckoBoundaryDoubles": True,
            "actualAndroidExecution": False, "actualGeckoExecution": False,
            "fullApplicationCompilation": False, "apkBuilt": False,
            "physicalPhoneAcceptance": False, "versionScope": "2.0.26-only",
            "runtimeAdmissionHostSourceSha256": hashlib.sha256(ADMISSION_HOST.encode("utf-8")).hexdigest(),
            "sourceSha256": before, "runs": runs,
            "scope": "The 2.0.26 production identity UI adapter and pure models compile against an installed Android platform JAR. "
                     "A JVM adapter host verifies route-admission projection over app/Gecko boundary doubles; "
                     "neither check establishes actual integration, Android execution or runtime UI behavior.",
        }
        target = ROOT / "work/environment-identity-ui/host-results.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
