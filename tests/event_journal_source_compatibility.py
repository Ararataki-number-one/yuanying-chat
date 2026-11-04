"""Exact source-input inverse for the reviewed native receipt journal addition.

Only retained historical source assertions call this port. Device and behavior
hosts continue to execute the complete current runner and strict EventTransfer.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELTA_PATH = ROOT / 'tests/fixtures/event-journal-source-deltas.json'
DELTA_SHA256 = '13620b58a536ebe4e0b822cd5b6ea11b9656cfdb83f2e18ee8c90ee0fa3c4254'
BASE_COMMIT = '03d0c4ace70942a3f6899daffac086cc6682885e'
PATHS = frozenset((
    'tests/gecko/run_device.py',
    'tests/experience46_source_compatibility.py',
    'tests/profile_experience46_source_compatibility_test.py',
    'tests/gecko_device_readiness_test.py',
    'tests/startup46_source_compatibility.py',
    'tests/profile_startup_whole_source46_test.py',
    'tests/profile_startup_f14_compatibility46_test.py',
))


def manifest():
    raw = DELTA_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DELTA_SHA256:
        raise ValueError('Receipt journal inverse fixture changed')
    value = json.loads(raw)
    if (value.get('schema') != 1 or value.get('baseCommit') != BASE_COMMIT
            or set(value.get('files', {})) != PATHS):
        raise ValueError('Receipt journal inverse source identity changed')
    return value


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in PATHS:
        raise ValueError('Receipt journal inverse requires exact bytes and owned relative path')
    row = manifest()['files'][relative]
    digest = hashlib.sha256(raw).hexdigest()
    if digest == row['previousSha256'] and len(raw) == row['previousBytes']:
        return raw
    if digest != row['reviewedSha256'] or len(raw) != row['reviewedBytes']:
        raise ValueError('Receipt journal inverse rejects unknown whole source')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if (not current or not previous or raw.count(current) != 1
                or hashlib.sha256(current).hexdigest() != delta['currentSha256']
                or hashlib.sha256(previous).hexdigest() != delta['previousSha256']):
            raise ValueError('Receipt journal inverse requires each exact contextual delta once')
        raw = raw.replace(current, previous, 1)
    if hashlib.sha256(raw).hexdigest() != row['previousSha256'] or len(raw) != row['previousBytes']:
        raise ValueError('Receipt journal inverse did not restore the complete previous source')
    return raw


def original_runner_tree(node):
    """Undo only the reviewed discovery delta for the old startup AST guard.

    The caller has already removed its separately reviewed optional trace.
    Formatting remains allowed; a complete unknown run AST always fails.
    """
    if type(node) is not ast.FunctionDef or node.name != 'run':
        raise ValueError('Receipt journal AST inverse requires the complete run function')
    row = manifest()['runTree']
    dump = lambda value: ast.dump(value, include_attributes=False)
    digest = hashlib.sha256(dump(node).encode()).hexdigest()
    if digest == row['previousSha256']:
        return copy.deepcopy(node)
    if digest != row['reviewedSha256']:
        raise ValueError('Receipt journal AST inverse rejects unknown complete run AST')
    restored = copy.deepcopy(node)
    statement = lambda value: ast.parse(value).body[0]
    transfer = statement('transfer=EventTransfer(identity=identity,nonce=nonce,slot=context-1,action=action,fetch=fetch_event)')
    start = [index for index, value in enumerate(restored.body) if dump(value) == dump(transfer)]
    discovery = statement('discovery=ReceiptJournalDiscovery(transfer)')
    metadata = statement("transfer_record['discovery']='native-committed-marker-journal'")
    if (len(start) != 1 or len(restored.body) <= start[0] + 2
            or dump(restored.body[start[0] + 1]) != dump(discovery)
            or dump(restored.body[start[0] + 2]) != dump(metadata)):
        raise ValueError('Receipt journal AST inverse requires the exact discovery and metadata positions')
    del restored.body[start[0] + 1:start[0] + 3]
    condition = statement('while time.monotonic()<deadline:\n pass').test
    loops = [value for value in restored.body if isinstance(value, ast.While) and dump(value.test) == dump(condition)]
    if len(loops) != 1:
        raise ValueError('Receipt journal AST inverse requires the original deadline loop')
    loop = loops[0]
    diagnostic = statement('for line in output.splitlines():\n pass')
    native = statement("for receipt in discovery.snapshot(adb_bytes('exec-out','content','read','--uri',discovery.uri())):\n pass")
    if (len(loop.body) != 4 or type(loop.body[1]) is not ast.For
            or type(loop.body[2]) is not ast.For
            or dump(loop.body[1].iter) != dump(diagnostic.iter)
            or dump(loop.body[1].target) != dump(diagnostic.target)
            or dump(loop.body[2].iter) != dump(native.iter)
            or dump(loop.body[2].target) != dump(native.target)):
        raise ValueError('Receipt journal AST inverse requires the exact adjacent native discovery loop')
    loop.body[1].body.extend(loop.body[2].body)
    del loop.body[2]
    if hashlib.sha256(dump(restored).encode()).hexdigest() != row['previousSha256']:
        raise ValueError('Receipt journal AST inverse did not restore the complete original run AST')
    return restored
