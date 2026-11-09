"""Failure-only, read-only ANR stacks for the disposable UI test package.

This does not retry a scene, dismiss a system dialog, alter a deadline, or
qualify a capture. Only an actually observed system ANR dialog enables it.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = 'local.pocketchat.test'
MAX_CAPTURE = 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def observed_dialog(attempts):
    """Use complete original cat bytes, never a truncated text or title alone."""
    for attempt in reversed(attempts):
        for command in reversed(attempt.get('commands', [])):
            if command.get('parts', [])[:2] != ['shell', 'cat'] or command.get('exitCode') != 0:
                continue
            output = command.get('stdout', {})
            if output.get('truncated') is not False or not isinstance(output.get('text'), str):
                continue
            raw = output['text'].encode('utf-8')
            if len(raw) != output.get('bytes') or digest(raw) != output.get('sha256'):
                continue
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                continue
            if root.tag != 'hierarchy':
                continue
            nodes = [node.attrib for node in root.iter('node')]
            titles = [node for node in nodes if node.get('package') == 'android'
                      and node.get('resource-id') == 'android:id/alertTitle'
                      and node.get('class') == 'android.widget.TextView']
            actions = [node for node in nodes if node.get('package') == 'android'
                       and node.get('resource-id') in ('android:id/aerr_close', 'android:id/aerr_wait')
                       and node.get('class') == 'android.widget.Button'
                       and node.get('enabled') == node.get('clickable') == 'true']
            if (len(titles) != 1 or titles[0].get('text') != "元婴期院士 isn't responding"
                    or sorted(node['resource-id'] for node in actions) != ['android:id/aerr_close', 'android:id/aerr_wait']):
                continue
            return dict(attempt=attempt['index'], xmlBytes=len(raw), xmlSha256=digest(raw),
                        observedAtWallTimeMillis=command.get('completedAtWallTimeMillis'),
                        systemDialog='application-not-responding', applicationLabel='元婴期院士')
    return None


def owned_stacks(raw):
    """Select complete ART blocks whose actual Cmd line is the test package.

    DropBox can include other processes and logcat. Neither is copied. Returned
    blocks remain observations; collection identity is not a claim that every
    historical block originated in the current scene.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_CAPTURE:
        raise ValueError('Bounded complete ANR stream required')
    result = []
    start = re.compile(rb'(?m)^----- pid ([1-9][0-9]*) at [^\r\n]{1,100} -----\r?$')
    consumed = 0
    for match in start.finditer(raw):
        if match.start() < consumed:
            continue
        pid = match[1]
        end = re.search(rb'(?m)^----- end ' + pid + rb' -----\r?$', raw[match.end():])
        if end is None:
            break  # A later header inside an unclosed block is ambiguous.
        consumed = match.end() + end.end()
        block = raw[match.start():consumed]
        if len(start.findall(block)) != 1:
            continue
        commands = re.findall(rb'(?m)^Cmd line: ([^\r\n]+)\r?$', block)
        if commands != [PACKAGE.encode()] or b'DALVIK THREADS' not in block:
            continue
        if not re.search(rb'(?m)^"main"[^\r\n]*\btid=1\b', block):
            continue
        result.append((int(pid), block))
    return result


