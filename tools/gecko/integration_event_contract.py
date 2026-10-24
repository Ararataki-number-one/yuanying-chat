"""Lossless, invocation-bound synthetic event transport; never an app oracle.

The small log receipt is a pointer, not the event. Only the complete UTF-8
provider payload, checked against the installed APK identity and its digest,
may be handed to the existing device assertions.
"""
import copy
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

# Shared SDK expectations come from selected source, never report-provided pins.
import importlib.util as _sdk_importlib
_sdk_spec=_sdk_importlib.spec_from_file_location('selected_sdk_identity_contract',Path(__file__).with_name('sdk_identity_contract.py'))
_sdk=_sdk_importlib.module_from_spec(_sdk_spec);_sdk_spec.loader.exec_module(_sdk)

if __package__:
    from .profile_invocation_contract import PACKAGE, SDK_COORDINATE, verify_installed
else:
    from profile_invocation_contract import PACKAGE, SDK_COORDINATE, verify_installed

TAG = 'PocketGeckoIntegration'
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024


def _require(condition, message):
    if not condition:
        raise ValueError('Synthetic event transfer: ' + message)


def _integer(value, minimum=1):
    return type(value) is int and minimum <= value <= 2**63 - 1


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON field: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Synthetic event transfer: non-finite JSON constant: ' + value)


def _json(text):
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Synthetic event transfer: malformed or truncated JSON') from error


def parse_receipt_line(line):
    """Ignore other log tags; reject malformed lines of this receipt-only tag.

    Bare JSON is also accepted for focused controls. There is deliberately no
    fallback to the old large log event and no fragment reassembly.
    """
    _require(isinstance(line, str), 'log line must be text')
    tagged = TAG in line
    bare = line.lstrip().startswith('{')
    if not tagged and not bare:
        return None
    begin = line.find('{')
    _require(begin >= 0, 'tagged receipt has no complete JSON object')
    receipt = _json(line[begin:])
    _require(isinstance(receipt, dict) and receipt.get('kind') in ('eventReceipt', 'eventTransportError'),
             'tagged event is not a transport receipt')
    return receipt


def _identity(identity):
    _require(isinstance(identity, dict), 'installed build identity missing')
    _require(type(identity.get('schema')) is int and identity['schema'] == 1,
             'installed build identity schema')
    _require(identity.get('package') == PACKAGE and identity.get('dirtySource') is False,
             'clean synthetic package identity')
    for key in ('sourceCommit', 'sourceTree'):
        _require(_hex(identity.get(key), 40), 'installed build identity ' + key)
    for key in ('apkSha256', 'buildStampSha256'):
        _require(_hex(identity.get(key), 64), 'installed build identity ' + key)
    for key in ('versionCode', 'apkBytes'):
        _require(_integer(identity.get(key)), 'installed build identity ' + key)
    _require(isinstance(identity.get('version'), str) and bool(identity['version']),
             'installed build version')
    _sdk.verify_sdk_identity(identity)


def validate_receipt(receipt, *, identity, nonce, slot, action, command=None):
    """Reject foreign receipts even when a caller elects to filter them first."""
    _identity(identity)
    _require(_hex(nonce, 32), 'expected invocation nonce')
    _require(type(slot) is int and (slot in (0, 1) or slot == 7 and action == 'downloadResume'), 'expected process slot')
    _require(isinstance(action, str) and bool(action), 'expected fixture action')
    if command is not None:
        _require(_integer(command), 'expected native command')
    _require(isinstance(receipt, dict) and receipt.get('kind') == 'eventReceipt', 'receipt kind')
    _require(type(receipt.get('schema')) is int and receipt['schema'] == 1, 'receipt schema')
    _require(receipt.get('runNonce') == nonce and receipt.get('fixtureAction') == action,
             'receipt belongs to another invocation or action')
    _require(type(receipt.get('processSlot')) is int and receipt['processSlot'] == slot
             and receipt.get('nativeContext') == 'environment-' + str(slot + 1),
             'receipt belongs to another environment')
    for key in ('command', 'sequence'):
        _require(_integer(receipt.get(key)), 'receipt ' + key)
    _require(command is None or receipt['command'] == command, 'receipt belongs to another native command')
    _require(isinstance(receipt.get('eventKind'), str) and bool(receipt['eventKind']), 'receipt event kind')
    if slot == 7:
        _require(receipt['eventKind'] == 'downloadResume', 'isolated file fixture event kind')
    _require(_integer(receipt.get('payloadBytes')) and receipt['payloadBytes'] <= MAX_PAYLOAD_BYTES,
             'receipt payload size')
    _require(_hex(receipt.get('payloadSha256'), 64), 'receipt payload digest')
    return receipt


