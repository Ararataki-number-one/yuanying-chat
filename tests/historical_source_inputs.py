"""Explicit immutable inputs for retained 2.1.4 source-history proofs.

Callers must name a historical read. This module does not wrap filesystem reads,
project current source, fetch Git objects, or supply current behavior hosts.
"""
from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '7383bb1dd82c5d2155ba7c8dcc11b541478f6cfe'
TREE = '56be467a913681f60dac48cefeedfce119b0a361'
MAX_BYTES = 4 * 1024 * 1024
_spec = importlib.util.spec_from_file_location('retained_public_git_objects', ROOT/'tools/browser/source_history.py')
_objects = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_objects)


def _path(relative):
    if type(relative) is not str or not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', relative):
        raise ValueError('A canonical historical source path is required')
    parts = PurePosixPath(relative).parts
    if (str(PurePosixPath(relative)) != relative or len(parts) < 2 or len(parts) > 16
            or parts[0] not in ('app', 'tests', 'tools', '.github')
            or any(part in ('', '.', '..') for part in parts)):
        raise ValueError('Historical source path is outside the retained proof scope')
    return parts


@lru_cache(maxsize=256)
def _verified_source(root, relative, commit_id, tree_id):
    parts = _path(relative)
    commit = _objects.object_bytes(root, 'commit', commit_id)
    trees = [line[5:].decode() for line in commit.split(b'\n\n', 1)[0].splitlines() if line.startswith(b'tree ')]
    if trees != [tree_id]:
        raise ValueError('Historical commit does not own the fixed release tree')
    selected = tree_id
    for index, part in enumerate(parts):
        tree = _objects.object_bytes(root, 'tree', selected)
        mode, selected = _objects.entry(tree, part)
        if index < len(parts) - 1:
            if mode != '40000':
                raise ValueError('Historical source directory must be an actual Git tree')
        elif mode not in ('100644', '100755'):
            raise ValueError('Historical source must be an ordinary Git file')
    raw = _objects.object_bytes(root, 'blob', selected)
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Historical source exceeds the retained proof bound')
    identity = dict(commit=commit_id, tree=tree_id, path=relative, blob=selected,
                    bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    historicalProofOnly=True, currentSourceReplacement=False)
    return raw, identity


def historical_bytes(relative):
    """Return verified bytes from the fixed real release, never the working tree."""
    return _verified_source(ROOT, relative, COMMIT, TREE)[0]


def historical_identity(relative):
    """Return a copy so consumers cannot mutate the cached provenance."""
    return dict(_verified_source(ROOT, relative, COMMIT, TREE)[1])
