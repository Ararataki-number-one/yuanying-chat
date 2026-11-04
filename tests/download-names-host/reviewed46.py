"""Exact additive 46 inverse, followed by the untouched historical guards."""
import hashlib,json
from pathlib import Path
MANIFEST_SHA='ca4b9668e0dfa59cc35df2782c31729824ca1705baf7d55e1f731644e6aa5e6c'
SCAFFOLD_MANIFEST_SHA='67b4b7872c6a8c66b8ded982ccf75f4dbcde58481262ca0c140070420bb614df'
def scaffold_manifest():
    raw=Path(__file__).with_name('reviewed210-scaffold-inverse.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCAFFOLD_MANIFEST_SHA,'Reviewed46 bounded edit 210 scaffold manifest bytes changed'
    return json.loads(raw)
def remove_scaffold(text,name,member):
    if name!='DesignDownloads.java' or not any(marker in text for marker in ['DownloadQuery query;','final DownloadReadGate reads=','final CheckBox collected;']):return text
    manifest=scaffold_manifest()
    # The selected behavioral methods are NOT projected back to an old body.
    # They are identical in these two source commits and compiled from the
    # current input by the original host. Reject any mutation of those bodies.
    for needle,digest in manifest['testedMethodSha256'].items():
        assert hashlib.sha256(member(text,needle).encode()).hexdigest()==digest,'Reviewed46 bounded edit current tested method drift: '+needle
    for edit in reversed(manifest['edits']):
        before,after=edit['before'],edit['after']
        assert hashlib.sha256(before.encode()).hexdigest()==edit['beforeSha256'] and hashlib.sha256(after.encode()).hexdigest()==edit['afterSha256'],'Reviewed46 bounded edit 210 scaffold digest changed'
        assert text.count(after)==1,'Reviewed46 bounded edit 210 scaffold must occur exactly once'
        text=text.replace(after,before,1)
    for needle,digest in manifest['testedMethodSha256'].items():
        assert hashlib.sha256(member(text,needle).encode()).hexdigest()==digest,'Reviewed46 bounded edit 210 scaffold altered a tested method: '+needle
    return text
def invert(text,name,member):
    text=remove_scaffold(text,name,member)
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
