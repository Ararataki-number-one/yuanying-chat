"""Exact additive 46 inverse, followed by the untouched historical guards."""
import hashlib,json
from pathlib import Path
MANIFEST_SHA='ca4b9668e0dfa59cc35df2782c31729824ca1705baf7d55e1f731644e6aa5e6c'
def invert(text,name):
    raw=Path(__file__).with_name('reviewed46-inverse.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==MANIFEST_SHA,'Reviewed46 inverse manifest bytes changed'
    manifest=json.loads(raw);file=manifest['files'][name]
    # Historical negative controls also pass an already projected prior body.
    # With no 46 additions, every byte still reaches the original whole guards.
    present=('DownloadDisplayCache' in text or 'DownloadMetadataValues' in text) if name=='DesignDownloads.java' else 'DownloadLibrary.changed(root)' in text
    if not present:return text
    for edit in reversed(file['edits']):
        before,after=edit['before'],edit['after']
        assert hashlib.sha256(before.encode()).hexdigest()==edit['beforeSha256'] and hashlib.sha256(after.encode()).hexdigest()==edit['afterSha256'],'Reviewed46 bounded edit digest changed'
        assert text.count(after)==1,'Reviewed46 bounded edit must occur exactly once'
        text=text.replace(after,before,1)
    return text
