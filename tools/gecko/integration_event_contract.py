"""Lossless, invocation-bound synthetic event transport; never an app oracle.

The small log receipt is a pointer, not the event. Only the complete UTF-8
provider payload, checked against the installed APK identity and its digest,
may be handed to the existing device assertions.
"""
import copy
import hashlib
import json
import re
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
