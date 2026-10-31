"""Prepare two exact historical inputs for unchanged profile source oracles.

The original checkout depth and all assertions remain unchanged. Full unittest
discovery imports the additive preparation module before running any test.
For a standalone old module in a shallow checkout, run this CLI first.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY = 'Ararataki-number-one/yuanying-chat'
ORIGINS = ('https://github.com/' + REPOSITORY, 'https://github.com/' + REPOSITORY + '.git')
GROUPS = (
    ('e99acdb873d4c44f303c0d97abf9c2c1fa281c30', '12f91afcb24b842a371ad8cdb663ff7af04c7b48', {
        'app/src/main/java/local/pocketchat/GeckoWebView.java': ('d25ea10c7b7fcaabfbce4376308bedec7e2153dd', 69847, '892af2842f87e20f6cf339f6654ca0651cdef11c9bda9ce0477daeff69ecc9bd'),
        'tests/fingerprint_source_compatibility.py': ('709c8837cc99c5281c9762ac0a75d00d904e29c7', 10225, '6fbcd5251aff92d99e4ab816c0b90c9aa979fe6c05d6181b057604671263e4b9'),
        'tests/profile_lifecycle39_source_compatibility_test.py': ('1da1837b69da5c532b84783f37adfe20795eb416', 5039, '088611f0e2b01f8d235fadf636fae8e8f4f45bcae298dcf054daec74f7371580'),
    }),
    ('b25974a69d6c8d6a7652f3c55455d2f6cccd5da7', '2b2dc1ee24305e020222941f96f851e365af4d62', {
        'app/src/main/java/local/pocketchat/GeckoWebView.java': ('44b018eab2d6a5dfe92b29db9230eaa91c850c4b', 70003, '07d027899ad2c4a48d3759fe19080d3aa72027aa75aac6147e470f310bb1a5be'),
        'tests/page_bridge42_source_compatibility.py': ('83932a7da7d0fa3eba79d0c43bb879852e480ef3', 2747, 'c91b1bc650ebcc5d5d4f88ad196b475344cc2b7ddc6aef86ed705b6caf1f05f6'),
        'tests/profile_page_bridge42_source_compatibility_test.py': ('fc4bf96cab29da488d425e0c1a4fb8f378c22fa8', 7671, '97aea159c2331ebff6dd918b1787d4797fbfb2796a7bcefc94c3fdd8f0edbaf2'),
        'tests/fingerprint_source_compatibility.py': ('526b62bfb30f58453e45866edb4ecabda64f41a2', 10386, '3f5bbd09edbd41cebe75f5e54a35ab4ad2b973715b448da6d56aa9159f828a2c'),
        'tests/profile_upload37_source_compatibility_test.py': ('79a7f6282b0ad3ecca6916162fb58aee01e5e36d', 4007, 'fa6ffaf6bdec99e818272450b01be2c3a7e27ec0efbf82af413b1de664928096'),
        'tests/profile_lifecycle39_source_compatibility_test.py': ('1eb0e079db301468b83a273e64c6ff3edce7855f', 5183, 'fe3b7208649dedf5285566443a713560e92562ab0da0c1a6386e70d0d14ba385'),
        'tests/profile_page_bridge_lifecycle_test.py': ('15c5d8e358a72ec1a4451bab34a25ca69f5413da', 6530, '5db78c19b8a8c764a63ad4a35f881ecf0d7369fc596ca974023ceb2667a66f1d'),
        'tests/profile_content_permission_decisions_test.py': ('dfeb5ce65c903853f40996d50ab21fcd946d84b2', 7966, 'd333590bd584124ed38f70c9da71f6c6989534b45e858ff57a49578b9b7b019f'),
        'tests/profile_reading_fit_completion_test.py': ('4c45d351eb9c4c959db0f716fa7ce190cb81d380', 18536, '8db811422515da902a615a8ba10f55e78950e106af430219d7bd0fc2ba571193'),
    }),
)


class MissingHistoricalInput(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise RuntimeError('Historical source preparation: ' + message)


def git(root, *parts):
    environment = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', '--no-replace-objects', *parts], cwd=root,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=environment)


def checked(root, *parts):
    result = git(root, *parts)
    require(result.returncode == 0, 'Git prerequisite failed: ' + repr(parts))
    return result.stdout


def object_bytes(root, kind, oid):
    result = git(root, 'cat-file', kind, oid)
    if result.returncode != 0:
        raise MissingHistoricalInput('Required ' + kind + ' object unavailable: ' + oid)
    raw = result.stdout
    require(hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid,
            'actual Git object bytes differ from fixed identity')
    return raw


def entry(raw, name):
    rows, offset = {}, 0
    while offset < len(raw):
        space, zero = raw.index(b' ', offset), raw.index(b'\0', offset)
        mode, basename = raw[offset:space], raw[space + 1:zero]
        require(zero + 21 <= len(raw) and basename not in rows, 'malformed historical tree')
        rows[basename] = (mode, raw[zero + 1:zero + 21].hex())
        offset = zero + 21
    require(name.encode() in rows, 'fixed path absent from historical tree')
    return rows[name.encode()]


def verify_group(root, group):
    owner, tree, files = group
    commit = object_bytes(root, 'commit', owner)
    headers = commit.split(b'\n\n', 1)[0].splitlines()
    require([row[5:].decode() for row in headers if row.startswith(b'tree ')] == [tree],
            'fixed owner commit does not own the fixed tree')
    cache, observed = {}, []
    for path, (blob, size, sha256) in files.items():
        current = tree
        for index, component in enumerate(path.split('/')):
            if current not in cache:
                cache[current] = object_bytes(root, 'tree', current)
            mode, current = entry(cache[current], component)
            require(mode == (b'100644' if index == len(path.split('/')) - 1 else b'40000'),
                    'fixed historical path mode differs')
        require(current == blob, 'fixed historical path resolves to another blob')
        raw = object_bytes(root, 'blob', blob)
        require(len(raw) == size and hashlib.sha256(raw).hexdigest() == sha256, 'whole historical source differs')
        observed.append(dict(path=path, blob=blob, bytes=size, sha256=sha256))
    return dict(ownerCommit=owner, tree=tree, files=observed)


def checkout_state(root):
    source = checked(root, 'rev-parse', 'HEAD').decode().strip()
    tree = checked(root, 'rev-parse', 'HEAD^{tree}').decode().strip()
    require(re.fullmatch('[0-9a-f]{40}', source) and re.fullmatch('[0-9a-f]{40}', tree), 'actual HEAD and tree required')
    require(not checked(root, 'status', '--porcelain', '--untracked-files=no').strip(), 'current tracked source must be clean')
    index = hashlib.sha256(checked(root, 'ls-files', '--stage', '-z')).hexdigest()
    return dict(sourceCommit=source, sourceTree=tree, indexEntriesSha256=index)


def authorize_fetch(root, environment):
    require(environment.get('CI') == 'true' and environment.get('GITHUB_ACTIONS') == 'true'
            and environment.get('GITHUB_SERVER_URL') == 'https://github.com'
            and environment.get('GITHUB_REPOSITORY') == REPOSITORY, 'missing history requires this actual GitHub CI repository')
    for key, maximum in (('GITHUB_RUN_ID', 20), ('GITHUB_RUN_ATTEMPT', 10)):
        value = environment.get(key)
        require(isinstance(value, str) and re.fullmatch('[1-9][0-9]{0,' + str(maximum - 1) + '}', value), 'actual positive workflow identity required')
    source = environment.get('GITHUB_SHA')
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source), 'actual current source commit required')
    require(checked(root, 'rev-parse', '--show-toplevel').decode().strip() == str(root), 'current checkout root differs')
    state = checkout_state(root)
    require(state['sourceCommit'] == source, 'workflow source differs from current checkout')
    require(checked(root, 'remote', 'get-url', 'origin').decode().strip() in ORIGINS, 'fixed GitHub origin required')
    return state


def prepare_original_history(root, environment=None):
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    ready, missing = {}, []
    for group in GROUPS:
        try:
            ready[group[0]] = verify_group(root, group)
        except MissingHistoricalInput:
            missing.append(group)
    fetches = []
    if missing:
        state = authorize_fetch(root, environment)
        for group in missing:
            # One exact public commit per missing group. No branch, tag,
            # FETCH_HEAD, worktree, index or original oracle is replaced.
            try:
                checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin', group[0])
            finally:
                require(checkout_state(root) == state, 'fetch changed HEAD, tree, index or tracked worktree')
            fetches.append(group[0])
            ready[group[0]] = verify_group(root, group)
    require(len(ready) == 2, 'both exact historical groups required')
    return dict(schema=1, status='verified-original-historical-inputs', groups=[ready[g[0]] for g in GROUPS],
                fetchedOwnerCommits=fetches, originalAssertionsExecuted=False, actualAndroidExecution=False,
                scope='Finite original source-oracle input preparation only; original tests must still run and pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    arguments = parser.parse_args()
    print(json.dumps(prepare_original_history(arguments.root), sort_keys=True))
