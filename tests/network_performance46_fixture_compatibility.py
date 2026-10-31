"""Invert only the reviewed fixture-local process renderer boundary.

Production admission and all original sample/health/timeout checks stay protected
by the older failed-chain whole-source golden after this exact input inverse.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH='tests/gecko/NetworkOptimizationIntegrationActivity.java'
PREVIOUS_SHA='162e962157f977296867fc8d34b8034d828932d18166d52be0e9256ced69b168'
CURRENT_SHA='16b09cbb6bfa4bcd3413cae23d0bdce44c5bac0ff6222d8e9d101467c4806ca5'
MANIFEST_PATH='tests/fixtures/network-performance-local-process46-inverse.json'
MANIFEST_SHA256='7e54f06265977462f05741a32c688ff4ddccb5760791f49054a5a1b6089a1974'
EXPECTED_IDS=['local-process-render-call-1', 'explicit-read-model-diagnostics', 'local-process-render-call-2', 'local-process-render-call-3', 'explicit-local-process-renderer-helper']

def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _pairs(rows):
 out={}
 for key,value in rows:
  if key in out:raise ValueError('Duplicate inverse metadata field')
  out[key]=value
 return out

def manifest():
 path=ROOT/MANIFEST_PATH
 if any(p.is_symlink()for p in (path,*path.parents)):raise ValueError('Inverse manifest symlink rejected')
 raw=path.read_bytes()
 if _sha(raw)!=MANIFEST_SHA256:raise ValueError('Reviewed local-process inverse manifest changed')
 value=json.loads(raw,object_pairs_hook=_pairs)
 if set(value)!={'schema','path','beforeSha256','afterSha256','changes'}or value.get('schema')!=1 or value['path']!=PATH or value['beforeSha256']!=PREVIOUS_SHA or value['afterSha256']!=CURRENT_SHA:raise ValueError('Unexpected fixture inverse identity')
 changes=value['changes']
 if not isinstance(changes,list)or [row.get('id')for row in changes]!=EXPECTED_IDS:raise ValueError('Reviewed fixture inverse change set differs')
 for row in changes:
  if set(row)!={'id','before','old','new','after'}or any(not isinstance(v,str)for v in row.values())or row['old']==row['new']or not row['before']or not row['after']:raise ValueError('Invalid exact fixture inverse change')
 return value

def restore_to_source3(raw,path=PATH):
 if path!=PATH or type(raw)is not bytes:raise ValueError('Exact protected fixture bytes/path required')
 digest=_sha(raw)
 if digest==PREVIOUS_SHA:return raw
 if digest!=CURRENT_SHA:raise ValueError('Unreviewed whole-source local-process fixture bytes')
 text=raw.decode('utf-8')
 for row in reversed(manifest()['changes']):
  literal=row['before']+row['new']+row['after']
  if text.count(literal)!=1:raise ValueError('Fixture renderer change missing, duplicated or moved: '+row['id'])
  text=text.replace(literal,row['before']+row['old']+row['after'],1)
 result=text.encode('utf-8')
 if _sha(result)!=PREVIOUS_SHA:raise ValueError('Exact original SOURCE3 whole fixture was not recovered')
 return result

def input_for_original_fixture(source):
 if not isinstance(source,str):raise ValueError('Fixture source text required')
 raw=source.encode('utf-8')
 if _sha(raw)in(CURRENT_SHA,PREVIOUS_SHA)or 'controlledLocalProcessReadModel'in source or '"readModelProjection"'in source:
  return restore_to_source3(raw).decode('utf-8')
 # Historical inputs predate this insertion. The original consumer continues to
 # enforce its unchanged complete older golden; this is no general bypass.
 return source
