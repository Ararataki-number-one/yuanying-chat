"""One original headerUp adb swipe after bounded, read-only emulator preparation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from profile_invocation_contract import verify_installed

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.CompactChromeIntegrationActivity'
HELPER = 'tests/native-input-driver/NativePreEmitReadiness.java'
CLI = 'tests/native-input-readiness-host/NativePreEmitReadinessCli.java'
ADAPTER = 'tools/gecko/chrome_header_readiness.py'
HELPER_SHA = '40130991cd673e5b38a5e1ca18c3bcca71cff74ec69550126cd6303ef0b66348'
CLASS = 'local.pocketchat.inputdriver.NativePreEmitReadinessCli'
MAX_OUTPUT = 2097152
REASONS = {'invalid-request', 'source-unverified', 'cache-unverified', 'identity-changed',
           'invalid-observation', 'observation-failed', 'output-too-large', 'deadline',
           'already-invoked', 'action-failed', 'receipt-unavailable'}


class HeaderReadinessFailure(Exception):
    def __init__(self, reason):
        self.reason = reason if reason in REASONS else 'observation-failed'
        super().__init__(self.reason)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise HeaderReadinessFailure('invalid-request')


def need(value, reason):
    if not value:
        raise HeaderReadinessFailure(reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def decode(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'invalid-observation')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(HeaderReadinessFailure('invalid-observation')))


def _bounded_run(parts, deadline, input_bytes=None, stdout_limit=MAX_OUTPUT, stderr_limit=65536, cwd=None):
    """Drain capped pipes concurrently; kill only this owned host child on failure."""
    need(deadline > time.monotonic(), 'deadline')
    need(input_bytes is None or len(input_bytes) <= MAX_OUTPUT, 'output-too-large')
    child = subprocess.Popen(parts, cwd=cwd, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffers = [bytearray(), bytearray()]
    failures = []
    def reader(stream, value, maximum):
        try:
            while True:
                chunk = stream.read(16384)
                if not chunk:
                    return
                if len(value) + len(chunk) > maximum:
                    failures.append('output-too-large'); child.kill(); return
                value.extend(chunk)
        except (OSError, ValueError):
            failures.append('observation-failed')
        finally:
            try:
                stream.close()
            except OSError:
                pass
    def writer():
        try:
            child.stdin.write(input_bytes); child.stdin.close()
        except (OSError, ValueError):
            failures.append('observation-failed')
    workers = [threading.Thread(target=reader, args=(child.stdout, buffers[0], stdout_limit), daemon=True),
               threading.Thread(target=reader, args=(child.stderr, buffers[1], stderr_limit), daemon=True)]
    if input_bytes is not None:
        workers.append(threading.Thread(target=writer, daemon=True))
    for worker in workers:
        worker.start()
    try:
        try:
            child.wait(timeout=max(.001, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            raise HeaderReadinessFailure('deadline') from None
        for worker in workers:
            worker.join(timeout=max(0, deadline-time.monotonic()))
        need(not any(worker.is_alive() for worker in workers), 'deadline')
        need(not failures, failures[0] if failures else 'observation-failed')
        need(time.monotonic() < deadline, 'deadline')
        return subprocess.CompletedProcess(parts, child.returncode, bytes(buffers[0]), bytes(buffers[1]))
    finally:
        if child.poll() is None:
            child.kill()
        try:
            child.wait(timeout=.2)
        except subprocess.TimeoutExpired:
            pass
        for worker in workers:
            worker.join(timeout=.05)


def _checked(parts, deadline, **kwargs):
    value = _bounded_run(parts, deadline, **kwargs)
    need(value.returncode == 0 and not value.stderr, 'observation-failed')
    return value.stdout


def _source_bindings(root, source, identity, deadline):
    need(re.fullmatch('[0-9a-f]{40}', source or '') is not None, 'source-unverified')
    head = _checked(['git', 'rev-parse', 'HEAD'], deadline, cwd=root, stdout_limit=128).decode().strip()
    tree = _checked(['git', 'rev-parse', 'HEAD^{tree}'], deadline, cwd=root, stdout_limit=128).decode().strip()
    dirty = _checked(['git', 'status', '--porcelain', '--untracked-files=normal'], deadline, cwd=root, stdout_limit=65536)
    need(head == source == identity['sourceCommit'] and tree == identity['sourceTree'] and not dirty.strip(), 'source-unverified')
    hashes = {}
    for name in (HELPER, CLI, ADAPTER):
        path = root/name
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_OUTPUT, 'source-unverified')
        actual = path.read_bytes()
        original = _checked(['git', 'show', source+':'+name], deadline, cwd=root)
        need(actual == original, 'source-unverified')
        hashes[name] = digest(actual)
    need(hashes[HELPER] == HELPER_SHA, 'source-unverified')
    return dict(sourceCommit=source, sourceTree=tree, sourceSha256=hashes)


def _class_hashes(classes):
    expected = {name+'.class' for name in ('NativePreEmitReadiness', 'NativePreEmitReadiness$Capture',
        'NativePreEmitReadiness$Clock', 'NativePreEmitReadiness$Probe', 'NativePreEmitReadiness$Result',
        'NativePreEmitReadiness$State', 'NativePreEmitReadinessCli')}
    folder = classes/'local/pocketchat/inputdriver'
    files = list(classes.rglob('*.class'))
    need(len(files) == len(expected) and {p.name for p in files} == expected
         and all(p.parent == folder and p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_OUTPUT for p in files), 'cache-unverified')
    return {p.name:digest(p.read_bytes()) for p in sorted(files)}


def _compile_parser(root, binding, deadline):
    home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
    java = (Path(home)/'bin/java').resolve() if home else Path(shutil.which('java') or '').resolve()
    javac = java.with_name('javac')
    need(java.is_file() and javac.is_file(), 'cache-unverified')
    version = _bounded_run([str(java), '-version'], deadline, stdout_limit=4096, stderr_limit=4096)
    need(version.returncode == 0 and re.search(rb'version "17[.\"]', version.stdout+version.stderr), 'cache-unverified')
    tool = dict(javaSha256=digest(java.read_bytes()), javacSha256=digest(javac.read_bytes()), versionSha256=digest(version.stdout+version.stderr))
    key = digest(json.dumps(dict(binding, tool=tool), sort_keys=True, separators=(',', ':')).encode())
    cache = root/'work/chrome-header-parser'/key
    manifest = cache/'manifest.json'; classes = cache/'classes'
    need(not cache.is_symlink() and not manifest.is_symlink() and not classes.is_symlink(), 'cache-unverified')
    if cache.exists():
        need(manifest.is_file() and manifest.stat().st_size <= 65536, 'cache-unverified')
        saved = decode(manifest.read_bytes())
        need(saved.get('binding') == binding and saved.get('tool') == tool and saved.get('classes') == _class_hashes(classes), 'cache-unverified')
    else:
        cache.mkdir(parents=True, exist_ok=False); classes.mkdir()
        _checked([str(javac), '-encoding', 'UTF-8', '-d', str(classes), str(root/HELPER), str(root/CLI)], deadline)
        saved = dict(binding=binding, tool=tool, classes=_class_hashes(classes))
        with manifest.open('x') as output:
            json.dump(saved, output, sort_keys=True)
    return [str(java), '-cp', str(classes), CLASS], dict(parserClassesSha256=digest(json.dumps(saved['classes'], sort_keys=True).encode()), cache=cache, classes=saved['classes'])


def _identity(prefix, identity, deadline):
    def call(*parts, limit=65536):
        return _checked(prefix+list(parts), deadline, stdout_limit=limit)
    pid = call('shell', 'pidof', PACKAGE, limit=128).decode('ascii').strip()
    need(re.fullmatch('[1-9][0-9]*', pid) is not None, 'identity-changed')
    first = call('exec-out', 'cat', '/proc/'+pid+'/stat').decode('ascii')
    status = call('exec-out', 'cat', '/proc/'+pid+'/status').decode('ascii')
    command = call('exec-out', 'cat', '/proc/'+pid+'/cmdline')
    last = call('exec-out', 'cat', '/proc/'+pid+'/stat').decode('ascii')
    need(first.startswith(pid+' (') and last.startswith(pid+' ('), 'identity-changed')
    ticks = first[first.rindex(')')+2:].split()[19]
    need(re.fullmatch('[1-9][0-9]*', ticks) is not None and ticks == last[last.rindex(')')+2:].split()[19], 'identity-changed')
    uids = re.findall(r'^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', status, re.MULTILINE)
    need(len(uids) == 1 and len(set(uids[0])) == 1 and 10000 <= int(uids[0][0]) < 100000
         and command.split(b'\0')[0] == PACKAGE.encode(), 'identity-changed')
    def package_uid(package):
        packages = call('shell', 'pm', 'list', 'packages', '-U', '--user', '0', package).decode('ascii').splitlines()
        rows = [re.fullmatch(r'package:([A-Za-z0-9_.]+) uid:([0-9]+)', row) for row in packages]
        need(rows and len(rows) <= 256 and all(rows), 'identity-changed')
        selected = [int(row[2]) for row in rows if row[1] == package]
        need(len(selected) == 1 and 10000 <= selected[0] < 100000, 'identity-changed')
        return selected[0]
    system = package_uid('com.android.systemui')
    need(package_uid(PACKAGE) == int(uids[0][0]) and system != int(uids[0][0]), 'identity-changed')
    provider = decode(call('exec-out', 'content', 'read', '--uri', 'content://'+PACKAGE+'.evidence/build-identity'))
    try:
        verify_installed(provider, identity)
    except (AssertionError, KeyError, TypeError, ValueError):
        raise HeaderReadinessFailure('identity-changed') from None
    return dict(pid=pid, uid=int(uids[0][0]), startTicks=ticks, systemUiUid=system)


def _focus_token(raw):
    fields = re.findall(r'^\s*mCurrentFocus=([^\r\n]*)$', raw.decode('utf-8'), re.MULTILINE)
    need(len(fields) == 1, 'invalid-observation')
    match = re.fullmatch(r'Window\{([0-9a-f]+) u0 '+re.escape(COMPONENT)+r'\}', fields[0].strip())
    need(match is not None, 'identity-changed')
    return match[1]


def header_up_once(*, argv, source, identity, start, end, nonce, out, root=ROOT, clock=time.monotonic, sleep=time.sleep):
    started = clock(); action_deadline = started+90; preparation_deadline = min(started+20, action_deadline-.320)
    safe_source = source if isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source) else None
    record = dict(schema=1, status='failed', reason='invalid-request', scope='chrome-header-up-only', sourceCommit=safe_source,
                  preEmitOnly=True, observations=0, elapsedMs=0, shadeObserved=False, gestureInvocations=0,
                  originalActionBudgetMs=90000, preparationBudgetMs=20000, swipeDurationMs=320,
                  applicationAcceptance=False, releaseAcceptance=False)
    path = None; owned_receipt = False
    try:
        parser = Parser(add_help=False, allow_abbrev=False)
        parser.add_argument('--adb', required=True); parser.add_argument('--serial', required=True)
        args, _ = parser.parse_known_args(argv)
        need(safe_source and args.adb and args.serial == 'emulator-5554' and re.fullmatch('[0-9a-f]{32}', nonce or '')
             and all(type(x) is int and x >= 0 for point in (start, end) for x in point)
             and len(start) == len(end) == 2, 'invalid-request')
        prefix = [args.adb, '-s', args.serial]; root = Path(root).resolve(); out = Path(out)
        need(out.is_dir() and not out.is_symlink(), 'invalid-request')
        path = out/('chrome-header-readiness-'+nonce+'.json')
        need(not path.exists() and not path.is_symlink(), 'already-invoked')
        with path.open('x') as target:
            json.dump(record, target, sort_keys=True)
        owned_receipt = True
        binding = _source_bindings(root, source, identity, preparation_deadline)
        command, compiled = _compile_parser(root, binding, preparation_deadline)
        record.update(sourceTree=binding['sourceTree'], adapterSourceSha256=binding['sourceSha256'][ADAPTER],
                      parserSourceSha256=binding['sourceSha256'][CLI], helperSourceSha256=binding['sourceSha256'][HELPER],
                      parserClassesSha256=compiled['parserClassesSha256'])
        for parts, expected in [(['shell', 'getprop', 'ro.kernel.qemu'], b'1'),
                                (['shell', 'getprop', 'ro.build.version.sdk'], b'35'),
                                (['shell', 'am', 'get-current-user'], b'0')]:
            need(_checked(prefix+parts, preparation_deadline, stdout_limit=128).strip() == expected, 'identity-changed')
        need(_checked(prefix+['shell', 'getprop', 'ro.hardware'], preparation_deadline, stdout_limit=128).strip()
             in (b'ranchu', b'goldfish'), 'identity-changed')
        initial = _identity(prefix, identity, preparation_deadline); token = None
        while record['observations'] < 101:
            need(clock() < preparation_deadline, 'deadline')
            need(_identity(prefix, identity, preparation_deadline) == initial, 'identity-changed')
            raw = _checked(prefix+['shell', 'dumpsys', 'window'], preparation_deadline)
            observed_token = _focus_token(raw)
            need(token is None or token == observed_token, 'identity-changed')
            need(_class_hashes(compiled['cache']/'classes') == compiled['classes'], 'cache-unverified')
            state = _checked(command+[str(initial['uid']), str(initial['systemUiUid']), COMPONENT, observed_token], preparation_deadline,
                             input_bytes=raw, stdout_limit=64, stderr_limit=64)
            need(state in (b'CLEAR\n', b'SHADE_VISIBLE\n'), 'invalid-observation')
            token = observed_token; record['observations'] += 1
            need(_identity(prefix, identity, preparation_deadline) == initial, 'identity-changed')
            need(clock() < preparation_deadline, 'deadline')
            if state == b'CLEAR\n':
                break
            record['shadeObserved'] = True
            sleep(min(.2, max(0, preparation_deadline-clock())))
        else:
            raise HeaderReadinessFailure('deadline')
        need(_source_bindings(root, source, identity, preparation_deadline) == binding
             and _identity(prefix, identity, preparation_deadline) == initial, 'identity-changed')
        need(clock() < preparation_deadline and action_deadline-clock() >= .320, 'deadline')
        record['gestureInvocations'] = 1
        original = prefix+['shell', 'input', 'swipe', str(start[0]), str(start[1]), str(end[0]), str(end[1]), '320']
        outcome = _bounded_run(original, action_deadline)
        need(outcome.returncode == 0, 'action-failed')
        need(clock() < action_deadline, 'deadline')
        record.update(status='passed', reason='clear')
        return record
    except HeaderReadinessFailure as error:
        record['reason'] = error.reason
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        record['reason'] = 'observation-failed'
        raise HeaderReadinessFailure('observation-failed') from None
    finally:
        record['elapsedMs'] = max(0, round((clock()-started)*1000))
        if owned_receipt and path is not None and path.is_file():
            try:
                temporary = path.with_suffix('.partial')
                with temporary.open('x') as target:
                    json.dump(record, target, sort_keys=True)
                temporary.replace(path)
            except OSError:
                raise HeaderReadinessFailure('receipt-unavailable') from None
        print('CHROME_HEADER_READINESS '+json.dumps(record, sort_keys=True, separators=(',', ':')), flush=True)
