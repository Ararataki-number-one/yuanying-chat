"""Fixture-only action dispatch without serial passive evidence read latency.

Every log receipt is fenced before input. Hardware requests additionally need
their complete original provider bytes and SDK/APK identity before dispatch.
All payloads still pass the unchanged ordered EventTransfer at completion.
"""
import copy
import math
import time

from integration_event_contract import EventTransfer, decode_event, event_uri, validate_receipt
from check_caret_compat_evidence import IDS, expected_layout, finite_number, verify_native_geometry, verify_viewport

RECEIPT_FIELDS = {'kind', 'schema', 'runNonce', 'fixtureAction', 'command', 'sequence',
                  'nativeContext', 'processSlot', 'eventKind', 'payloadBytes', 'payloadSha256'}
EVENT_KINDS = {'check', 'scenario', 'api', 'clipboard', 'checkpoint', 'trustedEvents',
               'report', 'stepNeeded', 'failureSnapshot'}
ACTION_LAYOUT = expected_layout()[2]


def require(condition, message):
    if not condition:
        raise ValueError('Caret dispatch: ' + message)


class CaretDispatch:
    def __init__(self, *, identity, nonce, slot, action, command, fetch, dispatch):
        self.identity = copy.deepcopy(identity)
        self.nonce, self.slot, self.action, self.command = nonce, slot, action, command
        self.fetch, self.dispatch = fetch, dispatch
        self.receipts, self.actions, self._raw_cache = [], {}, {}
        self._attempted, self._failure = set(), None
        self.terminal = False
        self.transfer = EventTransfer(identity=self.identity, nonce=nonce, slot=slot,
                                      action=action, command=command, fetch=self._fetch_cached)

    def _fetch_cached(self, uri):
        sequence = int(uri.rsplit('/', 1)[1])
        if sequence not in self._raw_cache:
            raw = self.fetch(uri)
            require(type(raw) is bytes, 'complete raw provider bytes required')
            self._raw_cache[sequence] = raw  # bytes are immutable; never cache mutated decoded actions.
        return self._raw_cache[sequence]

    def ingest(self, receipts):
        """Validate the complete batch first, then execute each owned action once.

        A terminal marker anywhere in this batch suppresses all pending input.
        Its payload and every deferred payload are verified during drain().
        """
        require(self._failure is None, 'dispatch already failed; input cannot be retried')
        try:
            self._ingest(receipts)
        except Exception as error:
            self._failure = error
            raise

    def _ingest(self, receipts):
        require(isinstance(receipts, list), 'complete receipt batch required')
        ledger, terminal = copy.deepcopy(self.receipts), self.terminal
        for receipt in receipts:
            require(isinstance(receipt, dict) and set(receipt) == RECEIPT_FIELDS,
                    'exact native receipt metadata required')
            validate_receipt(receipt, identity=self.identity, nonce=self.nonce, slot=self.slot,
                             action=self.action, command=self.command)
            require(receipt['eventKind'] in EVENT_KINDS, 'unknown fixture event kind')
            sequence = receipt['sequence']
            require(sequence <= 4096, 'receipt count exceeds native bound')
            if sequence <= len(ledger):
                require(receipt == ledger[sequence - 1], 'conflicting duplicate receipt')
                continue
            require(sequence == len(ledger) + 1, 'missing or out-of-order receipt')
            require(not terminal, 'event follows terminal report')
            ledger.append(copy.deepcopy(receipt))
            terminal = receipt['eventKind'] == 'report'
        self.receipts, self.terminal = ledger, terminal
        if terminal:
            return
        prepared = []
        for receipt in ledger:
            sequence = receipt['sequence']
            if receipt['eventKind'] != 'stepNeeded' or sequence in self._attempted:
                continue
            raw = self._fetch_cached(event_uri(receipt))
            event = decode_event(receipt, raw, identity=self.identity, nonce=self.nonce,
                                 slot=self.slot, action=self.action, command=self.command)
            value = event['result']
            self._validate_action(value, len(self._attempted) + len(prepared))
            prepared.append((sequence, value))
        # Fully decode and authorize every pending action before the first input
        # in this batch; later corruption cannot leave earlier input executed.
        for sequence, value in prepared:
            action = copy.deepcopy(value)
            action['executions'] = []
            self.actions[value['id']] = action
            self._attempted.add(sequence)  # Before dispatch: a partial command failure must never replay.
            executions = self.dispatch(action)
            require(isinstance(executions, list) and len(executions) == len(value['commands']),
                    'actual command execution records required')
            action['executions'] = copy.deepcopy(executions)
            require({key: item for key, item in action.items() if key != 'executions'} == value,
                    'dispatch mutated original action')

    def _validate_action(self, value, index):
        require(index < len(ACTION_LAYOUT), 'extra original Android action')
        expected = ACTION_LAYOUT[index]
        require(set(value) == {'id', 'scenario', 'origin', 'commands'}
                and value.get('id') == expected['id'] and value.get('id') not in self.actions
                and value.get('scenario') == expected['scenario']
                and value.get('origin') == 'adb-input-keyboard-and-touch'
                and isinstance(value.get('commands'), list)
                and len(value['commands']) == len(expected['commands']), 'source-expected Android action required')
        for command, wanted in zip(value['commands'], expected['commands']):
            require(isinstance(command, dict) and command.get('op') == wanted[0], 'original Android command order')
            if wanted[0] == 'tap':
                require(set(command) == {'op', 'x', 'y', 'expectedCaret', 'clientPoint', 'nativeGeometry', 'viewport'}
                        and type(command.get('x')) is int and type(command.get('y')) is int
                        and command['x'] >= 0 and command['y'] >= 0
                        and type(command.get('expectedCaret')) is int and command['expectedCaret'] == wanted[1],
                        'original touch target required')
                geometry, point = command['nativeGeometry'], command['clientPoint']
                require(isinstance(geometry, dict) and finite_number(geometry.get('timeOrigin'))
                        and geometry['timeOrigin'] > 0 and isinstance(point, dict)
                        and finite_number(point.get('x')) and finite_number(point.get('y')), 'owned native touch pose required')
                number = IDS.index(expected['scenario'])
                sdk = self.identity['sdkBuildIdentity']
                owner = dict(sourceCommit=self.identity['sourceCommit'], runId=sdk['runId'], runAttempt=sdk['runAttempt'],
                             runNonce=self.nonce, case=number, documentUrl='http://127.0.0.1:8771/caret?case=' + str(number),
                             timeOrigin=geometry['timeOrigin'])
                matrix, layout = verify_native_geometry(geometry, owner)
                verify_viewport(command['viewport'])
                mapped_x = geometry['originX'] + (matrix[0] * point['x'] + matrix[2]) * layout
                mapped_y = geometry['originY'] + (matrix[4] * point['y'] + matrix[5]) * layout
                require(finite_number(mapped_x) and finite_number(mapped_y)
                        and abs(command['x'] - mapped_x) <= .51 and abs(command['y'] - mapped_y) <= .51,
                        'original touch differs from actual matrix/origin')
            else:
                field = {'text': 'text', 'key': 'code', 'combination': 'codes'}[wanted[0]]
                require(set(command) == {'op', field} and type(command.get(field)) is type(wanted[1])
                        and command[field] == wanted[1], 'original Android command changed')

    def drain(self, *, timeout=600, clock=time.monotonic):
        """Verify every original event in sequence; never dispatch during drain."""
        require(self._failure is None, 'failed dispatch/collection cannot become acceptance')
        try:
            require(self.terminal, 'terminal receipt required before complete evidence drain')
            require(type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0,
                    'finite positive read-only evidence budget required')
            deadline = clock() + timeout
            for receipt in self.receipts:
                require(clock() <= deadline, 'read-only complete evidence deadline exceeded')
                self.transfer.read(receipt)
                require(clock() <= deadline, 'read-only complete evidence deadline exceeded')
        except Exception as error:
            self._failure = error
            raise
        return self.transfer
