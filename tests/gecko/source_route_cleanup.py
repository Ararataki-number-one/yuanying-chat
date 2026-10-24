"""Fence the existing synthetic-package cleanup; never changes a fixture result.

This is an exclusive-emulator test-runner boundary, not cancellation of a native
operation. All observations are read-only until the single fixed package stop.
"""
import hashlib
import json
import re
import subprocess
import time

PACKAGE = 'local.pocketchat.test'
TAG = 'PocketNetworkSourceRoute'
_PATH = re.compile(r'/data/app/[A-Za-z0-9_./~+=-]+/base\.apk')
_LINE = re.compile(r'^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(\d+)\s+\d+\s+[VDIWEFAS]\s+' + TAG + r'\s*:\s*(\{.*\})$')


class CleanupUnknown(ValueError):
    pass


def require(value, reason):
    if not value:
        raise CleanupUnknown(reason)


def invocation(raw, source, nonce, identity):
    """One current snapshot, not a cumulative count across logcat polls."""
    text = raw.decode('utf-8', errors='strict')
    rows = []
    for line in text.splitlines():
        match = _LINE.fullmatch(line)
        if not match:
            # Never accept a malformed or differently formatted invocation line.
            require(not (TAG in line and '"kind":"invocation"' in line),
                    'Invocation has no exact threadtime process identity')
            continue
        try:
            row = json.loads(match[2])
        except ValueError:
            require('invocation' not in match[2], 'Malformed invocation event')
            continue
        if row.get('kind') == 'invocation':
            rows.append((line, int(match[1]), row.get('value')))
    require(len(rows) == 1, 'Exactly one invocation event required; missing or newer invocation')
    line, pid, value = rows[0]
    require(isinstance(value, dict), 'Invocation payload missing')
    require(value.get('sourceCommit') == source and value.get('runNonce') == nonce
            and value.get('package') == PACKAGE, 'Invocation source/nonce/package changed')
    require(type(value.get('pid')) is int and value['pid'] == pid and pid > 0,
            'Invocation PID does not match the original logcat PID')
    require(type(value.get('uid')) is int and value['uid'] > 0, 'Invocation UID missing')
    require(value.get('buildIdentity') == identity, 'Invocation installed build identity changed')
    return dict(pid=pid, uid=value['uid'], eventSha256=hashlib.sha256(line.encode()).hexdigest(),
                sourceCommit=source, runNonce=nonce, package=PACKAGE)


def process_identity(pid, uid, stat_raw, status_raw, cmdline_raw):
    """Linux field 22 identifies this PID generation, including comm with spaces."""
    require(type(pid) is int and pid > 0 and type(uid) is int and uid > 0,
            'Positive exact process PID/UID required')
    stat = stat_raw.decode('ascii', errors='strict').strip()
    close = stat.rfind(')')
    require(stat.startswith(str(pid) + ' (') and close > 0, 'Invalid process stat PID')
    fields = stat[close + 1:].split()
    require(len(fields) >= 20 and fields[19].isdigit() and int(fields[19]) > 0,
            'Process startTicks unavailable')
    status = status_raw.decode('ascii', errors='strict')
    found = re.findall(r'^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', status, re.M)
    require(len(found) == 1 and all(int(item) == uid for item in found[0]),
            'Process UID does not match the installed test package')
    require(cmdline_raw.endswith(b'\0') and cmdline_raw.rstrip(b'\0') == PACKAGE.encode(),
            'Process is not the fixed test main process')
    return dict(pid=pid, uid=uid, startTicks=int(fields[19]), package=PACKAGE)


