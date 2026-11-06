"""Finite CPU/latency inputs for retained historical oracles only.

Actual applications, compilers, device runners and release checkers use raw
current source. Public8c is an earlier working212 input, not release qualification.
"""
import ast
import functools
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
ROOT=Path(__file__).resolve().parents[1]
BASE_COMMIT='8c11554b631684cae8f18cd5b7ad4311f943bf2c'
BASE_TREE='b77eac1a8a183e1d08b2ab726d64e199598abc3a'
FIXTURE=ROOT/'tests/fixtures/cpu-source-deltas.json'
FIXTURE_SHA256='5c951d6e53e97b5ba389d7ba1d595dd7d097570690120ab2a03ff3e85c2c6b5b'
PATHS=frozenset(('app/src/main/java/local/pocketchat/GeckoWebView.java', 'app/src/main/java/local/pocketchat/ChatSession.java', 'tests/gecko/FingerprintFollowupIntegrationActivity.java', 'tests/browser_acceptance_workflow_test.py', 'tests/browser_fingerprint_publish_gate_test.py', 'tests/browser_environment_publish_gate_test.py', 'tests/browser_ip_timezone_publish_gate_test.py', 'tests/pure212_ci_source_compatibility.py', 'tests/ip_timezone_source_compatibility.py', 'tests/dual_browser_source_compatibility.py', 'tests/profile_pure212_ci_source_compatibility_test.py', 'tests/profile_worker_timezone_source_compatibility_test.py', 'tests/profile_dual_browser_source_compatibility_test.py', 'tests/profile_ip_timezone_source_compatibility_test.py', 'tests/profile_native_protection_test.py', 'tests/native-protection-host/NativeProtectionControllerHost.java.in', 'tests/gecko-ip-window-barrier-host/run.py', 'tests/baselines/public-source-history.json', 'tools/browser/source_history.py', 'tests/gecko/run_ui_visuals.py', 'tests/ui_quick_sheet_source_compatibility.py', 'tests/profile_ui_observer_source_compatibility_test.py', 'tests/profile_ui_quick_sheet_source_compatibility_test.py'))
MAX_FIXTURE=1024*1024
MAX_SOURCE=512*1024
UI_RUNNER='tests/gecko/run_ui_visuals.py'
UI_LABEL='自动检测外部网络响应'
# One later historical host input; outside the frozen23 production/oracle rows.
UI_CAPTURE_TEST='tests/gecko_ui_visual_capture_test.py'
UI_CAPTURE_TEST_PREVIOUS=(40245,'8ab2a6335b9f313e38cb52deb4b7265ee1be3e8fefc4009d5ef5c3825c40d0c6')
UI_CAPTURE_TEST_REVIEWED=(40504,'2ff884dec5046332fc1598a24caf1a6a1045a5073889125e9e0d14da48a5c433')
UI_CAPTURE_TEST_PREVIOUS_CONTEXT="        old=subprocess.check_output(['git','show',base+':tests/gecko/run_ui_visuals.py'],cwd=ROOT,text=True);current=RUNNER.read_text()\n"
UI_CAPTURE_TEST_REVIEWED_CONTEXT="        spec=importlib.util.spec_from_file_location('cpu_capture_source_oracle',ROOT/'tests/cpu_source_compatibility.py')\n        history=importlib.util.module_from_spec(spec);spec.loader.exec_module(history)\n        old=subprocess.check_output(['git','show',base+':tests/gecko/run_ui_visuals.py'],cwd=ROOT,text=True);current=history.source_input(RUNNER.read_bytes(),history.UI_RUNNER).decode()\n"
UI_PREVIOUS_AST='bce34002d46c253efc144e2a709d92ebeeff26880cd60bb7861b94794b991132'
UI_REVIEWED_AST='fc13ddc21ba91cea5149aabafeac8471c119e142485aff039321c6d3de446edf'
UI_AST_PAIRS={UI_REVIEWED_AST:UI_PREVIOUS_AST,
 'c1efc91ad0e59b63c28b833884be72cd067759adcd356e205e3a510212d0c95b':'e321267b96c447c8d6253482134b9bec71a95838d67911ec363666ed0ff3b1ed'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def _ordinary(path):return path.is_file() and not any(p.is_symlink() for p in (path,*path.parents))
def manifest():
 if not _ordinary(FIXTURE):raise ValueError('Ordinary exact CPU source fixture required')
 raw=FIXTURE.read_bytes()
 if not 0<len(raw)<=MAX_FIXTURE or sha(raw)!=FIXTURE_SHA256:raise ValueError('Exact whole CPU metadata fixture required')
 def pairs(values):
  d={}
  for k,v in values:
   if k in d:raise ValueError('Duplicate CPU metadata key')
   d[k]=v
  return d
 value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite CPU metadata')))
 if type(value)is not dict or set(value)!={'schema','kind','baseCommit','baseTree','actualAndroidExecution','runtimeAcceptance','files'} or type(value.get('schema'))is not int or value['schema']!=1 or value.get('kind')!='cpu-latency-historical-source-only' or value.get('baseCommit')!=BASE_COMMIT or value.get('baseTree')!=BASE_TREE or value.get('actualAndroidExecution')is not False or value.get('runtimeAcceptance')is not False or type(value.get('files'))is not dict or set(value['files'])!=PATHS:raise ValueError('Finite CPU metadata identity differs')
 for row in value['files'].values():
  if type(row)is not dict or set(row)!={'previousSha256','previousBytes','reviewedSha256','reviewedBytes','contextLines','deltas'} or any(type(row.get(k))is not int or not 0<row[k]<=MAX_SOURCE for k in ('previousBytes','reviewedBytes')) or any(type(row.get(k))is not str or re.fullmatch('[0-9a-f]{64}',row[k])is None for k in ('previousSha256','reviewedSha256')) or row['previousSha256']==row['reviewedSha256'] or type(row.get('contextLines'))is not int or not 3<=row['contextLines']<=16 or type(row.get('deltas'))is not list or not 0<len(row['deltas'])<=64:raise ValueError('CPU row type/boundary differs')
  for i,d in enumerate(row['deltas']):
   if type(d)is not dict or set(d)!={'id','previous','current','previousSha256','currentSha256'} or d.get('id')!='context-%02d'%i or any(type(d.get(k))is not str or not 0<len(d[k].encode())<=64*1024 or sha(d[k].encode())!=d.get(k+'Sha256') for k in ('previous','current')) or d['previous']==d['current']:raise ValueError('CPU contextual delta differs')
 return value

def source_input(raw,relative):
 if type(raw)is not bytes or type(relative)is not str or relative not in PATHS:raise ValueError('Complete bytes and exact CPU metadata path required')
 row=manifest()['files'][relative]
 if (len(raw),sha(raw))==(row['previousBytes'],row['previousSha256']):return raw
 if (len(raw),sha(raw))!=(row['reviewedBytes'],row['reviewedSha256']):raise ValueError('CPU inverse rejects unknown whole source bytes')
 for d in reversed(row['deltas']):
  current,previous=d['current'].encode(),d['previous'].encode()
  if raw.count(current)!=1:raise ValueError('Missing duplicate moved or changed CPU context')
  raw=raw.replace(current,previous,1)
 if (len(raw),sha(raw))!=(row['previousBytes'],row['previousSha256']):raise ValueError('CPU inverse did not close to complete public212 source')
 return raw

def _capture_test_input(raw):
 if (len(raw),sha(raw))==UI_CAPTURE_TEST_PREVIOUS:return raw
 if (len(raw),sha(raw))!=UI_CAPTURE_TEST_REVIEWED:raise ValueError('Unknown whole capture source-oracle host')
 current,previous=UI_CAPTURE_TEST_REVIEWED_CONTEXT.encode(),UI_CAPTURE_TEST_PREVIOUS_CONTEXT.encode()
 if raw.count(current)!=1:raise ValueError('Missing duplicate moved or changed capture source-oracle context')
 raw=raw.replace(current,previous,1)
 if (len(raw),sha(raw))!=UI_CAPTURE_TEST_PREVIOUS:raise ValueError('Entire previous capture source-oracle host did not restore')
 return raw

def metadata_input(raw,relative):
 if type(raw)is not bytes or type(relative)is not str:raise ValueError('Exact metadata bytes and path required')
 if relative==UI_CAPTURE_TEST:return _capture_test_input(raw)
 return source_input(raw,relative) if relative in PATHS else raw

def wrap_bytes(original):
 @functools.wraps(original)
 def wrapped(raw,relative):
  if type(raw)is bytes and type(relative)is str and relative in PATHS:
   row=manifest()['files'][relative]
   if (len(raw),sha(raw)) in ((row['previousBytes'],row['previousSha256']),(row['reviewedBytes'],row['reviewedSha256'])):raw=source_input(raw,relative)
  return original(raw,relative)
 return wrapped

def tree_sha(tree):return sha(ast.dump(tree,include_attributes=False).encode())
def ui_tree_input(tree):
 if type(tree)is not ast.Module:raise ValueError('Complete UI metadata module required')
 digest=tree_sha(tree)
 if digest in UI_AST_PAIRS.values():return tree
 if digest not in UI_AST_PAIRS:raise ValueError('Unknown whole UI CPU metadata AST')
 candidates=[n for n in ast.walk(tree) if isinstance(n,ast.Set) and any(isinstance(e,ast.Constant) and e.value==UI_LABEL for e in n.elts)]
 if len(candidates)!=1:raise ValueError('Unique added latency expected-field set required')
 node=candidates[0];items=[e for e in node.elts if isinstance(e,ast.Constant) and e.value==UI_LABEL]
 if len(items)!=1:raise ValueError('Unique latency literal required')
 node.elts.remove(items[0])
 if tree_sha(tree)!=UI_AST_PAIRS[digest]:raise ValueError('Entire previous UI metadata module did not restore')
 return tree

def wrap_tree(original):
 @functools.wraps(original)
 def wrapped(tree):
  if type(tree)is ast.Module and tree_sha(tree)in UI_AST_PAIRS:tree=ui_tree_input(tree)
  return original(tree)
 return wrapped