def event_uri(receipt):
    """Only use a validated receipt to construct this shell-only provider URI."""
    _require(isinstance(receipt, dict) and type(receipt.get('processSlot')) is int
             and (receipt['processSlot'] in (0, 1) or receipt['processSlot'] == 7
                  and receipt.get('fixtureAction') == receipt.get('eventKind') == 'downloadResume') and _hex(receipt.get('runNonce'), 32)
             and _integer(receipt.get('sequence')), 'invalid evidence URI identity')
    return ('content://' + PACKAGE + '.evidence/gecko-events/' + str(receipt['processSlot'])
            + '/' + receipt['runNonce'] + '/' + str(receipt['sequence']))


def decode_event(receipt, raw, *, identity, nonce, slot, action, command=None):
    """Return the complete original event, preserving every result/failure field."""
    validate_receipt(receipt, identity=identity, nonce=nonce, slot=slot, action=action, command=command)
    _require(type(raw) is bytes, 'provider response must be raw bytes')
    _require(len(raw) == receipt['payloadBytes'] and len(raw) <= MAX_PAYLOAD_BYTES,
             'provider payload length differs from receipt')
    _require(hashlib.sha256(raw).hexdigest() == receipt['payloadSha256'],
             'provider payload digest differs from receipt')
    try:
        envelope = _json(raw.decode('utf-8', errors='strict'))
    except UnicodeError as error:
        raise ValueError('Synthetic event transfer: provider payload is not UTF-8') from error
    _require(isinstance(envelope, dict), 'provider envelope is not an object')
    _require(type(envelope.get('schema')) is int and envelope['schema'] == 1, 'provider envelope schema')
    _identity(envelope.get('buildIdentity'))
    verify_installed(envelope['buildIdentity'], identity)
    _require(envelope.get('sourceCommit') == identity['sourceCommit'], 'provider envelope source commit')
    for key in ('runNonce', 'fixtureAction', 'nativeContext'):
        _require(envelope.get(key) == receipt[key], 'provider envelope ' + key)
    for key in ('command', 'sequence', 'processSlot'):
        _require(type(envelope.get(key)) is int and envelope[key] == receipt[key], 'provider envelope ' + key)
    event = envelope.get('event')
    _require(isinstance(event, dict) and isinstance(event.get('result'), dict), 'complete original event/result required')
    _require(event.get('kind') == receipt['eventKind'], 'provider event kind differs from receipt')
    _require(type(event.get('processSlot')) is int and event['processSlot'] == slot
             and event.get('nativeContext') == receipt['nativeContext'], 'nested event environment differs')
    return event


class EventTransfer:
    """Fetch each owned event once; duplicates cannot swap an accepted payload.

    The nonce binds the first native command of an invocation. Subsequent
    receipts must retain that command and arrive without a sequence gap.
    Repeated logcat snapshots may repeat any already accepted exact receipt.
    The callback takes a provider URI and returns raw bytes, never decoded text.
    """
    def __init__(self, *, identity, nonce, slot, action, fetch, command=None):
        self.identity = copy.deepcopy(identity)
        self.nonce, self.slot, self.action = nonce, slot, action
        self.command, self.fetch = command, fetch
        self._cache = {}
        self.records = []

    def read(self, receipt):
        validate_receipt(receipt, identity=self.identity, nonce=self.nonce, slot=self.slot,
                         action=self.action, command=self.command)
        sequence = receipt['sequence']
        if sequence in self._cache:
            original, event = self._cache[sequence]
            _require(receipt == original, 'conflicting duplicate sequence receipt')
            return copy.deepcopy(event)
        _require(sequence == len(self._cache) + 1, 'missing or out-of-order event sequence')
        raw = self.fetch(event_uri(receipt))
        event = decode_event(receipt, raw, identity=self.identity,
                             nonce=self.nonce, slot=self.slot, action=self.action, command=self.command)
        if self.command is None:
            self.command = receipt['command']
        self._cache[sequence] = (copy.deepcopy(receipt), copy.deepcopy(event))
        self.records.append(dict(receipt=copy.deepcopy(receipt), rawUtf8=raw.decode('utf-8', errors='strict')))
        return copy.deepcopy(event)


SEQUENCE_GAP_ERROR = 'Synthetic event transfer: missing or out-of-order event sequence'


