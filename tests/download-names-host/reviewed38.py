"""Exact bounded inverse of the reviewed38 display-only source additions."""
import hashlib,json
from pathlib import Path
MANIFEST_SHA='d47ff93f57ba66ca2ebf3aa10c35a36721fbf78d3cf200a3318173cbf728495e'
def invert(text):
    raw=(Path(__file__).with_name('reviewed38-inverse.json')).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==MANIFEST_SHA,'Reviewed38 inverse manifest bytes changed'
    manifest=json.loads(raw)
    for edit in reversed(manifest['edits']):
        before,after=edit['before'],edit['after']
        assert hashlib.sha256(before.encode()).hexdigest()==edit['beforeSha256'] and hashlib.sha256(after.encode()).hexdigest()==edit['afterSha256'],'Reviewed38 bounded edit digest changed'
        assert text.count(after)==1,'Reviewed38 bounded edit must occur exactly once'
        text=text.replace(after,before,1)
    return text