class RouteCleanupFence:
    def __init__(self, adb, serial, source, nonce, identity, run=subprocess.run):
        require(isinstance(serial, str) and bool(serial) and not any(c.isspace() for c in serial),
                'Exact selected adb serial required')
        require(re.fullmatch('[0-9a-f]{40}', source or '') is not None
                and re.fullmatch('[0-9a-f]{32}', nonce or '') is not None,
                'Exact selected source and invocation nonce required')
        require(isinstance(identity, dict) and identity.get('package') == PACKAGE
                and identity.get('sourceCommit') == source
                and re.fullmatch('[0-9a-f]{64}', identity.get('apkSha256', '')) is not None,
                'Verified actual synthetic APK identity required')
        self.adb, self.serial, self.source, self.nonce = str(adb), serial, source, nonce
        self.identity, self.run = dict(identity), run
        self.installation, self.owner = None, None
        self.receipt = dict(schema=1, scope='Exclusive selected emulator fixed integration-package cleanup only',
                            package=PACKAGE, serial=serial, sourceCommit=source, runNonce=nonce,
                            status='cleanupUnknown', forceStopAttempted=False, originalPidGone=False,
                            fixtureResultChanged=False, nativeOperationCancelled=False,
                            startedAtMonotonicNs=time.monotonic_ns())

    def command(self, *parts, optional=False):
        result = self.run([self.adb, '-s', self.serial, *parts], capture_output=True,
                          timeout=30, check=False)
        require(isinstance(result.stdout, bytes) and isinstance(result.stderr, bytes),
                'Original binary adb output required')
        require(result.returncode == 0 or optional, 'ADB observation failed: ' + ' '.join(parts))
        return result

    def installation_now(self):
        serial = self.command('get-serialno').stdout.decode('ascii').strip()
        require(serial == self.serial, 'Selected adb transport changed')
        paths = self.command('shell', 'pm', 'path', PACKAGE).stdout.decode('ascii').splitlines()
        require(len(paths) == 1 and paths[0].startswith('package:'), 'One installed test base APK required')
        path = paths[0][8:]
        require(_PATH.fullmatch(path) is not None and '..' not in path.split('/'),
                'Unsafe or noncanonical installed test APK path')
        hashed = self.command('shell', 'sha256sum', path).stdout.decode('ascii').split()
        require(len(hashed) == 2 and hashed[1] == path
                and hashed[0] == self.identity['apkSha256'], 'Installed test APK bytes changed')
        packages = self.command('shell', 'cmd', 'package', 'list', 'packages', '-U', PACKAGE).stdout.decode('ascii').splitlines()
        exact = [re.fullmatch(r'package:' + re.escape(PACKAGE) + r' uid:(\d+)', line) for line in packages]
        exact = [item for item in exact if item]
        require(len(exact) == 1 and int(exact[0][1]) > 0, 'Exact installed test package UID unavailable')
        return dict(serial=serial, package=PACKAGE, installedApkPath=path,
                    apkSha256=hashed[0], sourceCommit=self.source, uid=int(exact[0][1]))

    def preflight(self):
        self.installation = self.installation_now()
        self.receipt['beforeLaunch'] = dict(self.installation)

    def process_now(self, pid, uid):
        pids = self.command('shell', 'pidof', PACKAGE, optional=True)
        require(pids.returncode in (0, 1), 'Cannot inspect fixed test process')
        require(pids.stdout.decode('ascii').strip() == str(pid), 'Current fixed test main PID changed')
        before = self.command('shell', 'cat', '/proc/' + str(pid) + '/stat').stdout
        status = self.command('shell', 'cat', '/proc/' + str(pid) + '/status').stdout
        cmdline = self.command('exec-out', 'cat', '/proc/' + str(pid) + '/cmdline').stdout
        after = self.command('shell', 'cat', '/proc/' + str(pid) + '/stat').stdout
        observed = process_identity(pid, uid, before, status, cmdline)
        require(observed == process_identity(pid, uid, after, status, cmdline),
                'Process generation changed around UID/cmdline inspection')
        return observed

    def observe(self, raw):
        require(self.installation is not None, 'No actual pre-launch APK observation')
        event = invocation(raw, self.source, self.nonce, self.identity)
        require(event['uid'] == self.installation['uid'], 'Event UID differs from installed package UID')
        observed = dict(self.process_now(event['pid'], event['uid']), eventSha256=event['eventSha256'])
        if self.owner is None:
            self.owner = observed
            self.receipt['firstOwnedEvent'] = dict(observed)
        else:
            require(observed == self.owner, 'Invocation process generation or event changed')
        return observed

    def poll(self, raw):
        """Polling never replaces the business failure; ownership errors are sticky."""
        if self.owner is None and b'"kind":"invocation"' not in raw:
            return
        if 'ownershipError' in self.receipt:
            return
        try:
            self.observe(raw)
        except Exception as error:
            self.receipt['ownershipError'] = repr(error)

    def cleanup(self, snapshot, evidence_saved):
        """Failure diagnostics must have been saved before any destructive action."""
        try:
            require(evidence_saved is True, 'Original failure/success evidence was not preserved')
            require(self.owner is not None, 'No previously observed nonce-owned process generation')
            require('ownershipError' not in self.receipt, 'Earlier invocation ownership observation failed')
            require(self.installation_now() == self.installation, 'Installed package/source/transport changed')
            # The callback persists this final original snapshot before returning.
            raw = snapshot()
            self.receipt['finalLogcatSha256'] = hashlib.sha256(raw).hexdigest()
            self.observe(raw)
            # A final short read closes the gap introduced by the read-only APK checks.
            require(self.process_now(self.owner['pid'], self.owner['uid'])
                    == {key: self.owner[key] for key in ('pid', 'uid', 'startTicks', 'package')},
                    'Process generation changed before cleanup')
            self.receipt['lastVerifiedOwner'] = dict(self.owner)
            self.receipt['forceStopAttempted'] = True
            self.command('shell', 'am', 'force-stop', PACKAGE)
            after = self.command('shell', 'pidof', PACKAGE, optional=True)
            require(after.returncode == 1 and after.stdout.strip() == b'',
                    'Fixed test main process still exists after force-stop')
            old = self.command('shell', 'cat', '/proc/' + str(self.owner['pid']) + '/stat', optional=True)
            require(old.returncode != 0 and not old.stdout.strip(), 'Original PID disappearance is unconfirmed')
            # A failed /proc read alone may be permission loss, not process exit.
            pids = self.command('shell', 'ps', '-A', '-o', 'PID').stdout.decode('ascii').splitlines()
            require(len(pids) > 1 and pids[0].strip() == 'PID'
                    and all(row.strip().isdigit() for row in pids[1:]), 'Complete current process list unavailable')
            listed = [int(row.strip()) for row in pids[1:]]
            require(self.owner['pid'] not in listed, 'Original PID still appears in the process list')
            self.receipt['afterStop'] = dict(mainPidofReturnCode=after.returncode,
                mainPidofStdout=after.stdout.decode('ascii'), procStatReturnCode=old.returncode,
                procStatStderr=old.stderr.decode('utf-8', errors='backslashreplace'),
                processList=listed, originalPidListed=False)
            self.receipt.update(status='cleaned', originalPidGone=True)
        except Exception as error:
            self.receipt.update(status='cleanupUnknown', reason=repr(error))
        self.receipt['endedAtMonotonicNs'] = time.monotonic_ns()
        return self.receipt
