"""Invert only the reviewed workspace UI bytes for historical scope comparisons."""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA = '8e2b8426314f2677702546d9918d959f108d89109532c9ec4702365d74a3a4a4'


def manifest():
    raw = Path(__file__).with_name('reviewed-workspace-ui-inverse.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA, 'Reviewed46 bounded edit workspace UI manifest bytes changed'
    return json.loads(raw)


def present(text, name='DesignDownloads.java'):
    return name == 'DesignDownloads.java' and any(marker in text for marker in (
        'DownloadWorkspaceStyle', 'stateLabel', 'downloadToolsExpanded'))


def invert(text, name, member):
    if not present(text, name):
        return text
    approved = manifest()
    # Execution hosts extract from the original current source, never this
    # historical projection. Validate current methods before removing UI bytes.
    for needle, digest in approved['currentMethodSha256'].items():
        assert hashlib.sha256(member(text, needle).encode()).hexdigest() == digest, 'Reviewed46 bounded edit current tested method drift: workspace UI ' + needle
    for edit in reversed(approved['edits']):
        before, after = edit['before'], edit['after']
        assert hashlib.sha256(before.encode()).hexdigest() == edit['beforeSha256'] and hashlib.sha256(after.encode()).hexdigest() == edit['afterSha256'], 'Reviewed46 bounded edit workspace UI digest changed'
        assert text.count(after) == 1, 'Reviewed46 bounded edit workspace UI must occur exactly once'
        text = text.replace(after, before, 1)
    for needle, digest in approved['priorMethodSha256'].items():
        assert hashlib.sha256(member(text, needle).encode()).hexdigest() == digest, 'Reviewed46 bounded edit workspace UI prior method mismatch: ' + needle
    # Unknown bytes outside these exact edits remain for the original four
    # whole-file guards. Do not replace the entire file with a stored snapshot.
    return text
