"""Leased isolation of the observed foreign notification source on CI QEMU only.

This is a test-device precondition, not an application fix or release evidence.
It never dismisses app notifications, substitutes a gesture or retries a scene.
"""
import json
import re
import subprocess
import time

PACKAGE = 'com.google.android.settings.intelligence'
TEST_PACKAGE = 'local.pocketchat.test'
SERIAL = 'emulator-5554'
RESTORE = {0: 'default-state', 1: 'enable'}


def require(condition, message):
    if not condition:
        raise RuntimeError('UI SettingsIntelligence isolation: ' + message)


def enabled_state(raw):
    """Read only the requested package's actual, installed User 0 member."""
    require(isinstance(raw, str), 'actual package dump required')
    lines = raw.splitlines()
    packages = [(index, match) for index, line in enumerate(lines)
                if (match := re.match(r'^([ \t]*)Package \[([^\]]+)\]', line))]
    require(len(packages) == 1 and packages[0][1][2] == PACKAGE, 'exact package dump required')
    index, header = packages[0]
    indent = lambda line: len(line) - len(line.lstrip(' \t'))
    block = []
    for line in lines[index + 1:]:
        if line.strip() and indent(line) <= len(header[1]):
            break
        if line.strip():
            block.append(line)
    member_indent = min((indent(line) for line in block), default=-1)
    users = [match for line in block
             if (match := re.fullmatch(r'([ \t]*)User 0:[ \t]*([^\r\n]*)', line))]
    require(len(users) == 1 and len(users[0][1]) == member_indent
            and re.findall(r'(?:^|[ \t])installed=([^ \t]+)', users[0][2]) == ['true'],
            'one installed User 0 state required')
    states = re.findall(r'(?:^|[ \t])enabled=([^ \t]+)', users[0][2])
    require(len(states) == 1 and states[0] in {'0', '1', '2', '3', '4'}, 'safe exact enabled-state integer required')
    return int(states[0])


def expected_apk(root, source, environment):
    """Bind the selected clean source, Gradle version and staged integration APK."""
    from profile_invocation_contract import expected_build
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source), 'source commit required')
    require(environment.get('GITHUB_SHA') == source, 'workflow source differs from runner')
    def git(*parts):
        return subprocess.check_output(['git', *parts], cwd=root, text=True, timeout=15).strip()
    require(git('rev-parse', 'HEAD') == source, 'checkout source differs from runner')
    require(not git('status', '--porcelain', '--untracked-files=no'), 'tracked source must be clean')
    tree = git('rev-parse', 'HEAD^{tree}')
    require(re.fullmatch('[0-9a-f]{40}', tree), 'source tree required')
    gradle = (root / 'app/build.gradle').read_text()
    versions = re.findall(r"versionName\s+'([^']+)'", gradle)
    codes = re.findall(r'versionCode\s+(\d+)', gradle)
    require(len(versions) == len(codes) == 1, 'unique current Gradle version required')
    identity = expected_build(root / 'work/gecko-integration/ui-current.apk', source, tree, versions[0], int(codes[0]))
    require(identity.get('package') == TEST_PACKAGE, 'integration APK required')
    return identity


