"""Reverse only the exact reviewed window-test changes, then verify whole source."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXTURE='tests/gecko/GeckoIntegrationTestActivity.java'
MANIFEST_SHA256='50b47065b5e295702ce7e4b368e4c19d592935b37bcbcc2735a4e8febe0b7082'
BASELINE_SHA256='6581b1d35024ce6edcf829575104e5dd3464ebfe20280e1a49d1c4b468325b39'
IDS=['view-field','touch-observe','touch-forwarded','shared-window-deadline','capture-window-bounds-owner','window-bounds-recheck','window-event-metadata']
def window_manifest():
 raw=(ROOT/'tests/fixtures/window-tap-readiness-additions.json').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:raise ValueError('Window readiness manifest changed')
 value=json.loads(raw)
 if value.get('schema')!=1 or value.get('path')!=FIXTURE or value.get('baselineSha256')!=BASELINE_SHA256 or [x.get('id') for x in value.get('changes',[])]!=IDS:raise ValueError('Window readiness change set differs')
 if value.get('helperPath')!='tests/gecko/GeckoWindowTapReadiness.java' or hashlib.sha256((ROOT/value['helperPath']).read_bytes()).hexdigest()!=value.get('helperSha256'):raise ValueError('Window readiness helper differs')
 return value

def strip_reviewed_window_additions(raw):
 if hashlib.sha256(raw).hexdigest()==BASELINE_SHA256:return raw
 from experience46_source_compatibility import experience46_source_bytes
 raw=experience46_source_bytes(raw,FIXTURE)
 source=raw.decode('utf-8')
 for item in reversed(window_manifest()['changes']):
  before,after=item['before'],item['after']
  added=item['inserted'] if 'inserted' in item else item['replacement']
  old='' if 'inserted' in item else item['original']
  literal=before+added+after
  if not added or source.count(literal)!=1:raise ValueError('Window readiness change missing, duplicated, modified or moved: '+item['id'])
  source=source.replace(literal,before+old+after,1)
 result=source.encode('utf-8')
 if hashlib.sha256(result).hexdigest()!=BASELINE_SHA256:raise ValueError('Whole original37 integration fixture differs')
 return result
