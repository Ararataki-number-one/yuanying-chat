"""Temporary, exact-package emulator guard for the two editing fixtures only."""
import re
import time

LAUNCHER = 'com.google.android.apps.nexuslauncher'
SERIAL = 'emulator-5554'
RESTORE_COMMAND = {0: 'default-state', 1: 'enable', 2: 'disable', 3: 'disable-user', 4: 'disable-until-used'}


def require(condition, message):
    if not condition:
        raise ValueError('Editing launcher guard: ' + message)


def _enabled_state(raw):
    require(isinstance(raw, str), 'actual package dump required')
    lines = raw.splitlines()
    packages = [(index, match) for index, line in enumerate(lines)
                if (match := re.match(r'^([ \t]*)Package \[([^\]]+)\]', line))]
    require(len(packages) == 1 and packages[0][1][2] == LAUNCHER,
            'exact launcher package dump required')
    index, header = packages[0]
    indent = lambda line: len(line) - len(line.lstrip(' \t'))
    # dumpsys also emits global Queries/User sections. Only the requested
    # Package's indented members can authorize an enabled-state mutation.
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


def _home(raw):
    require(isinstance(raw, str), 'actual HOME resolution required')
    components = re.findall(r'^\s*([A-Za-z0-9_.]+)/([A-Za-z0-9_.]+)\s*$', raw, re.M)
    require(len(components) == 1, 'one actual HOME component required')
    package, activity = components[0]
    return package + '/' + (package + activity if activity.startswith('.') else activity)


def _focus(raw):
    require(isinstance(raw, str), 'actual current-window dump required')
    values = re.findall(r'^\s*mCurrentFocus=(Window\{[^\n]+\}|null)\s*$', raw, re.M)
    require(len(values) == 1, 'one actual current focus required')
    return values[0]


def _error_focus(focus):
    return any(value in focus for value in ('Application Not Responding:', 'Application Error:', 'SYSTEM_ERROR'))


def _known_anr(focus):
    return re.fullmatch(r'Window\{[^\n]* u0 Application Not Responding: ' + re.escape(LAUNCHER) + r'\}', focus) is not None


