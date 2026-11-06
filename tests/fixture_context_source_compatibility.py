"""Five exact fixture-context inputs for retained source oracles only.

Runtime fixture Java, compilers, native checkers and device runners stay raw.
The previous public working source is a byte predecessor, not qualification.
"""
import functools
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/fixture-context-source-deltas.json'
FIXTURE_SHA256='b3e1da064763ea1c899996cc49e02a3c192fb72361cc2adbc1d1f324c4eda55b'
PATHS=frozenset(('tests/gecko/FingerprintFollowupIntegrationActivity.java','tests/dual_browser_source_compatibility.py','tests/profile_dual_browser_source_compatibility_test.py','tests/profile_worker_timezone_source_compatibility_test.py','tests/ip_timezone_source_compatibility.py'))
BASE='7b17f88173d4e7834fbeca56feeca7de03340d9f'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def manifest():
 if not FIXTURE.is_file()or any(p.is_symlink()for p in(FIXTURE,*FIXTURE.parents)):raise ValueError('Ordinary fixture-context metadata required')
 raw=FIXTURE.read_bytes()
 if not 0<len(raw)<=256*1024 or sha(raw)!=FIXTURE_SHA256:raise ValueError('Exact bounded fixture-context metadata required')
 def pairs(values):
  result={}
  for k,v in values:
   if k in result:raise ValueError('Duplicate fixture-context metadata key')
   result[k]=v
  return result
 value=json.loads(raw,object_pairs_hook=pairs)
 if type(value)is not dict or set(value)!={'schema','kind','previousSource','actualAndroidExecution','runtimeAcceptance','files'}or type(value.get('schema'))is not int or value['schema']!=1 or value.get('kind')!='fixture-context-historical-metadata-only'or value.get('previousSource')!=BASE or value.get('actualAndroidExecution')is not False or value.get('runtimeAcceptance')is not False or type(value.get('files'))is not dict or set(value['files'])!=PATHS:raise ValueError('Finite fixture-context scope required')
 for row in value['files'].values():
  if type(row)is not dict or set(row)!={'previousSha256','previousBytes','reviewedSha256','reviewedBytes','deltas'}or any(type(row.get(k))is not int or not 0<row[k]<=256*1024 for k in('previousBytes','reviewedBytes'))or any(type(row.get(k))is not str or len(row[k])!=64 or any(c not in'0123456789abcdef'for c in row[k])for k in('previousSha256','reviewedSha256'))or type(row.get('deltas'))is not list or not 0<len(row['deltas'])<=32:raise ValueError('Finite fixture-context row required')
  for i,d in enumerate(row['deltas']):
   if type(d)is not dict or set(d)!={'id','previous','current','previousSha256','currentSha256'}or d.get('id')!='context-%02d'%i or any(type(d.get(k))is not str or not 0<len(d[k].encode())<=128*1024 or sha(d[k].encode())!=d.get(k+'Sha256')for k in('previous','current')):raise ValueError('Exact fixture-context delta required')
 return value
def source_input(raw,relative):
 if type(raw)is not bytes or type(relative)is not str or relative not in PATHS:raise ValueError('Complete bytes and exact fixture metadata path required')
 row=manifest()['files'][relative]
 if(len(raw),sha(raw))==(row['previousBytes'],row['previousSha256']):return raw
 if(len(raw),sha(raw))!=(row['reviewedBytes'],row['reviewedSha256']):raise ValueError('Unknown whole fixture-context source')
 for d in reversed(row['deltas']):
  current,previous=d['current'].encode(),d['previous'].encode()
  if raw.count(current)!=1:raise ValueError('Missing duplicate moved or changed fixture context')
  raw=raw.replace(current,previous,1)
 if(len(raw),sha(raw))!=(row['previousBytes'],row['previousSha256']):raise ValueError('Complete fixture-context predecessor did not restore')
 return raw
def metadata_input(raw,relative):
 if type(raw)is not bytes or type(relative)is not str:raise ValueError('Exact fixture metadata bytes/path required')
 return source_input(raw,relative)if relative in PATHS else raw
def wrap_bytes(original):
 @functools.wraps(original)
 def wrapped(raw,relative):
  if type(raw)is bytes and type(relative)is str and relative in PATHS:
   row=manifest()['files'][relative]
   if(len(raw),sha(raw))in((row['previousBytes'],row['previousSha256']),(row['reviewedBytes'],row['reviewedSha256'])):raw=source_input(raw,relative)
  return original(raw,relative)
 return wrapped
