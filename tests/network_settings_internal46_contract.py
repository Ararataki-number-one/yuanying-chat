"""Exact reviewed46 stop-failure semantics; all prior safety checks invert whole-file.

No receipt or native report is rewritten. Unknown source revisions fail closed.
"""
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REVIEWED = {
    'tests/gecko/NetworkSettingsInternalApplication.java': ('b36d166f7e22496fc9341c4fcaa5ec7dd240a314b48790d3db7ad9f0d3d6b136', '22e8724a8a63feae80bb8291ea678b0673104e13e166a9735c8bf77c99128f31', (
        (b'a.applicationReceipt(name,output,wanted,"saved-unconfirmed","session",true);', b'a.applicationReceipt(name,output,wanted,stop?"failed":"saved-unconfirmed",stop?"core":"session",true);'),
        (b'    cases.put(J.obj("name",name,"expected",wanted,"result",output,"before",before,"after",after,"attemptCapturedBeforeInjection",true,', b'    if(stop){JSONObject result=output.getJSONObject("operationResult");a.check(name+": stopped core keeps rollback unconfirmed and retry available","unconfirmed".equals(result.optString("rollbackState"))&&Boolean.TRUE.equals(result.opt("retryAvailable")));}\n    cases.put(J.obj("name",name,"expected",wanted,"result",output,"before",before,"after",after,"attemptCapturedBeforeInjection",true,'),
        (b'boolean originalAttemptCurrent=a.ui(()->a.provider.applicationCurrent(attempt));', b'JSONObject injection=a.ui(()->J.obj("connection",a.session.connectionEpoch,"attemptCurrent",a.provider.applicationCurrent(attempt)));long connectionAtInjection=injection.getLong("connection");boolean originalAttemptCurrent=injection.getBoolean("attemptCurrent");'),
        (b'originalAttemptCurrent&&pendingUnchangedAtPoll&&a.ui(()->a.session.connectionEpoch==attempt.connection)', b'originalAttemptCurrent&&pendingUnchangedAtPoll&&connectionAtInjection==attempt.connection'),
        (b'"modelDesiredRevisionAtPoll",desiredAtPoll,"frozenConnection",attempt.connection,', b'"modelDesiredRevisionAtPoll",desiredAtPoll,"connectionAtInjection",connectionAtInjection,"frozenConnection",attempt.connection,'),
    )),
    'tests/gecko/run_network_settings_internal.py': ('07ff8880b514fa313c634ba21c4adc78938390758e84f7742de774fa722b24e6', 'efb4846cd41f41d8f1ea737c0695143981fe7d7806e72fe759a660875ae9d4a3', (
        (b'ROOT = pathlib.Path(__file__).resolve().parents[2]\n', b"ROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / 'tests'))\nfrom network_settings_internal46_contract import require_runner_source\nrequire_runner_source(pathlib.Path(__file__).read_bytes())\n"),
        (b"    names.add(CASE_NAMES[1] + ': actual stopped service invalidates the captured core receipt')\n", b"    names.add(CASE_NAMES[1] + ': actual stopped service invalidates the captured core receipt')\n    names.add(CASE_NAMES[1] + ': stopped core keeps rollback unconfirmed and retry available')\n"),
        (b"    assert actual['saveState'] == 'saved' and actual['scope'] == 'session'\n", b"    assert actual['saveState'] == 'saved' and actual['scope'] == ('core' if state == 'failed' else 'session')\n"),
        (b"    assert actual['appliedRevision'] == (wanted['savedRevision'] if state == 'applied' else 0)\n", b"    assert actual['appliedRevision'] == (wanted['savedRevision'] if state == 'applied' else 0)\n    if state == 'failed':\n        assert case['name'] == CASE_NAMES[1]\n        assert all(type(actual[field]) is int for field in ['generation', 'savedRevision', 'appliedRevision'])\n        assert actual['rollbackState'] == 'unconfirmed' and actual['retryAvailable'] is True\n"),
        (b"        verify_receipt(row, 'applied' if row in [bootstrap, cases[0]] else 'saved-unconfirmed')\n", b"        verify_receipt(row, 'applied' if row in [bootstrap, cases[0]] else 'failed' if row is cases[1] else 'saved-unconfirmed')\n"),
        (b"        assert case['observedConnection'] == case['frozenConnection']\n", b"        assert (type(case['connectionAtInjection']) is int and type(case['observedConnection']) is int\n                and case['connectionAtInjection'] == case['frozenConnection']\n                and case['observedConnection'] == case['frozenConnection'] + (1 if case is cases[1] else 0))\n"),
    )),
    'tests/gecko_settings_internal_gate_test.py': ('8fa7984ec87dcaf08c017397f21caaa0b56af1a4cc36aee4ce6f4e19d7ef23ed', '124a15774492a9cc3209e0d04aace5f074bb2518526674922c498aa195745df8', (
        (b"    return {'name': name, 'expected': wanted, 'result': {'done': True, 'ok': applied, 'operationResult': actual}}\n", b"    if name == m.CASE_NAMES[1] and not applied:\n        actual.update(applicationState='failed', scope='core', rollbackState='unconfirmed', retryAvailable=True)\n    return {'name': name, 'expected': wanted, 'result': {'done': True, 'ok': applied, 'operationResult': actual}}\n"),
        (b'modelDesiredRevisionAtPoll=4, frozenConnection=4, observedConnection=4)', b'modelDesiredRevisionAtPoll=4, connectionAtInjection=5, frozenConnection=5, observedConnection=6)'),
        (b'modelDesiredRevisionAtPoll=6, frozenConnection=6, observedConnection=6)', b'modelDesiredRevisionAtPoll=6, connectionAtInjection=6, frozenConnection=6, observedConnection=6)'),
    )),
}

def previous_source_bytes(raw, path):
    if path not in REVIEWED:
        raise ValueError('Unknown internal46 source path')
    previous, reviewed, deltas = REVIEWED[path]
    if hashlib.sha256(raw).hexdigest() != reviewed:
        raise ValueError('Internal46 source differs from reviewed whole bytes')
    for old, new in reversed(deltas):
        if raw.count(new) != 1:
            raise ValueError('Missing or repeated internal46 semantic delta')
        raw = raw.replace(new, old, 1)
    if hashlib.sha256(raw).hexdigest() != previous:
        raise ValueError('Internal46 inverse does not preserve original whole source')
    return raw


def require_runner_source(raw):
    path = 'tests/gecko/run_network_settings_internal.py'
    original = previous_source_bytes(raw, path)
    if hashlib.sha256(original).hexdigest() != '07ff8880b514fa313c634ba21c4adc78938390758e84f7742de774fa722b24e6':
        raise ValueError('Original internal verifier changed')
    return original
