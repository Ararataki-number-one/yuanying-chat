#!/usr/bin/env python3
"""Build the signed, emulator-only shell input driver; never a release APK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import subprocess
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_input_contract import decode, verify_signature_logs

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = 'tools/gecko/VerifyNativeInputSignature.java'
API = 'native-input-driver-signature-api.json'
PACKAGE = 'local.pocketchat.inputdriver'
INSTRUMENTATION = PACKAGE + '.NativeInputInstrumentation'
TARGET = 'local.pocketchat.test'
EXECUTION_BACKEND = 'shell-input-manager-global-v1'
ENTRY_POINT = PACKAGE + '.NativeInputShell'
EXECUTION_UID = 2000
PROTOCOLS = {
    'qualification': dict(durationMs=300, moveCount=19, intervalMs=15, maxLateMs=30, upSynchronous=True),
    'formal-collapse': dict(durationMs=320, moveCount=19, intervalMs=16, maxLateMs=32, upSynchronous=True),
}
ASSET = 'native-input-driver-build.json'
ANDROID = '{http://schemas.android.com/apk/res/android}'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(root):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    require(re.fullmatch('[0-9a-f]{40}', source) and re.fullmatch('[0-9a-f]{40}', tree), 'Invalid source identity')
    require(not git('status', '--porcelain', '--untracked-files=normal'), 'Input driver requires clean committed source')
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    require(run.isdigit() and attempt.isdigit(), 'Input driver requires CI run identity')
    return dict(sourceCommit=source, sourceTree=tree, runId=run, runAttempt=attempt)


def inputs(root):
    directory = root / 'tests/native-input-driver'
    files = sorted(directory.glob('*.java')) + [directory / 'AndroidManifest.xml']
    require(len(files) > 1 and all(p.is_file() and not p.is_symlink() for p in files), 'Missing regular driver sources')
    require(directory/'NativeInputShell.java' in files, 'Missing standalone shell entry source')
    manifest = ET.parse(files[-1]).getroot()
    require(manifest.get('package') == PACKAGE, 'Input driver must use its own package')
    require(manifest.get(ANDROID + 'sharedUserId') is None, 'Input driver cannot declare sharedUserId')
    entries = manifest.findall('instrumentation')
    require(len(entries) == 1 and entries[0].get(ANDROID + 'name') == INSTRUMENTATION
            and entries[0].get(ANDROID + 'targetPackage') == PACKAGE,
            'Instrumentation must target only the input driver itself')
    application = manifest.find('application')
    require(application is not None and not list(application), 'Input driver cannot declare Activities, services or providers')
    require(not manifest.findall('uses-permission'), 'Input driver cannot request privileged app permissions')
    return files, {p.relative_to(root).as_posix(): sha(p) for p in files}


def tools(java_home, android_sdk, android_jar=None):
    java_home, android_sdk = Path(java_home), Path(android_sdk)
    build = android_sdk / 'build-tools/37.0.0'
    found = dict(java=java_home/'bin/java', javac=java_home/'bin/javac', jar=java_home/'bin/jar',
                 androidJar=Path(android_jar) if android_jar else android_sdk/'platforms/android-37.1/android.jar',
                 aapt2=build/'aapt2', zipalign=build/'zipalign', apksigner=build/'apksigner', apksignerJar=(build/'lib/apksigner.jar').resolve(), d8=build/'lib/d8.jar')
    require(all(p.is_file() for k, p in found.items() if k not in ('aapt2', 'zipalign', 'apksigner', 'apksignerJar', 'd8') or android_jar is None),
            'Pinned JDK/SDK build tools are missing')
    version = subprocess.check_output([str(found['java']), '-version'], stderr=subprocess.STDOUT, text=True).strip()
    require(re.search(r'version "17[.\"]', version) is not None, 'Input driver requires JDK 17')
    return found, dict(javaVersion=version, platform='android-37.1' if android_jar is None else 'compile-only override',
                      buildTools='37.0.0', tools={key: dict(path=str(path), sha256=sha(path))
                                               for key, path in found.items() if path.is_file()})


def build(root, java_home, android_sdk, key=None, compile_only=False, android_jar=None):
    root = Path(root).resolve()
    require(compile_only or android_jar is None, 'A platform override is permitted only for compile-only checks')
    selected = None if compile_only else identity(root)
    sources, hashes = inputs(root)
    chain, provenance = tools(java_home, android_sdk, android_jar)
    work = root / 'work/native-input-driver-build' / ('compile-only' if compile_only else 'strict')
    if work.exists():
        shutil.rmtree(work)
    classes, dex, assets = work/'classes', work/'dex', work/'assets'
    for path in (classes, dex, assets):
        path.mkdir(parents=True)
    commands = []

    def run(*parts, capture=False, check=True):
        command = [str(x) for x in parts]
        commands.append(command)
        environment = dict(os.environ, JAVA_HOME=str(Path(java_home)),
                           PATH=str(Path(java_home)/'bin') + os.pathsep + os.environ.get('PATH', ''))
        return subprocess.run(command, cwd=root, check=check, env=environment,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None)

    run(chain['javac'], '-encoding', 'UTF-8', '-source', '8', '-target', '8',
        '-classpath', chain['androidJar'], '-d', classes, *[p for p in sources if p.suffix == '.java'])
    require(inputs(root)[1] == hashes, 'Input sources changed during compilation')
    if compile_only:
        result = dict(schema=1, status='compiled', compileOnly=True, actualAndroidExecution=False,
                      releaseAcceptance=False, inputs=hashes, toolchain=provenance, commands=commands)
        (work/'compile-only.json').write_text(json.dumps(result, indent=2)+'\n')
        return result

    verifier = root / VERIFIER
    require(verifier.is_file() and not verifier.is_symlink(), 'Missing regular signature verifier source')
    verifier_hash = sha(verifier)
    verifier_classes = work/'signature-verifier'; verifier_classes.mkdir()
    run(chain['javac'], '-encoding', 'UTF-8', '-classpath', chain['apksignerJar'],
        '-d', verifier_classes, verifier)

    expected_key = root / 'work/gecko-integration/integration-test.jks'
    require(key is not None and Path(key).absolute() == expected_key and not expected_key.is_symlink()
            and expected_key.is_file(), 'Only this CI run\'s explicit integration-test.jks is permitted')
    stamp = dict(schema=1, **selected, packageName=PACKAGE, instrumentation=INSTRUMENTATION,
                 targetPackage=TARGET, instrumentationTargetPackage=PACKAGE, protocols=PROTOCOLS,
                 inputs=hashes, toolchain=provenance, testOnly=True,
                 executionBackend=EXECUTION_BACKEND, entryPoint=ENTRY_POINT, executionUid=EXECUTION_UID,
                 inputTargetUidEnforced=True)
    asset_raw = (json.dumps(stamp, sort_keys=True, indent=2)+'\n').encode()
    (assets/ASSET).write_bytes(asset_raw)
    run(chain['jar'], 'cf', work/'classes.jar', '-C', classes, '.')
    run(chain['java'], '-cp', chain['d8'], 'com.android.tools.r8.D8', '--lib', chain['androidJar'],
        '--min-api', '26', '--output', dex, work/'classes.jar')
    unsigned, aligned, signed = work/'unsigned.apk', work/'aligned.apk', work/'signed.apk'
    run(chain['aapt2'], 'link', '-I', chain['androidJar'], '--manifest', sources[-1], '-A', assets,
        '-o', unsigned)
    dex_files = sorted(dex.glob('classes*.dex'))
    require(bool(dex_files), 'Input driver compiler produced no DEX')
    with zipfile.ZipFile(unsigned, 'a', compression=zipfile.ZIP_STORED) as archive:
        for path in dex_files:
            archive.write(path, path.name)
    run(chain['zipalign'], '-f', '-p', '4', unsigned, aligned)
    # The only accepted key path is the ephemeral key created by this CI build.
    run(chain['java'], '-jar', chain['apksignerJar'], 'sign', '--ks', expected_key, '--ks-key-alias', 'androiddebugkey',
        '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', signed, aligned)
    output = root/'work/gecko-integration'; output.mkdir(parents=True, exist_ok=True)
    verification = run(chain['java'], '-jar', chain['apksignerJar'], 'verify', '--verbose', '--print-certs', signed,
                       capture=True, check=False)
    signature_logs = {}
    for stream in ('stdout', 'stderr'):
        name = 'native-input-driver-signature-' + stream + '.log'
        data = getattr(verification, stream)
        (output/name).write_bytes(data)
        signature_logs[name] = hashlib.sha256(data).hexdigest()
    api = run(chain['java'], '-classpath', str(verifier_classes)+os.pathsep+str(chain['apksignerJar']),
              'VerifyNativeInputSignature', signed, verifier,
              *[selected[k] for k in ('sourceCommit','sourceTree','runId','runAttempt')], capture=True, check=False)
    api_logs = {}
    for stream in ('stdout', 'stderr'):
        name = 'native-input-driver-signature-api-' + stream + '.log'
        data = getattr(api, stream)
        (output/name).write_bytes(data)
        api_logs[name] = hashlib.sha256(data).hexdigest()
    (output/API).write_bytes(api.stdout)
    try:
        verification.check_returncode()
        api.check_returncode()
        value = decode(api.stdout)
        signer = value['signerCertificateSha256']
        evidence = dict(**selected, apkSha256=sha(signed), apkBytes=signed.stat().st_size,
                        signerCertificateSha256=signer, toolchain=provenance,
                        signatureVerifierSourceSha256=verifier_hash, signatureLogs=signature_logs,
                        signatureApiLogs=api_logs, signatureApiSha256=hashlib.sha256(api.stdout).hexdigest(),
                        signatureCliReturnCode=verification.returncode, signatureApiReturnCode=api.returncode)
        verify_signature_logs(output, evidence)
        require(value['loadedApksignerJarPath'] == str(chain['apksignerJar'].resolve())
                and value['apksignerJarSha256'] == sha(chain['apksignerJar'])
                and value['verifierSourceSha256'] == sha(verifier) == verifier_hash,
                'Signature verification implementation changed')
    except Exception:
        # These are diagnostic views only; acceptance uses original bytes and the API contract.
        for label, process in (('CLI', verification), ('API', api)):
            for stream in ('stdout', 'stderr'):
                raw = getattr(process, stream)
                print(label+' '+stream+' (diagnostic display): '+raw[:32768].decode('utf-8', 'backslashreplace'), file=sys.stderr)
        raise
    with zipfile.ZipFile(signed) as archive:
        require(archive.read('assets/'+ASSET) == asset_raw, 'Signed driver lost its source identity')
        require('classes.dex' in archive.namelist(), 'Signed driver has no executable code')
    require(identity(root) == selected and inputs(root)[1] == hashes and sha(verifier) == verifier_hash, 'Input source changed during the strict build')
    result = dict(stamp, status='built', compileOnly=False, actualAndroidExecution=False,
                  releaseAcceptance=False, apkSha256=sha(signed), apkBytes=signed.stat().st_size,
                  assetSha256=hashlib.sha256(asset_raw).hexdigest(), signerCertificateSha256=signer)
    result.update({key: evidence[key] for key in ('signatureLogs','signatureApiLogs','signatureApiSha256',
                  'signatureVerifierSourceSha256','signatureCliReturnCode','signatureApiReturnCode')})
    shutil.copy2(signed, output/'native-input-driver.apk')
    (output/ASSET).write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    (work/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, default=os.environ.get('JAVA_HOME'))
    parser.add_argument('--android-sdk', type=Path, default=os.environ.get('ANDROID_HOME'))
    parser.add_argument('--key', type=Path)
    parser.add_argument('--compile-only', action='store_true')
    parser.add_argument('--android-jar', type=Path)
    args = parser.parse_args()
    require(args.java_home is not None and args.android_sdk is not None, 'Explicit JDK and SDK roots are required')
    result = build(ROOT, args.java_home, args.android_sdk, args.key, args.compile_only, args.android_jar)
    print(json.dumps({key: result[key] for key in ('status', 'compileOnly', 'actualAndroidExecution', 'releaseAcceptance')}))


if __name__ == '__main__':
    main()
