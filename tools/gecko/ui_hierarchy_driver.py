"""Prepare a source-bound, read-only shell hierarchy driver for the two CI emulators.

The driver uses the device's AOSP XML formatter with real screen dimensions for
its screen-coordinate bounds. Bounded non-null-root acquisition replaces the
global idle wait; the caller retains its original absolute deadline.
"""
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JAVA_SOURCE = 'tests/ui-hierarchy-driver/NativeHierarchyCapture.java'
PYTHON_SOURCE = 'tools/gecko/ui_hierarchy_driver.py'
ENTRY_POINT = 'local.pocketchat.hierarchydriver.NativeHierarchyCapture'
SYSTEM_JAR = '/system/framework/uiautomator.jar'
STAMP = 'hierarchy-driver-build.json'
EMBEDDED_SOURCE = 'sources/NativeHierarchyCapture.java'
BACKEND = 'aosp-shell-root-without-global-idle-v1'
REMOTE_XML = re.compile(r'/sdcard/pocketchat-ui-visual-[0-9a-f]{32}-[1-9][0-9]*\.xml')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity(root, source):
    root = Path(root).resolve()

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.PIPE)

    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source), 'Exact committed hierarchy source required')
    require(git('rev-parse', 'HEAD').decode().strip() == source, 'Hierarchy driver source differs from checkout HEAD')
    tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
    require(re.fullmatch('[0-9a-f]{40}', tree), 'Invalid hierarchy source tree')
    require(not git('status', '--porcelain', '--untracked-files=normal').strip(),
            'Hierarchy driver requires clean committed source')
    inputs = {}
    for name in (JAVA_SOURCE, PYTHON_SOURCE):
        path = root/name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
                'Missing regular hierarchy driver source: ' + name)
        raw = path.read_bytes()
        require(raw == git('show', source + ':' + name), 'Hierarchy driver source differs from Git bytes: ' + name)
        inputs[name] = hashlib.sha256(raw).hexdigest()
    run, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    require(re.fullmatch('[1-9][0-9]*', run) and re.fullmatch('[1-9][0-9]*', attempt),
            'Hierarchy driver requires the current CI run identity')
    return dict(sourceCommit=source, sourceTree=tree, runId=run, runAttempt=attempt, inputs=inputs)


def toolchain():
    java_home = os.environ.get('JAVA_HOME')
    sdk_home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    require(java_home and sdk_home, 'Hierarchy driver requires explicit existing JDK and Android SDK roots')
    java_home, sdk_home = Path(java_home), Path(sdk_home)
    paths = dict(java=java_home/'bin/java', javac=java_home/'bin/javac', jar=java_home/'bin/jar',
                 androidJar=sdk_home/'platforms/android-37.1/android.jar',
                 d8=sdk_home/'build-tools/37.0.0/lib/d8.jar')
    paths = {key: path.resolve() for key, path in paths.items()}
    require(all(path.is_file() for path in paths.values()), 'Pinned hierarchy compiler dependencies are missing')
    version = subprocess.check_output([str(paths['java']), '-version'], stderr=subprocess.STDOUT, text=True)
    require(re.search(r'version "17[.\"]', version), 'Hierarchy driver requires JDK 17')
    evidence = dict(javaVersion=version.strip(), platform='android-37.1', buildTools='37.0.0',
                    tools={key: dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))
                           for key, path in paths.items()})
    return paths, evidence


