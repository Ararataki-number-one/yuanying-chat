"""One predetermined native sequence per gesture, from a separate self-target APK."""
import re
import json
import subprocess
import time
import zipfile
from pathlib import Path

from native_input_contract import SELF, TARGET, decode, require, sha, verify_build, verify_receipt, verify_target_proof, verify_signature_logs


class NativeInputDriver:
    def __init__(self, *, root, out, adb, serial, nonce, target_apk=None, expected_source=None, driver_apk=None, build_receipt=None, install=True, target_byte_proof=None):
        self.root, self.out = Path(root), Path(out)
        self.adb, self.serial, self.nonce = adb, serial, nonce
        require(re.fullmatch('[0-9a-f]{32}', nonce), 'run nonce')
        self.source = expected_source or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root, text=True).strip()
        self.read_source = lambda source, path: subprocess.check_output(['git', 'show', source + ':' + path], cwd=self.root)
        self.apk = Path(driver_apk or self.root / 'work/gecko-integration/native-input-driver.apk')
        self.build_path = Path(build_receipt or self.root / 'work/gecko-integration/native-input-driver-build.json')
        self.build_raw = self.build_path.read_bytes(); self.build = decode(self.build_raw)
        verify_build(self.build, self.source, self.read_source)
        verify_signature_logs(self.build_path.parent, self.build)
        require(sha(self.apk.read_bytes()) == self.build['apkSha256'], 'driver APK bytes')
        with zipfile.ZipFile(self.apk) as archive:
            raw = archive.read('assets/native-input-driver-build.json')
        require(sha(raw) == self.build['assetSha256'], 'embedded asset bytes')
        self.target_apk = Path(target_apk or self.root / 'app/build/outputs/apk/integration/app-x86_64-integration.apk')
        self.target_hash = sha(self.target_apk.read_bytes())
        self.target_proof_raw = Path(target_byte_proof or self.out / 'installed-apk-read-performance-before.json').read_bytes()
        self.target_proof = decode(self.target_proof_raw)
        verify_target_proof(self.target_proof, self.target_hash, self.target_apk.stat().st_size)
        target_paths = self.command('shell', 'pm', 'path', TARGET).stdout.decode('utf-8').splitlines()
        require(target_paths == ['package:' + self.target_proof['installedApkPath']], 'target installed path changed since byte proof')
        self.receipts, self.invoked = [], set()
        # An isolated driver may have a different test certificate in the next A/B role.
        if install:
            installed = self.command('shell', 'pm', 'path', SELF, check=False)
            if b'package:' in installed.stdout:
                self.command('uninstall', SELF)
            self.command('install', str(self.apk))
        paths = self.command('shell', 'pm', 'path', SELF).stdout.decode('utf-8').splitlines()
        require(len(paths) == 1 and paths[0].startswith('package:/data/app/'), 'installed driver base APK')
        installed_path = paths[0][len('package:'):]
        require(re.fullmatch(r'/data/app/[A-Za-z0-9/._~+=-]+/base\.apk', installed_path), 'installed APK path')
        require(self.build['apkBytes'] < 4194304, 'bounded small driver APK')
        installed_raw = self.command('shell', '-T', 'dd', 'if=' + installed_path, 'bs=4194304', 'skip=0', 'count=1', 'status=none').stdout
        require(len(installed_raw) == self.build['apkBytes'] and sha(installed_raw) == self.build['apkSha256'], 'actual installed driver bytes')
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / ('native-input-setup-' + nonce + '.json')).write_text(json.dumps(dict(
            sourceCommit=self.source, nonce=nonce, installationRequested=install, installedApkPath=installed_path,
            actualInstalledApkRead=True, apkBytes=len(installed_raw), apkSha256=sha(installed_raw),
            signerCertificateSha256=self.build['signerCertificateSha256'],
            signatureBinding='Exact installed bytes match signed build; device certificate is also checked in each injection receipt.'), indent=2) + '\n')
        proof_path = self.out / ('native-input-target-proof-' + nonce + '.json')
        require(not proof_path.exists(), 'existing target proof for invocation')
        proof_path.write_bytes(self.target_proof_raw)
        destination = self.out / 'native-input-driver-build.json'
        if destination.resolve() != self.build_path.resolve():
            destination.write_bytes(self.build_raw)
        for name in self.build['signatureLogs']:
            target = self.out / name
            if target.resolve() != (self.build_path.parent / name).resolve():
                target.write_bytes((self.build_path.parent / name).read_bytes())

    def command(self, *parts, timeout=20, check=True):
        result = subprocess.run([self.adb, '-s', self.serial, *parts], capture_output=True, timeout=timeout)
        if check:
            require(result.returncode == 0, 'ADB command failed: ' + ' '.join(parts[:3]))
        return result

    def inject(self, gesture, *, expires_uptime_ms, purpose='qualification'):
        name = gesture['id']; require(name not in self.invoked, 'gesture replay forbidden'); self.invoked.add(name)
        require((purpose == 'qualification' and name in ('baseline-scroll', 'current-scroll'))
                or (purpose == 'formal-collapse' and name == 'formal-collapse'), 'gesture purpose')
        pid = self.command('shell', 'pidof', TARGET).stdout.decode('ascii').strip()
        require(re.fullmatch('[1-9][0-9]*', pid), 'one measured main process required')
        request = {key: gesture[key] for key in ('x', 'startY', 'endY')}
        require(all(type(v) is int and v >= 0 for v in request.values()), 'integer screen endpoints')
        request.update(targetPid=pid, expiresUptimeMs=expires_uptime_ms, targetByteProofSha256=sha(self.target_proof_raw),
                       targetApkPath=self.target_proof['installedApkPath'], targetApkBytes=self.target_proof['actualFileBytes'])
        base = 'native-input-' + self.nonce + '-' + name
        path = self.out / (base + '.json'); require(not path.exists(), 'existing invocation receipt')
        arguments = dict(nonce=self.nonce, gesture=name, purpose=purpose, expires=str(expires_uptime_ms), targetPid=pid,
                         source=self.source, tree=self.build['sourceTree'], driverApkSha256=self.build['apkSha256'],
                         targetApkSha256=self.target_hash, targetByteProofSha256=sha(self.target_proof_raw),
                         targetApkPath=self.target_proof['installedApkPath'], targetApkBytes=str(self.target_proof['actualFileBytes']), x=str(request['x']), startY=str(request['startY']), endY=str(request['endY']))
        command = ['shell', 'am', 'instrument', '-w', '-r']
        for key, value in arguments.items():
            command.extend(['-e', key, value])
        command.append(SELF + '/' + SELF + '.NativeInputInstrumentation')
        started = time.monotonic_ns(); result = None; timeout_error = None
        row = dict(file=path.name, sha256=None, gesture=name, request=request,
                   hostStartedMonotonicNs=started, hostCompletedMonotonicNs=None)
        self.receipts.append(row)
        try:
            result = self.command(*command, timeout=20, check=False)
            require(result.returncode == 0, 'instrumentation transport failed')
        except subprocess.TimeoutExpired as error:
            timeout_error = error
            raise
        finally:
            # A timed-out am/adb client does not stop an Android instrumentation.
            # Stop only the independent driver, never the measured application.
            cleanup_errors = []
            if result is None or result.returncode != 0:
                try:
                    self.command('shell', 'am', 'force-stop', SELF, timeout=5, check=False)
                except Exception as error:
                    cleanup_errors.append('driver stop: ' + str(error))
            if result is not None:
                (self.out / (base + '-stdout.log')).write_bytes(result.stdout)
                (self.out / (base + '-stderr.log')).write_bytes(result.stderr)
            elif timeout_error is not None:
                (self.out / (base + '-stdout.log')).write_bytes(timeout_error.stdout or b'')
                (self.out / (base + '-stderr.log')).write_bytes(timeout_error.stderr or b'')
            try:
                captured = self.command('exec-out', 'run-as', SELF, 'cat', 'files/' + base + '.json', timeout=5, check=False)
                (self.out / (base + '-read-stderr.log')).write_bytes(captured.stderr)
                if captured.returncode == 0:
                    path.write_bytes(captured.stdout)
                    row['sha256'] = sha(captured.stdout)
            except Exception as error:
                cleanup_errors.append('receipt collection: ' + str(error))
            if cleanup_errors:
                (self.out / (base + '-collection.json')).write_text(json.dumps(dict(errors=cleanup_errors), indent=2) + '\n')
            row['hostCompletedMonotonicNs'] = time.monotonic_ns()
        raw = path.read_bytes(); value = decode(raw)
        verify_receipt(value, build=self.build, purpose=purpose, nonce=self.nonce, gesture=name, target_apk=self.target_hash, request=request)
        after = self.command('shell', 'pidof', TARGET).stdout.decode('ascii').strip()
        require(after == pid, 'measured PID changed after driver')
        return row

    def evidence(self, purpose='qualification'):
        return dict(purpose=purpose, nonce=self.nonce, buildSha256=sha(self.build_raw),
                    targetByteProofFile='native-input-target-proof-' + self.nonce + '.json',
                    targetByteProofSha256=sha(self.target_proof_raw), receipts=list(self.receipts))