def collect(*, adb, serial, source, nonce, directory, observation, environment=None, execute=None):
    environment = os.environ if environment is None else environment
    execute = subprocess.run if execute is None else execute
    record = dict(schema=1, diagnosticOnly=True, releaseAcceptance=False,
                  sourceCommit=source, captureRunNonce=nonce, observedDialog=observation,
                  applicationPackage=PACKAGE, commands=[], stackFiles=[],
                  status='not-collected', originalFailurePreserved=True,
                  scope='Failure-only collection of complete test-process ART blocks; no input, restart, scene replay, timeout extension or acceptance.')
    if (environment.get('CI') != 'true' or serial != 'emulator-5554'
            or not re.fullmatch('[0-9a-f]{40}', source) or not re.fullmatch('[0-9a-f]{32}', nonce)
            or not re.fullmatch('[1-9][0-9]*', environment.get('GITHUB_RUN_ID', ''))
            or not re.fullmatch('[1-9][0-9]*', environment.get('GITHUB_RUN_ATTEMPT', ''))
            or not isinstance(observation, dict) or observation.get('systemDialog') != 'application-not-responding'):
        return record
    record.update(runId=environment['GITHUB_RUN_ID'], runAttempt=environment['GITHUB_RUN_ATTEMPT'])
    directory = Path(directory)
    if any(path.is_symlink() for path in (directory, *directory.parents)) or not directory.is_dir():
        raise ValueError('Existing ordinary diagnostic directory required')
    path = directory / ('ui-anr-' + nonce + '.json')
    if path.exists() or path.is_symlink():
        raise ValueError('ANR diagnostic already collected for this capture')
    sources = [Path(__file__).with_name(name) for name in
               ('ui_anr_diagnostic.py', 'diagnostic_capture_privacy.py', 'caret_ime_guard.py')]
    record['sourceFiles'] = {'tools/gecko/' + item.name:
                            dict(bytes=item.stat().st_size, sha256=digest(item.read_bytes()))
                            for item in sources}

    def run(parts, timeout):
        row = dict(parts=list(parts), startedAtMonotonicNanos=time.monotonic_ns(), timeoutSeconds=timeout)
        record['commands'].append(row)
        try:
            value = execute([str(adb), '-s', serial, *parts], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
            row.update(returnCode=value.returncode,
                       stdoutBytes=len(value.stdout), stdoutSha256=digest(value.stdout),
                       stderrBytes=len(value.stderr), stderrSha256=digest(value.stderr))
            return value
        except subprocess.TimeoutExpired as error:
            row.update(returnCode=None, timedOut=True,
                       stdoutBytes=len(error.stdout or b''), stdoutSha256=digest(error.stdout or b''),
                       stderrBytes=len(error.stderr or b''), stderrSha256=digest(error.stderr or b''))
            raise
        finally:
            row['completedAtMonotonicNanos'] = time.monotonic_ns()

    try:
        confirmed = run(('shell', 'getprop', 'ro.kernel.qemu'), 3)
        if confirmed.returncode != 0 or confirmed.stdout.strip() != b'1' or confirmed.stderr:
            raise ValueError('Confirmed disposable emulator required')
        # Device-side byte cap prevents a large global DropBox history from
        # entering the host capture. Only complete owned stack blocks survive.
        command = 'dumpsys dropbox --print data_app_anr | head -c 1048577'
        captured = run(('shell', 'sh', '-c', command), 7)
        record['streamTruncated'] = len(captured.stdout) > MAX_CAPTURE
        if captured.returncode != 0 or captured.stderr or record['streamTruncated']:
            raise ValueError('ANR stream failed or exceeded its fixed byte bound')
        if __package__:
            from .diagnostic_capture_privacy import checked_bytes
        else:
            from diagnostic_capture_privacy import checked_bytes
        for ordinal, (pid, raw) in enumerate(owned_stacks(captured.stdout), 1):
            derivative, privacy = checked_bytes(raw)
            filename = 'ui-anr-' + nonce + '-stack-' + str(ordinal) + '.txt'
            with (directory / filename).open('xb') as stream:
                stream.write(derivative)
            record['stackFiles'].append(dict(file=filename, pid=pid, bytes=len(derivative),
                                             sha256=digest(derivative), privacy=privacy))
        record['status'] = 'owned-stacks-collected' if record['stackFiles'] else 'owned-stack-unavailable'
    except Exception as error:
        # No raw error output or broader log stream is published. The original
        # scene failure remains the caller's exception, regardless of this result.
        record.update(status='collection-failed', errorType=type(error).__name__)
    finally:
        record['sourceInputsUnchanged'] = all(
            item.stat().st_size == record['sourceFiles']['tools/gecko/' + item.name]['bytes']
            and digest(item.read_bytes()) == record['sourceFiles']['tools/gecko/' + item.name]['sha256']
            for item in sources)
        if not record['sourceInputsUnchanged']:
            record.update(status='collection-failed', collectionFailure='Diagnostic source changed during collection')
        with path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record
