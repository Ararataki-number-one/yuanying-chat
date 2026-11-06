"""Exact callback telemetry inverse for historical source-byte oracles only.

Runtime verification and native reports use the current files. This explicit
input port accepts only the three complete reviewed sources and no old variants.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELTA_PATH = ROOT / 'tests/fixtures/network-settings-callback-source-deltas.json'
DELTA_SHA256 = '232bb1fea99a27287a048771e78d10d47d94802e002db2097c82a12274b2a916'
BASE_COMMIT = 'e21b4fd6698074310ee36f85f980b16ad643c934'
BASE_TREE = 'cee24c278512c18926edf3db5102c87958f6b699'
BASE_SOURCES = {
    'tests/gecko/run_network_settings_internal.py': 'efb4846cd41f41d8f1ea737c0695143981fe7d7806e72fe759a660875ae9d4a3',
    'tests/gecko/NetworkSettingsInternalApplication.java': '22e8724a8a63feae80bb8291ea678b0673104e13e166a9735c8bf77c99128f31',
    'tests/gecko_settings_internal_gate_test.py': '124a15774492a9cc3209e0d04aace5f074bb2518526674922c498aa195745df8',
}
MAX_DELTA_BYTES = 20000
MAX_SOURCE_BYTES = 100000


def manifest():
    raw = DELTA_PATH.read_bytes()
    if len(raw) > MAX_DELTA_BYTES or hashlib.sha256(raw).hexdigest() != DELTA_SHA256:
        raise ValueError('Callback source fixture differs from the exact reviewed bytes')
    value = json.loads(raw)
    if (type(value.get('schema')) is not int or value['schema'] != 1
            or value.get('baseCommit') != BASE_COMMIT or value.get('baseTree') != BASE_TREE
            or set(value.get('files', {})) != set(BASE_SOURCES)):
        raise ValueError('Callback source fixture has an unknown historical identity')
    for path, previous in BASE_SOURCES.items():
        if value['files'][path]['previousSha256'] != previous:
            raise ValueError('Callback source fixture changed the historical whole source')
    return value


def source_input(raw, path):
    if type(raw) is not bytes or type(path) is not str or path not in BASE_SOURCES:
        raise ValueError('Callback source input requires bytes and an exact reviewed path')
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('Callback source input exceeds its bounded whole-file size')
    row = manifest()['files'][path]
    if hashlib.sha256(raw).hexdigest() != row['reviewedSha256']:
        raise ValueError('Callback source input differs from the complete reviewed current file')
    for delta in reversed(row['deltas']):
        current, previous = delta['current'].encode('utf-8'), delta['previous'].encode('utf-8')
        if not current or not previous or raw.count(current) != 1:
            raise ValueError('Callback source inverse requires each exact contextual addition once')
        raw = raw.replace(current, previous, 1)
    if hashlib.sha256(raw).hexdigest() != BASE_SOURCES[path]:
        raise ValueError('Callback source inverse did not recover the whole historical file')
    return raw
