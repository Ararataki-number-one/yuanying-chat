#!/usr/bin/env python3
"""Build a private, self-targeting Android test APK; never build the browser APK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = "local.pocketchat.aidiagnostics"
INSTRUMENTATION = "local.pocketchat.AiDiagnosticInstrumentation"
ANDROID = "{http://schemas.android.com/apk/res/android}"
PRODUCTION = tuple("app/src/main/java/local/pocketchat/" + name + ".java" for name in (
    "J", "AiDiagnosticUi", "AiDiagnosticGateway", "AiDiagnosticReply",
    "AiDiagnosticEvidence", "AiDiagnosticJson"))
TEST_JAVA = {"AiDiagnosticInstrumentation.java", "MainActivity.java", "AiDiagnosticRoute.java"}
MAX_INPUT_BYTES = 2 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def regular(path, limit=None):
    require(path.is_file() and not path.is_symlink(), "Missing or nonregular input: " + str(path))
    require(limit is None or 0 < path.stat().st_size <= limit, "Input size outside bound: " + str(path))
    return path


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON member")
        value[key] = item
    return value


def validate_manifest(path):
    root = ET.fromstring(regular(path, 65536).read_bytes())
    require(root.tag == "manifest" and root.get("package") == PACKAGE, "Unexpected test package")
    require(root.get(ANDROID + "sharedUserId") is None, "Shared UID is forbidden")
    # No permission is needed, including INTERNET. Reject other manifest-level
    # capabilities too; this APK exists only inside the disposable test AVD.
    require(all(node.tag in {"uses-sdk", "application", "instrumentation"} for node in root),
            "Unexpected test manifest capability")
    sdk = root.findall("uses-sdk")
    require(len(sdk) == 1 and sdk[0].get(ANDROID + "minSdkVersion") == "35"
            and sdk[0].get(ANDROID + "targetSdkVersion") == "35", "API 35 manifest required")
    entries = root.findall("instrumentation")
    require(len(entries) == 1 and entries[0].get(ANDROID + "name") == INSTRUMENTATION
            and entries[0].get(ANDROID + "targetPackage") == PACKAGE,
            "Instrumentation must target this test package itself")
    apps = root.findall("application")
    require(len(apps) == 1, "Exactly one test application required")
    app = apps[0]
    require(app.get(ANDROID + "testOnly") == "true" and app.get(ANDROID + "allowBackup") == "false",
            "Explicit testOnly and backup prohibition required")
    require(app.get(ANDROID + "name") is None and app.get(ANDROID + "usesCleartextTraffic") != "true"
            and app.get(ANDROID + "networkSecurityConfig") is None,
            "No custom application or network trust configuration permitted")
    activities = list(app)
    require(len(activities) == 1 and activities[0].tag == "activity"
            and activities[0].get(ANDROID + "name") == "local.pocketchat.MainActivity"
            and activities[0].get(ANDROID + "exported") == "false"
            and not list(activities[0]), "Only the private test Activity may be packaged")


def inputs():
    pins_path = regular(HERE / "source-hashes.json", 16384)
    pins = json.loads(pins_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    require(type(pins) is dict and set(pins) == set(PRODUCTION), "Exactly six production source pins required")
    require(all(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) for value in pins.values()),
            "Invalid production SHA-256 pin")
    discovered = {path.relative_to(HERE).as_posix() for path in HERE.rglob("*.java")}
    require(discovered == TEST_JAVA, "Unexpected or missing test Java source")
    production = {name: sha(regular(ROOT / name, MAX_INPUT_BYTES)) for name in PRODUCTION}
    require(production == pins, "Production source differs from the explicit accepted SHA-256 pins")
    manifest = HERE / "AndroidManifest.xml"
    validate_manifest(manifest)
    tests = {path.relative_to(ROOT).as_posix(): sha(regular(path, MAX_INPUT_BYTES))
             for path in [*(HERE / name for name in sorted(TEST_JAVA)), manifest]}
    files = [*(ROOT / name for name in PRODUCTION), *(HERE / name for name in sorted(TEST_JAVA))]
    require(sum(path.stat().st_size for path in files) <= MAX_INPUT_BYTES, "Source byte limit exceeded")
    return files, manifest, dict(productionSources=production, testSources=tests,
                                productionPinsSha256=sha(pins_path), buildScriptSha256=sha(Path(__file__)))


def properties(path):
    return dict(line.split("=", 1) for line in regular(path, 65536).read_text().splitlines()
                if "=" in line and not line.lstrip().startswith("#"))


def environment(java_home, scratch):
    env = dict(os.environ)
    for name in ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "JDK_JAVAC_OPTIONS", "CLASSPATH"):
        env.pop(name, None)
    env.update(JAVA_HOME=str(java_home), PATH=str(java_home / "bin") + os.pathsep + os.defpath,
               LC_ALL="C", TMPDIR=str(scratch))
    return env


def run(command, env, timeout=180):
    result = subprocess.run([str(part) for part in command], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env, timeout=timeout, check=False)
    require(len(result.stdout) + len(result.stderr) <= 4 * 1024 * 1024, "Tool output exceeded bound")
    if result.returncode:
        # Inputs are synthetic and bounded. Compiler diagnostics are useful;
        # commands, key material, environment and arbitrary paths are not dumped.
        error = (result.stdout + result.stderr)[:16384].decode("utf-8", "replace")
        raise ValueError(Path(str(command[0])).name + " failed: " + error)
    return result.stdout, result.stderr


def toolchain(sdk, scratch):
    require(sdk.is_absolute() and sdk.is_dir(), "--sdk must be an existing absolute SDK directory")
    platform = sdk / "platforms/android-35"
    build = sdk / "build-tools/37.0.0"
    props = properties(platform / "source.properties")
    require(props.get("AndroidVersion.ApiLevel") == "35" and props.get("Pkg.UserSrc") != "true",
            "Official Android 35 platform metadata required")
    package = ET.fromstring(regular(platform / "package.xml", 1024 * 1024).read_bytes())
    packages = [node for node in package.iter() if node.tag.rsplit("}", 1)[-1] == "localPackage"]
    require(len(packages) == 1 and packages[0].get("path") == "platforms;android-35",
            "Android platform package identity differs")
    require(properties(build / "source.properties").get("Pkg.Revision") == "37.0.0",
            "Build-tools 37.0.0 required")
    java_home = Path(os.environ.get("JAVA_HOME", ""))
    require(java_home.is_absolute() and java_home.is_dir(), "Explicit absolute JAVA_HOME for JDK 17 required")
    chain = {name: regular(java_home / "bin" / name) for name in ("java", "javac", "jar", "keytool")}
    chain.update(androidJar=regular(platform / "android.jar"), aapt2=regular(build / "aapt2"),
                 zipalign=regular(build / "zipalign"), d8=regular(build / "lib/d8.jar"),
                 apksigner=regular(build / "lib/apksigner.jar"))
    with zipfile.ZipFile(chain["androidJar"]) as archive:
        require({"android/app/Instrumentation.class", "android/content/Context.class",
                 "org/json/JSONObject.class"} <= set(archive.namelist()), "Official Android API classes missing")
    env = environment(java_home, scratch)
    out, err = run([chain["java"], "-version"], env, 15)
    version = (out + err).decode("utf-8", "strict").strip()
    require(re.search(r'\bversion "17(?:[."]|\+)', version) is not None, "JDK 17 required")
    receipt = dict(javaVersion=version, androidApi=35, buildTools="37.0.0",
                   sha256={name: sha(path) for name, path in chain.items()})
    receipt["sha256"].update(androidPlatformProperties=sha(platform / "source.properties"),
                             androidPlatformPackage=sha(platform / "package.xml"),
                             androidBuildToolsProperties=sha(build / "source.properties"))
    return chain, env, receipt


def verify_apk(chain, apk, expected_signer, env):
    output, _ = run([chain["java"], "-jar", chain["apksigner"], "verify",
                     "--verbose", "--print-certs", apk], env, 60)
    signers = re.findall(
        rb"^(?:Signer #[0-9]+ |V[1-4](?:\.[0-9]+)? Signer(?: #[0-9]+)?: )"
        rb"certificate SHA-256 digest: ([0-9a-fA-F]{64})\r?$", output, re.MULTILINE)
    require(re.search(rb"^Number of signers: 1\r?$", output, re.MULTILINE)
            and {value.decode().lower() for value in signers} == {expected_signer},
            "APK signer differs from the ephemeral test certificate")
    output, _ = run([chain["aapt2"], "dump", "badging", apk], env, 30)
    badging = output.decode("utf-8", "strict")
    require(re.search(r"^package: name='" + re.escape(PACKAGE) + r"' ", badging, re.MULTILINE),
            "Packaged application ID differs")
    require("native-code:" not in badging, "Standalone test APK must not contain native libraries")
    output, _ = run([chain["aapt2"], "dump", "permissions", apk], env, 30)
    require(b"uses-permission" not in output and b"android.permission." not in output,
            "Packaged APK unexpectedly requests permissions")
    output, _ = run([chain["aapt2"], "dump", "xmltree", "--file", "AndroidManifest.xml", apk], env, 30)
    xmltree = output.decode("utf-8", "strict")
    require(INSTRUMENTATION in xmltree and ("targetPackage" in xmltree) and ("testOnly" in xmltree),
            "Packaged instrumentation metadata missing")
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        require("classes.dex" in names and not any(name.startswith("lib/") for name in names),
                "Test APK executable shape differs")


def build(sdk, output):
    require(output.is_absolute() and not output.exists() and not output.is_symlink(),
            "--output must be a new absolute private directory")
    require(output.parent.is_dir(), "Output parent directory must already exist")
    sources, manifest, identities = inputs()
    output.mkdir(mode=0o700)
    try:
        with tempfile.TemporaryDirectory(prefix=".build-", dir=output) as temporary:
            scratch = Path(temporary)
            chain, env, tools_receipt = toolchain(sdk, scratch)
            classes, dex = scratch / "classes", scratch / "dex"
            classes.mkdir(); dex.mkdir()
            # Freeze exact source bytes in the private workspace; no source rewriting.
            frozen = scratch / "source"
            copies = []
            for path in sources:
                copy = frozen / path.relative_to(ROOT)
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.write_bytes(path.read_bytes())
                relative = path.relative_to(ROOT).as_posix()
                expected = identities["productionSources"].get(relative, identities["testSources"].get(relative))
                require(sha(copy) == expected, "Source changed while freezing private build inputs")
                copies.append(copy)
            manifest_copy = scratch / "AndroidManifest.xml"
            manifest_copy.write_bytes(manifest.read_bytes())
            require(sha(manifest_copy) == identities["testSources"][manifest.relative_to(ROOT).as_posix()],
                    "Manifest changed while freezing private build inputs")
            require(inputs()[2] == identities, "Build inputs changed while copying")
            run([chain["javac"], "-proc:none", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                 "-classpath", chain["androidJar"], "-sourcepath", frozen,
                 "-d", classes, *copies], env)
            classes_jar = scratch / "classes.jar"
            run([chain["jar"], "cf", classes_jar, "-C", classes, "."], env, 30)
            run([chain["java"], "-cp", chain["d8"], "com.android.tools.r8.D8",
                 "--lib", chain["androidJar"], "--min-api", "35", "--output", dex, classes_jar], env)
            unsigned, aligned, signed = (scratch / name for name in ("unsigned.apk", "aligned.apk", "signed.apk"))
            run([chain["aapt2"], "link", "-I", chain["androidJar"], "--manifest", manifest_copy,
                 "-o", unsigned], env, 60)
            dex_files = sorted(dex.glob("classes*.dex"))
            require(1 <= len(dex_files) <= 4, "Unexpected dex file count")
            with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_STORED) as archive:
                for path in dex_files:
                    archive.write(path, path.name)
            run([chain["zipalign"], "-f", "-p", "4", unsigned, aligned], env, 30)
            key = scratch / "ephemeral-test.jks"
            run([chain["keytool"], "-genkeypair", "-storetype", "JKS", "-keystore", key,
                 "-alias", "androiddebugkey", "-storepass", "android", "-keypass", "android",
                 "-dname", "CN=PocketChat Disposable AI Instrumentation", "-keyalg", "RSA",
                 "-keysize", "2048", "-validity", "2", "-noprompt"], env, 60)
            key.chmod(0o600)
            cert, _ = run([chain["keytool"], "-exportcert", "-keystore", key, "-alias",
                           "androiddebugkey", "-storepass", "android"], env, 30)
            signer = hashlib.sha256(cert).hexdigest()
            run([chain["java"], "-jar", chain["apksigner"], "sign", "--ks", key,
                 "--ks-key-alias", "androiddebugkey", "--ks-pass", "pass:android",
                 "--key-pass", "pass:android", "--v4-signing-enabled", "false",
                 "--out", signed, aligned], env, 60)
            verify_apk(chain, signed, signer, env)
            require(inputs()[2] == identities, "Build inputs changed during compilation")
            receipt = dict(schema=1, kind="ai-diagnostic-instrumentation-build", status="built",
                           package=PACKAGE, instrumentation=INSTRUMENTATION, targetPackage=PACKAGE,
                           testOnly=True, internetPermission=False, originalApk=False,
                           actualAndroidExecution=False, providerRequests=0, **identities,
                           apkSha256=sha(signed), apkBytes=signed.stat().st_size,
                           signerSha256=signer, toolchain=tools_receipt)
            require(receipt["apkBytes"] <= 16 * 1024 * 1024, "Standalone APK exceeds size bound")
            destination = output / "instrumentation-test.apk"
            shutil.copyfile(signed, destination)
            destination.chmod(0o600)
            report = output / "build-report.json"
            report.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            report.chmod(0o600)
        require({path.name for path in output.iterdir()} == {"instrumentation-test.apk", "build-report.json"},
                "Unexpected private build output")
        return receipt
    except BaseException:
        # This function created the directory and owns only these two outputs.
        for name in ("instrumentation-test.apk", "build-report.json"):
            (output / name).unlink(missing_ok=True)
        if output.exists() and not any(output.iterdir()):
            output.rmdir()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        receipt = build(args.sdk, args.output)
    except (ValueError, OSError, ET.ParseError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        print("Instrumentation build failed: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps({key: receipt[key] for key in ("status", "package", "apkSha256", "signerSha256")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