class Lease:
    def __init__(self, adb, serial, record, path):
        self.adb, self.serial, self.record, self.path = adb, serial, record, path
        self.initial_state, self.changed, self.closed = None, False, False

    def save(self):
        self.path.write_text(json.dumps(self.record, sort_keys=True, indent=2) + '\n')

    def command(self, *parts):
        row = dict(parts=list(parts), startedAtMonotonicNanos=time.monotonic_ns())
        self.record['commands'].append(row)
        try:
            value = self.adb(*parts)
            require(isinstance(value, str), 'complete actual command stdout required')
            row.update(status='passed', stdout=value)
            return value
        except BaseException as error:
            row.update(status='failed', errorType=type(error).__name__, error=str(error))
            raise
        finally:
            row['completedAtMonotonicNanos'] = time.monotonic_ns()

    def bind_device(self):
        require(self.serial == SERIAL, 'only the fixed UI synthetic endpoint is allowed')
        require(self.command('shell', 'getprop', 'ro.kernel.qemu').strip() == '1', 'confirmed QEMU required')
        require(self.command('shell', 'am', 'get-current-user').strip() == '0', 'actual current User 0 required')
        paths = self.command('shell', 'pm', 'path', TEST_PACKAGE).splitlines()
        require(len(paths) == 1 and re.fullmatch(r'package:(/data/app/[A-Za-z0-9_./=+~-]+/base\.apk)', paths[0]),
                'one actual installed integration APK path required')
        installed = paths[0][len('package:'):]
        raw = self.command('shell', 'sha256sum', installed).strip()
        require(re.fullmatch(r'[0-9a-f]{64}  ' + re.escape(installed), raw), 'actual installed APK digest required')
        require(raw[:64] == self.record['buildIdentity']['apkSha256'], 'installed APK differs from current integration build')
        self.record.update(confirmedQemu=True, confirmedUser0=True, installedApkPath=installed, installedApkSha256=raw[:64])

    def prepare(self):
        self.bind_device()
        packages = self.command('shell', 'pm', 'list', 'packages', '--user', '0', PACKAGE).splitlines()
        require(len(packages) <= 1 and all(row == 'package:' + PACKAGE for row in packages), 'exact foreign package presence required')
        if not packages:
            self.record['status'] = 'foreign-package-absent'
            return
        raw = self.command('shell', 'dumpsys', 'package', PACKAGE)
        self.initial_state = enabled_state(raw)
        self.record.update(initialPackageRaw=raw, initialEnabledState=self.initial_state)
        if self.initial_state in (2, 3, 4):
            self.record['status'] = 'already-disabled-unchanged'
            return
        # Ownership is recorded before the command: a failing command may have
        # already changed the actual device and must still be restored.
        self.changed = True
        self.record['mutationAttempted'] = True
        self.command('shell', 'pm', 'disable-user', '--user', '0', PACKAGE)
        self.command('shell', 'am', 'force-stop', '--user', '0', PACKAGE)
        raw = self.command('shell', 'dumpsys', 'package', PACKAGE)
        self.record['disabledPackageRaw'] = raw
        require(enabled_state(raw) == 3, 'temporary disabled-user state was not confirmed')
        self.record['status'] = 'foreign-package-disabled'

    def restore(self):
        if self.closed:
            return
        if self.changed:
            self.bind_device()
            self.command('shell', 'pm', RESTORE[self.initial_state], '--user', '0', PACKAGE)
            raw = self.command('shell', 'dumpsys', 'package', PACKAGE)
            self.record['restoredPackageRaw'] = raw
            require(enabled_state(raw) == self.initial_state, 'exact initial enabled state was not restored')
        self.closed = True
        self.record['restorationVerified'] = True


def prepare_workflow(adb, *, serial, environment, root, source, record_path):
    record = dict(schema=1, package=PACKAGE, serial=serial, commands=[], mutationAttempted=False,
                  applicationNotificationsChanged=False, workloadChanged=False, releaseAcceptance=False,
                  physicalPhoneAcceptance=False, restorationVerified=False,
                  scope='Temporary exact foreign notification source lease around unchanged UI workload')
    lease = Lease(adb, serial, record, record_path)
    run, attempt = environment.get('GITHUB_RUN_ID'), environment.get('GITHUB_RUN_ATTEMPT')
    if environment.get('CI') != 'true' or not isinstance(run, str) or re.fullmatch('[1-9][0-9]{0,19}', run) is None:
        record['status'] = 'not-ci-unchanged'
        lease.save()
        return lease
    require(isinstance(attempt, str) and re.fullmatch('[1-9][0-9]{0,9}', attempt), 'workflow run attempt required')
    require(serial == SERIAL, 'only the fixed UI synthetic endpoint is allowed')
    record.update(runId=run, runAttempt=attempt, buildIdentity=expected_apk(root, source, environment))
    try:
        lease.prepare()
        lease.save()
    except BaseException as error:
        record.update(status='failed', errorType=type(error).__name__, error=str(error))
        try:
            lease.restore()
        except BaseException as restore_error:
            record.update(restoreErrorType=type(restore_error).__name__, restoreError=str(restore_error))
            raise RuntimeError('UI foreign source setup and exact restoration failed') from restore_error
        finally:
            lease.save()
        raise
    return lease


def finish_workflow(lease, report):
    try:
        lease.restore()
    except BaseException as error:
        lease.record.update(restoreErrorType=type(error).__name__, restoreError=str(error))
        report.update(status='failed', deviceRestorationError=str(error))
        raise
    finally:
        lease.save()