def compile_driver(java_source, directory, paths, run):
    """Compile actual Java/D8 inputs; callers must separately supply their identity proof."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    classes, dex = directory/'classes', directory/'dex'
    classes.mkdir()
    dex.mkdir()
    run([paths['javac'], '-encoding', 'UTF-8', '-source', '8', '-target', '8',
         '-classpath', paths['androidJar'], '-d', classes, java_source], timeout=60)
    run([paths['jar'], 'cf', directory/'classes.jar', '-C', classes, '.'], timeout=30)
    run([paths['java'], '-cp', paths['d8'], 'com.android.tools.r8.D8', '--lib', paths['androidJar'],
         '--min-api', '32', '--output', dex, directory/'classes.jar'], timeout=60)
    outputs = sorted(path.name for path in dex.iterdir())
    require(outputs == ['classes.dex'] and (dex/'classes.dex').stat().st_size > 0,
            'Hierarchy compiler did not produce exactly one executable DEX')
    return dex/'classes.dex'


def package_driver(path, dex, java_source, stamp):
    stamp_raw = (json.dumps(stamp, sort_keys=True, indent=2) + '\n').encode()
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in (('classes.dex', Path(dex).read_bytes()), (STAMP, stamp_raw),
                          (EMBEDDED_SOURCE, Path(java_source).read_bytes())):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    require(Path(path).stat().st_size < 2097152, 'Hierarchy driver exceeds its native archive bound')
    with zipfile.ZipFile(path) as archive:
        require(archive.namelist() == ['classes.dex', STAMP, EMBEDDED_SOURCE], 'Hierarchy driver archive shape changed')
        require(archive.read(STAMP) == stamp_raw and archive.read(EMBEDDED_SOURCE) == Path(java_source).read_bytes(),
                'Hierarchy driver lost its source provenance')
    return hashlib.sha256(stamp_raw).hexdigest()


class Preparation:
    def __init__(self, directory, nonce):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        # Keep the complete receipt at the diagnostics root: the original full-CI
        # bundle already archives this location without a new artifact allowlist.
        self.path = directory/('ui-hierarchy-driver-' + nonce + '.json')
        require(not self.path.exists(), 'Hierarchy preparation receipt already exists')
        self.evidence = dict(schema=1, status='preparing', backend=BACKEND, readOnly=True,
            executionUid=2000, entryPoint=ENTRY_POINT, preparationNonce=nonce,
            actualAndroidExecution=False, releaseAcceptance=False,
            scope='Driver compilation and emulator installation provenance; UI acceptance remains with the caller.',
            startedAtUnixNs=time.time_ns(), commands=[])
        self.save()

    def save(self):
        pending = self.path.with_suffix('.partial')
        pending.write_text(json.dumps(self.evidence, ensure_ascii=False, indent=2) + '\n')
        pending.replace(self.path)

    def run(self, command, *, timeout=90):
        command = [str(part) for part in command]
        row = dict(command=command, startedAtUnixNs=time.time_ns(), timeoutSeconds=timeout)
        self.evidence['commands'].append(row)
        self.save()
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout, check=False)
            for stream in ('stdout', 'stderr'):
                raw = getattr(result, stream)
                row[stream] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    text=raw[:8192].decode('utf-8', 'replace'), truncated=len(raw) > 8192)
            row['exitCode'] = result.returncode
            result.check_returncode()
            return result
        except Exception as error:
            row.update(errorType=type(error).__name__, error=str(error))
            raise
        finally:
            row['completedAtUnixNs'] = time.time_ns()
            self.save()


def device_properties(run, adb, serial):
    def shell(*parts):
        result = run([adb, '-s', serial, 'shell', *parts], timeout=15)
        require(not result.stderr, 'Unexpected hierarchy preparation device error')
        return result.stdout.decode('utf-8', 'strict').strip()

    values = dict(uid=shell('id', '-u'), api=shell('getprop', 'ro.build.version.sdk'),
                  qemu=shell('getprop', 'ro.kernel.qemu'), hardware=shell('getprop', 'ro.hardware'),
                  fingerprint=shell('getprop', 'ro.build.fingerprint'))
    require(values['uid'] == '2000', 'Hierarchy driver requires shell UID 2000')
    require(values['api'] in ('32', '35') and values['qemu'] == '1'
            and values['hardware'] in ('ranchu', 'goldfish'), 'Unsupported hierarchy capture device')
    checksum = shell('sha256sum', SYSTEM_JAR)
    match = re.fullmatch(r'([0-9a-f]{64})  ' + re.escape(SYSTEM_JAR), checksum)
    require(match is not None, 'Cannot bind the device AOSP hierarchy formatter')
    values.update(systemJar=SYSTEM_JAR, systemJarSha256=match.group(1),
                  viewportMode='getRealSize',
                  compressedHierarchy=False, globalIdleWait=False)
    return values


class HierarchyDriver:
    def __init__(self, evidence, report_path):
        self.evidence = evidence
        self.report_path = Path(report_path)
        self._identity = {key: evidence[key] for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt')}
        self._remote = evidence['installedJar']['remotePath']
        self._jar_sha = evidence['installedJar']['sha256']
        self._system_sha = evidence['device']['systemJarSha256']
        self._attempts = set()

    def dump_parts(self, remote, remaining, *, sync_window=False):
        require(type(sync_window) is bool, 'Window input synchronization must be an explicit boolean')
        require(isinstance(remote, str) and REMOTE_XML.fullmatch(remote), 'Invalid current-attempt hierarchy path')
        require(remote not in self._attempts, 'Hierarchy driver cannot reuse a prior attempt path')
        require(type(remaining) in (int, float) and math.isfinite(remaining) and remaining > 0,
                'Finite current caller remainder required for hierarchy acquisition')
        milliseconds = math.floor(min(90, remaining) * 1000)
        if milliseconds <= 0:
            raise TimeoutError('Existing UI scene deadline has less than one millisecond remaining')
        self._attempts.add(remote)
        identity = self._identity
        parts = ['shell', 'CLASSPATH=' + self._remote + ':' + SYSTEM_JAR, 'app_process', '/system/bin', ENTRY_POINT,
                remote, str(milliseconds), self._jar_sha, identity['sourceCommit'], identity['sourceTree'],
                identity['runId'], identity['runAttempt'], self._system_sha]
        if sync_window:
            parts.append('sync-window-input')
        return parts


def prepare_driver(adb, serial, source, diagnostics_dir):
    """Build and verify the exact driver before a caller begins its scene deadline."""
    require(isinstance(serial, str) and re.fullmatch(r'emulator-[0-9]+', serial),
            'Hierarchy driver requires an explicit emulator serial')
    diagnostics_dir = Path(diagnostics_dir).resolve()
    nonce = secrets.token_hex(16)
    preparation = Preparation(diagnostics_dir, nonce)
    evidence, run = preparation.evidence, preparation.run
    try:
        selected = source_identity(ROOT, source)
        evidence.update(selected)
        paths, compiler = toolchain()
        evidence['toolchain'] = compiler
        device = device_properties(run, str(adb), serial)
        evidence.update(serial=serial, device=device)
        output = Path(diagnostics_dir)/'ui-hierarchy-driver-build'/nonce
        dex = compile_driver(ROOT/JAVA_SOURCE, output, paths, run)
        stamp = dict(schema=1, **selected, backend=BACKEND, entryPoint=ENTRY_POINT, executionUid=2000,
                     readOnly=True, toolchain=compiler, supportedApis=[32, 35],
                     viewportModes={'32': 'getRealSize', '35': 'getRealSize'}, compressedHierarchy=False,
                     globalIdleWait=False, rootPollLimitMillis=1000)
        jar = output/'hierarchy-driver.jar'
        stamp_hash = package_driver(jar, dex, ROOT/JAVA_SOURCE, stamp)
        require(source_identity(ROOT, source) == selected, 'Hierarchy source changed during compilation')
        for key, path in paths.items():
            require(sha(path) == compiler['tools'][key]['sha256'], 'Hierarchy compiler dependency changed')
        jar_hash, jar_bytes = sha(jar), jar.stat().st_size
        evidence['build'] = dict(jarPath=str(jar.resolve()), jarBytes=jar_bytes, jarSha256=jar_hash,
                                jarBase64=base64.b64encode(jar.read_bytes()).decode('ascii'),
                                dexSha256=sha(dex), stampSha256=stamp_hash)
        remote = ('/data/local/tmp/pocketchat-ui-hierarchy-' + source[:12] + '-' + selected['runId']
                  + '-' + selected['runAttempt'] + '-' + nonce + '.jar')
        run([str(adb), '-s', serial, 'push', str(jar), remote], timeout=30)
        readback = run([str(adb), '-s', serial, 'exec-out', 'cat', remote], timeout=30)
        require(not readback.stderr and len(readback.stdout) == jar_bytes
                and hashlib.sha256(readback.stdout).hexdigest() == jar_hash,
                'Installed hierarchy driver bytes differ from the source-bound build')
        require(source_identity(ROOT, source) == selected and sha(jar) == jar_hash,
                'Hierarchy identity changed during device preparation')
        evidence.update(installedJar=dict(remotePath=remote, bytes=jar_bytes, sha256=jar_hash,
            readbackBytes=len(readback.stdout), readbackSha256=hashlib.sha256(readback.stdout).hexdigest(),
            readbackBase64=base64.b64encode(readback.stdout).decode('ascii')),
            status='verified', completedAtUnixNs=time.time_ns())
        verify_evidence(evidence, source)
        preparation.save()
        return HierarchyDriver(evidence, preparation.path)
    except Exception as error:
        evidence.update(status='failed', errorType=type(error).__name__, error=str(error), completedAtUnixNs=time.time_ns())
        preparation.save()
        raise


def verify_evidence(evidence, source, *, root=None):
    """Recompute a receipt's original archive/readback and committed-source bindings."""
    root = ROOT if root is None else Path(root)
    require(type(evidence.get('schema')) is int and evidence.get('schema') == 1 and evidence.get('status') == 'verified'
            and evidence.get('backend') == BACKEND and evidence.get('readOnly') is True
            and type(evidence.get('executionUid')) is int and evidence.get('executionUid') == 2000
            and evidence.get('entryPoint') == ENTRY_POINT
            and evidence.get('actualAndroidExecution') is False and evidence.get('releaseAcceptance') is False,
            'Invalid hierarchy preparation evidence scope')
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source)
            and evidence.get('sourceCommit') == source, 'Hierarchy receipt source mismatch')
    tree = subprocess.check_output(['git', 'rev-parse', source + '^{tree}'], cwd=root, stderr=subprocess.PIPE).decode().strip()
    require(evidence.get('sourceTree') == tree and re.fullmatch('[0-9a-f]{40}', tree), 'Hierarchy receipt tree mismatch')
    committed = {name: subprocess.check_output(['git', 'show', source + ':' + name], cwd=root, stderr=subprocess.PIPE)
                 for name in (JAVA_SOURCE, PYTHON_SOURCE)}
    inputs = {name: hashlib.sha256(raw).hexdigest() for name, raw in committed.items()}
    require(evidence.get('inputs') == inputs, 'Hierarchy receipt does not match actual Git source bytes')
    run, attempt = evidence.get('runId'), evidence.get('runAttempt')
    require(isinstance(run, str) and re.fullmatch('[1-9][0-9]*', run)
            and isinstance(attempt, str) and re.fullmatch('[1-9][0-9]*', attempt), 'Invalid hierarchy receipt run')
    nonce, serial = evidence.get('preparationNonce'), evidence.get('serial')
    require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce)
            and isinstance(serial, str) and re.fullmatch('emulator-[0-9]+', serial), 'Invalid hierarchy receipt device identity')
    device, compiler = evidence['device'], evidence['toolchain']
    require(device['uid'] == '2000' and device['api'] in ('32', '35') and device['qemu'] == '1'
            and device['hardware'] in ('ranchu', 'goldfish') and device['systemJar'] == SYSTEM_JAR
            and re.fullmatch('[0-9a-f]{64}', device['systemJarSha256'])
            and device['viewportMode'] == 'getRealSize'
            and device['compressedHierarchy'] is False and device['globalIdleWait'] is False,
            'Hierarchy receipt changes native device/formatter semantics')
    require(compiler['platform'] == 'android-37.1' and compiler['buildTools'] == '37.0.0'
            and re.search(r'version "17[.\"]', compiler['javaVersion']), 'Hierarchy receipt compiler is not pinned')
    chain = compiler['tools']
    require(set(chain) == {'java', 'javac', 'jar', 'androidJar', 'd8'}, 'Missing hierarchy compilation dependency')
    for item in chain.values():
        require(isinstance(item['path'], str) and Path(item['path']).is_absolute()
                and type(item['bytes']) is int and item['bytes'] > 0
                and re.fullmatch('[0-9a-f]{64}', item['sha256']), 'Invalid hierarchy compiler dependency binding')
    build, installed = evidence['build'], evidence['installedJar']
    require(isinstance(build['jarBase64'], str) and len(build['jarBase64']) <= 2796204
            and isinstance(installed['readbackBase64'], str) and len(installed['readbackBase64']) <= 2796204,
            'Hierarchy archive proof exceeds its bound')
    raw = base64.b64decode(build['jarBase64'], validate=True)
    readback = base64.b64decode(installed['readbackBase64'], validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    require(all(type(value) is int for value in (build['jarBytes'], installed['bytes'], installed['readbackBytes']))
            and 0 < len(raw) < 2097152 and readback == raw and build['jarBytes'] == len(raw)
            and build['jarSha256'] == digest and installed['bytes'] == len(raw)
            and installed['readbackBytes'] == len(raw) and installed['sha256'] == digest
            and installed['readbackSha256'] == digest, 'Hierarchy build and actual device readback differ')
    expected_stamp = dict(schema=1, sourceCommit=source, sourceTree=tree, runId=run, runAttempt=attempt,
        inputs=inputs, backend=BACKEND, entryPoint=ENTRY_POINT, executionUid=2000, readOnly=True,
        toolchain=compiler, supportedApis=[32, 35], viewportModes={'32': 'getRealSize', '35': 'getRealSize'},
        compressedHierarchy=False, globalIdleWait=False, rootPollLimitMillis=1000)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.namelist() == ['classes.dex', STAMP, EMBEDDED_SOURCE], 'Unexpected hierarchy archive contents')
        require(all(entry.compress_type == zipfile.ZIP_STORED for entry in archive.infolist()),
                'Hierarchy archive is not the bounded original build format')
        stamp_raw = archive.read(STAMP)
        require(stamp_raw == (json.dumps(expected_stamp, sort_keys=True, indent=2) + '\n').encode()
                and hashlib.sha256(stamp_raw).hexdigest() == build['stampSha256'], 'Hierarchy embedded source/build stamp mismatch')
        require(archive.read(EMBEDDED_SOURCE) == committed[JAVA_SOURCE], 'Hierarchy embedded Java differs from committed bytes')
        dex = archive.read('classes.dex')
        require(dex.startswith(b'dex\n') and hashlib.sha256(dex).hexdigest() == build['dexSha256'],
                'Hierarchy executable bytes differ from build receipt')
    remote = '/data/local/tmp/pocketchat-ui-hierarchy-' + source[:12] + '-' + run + '-' + attempt + '-' + nonce + '.jar'
    require(installed['remotePath'] == remote, 'Hierarchy installed path is not source/run/nonce owned')
    commands = evidence['commands']
    require(len(commands) == 11 and all(type(row.get('exitCode')) is int and row.get('exitCode') == 0 for row in commands),
            'Hierarchy preparation lacks its complete successful command sequence')
    adb = commands[0]['command'][0]
    expected_device = [(['id', '-u'], device['uid']), (['getprop', 'ro.build.version.sdk'], device['api']),
        (['getprop', 'ro.kernel.qemu'], device['qemu']), (['getprop', 'ro.hardware'], device['hardware']),
        (['getprop', 'ro.build.fingerprint'], device['fingerprint']),
        (['sha256sum', SYSTEM_JAR], device['systemJarSha256'] + '  ' + SYSTEM_JAR)]

    def output_matches(record, original):
        return (type(record.get('bytes')) is int and type(record.get('truncated')) is bool
            and record == dict(bytes=len(original), sha256=hashlib.sha256(original).hexdigest(),
            text=original[:8192].decode('utf-8', 'replace'), truncated=len(original) > 8192)
        )

    for index, row in enumerate(commands):
        require(type(row.get('timeoutSeconds')) is int and row['timeoutSeconds'] > 0,
                'Invalid hierarchy preparation command timeout')
        for stream in ('stdout', 'stderr'):
            observed = row[stream]
            require(type(observed.get('bytes')) is int and observed['bytes'] >= 0
                    and type(observed.get('truncated')) is bool and isinstance(observed.get('text'), str)
                    and isinstance(observed.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', observed['sha256']),
                    'Invalid hierarchy command output metadata')
            if index == 10 and stream == 'stdout':
                original = readback
            else:
                # Compiler/device/push output must be complete to recompute its
                # full digest. A truncated prefix alone cannot prove that hash.
                require(observed['truncated'] is False and observed['bytes'] <= 8192,
                        'Hierarchy command output lacks complete original bytes')
                original = observed['text'].encode('utf-8')
            require(output_matches(observed, original), 'Hierarchy command output metadata differs from original bytes')

    for row, (parts, value) in zip(commands, expected_device):
        require(row['command'] == [adb, '-s', serial, 'shell', *parts] and row['timeoutSeconds'] == 15
                and output_matches(row['stderr'], b''), 'Hierarchy device command provenance differs')
        original = row['stdout']['text'].encode()
        require(output_matches(row['stdout'], original) and original.decode().strip() == value,
                'Hierarchy device observation differs from its original command output')
    output_dir = Path(build['jarPath']).parent
    java_source = commands[6]['command'][-1]
    require(Path(build['jarPath']).is_absolute() and Path(java_source).is_absolute()
            and java_source.endswith('/' + JAVA_SOURCE), 'Invalid hierarchy compile input/output paths')
    expected_build = [
        [chain['javac']['path'], '-encoding', 'UTF-8', '-source', '8', '-target', '8',
         '-classpath', chain['androidJar']['path'], '-d', str(output_dir/'classes'), java_source],
        [chain['jar']['path'], 'cf', str(output_dir/'classes.jar'), '-C', str(output_dir/'classes'), '.'],
        [chain['java']['path'], '-cp', chain['d8']['path'], 'com.android.tools.r8.D8', '--lib', chain['androidJar']['path'],
         '--min-api', '32', '--output', str(output_dir/'dex'), str(output_dir/'classes.jar')]]
    require([row['command'] for row in commands[6:9]] == expected_build
            and [row['timeoutSeconds'] for row in commands[6:9]] == [60, 30, 60], 'Hierarchy build command/source provenance differs')
    require(commands[9]['command'] == [adb, '-s', serial, 'push', build['jarPath'], remote]
            and commands[10]['command'] == [adb, '-s', serial, 'exec-out', 'cat', remote]
            and commands[9]['timeoutSeconds'] == commands[10]['timeoutSeconds'] == 30
            and output_matches(commands[10]['stdout'], readback) and output_matches(commands[10]['stderr'], b''),
            'Hierarchy device readback provenance differs')
    require(type(evidence['startedAtUnixNs']) is int and type(evidence['completedAtUnixNs']) is int
            and evidence['startedAtUnixNs'] <= evidence['completedAtUnixNs'], 'Invalid hierarchy preparation interval')
    prior = evidence['startedAtUnixNs']
    for row in commands:
        require(type(row['startedAtUnixNs']) is int and type(row['completedAtUnixNs']) is int
                and prior <= row['startedAtUnixNs'] <= row['completedAtUnixNs'] <= evidence['completedAtUnixNs'],
                'Hierarchy preparation command order is inconsistent')
        prior = row['completedAtUnixNs']
    return evidence
