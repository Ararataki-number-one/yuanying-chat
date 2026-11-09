"""Bounded observations around the existing single shell tap; never a tap retry.

These integrated receipts diagnose delivery; they cannot pass acceptance.
Window/input dumps are projected in memory. Only fixed controlled components and
typed metadata are retained; arbitrary titles, accounts and document text are not.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

STAGES = ('file-picker-1', 'file-picker-2', 'download-click')
COMPONENT = r'local\.pocketchat\.test/local\.pocketchat\.(?:BrowserIntegrationActivity|BrowserActivity|MainActivity)'
COMPONENT_RE = re.compile(r'(?<![A-Za-z0-9_.])(' + COMPONENT + r')(?![A-Za-z0-9_.])')
RAW_LIMIT = 16 * 1024
STATE_LIMIT = 2 * 1024 * 1024
LOG_LIMIT = 128 * 1024
LOG_LINES = 200
OBSERVATION_TIMEOUT = 2


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def state_projection(raw, kind):
    """No entire dump or unrecognized string value leaves this function."""
    result = dict(kind=kind, originalBytes=len(raw), originalSha256=digest(raw),
                  complete=len(raw) <= STATE_LIMIT, retainedRawDump=False,
                  controlledComponents=[], fields={}, controlledWindowFields=[])
    if len(raw) > STATE_LIMIT:
        result['status'] = 'over-limit'
        return result
    try:
        text = raw.decode('utf-8', 'strict')
    except UnicodeDecodeError:
        result['status'] = 'invalid-utf8'
        return result
    result['status'] = 'projected'
    result['controlledComponents'] = sorted(set(COMPONENT_RE.findall(text)))
    # Fixed scalar names only. A non-matching value is never copied verbatim.
    scalar = re.compile(r'^\s*(mTopFocusedDisplayId|FocusedDisplayId|DispatchEnabled|DispatchFrozen)\s*[:=]\s*(true|false|[0-9]{1,8})\s*$', re.M)
    for key, value in scalar.findall(text):
        result['fields'].setdefault(key, []).append(value if value in ('true', 'false') else int(value))
    focus = re.findall(r'^\s*mCurrentFocus=([^\r\n]*)$', text, re.M)
    if focus:
        result['currentFocus'] = []
        for line in focus[:4]:
            found = COMPONENT_RE.search(line)
            result['currentFocus'].append(found.group(1) if found else 'other-or-none')
    for line in text.splitlines():
        match = COMPONENT_RE.search(line)
        if not match:
            continue
        row = dict(component=match.group(1))
        for key in ('displayId', 'ownerPid', 'ownerUid', 'paused', 'visible', 'hasFocus', 'inputConfig'):
            values = re.findall(r'\b' + key + r'\s*[:=]\s*(true|false|0x[0-9a-fA-F]{1,16}|[0-9]{1,12})(?![A-Za-z0-9_])', line)
            if values:
                row[key] = values[:4]
        result['controlledWindowFields'].append(row)
        if len(result['controlledWindowFields']) == 16:
            result['windowProjectionLimitReached'] = True
            break
    return result


def activity_projection(raw, *, source, nonce, identity):
    result = dict(originalBytes=len(raw), originalSha256=digest(raw), retainedRawReport=False)
    if len(raw) > STATE_LIMIT:
        return dict(result, status='over-limit')
    try:
        value = json.loads(raw)
        if (type(value) is not dict or value.get('sourceCommit') != source or
                value.get('runNonce') != nonce or value.get('buildIdentity') != identity):
            return dict(result, status='binding-rejected')
        result['status'] = 'projected'
        result['stage'] = value.get('stage') if value.get('stage') in (*STAGES, 'failed', 'download-publication', 'complete') else 'other-stage'
        for key in ('foreground', 'pendingChooser', 'routeAllowed'):
            if type(value.get(key)) is bool:
                result[key] = value[key]
        result['nativeInputEvents'] = []
        for event in value.get('nativeInputEvents', [])[-12:]:
            if type(event) is not dict or event.get('stage') not in STAGES:
                continue
            row = {'stage': event['stage']}
            for key in ('action', 'x', 'y', 'eventTime'):
                v = event.get(key)
                if type(v) in (int, float) and -1 <= v <= 10**12:
                    row[key] = v
            if type(event.get('handled')) is bool:
                row['handled'] = event['handled']
            result['nativeInputEvents'].append(row)
        return result
    except (TypeError, ValueError, UnicodeDecodeError):
        return dict(result, status='invalid-report')


def selected_failure_log(raw):
    """Retain exact original lines only for a finite payload-free grammar.

    Unknown messages are explicitly excluded, counted, and covered by the raw
    capture hash. This is not advertised as a complete logcat export.
    """
    bounded = raw[:LOG_LIMIT]
    lines = bounded.splitlines(keepends=True)
    prefix = re.compile(rb'^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s+(?:InputDispatcher|WindowManager)\s*:\s*')
    generic = re.compile(r'(?:Dropping|Rejecting|Ignoring) (?:touch |input )?event because (?:there is no focused window|there is no touched window|there is no touchable window|the touch is outside of all windows|dispatch is disabled|dispatch is frozen)\.?')
    window = re.compile(r"(?:Window )?(?:Window\{[0-9a-f]+ u0 " + COMPONENT + r"\}|'[0-9a-f]+ " + COMPONENT + r"') (?:is not ready for input|is not focused|is not visible|has no input channel|is unresponsive)\.?")
    retained = []
    for line in lines[:LOG_LINES]:
        m = prefix.match(line)
        if not m:
            continue
        try:
            message = line[m.end():].decode('utf-8', 'strict').rstrip('\r\n')
        except UnicodeDecodeError:
            continue
        if generic.fullmatch(message) or window.fullmatch(message):
            retained.append(line)
    return b''.join(retained), dict(originalBytes=len(raw), originalSha256=digest(raw),
        byteLimitReached=len(raw) > LOG_LIMIT, lineLimitReached=len(lines) > LOG_LINES,
        inspectedLines=min(len(lines), LOG_LINES), retainedLines=len(retained),
        excludedLines=min(len(lines), LOG_LINES)-len(retained),
        scope='Finite original InputDispatcher/WindowManager lines only; unknown or payload-bearing messages are not retained.')


class InputDeliveryDiagnostics:
    def __init__(self, *, adb, output, source, tree, nonce, identity, clock=time.monotonic_ns):
        if not re.fullmatch('[0-9a-f]{40}', source) or not re.fullmatch('[0-9a-f]{40}', tree) or not re.fullmatch('[0-9a-f]{32}', nonce):
            raise ValueError('Exact source/tree/nonce required')
        self.adb, self.output, self.source, self.nonce, self.identity, self.clock = adb, Path(output), source, nonce, identity, clock
        self.output.mkdir(parents=True, exist_ok=True)
        self.invoked = set()
        self.report = dict(schema=1, fixtureType='browser-input-delivery-diagnostic-v1', sourceCommit=source,
            sourceTree=tree, runNonce=nonce, sdkRunId=identity.get('sdkBuildIdentity', {}).get('runId'),
            sdkRunAttempt=identity.get('sdkBuildIdentity', {}).get('runAttempt'), taps=[], failures=[],
            diagnosticOnly=True, acceptanceResultOverridden=False, retryPerformed=False,
            deadlineExtended=False, sourceInput='tools/browser/input_delivery_diagnostics.py')

    def _write(self, name, raw):
        final = self.output / name
        fd, temporary = tempfile.mkstemp(prefix='.input-observation-', dir=self.output)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, final)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return dict(file=name, bytes=len(raw), sha256=digest(raw))

    def _persist(self):
        try:
            self._write('browser-input-delivery-diagnostics.json', (json.dumps(self.report, ensure_ascii=False, indent=2)+'\n').encode())
        except OSError as error:
            self.report['failures'].append(dict(operation='persist', errorClass=type(error).__name__))

    def _observe(self, parts, project):
        row = dict(command=list(parts), startedMonotonicNs=self.clock())
        try:
            value = self.adb(*parts, check=False, timeout=OBSERVATION_TIMEOUT)
            row.update(returnCode=value.returncode, stdout=project(value.stdout),
                       stderrBytes=len(value.stderr), stderrSha256=digest(value.stderr))
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            row.update(status='observation-failed', errorClass=type(error).__name__)
        finally:
            row['completedMonotonicNs'] = self.clock()
        return row

    def _states(self, current=None, *, identity):
        rows = []
        if current is not None:
            rows.append(dict(kind='already-validated-activity', observation=activity_projection(
                json.dumps(current).encode(), source=self.source, nonce=self.nonce, identity=identity)))
        for kind, parts in (
            ('window', ('shell', 'dumpsys', '-t', '1', 'window', 'windows')),
            ('input', ('shell', 'dumpsys', '-t', '1', 'input'))):
            rows.append(self._observe(parts, lambda raw, kind=kind: state_projection(raw, kind)))
        if current is None:
            rows.append(self._observe(('exec-out', 'content', 'read', '--uri', 'content://local.pocketchat.test.browser-evidence/result'),
                lambda raw: activity_projection(raw, source=self.source, nonce=self.nonce, identity=identity)))
        return rows

    def tap(self, stage, x, y, current, *, verified_identity):
        if stage not in STAGES or stage in self.invoked or any(type(v) is not int or not 0 <= v <= 10000000 for v in (x, y)):
            raise ValueError('One original tap per declared stage required')
        # The caller has already run the original verify_installed, including
        # its complete selected-source SDK logic, on this exact current report.
        # Freeze the full observed identity, including native descriptive fields
        # such as scope, for both projections. Every expected field must still
        # match; the optional observations cannot authorize a different build.
        if (type(verified_identity) is not dict or current.get('buildIdentity') != verified_identity
                or any(verified_identity.get(key) != value for key, value in self.identity.items())):
            raise ValueError('Already verified actual installed identity required')
        observed_identity = json.loads(json.dumps(verified_identity))
        self.invoked.add(stage)
        row = dict(stage=stage, command=['shell', 'input', 'tap', str(x), str(y)],
                   before=self._states(current, identity=observed_identity),
                   identityBinding='exact-already-verified-installed-identity',
                   commandInvocations=0, originalTimeoutSeconds=30)
        self.report['taps'].append(row); self._persist()
        value = None; original_error = None
        row['startedMonotonicNs'] = self.clock()
        try:
            row['commandInvocations'] = 1
            value = self.adb('shell', 'input', 'tap', str(x), str(y))
            row['returnCode'] = value.returncode
            return value
        except (OSError, subprocess.SubprocessError) as error:
            original_error = error
            row.update(errorClass=type(error).__name__, returnCode=getattr(error, 'returncode', None))
            raise
        finally:
            row['completedMonotonicNs'] = self.clock()
            try:
                for name in ('stdout', 'stderr'):
                    raw = (getattr(value, name, None) if value is not None else getattr(original_error, name, None)) or b''
                    if not isinstance(raw, bytes):
                        row[name] = dict(status='unexpected-nonbinary-output')
                        continue
                    item = self._write('browser-input-'+stage+'-'+name+'.txt', raw[:RAW_LIMIT])
                    item.update(originalBytes=len(raw), originalSha256=digest(raw),
                        complete=len(raw) <= RAW_LIMIT and not isinstance(original_error, subprocess.TimeoutExpired))
                    row[name] = item
                row['after'] = self._states(identity=observed_identity)
            except (OSError, subprocess.SubprocessError, ValueError) as diagnostic_error:
                row['collectionErrorClass'] = type(diagnostic_error).__name__
            self._persist()

    def failure(self):
        """Called only after the original workload has already failed."""
        def project(raw):
            selected, summary = selected_failure_log(raw)
            summary['retained'] = self._write('browser-input-failure-system-lines.txt', selected)
            return summary
        self.report['failureLog'] = self._observe(('logcat', '-d', '-b', 'main', '-b', 'system', '-v', 'threadtime', '-t', str(LOG_LINES), 'InputDispatcher:I', 'WindowManager:I', '*:S'), project)
        self._persist()

    def finish(self, workload_status):
        self.report['workloadStatus'] = workload_status if workload_status in ('passed', 'failed') else 'unknown'
        def system_value(raw):
            result = dict(originalBytes=len(raw), originalSha256=digest(raw))
            try:
                value = raw.decode('ascii', 'strict').strip()
                if len(raw) <= 512 and re.fullmatch(r'[A-Za-z0-9._:/;+ -]{1,400}', value):
                    return dict(result, status='observed', value=value)
            except UnicodeDecodeError:
                pass
            return dict(result, status='unsupported-value')
        self.report['systemIdentityAfterWorkload'] = [self._observe(('shell', 'getprop', key), system_value)
            for key in ('ro.build.version.sdk', 'ro.build.version.release', 'ro.build.fingerprint')]
        self.report['finalizedMonotonicNs'] = self.clock()
        self._persist()
