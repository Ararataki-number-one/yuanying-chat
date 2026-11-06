"""Bind this fixture's four admitted direct jobs to its unfiltered callbacks.

This checks callback accounting only. The caller retains the original operation,
model, route, APK and Android evidence checks; internal recovery cannot replace
the result of an earlier direct operation.
"""
import re
import uuid


_CANONICAL_FIELDS = {'id', 'ok', 'internal', 'operationResult'}
_EVENT_FIELDS = _CANONICAL_FIELDS | {'sequence', 'targetDirect'}
_RECEIPT_FIELDS = {
    'environmentId', 'generation', 'candidateId', 'savedRevision',
    'appliedRevision', 'saveState', 'applicationState', 'scope', 'message',
}
_OPTIONAL_RECEIPT_FIELDS = {
    'networkAppliedRevision', 'browserAppliedRevision', 'coreGeneration',
    'verifiedAt', 'rollbackState', 'retryAvailable', 'recoveryRequired',
}


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _same_json(left, right):
    """JSON equality that never equates a Boolean with a numeric revision."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (left.keys() == right.keys()
                and all(_same_json(value, right[key]) for key, value in left.items()))
    if isinstance(left, list):
        return len(left) == len(right) and all(map(lambda pair: _same_json(*pair), zip(left, right)))
    return left == right


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def _internal_receipt(receipt):
    """Check current production receipt shape, not whether a route was applied."""
    _require(type(receipt) is dict, 'Internal outcome must be a receipt object')
    _require(_RECEIPT_FIELDS <= receipt.keys(), 'Internal receipt fields missing')
    _require(receipt.keys() <= _RECEIPT_FIELDS | _OPTIONAL_RECEIPT_FIELDS,
             'Unknown internal receipt fields')
    environment = receipt['environmentId']
    _require(type(environment) is str, 'Internal environment ID must be a string')
    try:
        normalized = str(uuid.UUID(environment))
    except (ValueError, AttributeError):
        raise AssertionError('Internal environment ID must be a canonical UUID') from None
    _require(normalized == environment, 'Internal environment ID must be a canonical UUID')
    for field in ('generation', 'savedRevision', 'appliedRevision'):
        _require(_nonnegative_integer(receipt[field]), 'Invalid internal ' + field)
    for field in ('networkAppliedRevision', 'browserAppliedRevision', 'verifiedAt'):
        if field in receipt:
            _require(_nonnegative_integer(receipt[field]), 'Invalid internal ' + field)
    for field in ('retryAvailable', 'recoveryRequired'):
        if field in receipt:
            _require(type(receipt[field]) is bool, 'Invalid internal ' + field)
    _require(receipt['saveState'] in ('saved', 'superseded', 'uncertain', 'failed'),
             'Invalid internal save state')
    _require(receipt['applicationState'] in (
        'applied', 'failed', 'cancelled', 'pending', 'saved-unconfirmed',
        'superseded', 'unconfirmed'), 'Invalid internal application state')
    _require(receipt['scope'] in ('session', 'core', 'next-session'),
             'Invalid internal receipt scope')
    _require(type(receipt['message']) is str, 'Internal receipt message must be a string')
    candidate = receipt['candidateId']
    _require(type(candidate) is str and re.fullmatch('[a-z0-9:-]{0,96}', candidate) is not None,
             'Invalid internal candidate ID')
    _require(bool(candidate) or receipt['savedRevision'] == 0
             and receipt['saveState'] in ('superseded', 'uncertain', 'failed'),
             'A saved internal candidate cannot be empty')
    if 'coreGeneration' in receipt:
        _require(type(receipt['coreGeneration']) is str and bool(receipt['coreGeneration']),
                 'Invalid internal core generation')
    if 'rollbackState' in receipt:
        _require(receipt['rollbackState'] in ('verified', 'unconfirmed', 'unchanged', 'stopped'),
                 'Invalid internal rollback state')


def verify_callback_cohort(report):
    """Require exactly one raw callback and immutable result per admitted job."""
    _require(type(report) is dict, 'Callback report must be an object')
    admitted = report.get('applicationDirectJobs')
    _require(type(admitted) is list and len(admitted) == 4,
             'Exactly four admitted direct jobs are required')
    _require(all(type(job) is str and bool(job) and not job.startswith('internal:')
                 for job in admitted), 'Invalid admitted direct job ID')
    _require(len(set(admitted)) == 4, 'Admitted direct job IDs must be unique')
    targets = set(admitted)
    events = report.get('applicationCallbackEvents')
    _require(type(events) is list, 'Unfiltered callback event array required')
    count = report.get('applicationCallbackCount')
    _require(type(count) is int and count == len(events),
             'Raw callback count differs from independently emitted high-water mark')
    observed = {}
    for sequence, event in enumerate(events):
        _require(type(event) is dict and event.keys() == _EVENT_FIELDS,
                 'Callback event fields differ')
        _require(type(event['sequence']) is int and event['sequence'] == sequence,
                 'Callback events must retain consecutive raw sequence numbers')
        job = event['id']
        _require(type(job) is str and bool(job), 'Invalid callback job ID')
        internal = job.startswith('internal:')
        _require(type(event['internal']) is bool and event['internal'] is internal,
                 'Callback internal marker differs from its job ID')
        _require(type(event['ok']) is bool, 'Callback ok must be a Boolean')
        target = job in targets and not internal
        _require(type(event['targetDirect']) is bool and event['targetDirect'] is target,
                 'Callback target marker differs from direct admission')
        _require(internal or target, 'Unregistered direct callback job')
        outcome = event['operationResult']
        _require(outcome is None or type(outcome) is dict,
                 'Callback outcome must be an object or null')
        if internal:
            if outcome is not None:
                _internal_receipt(outcome)
            continue
        _require(outcome is not None, 'Direct callback must carry its operation result')
        _require(job not in observed, 'Repeated direct callback must not be deduplicated')
        observed[job] = {key: event[key] for key in _CANONICAL_FIELDS}
    _require(observed.keys() == targets, 'A registered direct callback is missing')
    canonical = report.get('applicationResults')
    _require(type(canonical) is list and len(canonical) == 4,
             'Exactly four canonical direct results are required')
    seen = set()
    for row in canonical:
        _require(type(row) is dict and row.keys() == _CANONICAL_FIELDS,
                 'Canonical direct result fields differ')
        job = row['id']
        _require(type(job) is str and job in targets and job not in seen,
                 'Canonical direct jobs must match admission exactly once')
        _require(_same_json(row, observed[job]),
                 'Canonical direct result differs from its original callback')
        seen.add(job)
    _require(seen == targets, 'Canonical direct result missing')
