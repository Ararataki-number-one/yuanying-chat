"""Prepare three exact historical inputs for unchanged profile source oracles.

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
    ('f263613422632740caed76505a20cb6696905003', 'fa5fa7aea024e8225781c7da651c740ff7a4a59d', {
        'app/src/main/java/local/pocketchat/BrowserReading.java': ('3dfc061c70de5869dcef7c5a8a2f1519f7477d96', 8637, '0dfe38b61010a787bbf66dd0df5c10ab9f4f43f2e3eea70bd2c5c7b098165dfc'),
        'app/src/main/java/local/pocketchat/BrowserReadingPolicy.java': ('d1faf6f7b66d70f69e752785beeb05cb01392db8', 4201, '889e227255f438d881cf7103bbed130c8989297dcd707d82241bdbecd163f2fd'),
        'tests/profile_reading_fit_completion_test.py': ('4c45d351eb9c4c959db0f716fa7ce190cb81d380', 18536, '8db811422515da902a615a8ba10f55e78950e106af430219d7bd0fc2ba571193'),
        'tests/profile_native43_source_compatibility_test.py': ('b15815598a4723aac708f47e8aa8835c63cadf47', 8270, '3e36d91feb39362f607e65179c99128ea4ac90091ee04c49d854ea8124c20636'),
        'tests/profile_reading_zoom_trace_test.py': ('b44ea2468d17b0baa87fa238b66abe4c28c47a67', 13158, '5927302dae44225c3c2cc006f8f3ddbc9a69d098c8ef88df0f7ace0946867fe0'),
        'app/src/main/java/local/pocketchat/GeckoWebView.java': ('02452dcb4ac47f9a7765bbf014060fb7ec42162a', 70564, '32e06089272bbbaf63ed94449ea208cd2feb930cc05a903ab3e83efb0f140546'),
        'app/src/main/java/local/pocketchat/ChatSession.java': ('c2111e2d6193506a2415c7015966d4f675e0f530', 69541, '0e0d3b49066ac09c87f072b755d6702d2ded23c8ed66afe545dc7c34ffe4c61c'),
        'tests/native43_source_compatibility.py': ('88ba6b6508f7570c178343c1b44690154ae47835', 2100, 'bcfd5225bcfd4062dce70fe831da0b376e0e624d561498831ce55a565582e535'),
        'tests/browser-reading-host/local/pocketchat/ChatSession.java': ('7b9d6e6a28a7e8d38ca00a5bbdec990de61940dd', 3063, '366b6de6e82de8ff8f71226bfb0f15a0125fcb66930f97e82e8c993a222c67ff'),
        'tests/browser-reading-host/local/pocketchat/BrowserReadingHostTest.java': ('b0bfeb7fe4afd21c4a0675a5fbd4f1b199bf0493', 25274, '8e29601536facc3c49a64346b523fdcc671159cfd2f8d414ec72a129a7bd9a3e'),
        'tests/gecko/GeckoIntegrationTestActivity.java': ('0a0bdfcf4acda4de28f50c869c8604237dd67598', 123686, 'd79a5f95b521a909a5ef5bfb0ce68a9156cea5f3bdea5657bdd571a705dc4f8f'),
        'tests/gecko/run_device.py': ('fb8e09d74ceddd57e1683e22b6f60f43f8d6e87f', 88701, '54fa412be9f89e46d61597caf61b0246e451e6c9b5eebca592e36b05686ab8a6'),
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
    require(len(ready) == 3, 'all three exact historical groups required')
    return dict(schema=1, status='verified-original-historical-inputs', groups=[ready[g[0]] for g in GROUPS],
                fetchedOwnerCommits=fetches, originalAssertionsExecuted=False, actualAndroidExecution=False,
                scope='Finite original source-oracle input preparation only; original tests must still run and pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    arguments = parser.parse_args()
    print(json.dumps(prepare_original_history(arguments.root), sort_keys=True))