class LauncherGuard:
    def __init__(self, *, adb, identity, record, nonce, serial=SERIAL):
        require(serial == SERIAL, 'only the fixed synthetic adb target is allowed')
        require(isinstance(identity, dict) and type(identity.get('schema')) is int and identity['schema'] == 1,
                'source/run identity required')
        for field in ('sourceCommit', 'sourceTree'):
            require(isinstance(identity.get(field), str) and re.fullmatch('[0-9a-f]{40}', identity[field]), field)
        for field in ('runId', 'runAttempt'):
            require(isinstance(identity.get(field), str) and re.fullmatch('[1-9][0-9]*', identity[field]), field)
        require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce), 'owned guard nonce required')
        self.adb, self.record, self.initial_state, self.initial_home = adb, record, None, None
        self.changed, self.used = False, False
        record.update(schema=1, status='failed', identity=dict(identity), runNonce=nonce,
                      exactLauncherPackage=LAUNCHER, serial=SERIAL, commands=[],
                      mutationAttempted=False, restorationVerified=False,
                      applicationAcceptance=False, physicalPhoneAcceptance=False,
                      scope='Temporary known-launcher state around unchanged editing fixtures; actual HOME state must be restored before later suites.')

    def command(self, *parts):
        row = dict(parts=list(parts), startedAtMonotonicNanos=time.monotonic_ns())
        self.record['commands'].append(row)
        try:
            value = self.adb(*parts)
            require(isinstance(value, str), 'complete actual command stdout required')
            row.update(stdout=value, status='passed')
            return value
        except BaseException as error:
            def stream(value):
                return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
            row.update(status='failed', errorType=type(error).__name__, error=str(error),
                       stdout=stream(getattr(error, 'stdout', None)), stderr=stream(getattr(error, 'stderr', None)))
            raise
        finally:
            row['completedAtMonotonicNanos'] = time.monotonic_ns()

    def home(self):
        raw = self.command('shell', 'cmd', 'package', 'resolve-activity', '--brief', '--user', '0',
                           '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
        return raw, _home(raw)

    def window(self):
        raw = self.command('shell', 'dumpsys', 'window', 'displays')
        return raw, _focus(raw)

    def prepare(self):
        require(self.command('shell', 'getprop', 'ro.kernel.qemu').strip() == '1', 'confirmed fixed emulator required')
        self.record['confirmedQemu'] = True
        require(self.command('shell', 'am', 'get-current-user').strip() == '0', 'actual current Android User 0 required')
        self.record['confirmedUser0'] = True
        packages = self.command('shell', 'pm', 'list', 'packages', LAUNCHER).splitlines()
        require(all(line == 'package:' + LAUNCHER for line in packages) and len(packages) <= 1,
                'exact launcher package presence required')
        self.record['launcherPresent'] = bool(packages)
        home_raw, self.initial_home = self.home()
        window_raw, focus = self.window()
        self.record.update(initialHomeRaw=home_raw, initialHome=self.initial_home,
                           initialWindowRaw=window_raw, initialFocus=focus)
        require(not _error_focus(focus) or _known_anr(focus),
                'foreign/application error window cannot be suppressed')
        if not packages:
            require(not _error_focus(focus), 'absent launcher cannot own an error window')
            return
        package_raw = self.command('shell', 'dumpsys', 'package', LAUNCHER)
        self.initial_state = _enabled_state(package_raw)
        self.record.update(initialPackageRaw=package_raw, initialEnabledState=self.initial_state)
        self.changed = True  # Restore even if a failed command already changed Android state.
        self.record['mutationAttempted'] = True
        self.command('shell', 'pm', 'disable-user', '--user', '0', LAUNCHER)
        self.command('shell', 'am', 'force-stop', '--user', '0', LAUNCHER)
        disabled_raw = self.command('shell', 'dumpsys', 'package', LAUNCHER)
        require(_enabled_state(disabled_raw) == 3, 'temporary disabled-user state was not observed')
        self.record['disabledPackageRaw'] = disabled_raw
        deadline = time.monotonic() + 5
        while True:
            raw, focus = self.window()
            self.record['guardedWindowRaw'], self.record['guardedFocus'] = raw, focus
            require(not _error_focus(focus) or _known_anr(focus),
                    'a foreign/application error window still owns actual input focus')
            if focus != 'null' and not _known_anr(focus):
                break
            require(time.monotonic() < deadline, 'actual foreground window did not become available')
            time.sleep(.1)  # Setup window verification only; never input pacing or replay.

    def restore(self):
        if self.changed:
            self.command('shell', 'pm', RESTORE_COMMAND[self.initial_state], '--user', '0', LAUNCHER)
            raw = self.command('shell', 'dumpsys', 'package', LAUNCHER)
            self.record['restoredPackageRaw'] = raw
            require(_enabled_state(raw) == self.initial_state, 'exact initial enabled state was not restored')
        if self.initial_home is not None:
            raw, home = self.home()
            self.record.update(restoredHomeRaw=raw, restoredHome=home)
            require(home == self.initial_home, 'exact initial HOME component was not restored')
            raw, focus = self.window()
            self.record.update(restoredWindowRaw=raw, restoredFocus=focus)
        self.record['restorationVerified'] = True

    def run(self, workload):
        require(not self.used, 'editing environment guard cannot be replayed')
        self.used = True
        failure = None
        try:
            self.prepare()
            result = workload()
        except BaseException as error:
            failure = error
            self.record.update(errorType=type(error).__name__, error=str(error))
        try:
            self.restore()
        except BaseException as error:
            self.record.update(restoreErrorType=type(error).__name__, restoreError=str(error))
            raise RuntimeError('Exact launcher/HOME restoration failed; later suites must not run') from error
        if failure is not None:
            raise failure
        self.record['status'] = 'passed'
        return result
