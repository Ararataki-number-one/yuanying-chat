"""Read-only UI hierarchy acquisition within the caller's existing deadline."""
import hashlib
import json
import math
from pathlib import Path
import secrets
import subprocess
import time
import xml.etree.ElementTree as ET

NULL_ROOT = 'ERROR: null root node returned by UiTestAutomationBridge.'


class CaptureNotReady(RuntimeError):
    pass


class UiVisualCapture:
    def __init__(self, *, adb, serial, source, diagnostics):
        self.adb, self.serial = str(adb), serial
        self.diagnostics = Path(diagnostics)
        self.nonce = secrets.token_hex(16)
        self.count, self.records = 0, []
        self.report = dict(schema=1, sourceCommit=source, runNonce=self.nonce, serial=serial,
            scope='Read-only accessibility acquisition; no input, Activity restart, layout change or UI acceptance.',
            attemptCount=0, droppedAttempts=0, attempts=self.records)
        self.save()

    def save(self):
        self.report['attemptCount'] = self.count
        self.report['droppedAttempts'] = self.count - len(self.records)
        pending = self.diagnostics.with_suffix('.partial')
        pending.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + '\n')
        pending.replace(self.diagnostics)

    @staticmethod
    def output(raw):
        return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    text=raw[:8192].decode('utf-8', 'replace'), truncated=len(raw) > 8192)

    def command(self, parts, record, deadline):
        remaining = 90 if deadline is None else deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Existing UI scene deadline expired before accessibility acquisition')
        row = dict(parts=list(parts), startedAtWallTimeMillis=time.time_ns() // 1_000_000,
                   startedAtMonotonicNanos=time.monotonic_ns(), timeoutSeconds=min(90, remaining))
        record['commands'].append(row)
        try:
            result = subprocess.run([self.adb, '-s', self.serial, *parts],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=row['timeoutSeconds'], check=False)
            row.update(exitCode=result.returncode, stdout=self.output(result.stdout), stderr=self.output(result.stderr))
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Existing UI scene deadline expired during accessibility acquisition')
            return result
        except subprocess.TimeoutExpired as error:
            row.update(exitCode=None, timedOut=True, stdout=self.output(error.stdout or b''),
                       stderr=self.output(error.stderr or b''))
            raise
        except Exception as error:
            row.setdefault('exitCode', None)
            row.update(error=str(error))
            raise
        finally:
            row['completedAtMonotonicNanos'] = time.monotonic_ns()
            row['completedAtWallTimeMillis'] = time.time_ns() // 1_000_000

    def attempt(self, deadline):
        self.count += 1
        remote = '/sdcard/pocketchat-ui-visual-' + self.nonce + '-' + str(self.count) + '.xml'
        record = dict(index=self.count, remotePath=remote, commands=[],
                      startedAtMonotonicNanos=time.monotonic_ns(),
                      existingSceneDeadline=deadline, status='failed')
        # Retain a bounded suffix, explicitly accounting for every dropped row.
        self.records.append(record)
        if len(self.records) > 256:
            del self.records[0]
        try:
            dumped = self.command(('shell', 'uiautomator', 'dump', remote), record, deadline)
            combined = (dumped.stdout + dumped.stderr).decode('utf-8', 'strict').strip()
            if dumped.returncode in (0, 1) and combined == NULL_ROOT:
                raise CaptureNotReady(NULL_ROOT)
            if dumped.returncode != 0:
                raise subprocess.CalledProcessError(dumped.returncode, record['commands'][-1]['parts'],
                                                   output=dumped.stdout, stderr=dumped.stderr)
            acknowledgements = {'', 'UI hierchary dumped to: ' + remote, 'UI hierarchy dumped to: ' + remote}
            if dumped.stderr or dumped.stdout.decode('utf-8', 'strict').strip() not in acknowledgements:
                raise RuntimeError('Unexpected accessibility dump output: ' + combined[:8192])
            read = self.command(('shell', 'cat', remote), record, deadline)
            missing = ('cat: ' + remote + ': No such file or directory').encode()
            if read.returncode == 1 and not read.stdout and read.stderr.strip() == missing:
                raise CaptureNotReady('Owned current-attempt hierarchy was not created')
            if read.returncode != 0:
                raise subprocess.CalledProcessError(read.returncode, record['commands'][-1]['parts'],
                                                   output=read.stdout, stderr=read.stderr)
            if read.stderr:
                raise RuntimeError('Unexpected hierarchy read error: ' + read.stderr[:8192].decode('utf-8', 'replace'))
            xml = read.stdout.decode('utf-8', 'strict')
            tree = ET.fromstring(xml)
            if tree.tag != 'hierarchy':
                raise ValueError('Accessibility capture has no hierarchy root')
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Existing UI scene deadline expired during hierarchy validation')
            record.update(status='captured', xmlBytes=len(read.stdout), xmlSha256=hashlib.sha256(read.stdout).hexdigest())
            return xml
        except CaptureNotReady as error:
            record.update(status='not-ready', reason=str(error))
            raise
        except Exception as error:
            record.update(status='failed', errorType=type(error).__name__, error=str(error))
            raise
        finally:
            record['completedAtMonotonicNanos'] = time.monotonic_ns()
            self.save()

    def read(self, deadline=None):
        if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise ValueError('Existing finite UI scene deadline required')
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Existing UI scene deadline expired during accessibility readiness')
            try:
                return self.attempt(deadline)
            except CaptureNotReady:
                if deadline is None:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Existing UI scene deadline expired during accessibility readiness')
                time.sleep(min(.5, remaining))  # Read-only acquisition polling, never input pacing.
