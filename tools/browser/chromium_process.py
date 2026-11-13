"""Own one desktop Chromium process and its original 12-second CDP startup.

The receipt describes process startup only. It does not qualify browser APIs or
Android behavior; those checks remain in the two calling fixtures.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


STARTUP_SECONDS = 12


class _OwnedProcessGroup:
    """Keep the Linux launcher waitable until its entire new group retires.

    Reaping an exited launcher early would permit its numeric PID/PGID to be
    reused. WNOWAIT preserves that ownership even when only descendants remain.
    """
    def __init__(self, process):
        self.process, self.pid = process, process.pid

    def poll(self):
        try:
            result = os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            raise RuntimeError('Chromium launcher ownership was lost before group cleanup') from None
        if result is None:
            return None
        if result.si_code == os.CLD_EXITED:
            return result.si_status
        if result.si_code in (os.CLD_KILLED, os.CLD_DUMPED):
            return -result.si_status
        raise RuntimeError('Unrecognized Chromium launcher exit state')

    def signal(self, value):
        self.poll()  # The unreaped child still reserves this PID/PGID.
        if os.getpgid(self.pid) != self.pid or os.getsid(self.pid) != self.pid:
            raise RuntimeError('Chromium no longer owns its original process group')
        os.killpg(self.pid, value)

    def live_members(self):
        self.poll()
        members = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                fields = (entry/'stat').read_bytes().rsplit(b')', 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if int(fields[2]) != self.pid:
                continue
            if int(fields[3]) != self.pid:
                raise RuntimeError('Chromium process group session ownership changed')
            if fields[0] not in (b'Z', b'X'):
                members.append(int(entry.name))
        return members

    def wait_group(self, deadline):
        while time.monotonic() < deadline:
            members = self.live_members()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            if not members:
                return True
            time.sleep(min(.05, remaining))
        return False

    def retire(self, receipt):
        receipt['returnCodeBeforeCleanup'] = self.poll()
        receipt['cleanup'] = 'already-exited'
        receipt['cleanupBudgetMs'] = dict(term=5000, kill=5000)
        deadline = time.monotonic() + 5
        try:
            if self.live_members():
                self.signal(signal.SIGTERM)
                receipt['cleanup'] = 'sigterm'
                deadline = time.monotonic() + 5
                if not self.wait_group(deadline):
                    self.signal(signal.SIGKILL)
                    receipt['cleanup'] = 'sigkill'
                    deadline = time.monotonic() + 5
                    if not self.wait_group(deadline):
                        raise RuntimeError('Chromium process group did not retire within its cleanup budget')
        except Exception as error:
            receipt['groupCleanupError'] = type(error).__name__
            if receipt['cleanup'] != 'sigkill':
                # Observation failure does not establish that descendants exited.
                self.signal(signal.SIGKILL)
                receipt['cleanup'] = 'sigkill'
                deadline = time.monotonic() + 5
            raise
        finally:
            # No group signal follows this wait: the PID can now be released.
            self.process.wait(timeout=max(0, deadline - time.monotonic()))
            receipt['returnCodeAfterCleanup'] = self.process.returncode


def _endpoint(process, port_file, receipt, *, clock=time.monotonic, sleep=time.sleep):
    started = clock()
    deadline = started + STARTUP_SECONDS
    try:
        while True:
            if clock() >= deadline:
                receipt['status'] = 'deadline'
                raise RuntimeError('Actual Chromium debugging endpoint did not start within 12 seconds')
            if process.poll() is not None:
                receipt['status'] = 'process-exited'
                raise RuntimeError('Actual Chromium exited before its debugging endpoint was ready')
            if port_file.is_file():
                with port_file.open('rb') as source:
                    raw = source.read(4097)
                receipt['portFileBytes'] = len(raw)
                if clock() >= deadline:
                    receipt['status'] = 'deadline'
                    raise RuntimeError('Actual Chromium debugging endpoint arrived after the 12-second deadline')
                try:
                    lines = raw.decode('utf-8').splitlines()
                except UnicodeError:
                    receipt['status'] = 'invalid-endpoint'
                    raise RuntimeError('Actual Chromium wrote a non-UTF-8 debugging endpoint') from None
                if (len(raw) > 4096 or len(lines) < 2 or not lines[0].isdigit()
                        or not 0 < int(lines[0]) < 65536
                        or re.fullmatch(r'/devtools/browser/[A-Za-z0-9_-]+', lines[1]) is None):
                    receipt['status'] = 'invalid-endpoint'
                    raise RuntimeError('Actual Chromium wrote an invalid debugging endpoint')
                if process.poll() is not None:
                    receipt['status'] = 'process-exited'
                    raise RuntimeError('Actual Chromium exited while its debugging endpoint was being read')
                if clock() >= deadline:
                    receipt['status'] = 'deadline'
                    raise RuntimeError('Actual Chromium debugging endpoint arrived after the 12-second deadline')
                receipt['status'] = 'endpoint-ready'
                return 'ws://127.0.0.1:' + lines[0] + lines[1]
            sleep(min(.1, max(0, deadline-clock())))
    finally:
        receipt['startupElapsedMs'] = max(0, round((clock()-started)*1000))


@contextmanager
def chromium_endpoint(*, command, environment, profile, output, version, source_files):
    """Yield one endpoint; archive startup evidence and retire the owned child."""
    output = Path(output)
    stdout_path = output/'chromium.stdout.log'
    stderr_path = output/'chromium.stderr.log'
    port_file = Path(profile)/'DevToolsActivePort'
    receipt = dict(schema=1, scope='desktop-child-startup-only', status='launch-failed',
                   startupBudgetMs=STARTUP_SECONDS*1000, version=version,
                   command=list(command), sourceFiles=dict(source_files),
                   environmentPresent={key:bool(environment.get(key)) for key in
                       ('DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME')})
    group = None
    try:
        with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
            try:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                           env=environment, start_new_session=True)
                group = _OwnedProcessGroup(process)
                receipt['pid'] = process.pid
                receipt['status'] = 'observing-endpoint'
                yield _endpoint(group, port_file, receipt)
            finally:
                if group is not None:
                    receipt['portFilePresentAtCleanup'] = port_file.is_file()
                    group.retire(receipt)
    except Exception as error:
        receipt['errorType'] = type(error).__name__
        raise
    finally:
        receipt['logs'] = {}
        for path in (stdout_path, stderr_path):
            if path.is_file():
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    for chunk in iter(lambda:source.read(65536), b''):
                        digest.update(chunk)
                receipt['logs'][path.name] = dict(bytes=path.stat().st_size, sha256=digest.hexdigest())
        (output/'chromium.startup.json').write_text(json.dumps(receipt, indent=2)+'\n')
