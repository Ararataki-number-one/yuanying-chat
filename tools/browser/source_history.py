"""Explicit setup-time restoration of fixed public source-oracle dependencies.

Only the setup CLI may fetch missing objects. Existing tests keep their original
Git reads and assertions; they receive exact commit/tree/blob bytes beforehand.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'Ararataki-number-one/yuanying-chat'
ORIGINS = ('https://github.com/' + REPOSITORY, 'https://github.com/' + REPOSITORY + '.git')
MANIFEST = 'tests/baselines/public-source-history.json'
MANIFEST_SHA256 = '3a25f8963e7571f7e8c33f48998d67381d595896bc942aca227a71e48cf5ae17'


class MissingHistoricalObject(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise RuntimeError('Public source history preparation: ' + message)


def git(root, *parts):
    environment = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', '--no-replace-objects', *parts], cwd=root,
                          capture_output=True, timeout=120, env=environment)


def checked(root, *parts):
    result = git(root, *parts)
    require(result.returncode == 0, 'Git operation failed: ' + repr(parts))
    return result.stdout


def manifest(root):
    path = Path(root) / MANIFEST
    require(not path.is_symlink() and path.is_file(), 'fixed dependency manifest missing')
    raw = path.read_bytes()
    require(len(raw) <= 256 * 1024 and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256,
            'fixed dependency manifest bytes differ')
    value = json.loads(raw)
    require(type(value) is dict and set(value) == {'schema', 'repository', 'scope', 'groups'}
            and type(value['schema']) is int and value['schema'] == 1 and value['repository'] == REPOSITORY,
            'fixed dependency manifest shape differs')
    groups = value['groups']
    require(type(groups) is list and 0 < len(groups) <= 32, 'bounded dependency groups required')
    commits = set()
    for group in groups:
        require(type(group) is dict and set(group) == {'commit', 'tree', 'files'}
                and re.fullmatch('[0-9a-f]{40}', group.get('commit', ''))
                and re.fullmatch('[0-9a-f]{40}', group.get('tree', ''))
                and group['commit'] not in commits, 'fixed full commit/tree identities required')
        commits.add(group['commit'])
        require(type(group['files']) is dict and 0 < len(group['files']) <= 256, 'bounded fixed paths required')
        for name, row in group['files'].items():
            require(type(name) is str and re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', name)
                    and not name.startswith('/') and all(p not in ('', '.', '..') for p in name.split('/')),
                    'invalid fixed source path')
            require(type(row) is dict and set(row) == {'mode', 'blob', 'bytes', 'sha256'}
                    and row['mode'] in ('100644', '100755') and type(row['bytes']) is int
                    and 0 < row['bytes'] <= 4 * 1024 * 1024
                    and re.fullmatch('[0-9a-f]{40}', row.get('blob', ''))
                    and re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')), 'invalid fixed source object pin')
    return groups


def object_bytes(root, kind, identity):
    result = git(root, 'cat-file', kind, identity)
    if result.returncode != 0:
        raise MissingHistoricalObject(kind + ' object unavailable: ' + identity)
    raw = result.stdout
    require(hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == identity,
            'actual Git object identity differs')
    return raw


def entry(raw, component):
    offset, found = 0, {}
    while offset < len(raw):
        space, zero = raw.index(b' ', offset), raw.index(b'\0', offset)
        mode, name = raw[offset:space], raw[space + 1:zero]
        require(zero + 21 <= len(raw) and name not in found, 'malformed source tree')
        found[name] = (mode.decode(), raw[zero + 1:zero + 21].hex())
        offset = zero + 21
    require(component.encode() in found, 'fixed source path absent')
    return found[component.encode()]


def verify_group(root, group):
    commit = object_bytes(root, 'commit', group['commit'])
    trees = [line[5:].decode() for line in commit.split(b'\n\n', 1)[0].splitlines() if line.startswith(b'tree ')]
    require(trees == [group['tree']], 'fixed commit does not own the fixed tree')
    cache, observed = {}, []
    for name, pin in group['files'].items():
        tree = group['tree']
        parts = name.split('/')
        for index, component in enumerate(parts):
            if tree not in cache:
                cache[tree] = object_bytes(root, 'tree', tree)
            mode, tree = entry(cache[tree], component)
            require(mode == (pin['mode'] if index == len(parts) - 1 else '40000'), 'fixed source mode differs')
        require(tree == pin['blob'], 'fixed source path resolves to another blob')
        raw = object_bytes(root, 'blob', tree)
        require(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'],
                'whole historical source bytes differ')
        observed.append(dict(path=name, **pin))
    return dict(commit=group['commit'], tree=group['tree'], files=observed)


def checkout_state(root):
    source = checked(root, 'rev-parse', 'HEAD').decode().strip()
    tree = checked(root, 'rev-parse', 'HEAD^{tree}').decode().strip()
    require(re.fullmatch('[0-9a-f]{40}', source) and re.fullmatch('[0-9a-f]{40}', tree), 'actual source identity required')
    status = checked(root, 'status', '--porcelain', '--untracked-files=no')
    index = checked(root, 'ls-files', '--stage', '-z')
    material = hashlib.sha256()
    for value in checked(root, 'ls-files', '-z').split(b'\0'):
        if not value:
            continue
        path = Path(root) / os.fsdecode(value)
        material.update(value + b'\0')
        material.update(os.readlink(path).encode() if path.is_symlink() else hashlib.sha256(path.read_bytes()).digest())
    return dict(sourceCommit=source, sourceTree=tree, indexSha256=hashlib.sha256(index).hexdigest(),
                trackedStatusSha256=hashlib.sha256(status).hexdigest(), trackedBytesSha256=material.hexdigest())


def authorize_fetch(root, environment):
    require(environment.get('CI') == 'true' and environment.get('GITHUB_ACTIONS') == 'true'
            and environment.get('GITHUB_SERVER_URL') == 'https://github.com'
            and environment.get('GITHUB_REPOSITORY') == REPOSITORY, 'missing objects require this actual repository CI setup')
    for key, maximum in (('GITHUB_RUN_ID', 20), ('GITHUB_RUN_ATTEMPT', 10)):
        require(isinstance(environment.get(key), str)
                and re.fullmatch('[1-9][0-9]{0,' + str(maximum - 1) + '}', environment[key]), 'positive CI run/attempt required')
    state = checkout_state(root)
    require(not checked(root, 'status', '--porcelain', '--untracked-files=no').strip(), 'tracked source must be clean before network fetch')
    require(environment.get('GITHUB_SHA') == state['sourceCommit'], 'CI source differs from checkout')
    require(checked(root, 'rev-parse', '--show-toplevel').decode().strip() == str(Path(root).resolve()), 'checkout root differs')
    require(checked(root, 'remote', 'get-url', 'origin').decode().strip() in ORIGINS, 'only the fixed public repository origin is allowed')
    return state


def prepare_public_history(root=ROOT, environment=None):
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    groups = manifest(root)
    before = checkout_state(root)
    observed, fetched = [], []
    for group in groups:
        try:
            ready = verify_group(root, group)
        except MissingHistoricalObject:
            state = authorize_fetch(root, environment)
            require(state == before, 'checkout changed before dependency fetch')
            try:
                checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin', group['commit'])
            finally:
                require(checkout_state(root) == before, 'dependency fetch changed HEAD, index or tracked bytes')
            fetched.append(group['commit'])
            ready = verify_group(root, group)
        observed.append(ready)
    require(checkout_state(root) == before, 'historical verification changed checkout')
    return dict(schema=1, status='passed', repository=REPOSITORY, sourceCommit=before['sourceCommit'],
                sourceTree=before['sourceTree'], checkoutUnchanged=True, manifestSha256=MANIFEST_SHA256,
                groups=observed, fetchedCommits=fetched, testsExecuted=False, actualAndroidExecution=False,
                scope='Explicit setup-time exact public source dependencies. Actual commit/tree/blob and whole-file bytes; no test-time lazy fetch, source projection, checkout, signing or app execution.')
