"""Reverse only separately pinned optional integration trace insertions."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST_SHA256='80bcd24da9c5e7eb1ab975fa6e4d1ffa5193c63e5ecafa870b220c3d5fb16478'
PATHS={
 'tests/gecko/GeckoIntegrationTestActivity.java':('7d6cc589a2718f629568205c79c290ef713d745b05a62a700a72451846c8d814',['trace-model','case-field','view-request','case-toggle','native-observation','poll-observation','event-report']),
 'tests/gecko/run_device.py':('019bc8e8b8e61def3d6fe87fe70d9eb7a87a3a556d86b921489331f9f4757e5d',['runner-option','runner-intent']),
}
def trace_manifest():
 raw=(ROOT/'tests/fixtures/reading-zoom-trace-additions.json').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:raise ValueError('Optional reading trace manifest changed')
 data=json.loads(raw)
 if data.get('schema')!=1 or set(data.get('paths',{}))!=set(PATHS):raise ValueError('Unexpected optional trace paths')
 for path,(digest,ids) in PATHS.items():
  row=data['paths'][path]
  if row.get('baselineSha256')!=digest or [x.get('id') for x in row.get('insertions',[])]!=ids:raise ValueError('Optional trace insertion set changed')
 return data

def strip_reviewed_reading_trace_additions(raw,path):
 if path not in PATHS:raise ValueError('Unexpected protected trace path')
 if hashlib.sha256(raw).hexdigest()==PATHS[path][0]:return raw
 if path=='tests/gecko/GeckoIntegrationTestActivity.java':
  from window_tap_readiness_contract import strip_reviewed_window_additions
  raw=strip_reviewed_window_additions(raw)
 source=raw.decode('utf-8');row=trace_manifest()['paths'][path]
 for item in reversed(row['insertions']):
  before,added,after=(item[k] for k in ('before','inserted','after'));literal=before+added+after
  if not added or source.count(literal)!=1:raise ValueError('Optional trace addition changed, missing, duplicated or moved: '+item['id'])
  source=source.replace(literal,before+after,1)
 return source.encode('utf-8')

def original_reading_fixture_bytes(raw,path):
 if path=='tests/gecko/run_device.py' and hashlib.sha256(raw).hexdigest()!=PATHS[path][0]:
  from experience46_source_compatibility import experience46_source_bytes
  raw=experience46_source_bytes(raw,path)
 result=strip_reviewed_reading_trace_additions(raw,path)
 if hashlib.sha256(result).hexdigest()!=PATHS[path][0]:raise ValueError('Original whole-source reading oracle changed')
 return result
