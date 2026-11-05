"""Finite whole-byte inverse for only the reviewed native-admission prerequisite.

Historical source guard only. Android/runtime hosts always execute current files.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/connection-timezone-prerequisite-source-deltas.json'
FIXTURE_SHA256='cf99d65553fa119fe6154f591487b103a1b805646220490c6992f19ba073b0b8'
PATHS=frozenset(('tests/gecko/GeckoConnectionPoolIntegrationActivity.java','tests/gecko/PreconnectIntegrationActivity.java'))
def digest(raw):return hashlib.sha256(raw).hexdigest()
def manifest():
    raw=FIXTURE.read_bytes()
    if not 0<len(raw)<=128*1024 or digest(raw)!=FIXTURE_SHA256:raise ValueError('Native prerequisite inverse manifest is not reviewed exact bytes')
    value=json.loads(raw)
    if value.get('schema')!=1 or value.get('kind')!='fixture-native-prerequisite-only' or set(value.get('files',{}))!=PATHS:raise ValueError('Native prerequisite inverse identity differs')
    return value

def original_connection_fixture(raw,path):
    if type(raw)is not bytes or type(path)is not str or path not in PATHS:raise ValueError('Complete owned fixture bytes required')
    record=manifest()['files'][path]
    if len(raw)==record['beforeBytes'] and digest(raw)==record['beforeSha256']:return raw
    if len(raw)!=record['currentBytes'] or digest(raw)!=record['currentSha256']:raise ValueError('Unknown whole native prerequisite fixture bytes')
    for delta in reversed(record['deltas']):
        before,current=delta['before'].encode(),delta['current'].encode()
        if digest(before)!=delta['beforeSha256'] or digest(current)!=delta['currentSha256'] or raw.count(current)!=1:raise ValueError('Native prerequisite exact delta differs')
        raw=raw.replace(current,before,1)
    if len(raw)!=record['beforeBytes'] or digest(raw)!=record['beforeSha256']:raise ValueError('Native prerequisite did not restore original whole fixture')
    return raw

def legacy_pool_activity_input(text):
    """Old whole-hash negatives expect changed bytes, rather than exceptions.
    Unknown bytes are never restored/approved: the unchanged old golden hash
    comparison still rejects them in its positive path and detects its mutant.
    """
    try:return original_connection_fixture(text.encode(),'tests/gecko/GeckoConnectionPoolIntegrationActivity.java').decode()
    except ValueError:return text