def sequence_failure_plan(reader, receipt):
    """Pure, owned diagnostic paths; never invent a missing receipt or event."""
    _require(type(reader) is EventTransfer, 'diagnostic reader type')
    validate_receipt(receipt, identity=reader.identity, nonce=reader.nonce, slot=reader.slot,
                     action=reader.action, command=reader.command)
    expected = len(reader._cache) + 1
    _require(set(reader._cache) == set(range(1, expected)) and len(reader.records) == expected - 1,
             'diagnostic reader progress')
    observed = receipt['sequence']
    _require(1 <= expected <= 4096 and 1 <= observed <= 4096
             and observed != expected and observed not in reader._cache,
             'diagnostic sequence gap')
    # A path descriptor is not an authentic receipt for the missing sequence.
    # event_uri only formats the already validated owner and bounded sequence.
    paths = []
    for role, sequence in (('expected', expected), ('current', observed)):
        path_owner = dict(receipt, sequence=sequence)
        paths.append(dict(role=role, sequence=sequence, uri=event_uri(path_owner),
                          receiptObserved=role == 'current'))
    return dict(schema=1, diagnosticOnly=True, acceptance=False,
                sourceCommit=reader.identity['sourceCommit'], buildIdentity=copy.deepcopy(reader.identity),
                runNonce=reader.nonce, processSlot=reader.slot, fixtureAction=reader.action,
                command=receipt['command'], previouslyAcceptedCommand=reader.command,
                expectedSequence=expected, observedReceipt=copy.deepcopy(receipt), paths=paths,
                perReadTimeoutSeconds=5, maximumProviderReads=2,
                scope='Post-failure existing-file observations only; no missing receipt, accepted event, retry or app assertion')


def _capture_sequence_failure(reader, receipt, filtered_log, out, adb, serial):
    plan = sequence_failure_plan(reader, receipt)
    _require(type(filtered_log) is str, 'diagnostic host-observed snapshot type')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / 'device-event-sequence-failure.json'
    names = ['device-event-sequence-filtered.log'] + [
        'device-event-sequence-' + role + '.' + stream + '.log'
        for role in ('expected', 'current') for stream in ('stdout', 'stderr')]
    _require(not summary_path.exists() and not any((out / name).exists() for name in names),
             'diagnostic output already exists')
    plan.update(originalError=SEQUENCE_GAP_ERROR, acceptedEventCount=len(reader.records),
                filteredSnapshotEncoding='host-observed UTF-8 (original adb text output)',
                reads=[], diagnosticErrors=[])
    def retain(name, data):
        _require(type(data) is bytes, 'diagnostic stream must be original bytes')
        with (out / name).open('xb') as target:
            target.write(data)
        return dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    def summary():
        summary_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    plan['filteredSnapshot'] = retain(names[0], filtered_log.encode('utf-8'))
    summary()
    for path in plan['paths']:
        row = dict(path, diagnosticOnly=True, acceptance=False, timeoutSeconds=5,
                   hostStartedMonotonicNs=time.monotonic_ns())
        stdout = stderr = b''
        command = [adb, '-s', serial, 'exec-out', 'content', 'read', '--uri', path['uri']]
        row['commandArguments'] = command
        try:
            result = subprocess.run(command, capture_output=True, timeout=5, check=False)
            row.update(status='completed', returnCode=result.returncode)
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            row.update(status='timeout', returnCode=None, exceptionType=type(error).__name__,
                       timeoutStdoutPresent=error.stdout is not None,
                       timeoutStderrPresent=error.stderr is not None)
            stdout = error.stdout if error.stdout is not None else b''
            stderr = error.stderr if error.stderr is not None else b''
        except Exception as error:
            row.update(status='capture-error', returnCode=None, exceptionType=type(error).__name__,
                       error=str(error))
        row['hostFinishedMonotonicNs'] = time.monotonic_ns()
        plan['reads'].append(row)
        try:
            for stream, data in (('stdout', stdout), ('stderr', stderr)):
                row[stream] = retain('device-event-sequence-' + path['role'] + '.' + stream + '.log', data)
            if path['receiptObserved'] and row['status'] == 'completed' and row['returnCode'] == 0:
                # Still diagnostic-only; this does not call read/decode, mutate
                # the collector, or feed the original application's assertions.
                row['observedReceiptBytesMatch'] = (len(stdout) == receipt['payloadBytes']
                    and hashlib.sha256(stdout).hexdigest() == receipt['payloadSha256'])
        except Exception as error:
            plan['diagnosticErrors'].append(dict(role=path['role'], error=type(error).__name__ + ': ' + str(error)))
        summary()


def read_with_sequence_failure_diagnostics(reader, receipt, *, filtered_log, out, adb, serial):
    """One original read; after its exact gap error collect evidence, then re-raise it."""
    try:
        return reader.read(receipt)
    except ValueError as original_error:
        if str(original_error) == SEQUENCE_GAP_ERROR:
            try:
                _capture_sequence_failure(reader, receipt, filtered_log, out, adb, serial)
            except Exception:
                # Diagnostic validation/IO cannot replace, hide, or cure the
                # original failure. No second read or business event is allowed.
                pass
        raise
