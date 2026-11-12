#!/usr/bin/env python3
"""Prepare pinned public history before unchanged profile host tests run."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('profile_host_public_history', ROOT / 'tools/browser/source_history.py')
history = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(history)


def require(condition, message):
    if not condition:
        raise RuntimeError('Profile host prerequisites: ' + message)


def authorize_fetch(root, source, environment):
    """Authorize the actual checkout using the event, without rewriting GITHUB_SHA."""
    require(environment.get('CI') == 'true' and environment.get('GITHUB_ACTIONS') == 'true'
            and environment.get('GITHUB_SERVER_URL') == 'https://github.com'
            and environment.get('GITHUB_REPOSITORY') == history.REPOSITORY,
            'missing history requires the fixed repository GitHub CI')
    for key, maximum in (('GITHUB_RUN_ID', 20), ('GITHUB_RUN_ATTEMPT', 10)):
        require(isinstance(environment.get(key), str)
                and re.fullmatch('[1-9][0-9]{0,' + str(maximum - 1) + '}', environment[key]),
                'positive workflow run and attempt required')
    require(re.fullmatch('[0-9a-f]{40}', environment.get('GITHUB_SHA', '')),
            'actual workflow SHA required')
    event_path = Path(environment.get('GITHUB_EVENT_PATH', ''))
    require(event_path.is_file() and not event_path.is_symlink() and event_path.stat().st_size <= 2 * 1024 * 1024,
            'bounded actual GitHub event required')
    event = json.loads(event_path.read_bytes())
    require(type(event) is dict and type(event.get('repository')) is dict
            and event['repository'].get('full_name') == history.REPOSITORY,
            'event repository differs')
    name, ref = environment.get('GITHUB_EVENT_NAME'), environment.get('GITHUB_REF')
    if name == 'pull_request':
        pull = event.get('pull_request')
        number = event.get('number')
        require(type(pull) is dict and type(number) is int and number > 0
                and ref == 'refs/pull/' + str(number) + '/merge', 'actual pull request event required')
        require(pull.get('head', {}).get('sha') == source
                and pull.get('base', {}).get('repo', {}).get('full_name') == history.REPOSITORY,
                'event pull request head or base repository differs')
    elif name == 'push':
        require(environment['GITHUB_SHA'] == source and event.get('after') == source
                and event.get('ref') == ref and isinstance(ref, str)
                and ref.startswith(('refs/heads/', 'refs/tags/')), 'push source or ref differs')
    elif name == 'workflow_dispatch':
        require(environment['GITHUB_SHA'] == source and isinstance(ref, str)
                and ref.startswith(('refs/heads/', 'refs/tags/'))
                and event.get('ref') in (ref, ref.split('/', 2)[2]), 'dispatch source or ref differs')
    else:
        require(False, 'unsupported workflow event')
    require(history.checked(root, 'rev-parse', '--show-toplevel').decode().strip() == str(root),
            'checkout root differs')
    require(history.checked(root, 'remote', 'get-url', 'origin').decode().strip() in history.ORIGINS,
            'fixed public GitHub origin required')
    require(not history.checked(root, 'status', '--porcelain', '--untracked-files=no').strip(),
            'tracked checkout must be clean before network fetch')


def prepare_history(root=ROOT, *, source_commit, environment=None):
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact checkout source commit required')
    groups = history.manifest(root)
    require(len(groups) == 21, 'all twenty-one fixed historical owner groups required')
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'requested source differs from actual checkout')
    missing = []
    for group in groups:
        try:
            history.verify_group(root, group)
        except history.MissingHistoricalObject:
            missing.append(group['commit'])
    if missing:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before history fetch')
        try:
            # Exact owners only: no ref updates or lazy/test-time retrieval.
            # --no-filter also supplies blobs in local partial-clone checkouts.
            history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                            '--no-filter', 'origin', *missing)
        finally:
            require(history.checkout_state(root) == before,
                    'history fetch changed HEAD, tree, index or tracked bytes')
    observed = [history.verify_group(root, group) for group in groups]
    require(history.checkout_state(root) == before, 'history verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                manifestSha256=history.MANIFEST_SHA256, groups=observed, fetchedCommits=missing,
                checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)


# These are the existing compatibility declarations and their existing whole-
# fixture digests. The original twenty-one-owner inventory above stays intact.
# No inverse is applied: tests continue reading the actual historical Git blobs.
COMPATIBILITY_DECLARATIONS = (
    ('gradle-transport-source-deltas.json', '0e34228b10f4ecb511c584f5fc071e06ffd87e6981caddd80b0510897fbcc793', 'base', 'previous'),
    ('gradle-workflow-test-source-deltas.json', '5d1f33ee4997b73e4c8785fbac39e831311247b5cae7c6d3e8c6182a8350a6ee', 'base', 'previous'),
    ('glass-diagnostic-source-deltas.json', '8aae6519cefb08e232b6f33849a6b03bbba5e5b468a504c850ea8694a5f8acf5', 'base', 'previous'),
    ('ui-navigation-source-deltas.json', '98c2c894fc4eda4adc28d06064943af7b68a99e9c4270b2ed32dafc21bf80775', 'reviewed', 'reviewed'),
    ('environment-workspace-workflow-source-deltas.json', 'c7124c5d48a58ef71204e236941d84cf6408194b39af2520ace79b120e3358de', 'previous', 'previous'),
)
COMPATIBILITY_OWNERS = frozenset((
    '7402ead321ca74b9fbefeab32a1aaffb32832011',
    '4363dbc04df80d5c82ba966248e47a3fd69cbcc8',
    '4e99ab57a4d58a2ce7ab4d7d8d0c3362da41cd2e',
))
# The unchanged workflow/diagnostic compatibility tests also read these paths
# directly from the same declared owners. Their Git identities come from
# that fixed tree; the existing tests retain their original content assertions.
COMPATIBILITY_DIRECT_READS = {
    '7402ead321ca74b9fbefeab32a1aaffb32832011': (
        'tests/resource_startup_source_compatibility.py',
        'tests/fixtures/profile-fixture-root-source-deltas.json',
        'tests/fixtures/resource-startup-source-deltas.json',
        'tests/fixtures/final-browser-source-deltas.json',
    ),
    '4363dbc04df80d5c82ba966248e47a3fd69cbcc8': (
        'tests/profile_editing_transport13_diagnostic_test.py',
    ),
}


def compatibility_groups(root):
    groups, declarations = {}, []
    for name, digest, owner_prefix, file_prefix in COMPATIBILITY_DECLARATIONS:
        path = Path(root) / 'tests/fixtures' / name
        require(path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
                and 0 < path.stat().st_size <= 65536, 'ordinary bounded compatibility declaration required')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'existing compatibility declaration bytes differ')
        value = json.loads(raw)
        owner, tree = value[owner_prefix + 'Commit'], value[owner_prefix + 'Tree']
        require(owner in COMPATIBILITY_OWNERS and re.fullmatch('[0-9a-f]{40}', tree),
                'fixed compatibility owner/tree required')
        group = groups.setdefault(owner, dict(commit=owner, tree=tree, files={}))
        require(group['tree'] == tree, 'compatibility declarations disagree on owner tree')
        rows = value['files'] if 'files' in value else {value['path']: value}
        for relative, row in rows.items():
            pin = dict(bytes=row[file_prefix + 'Bytes'], sha256=row[file_prefix + 'Sha256'])
            require(type(relative) is str and re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', relative)
                    and not relative.startswith('/') and all(part not in ('', '.', '..') for part in relative.split('/'))
                    and type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 * 1024 * 1024
                    and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'bounded compatibility source pin required')
            require(relative not in group['files'] or group['files'][relative] == pin,
                    'compatibility declarations disagree on source bytes')
            group['files'][relative] = pin
        declarations.append(dict(path=str(path.relative_to(root)), bytes=len(raw), sha256=digest,
                                 commit=owner, tree=tree, sourceView=file_prefix))
    require(set(groups) == COMPATIBILITY_OWNERS, 'all three fixed compatibility owners required')
    for owner, paths in COMPATIBILITY_DIRECT_READS.items():
        for path in paths:
            groups[owner]['files'].setdefault(path, {})
    return list(groups.values()), declarations


def compatibility_object_bytes(root, kind, identity):
    """Only Git's explicit missing response authorizes a supplemental fetch."""
    require(kind in ('commit', 'tree', 'blob') and re.fullmatch('[0-9a-f]{40}', identity),
            'exact compatibility object kind/identity required')
    environment = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', '--no-replace-objects', 'cat-file', '--batch-check=%(objectname) %(objecttype)'],
                            input=(identity+'\n').encode(), cwd=root, capture_output=True, timeout=120, env=environment)
    require(result.returncode == 0 and not result.stderr, 'compatibility object probe failed')
    if result.stdout == (identity+' missing\n').encode():
        raise history.MissingHistoricalObject(kind+' compatibility object unavailable: '+identity)
    require(result.stdout == (identity+' '+kind+'\n').encode(), 'compatibility object type differs')
    try:
        return history.object_bytes(root, kind, identity)
    except history.MissingHistoricalObject as error:
        # A probe established that the object exists. Corruption or a later
        # read failure must remain an error, never a request to fetch again.
        raise RuntimeError('Compatibility object became unreadable after its type probe') from error


def verify_compatibility_group(root, group):
    commit = compatibility_object_bytes(root, 'commit', group['commit'])
    trees = [line[5:].decode() for line in commit.split(b'\n\n', 1)[0].splitlines() if line.startswith(b'tree ')]
    require(trees == [group['tree']], 'compatibility commit does not own declared tree')
    cache, observed = {}, []
    for relative, pin in group['files'].items():
        identity = group['tree']
        parts = relative.split('/')
        for index, part in enumerate(parts):
            if identity not in cache:
                cache[identity] = compatibility_object_bytes(root, 'tree', identity)
            mode, identity = history.entry(cache[identity], part)
            require(mode == ('100644' if index == len(parts)-1 else '40000'), 'compatibility source mode differs')
        raw = compatibility_object_bytes(root, 'blob', identity)
        digest = hashlib.sha256(raw).hexdigest()
        if pin:
            require(len(raw) == pin['bytes'] and digest == pin['sha256'], 'declared historical source bytes differ')
        observed.append(dict(path=relative, mode=mode, blob=identity, bytes=len(raw), sha256=digest,
                             declarationContentPinChecked=bool(pin)))
    return dict(commit=group['commit'], tree=group['tree'], files=observed)


def prepare_compatibility_history(root=ROOT, *, source_commit, environment=None):
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact compatibility checkout source required')
    groups, declarations = compatibility_groups(root)
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'compatibility source differs from actual checkout')
    missing = []
    for group in groups:
        try:
            verify_compatibility_group(root, group)
        except history.MissingHistoricalObject:
            missing.append(group['commit'])
    if missing:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before compatibility fetch')
        try:
            history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                            '--no-filter', 'origin', *missing)
        finally:
            require(history.checkout_state(root) == before,
                    'compatibility fetch changed HEAD, tree, index or tracked bytes')
    observed = [verify_compatibility_group(root, group) for group in groups]
    require(history.checkout_state(root) == before, 'compatibility verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                declarations=declarations, groups=observed, fetchedCommits=missing, checkoutUnchanged=True,
                testsExecuted=False, actualAndroidExecution=False,
                scope='Setup-only exact declared compatibility owners and linked blobs; no test/source projection or ref update.')


FIXTURE_ROOT_DECLARATION = 'tests/fixtures/profile-fixture-root-source-deltas.json'
FIXTURE_ROOT_DECLARATION_SHA256 = 'edad6886ab8867e8d76249de55f9ed23d1b664f830039eaf8e04caf9f9f19e1a'
FIXTURE_ROOT_OWNER = '6ee06aced87581e52aa301431f8996ed46d666b8'
FIXTURE_ROOT_TREE = '19b74a878d2c238cdb209dd51d2fb66076057963'
FIXTURE_ROOT_PATHS = frozenset((
    'tests/gecko/FingerprintFollowupIntegrationActivity.java',
    'tests/dual_browser_source_compatibility.py',
    'tests/profile_dual_browser_source_compatibility_test.py',
    'tests/profile_worker_timezone_source_compatibility_test.py',
    'tests/final_browser_source_compatibility.py',
))
# Original environment-workflow tests read these eight additional paths from
# this exact owner. Keep them separate from the original three-owner/15-file
# compatibility inventory, including when that inventory is already present.
ENVIRONMENT_WORKFLOW_OWNER = '4e99ab57a4d58a2ce7ab4d7d8d0c3362da41cd2e'
ENVIRONMENT_WORKFLOW_TREE = '5af60118121ccdc5bff9410dc13e20b05af9b391'
ENVIRONMENT_WORKFLOW_DIRECT_READS = (
    ('tests/baselines/public-source-history.json', '00d2d1da28b99e4df5a3ff68a84213f0ec81daa0', 72888,
     '52831c72831c3d1ed43ae040efeef9436fb9b71ba78aa5a8ec6f0b4e3be6e745'),
    ('tests/profile_gradle_workflow_test_source_compatibility_test.py', '9cccb334856513cff2ae1bcffb9d1e2c0945604c', 6740,
     '7546f7a434ed3df4aff2cd33be578ad789a05b8025f16955c8485cfa602799c2'),
    ('tests/fixtures/gradle-transport-source-deltas.json', 'e2b42f0ca4e8424d8dadff454fca102311e0ee31', 7634,
     '0e34228b10f4ecb511c584f5fc071e06ffd87e6981caddd80b0510897fbcc793'),
    ('tests/fixtures/gradle-workflow-test-source-deltas.json', 'a0bf8faaa0ca7c04ddc22a311810c3a5b51ae23e', 57151,
     '5d1f33ee4997b73e4c8785fbac39e831311247b5cae7c6d3e8c6182a8350a6ee'),
    ('tests/fixtures/profile-glass-host-workflow-deltas.json', '386dad6063e94adba8b001e0c217441ae7261c2d', 13489,
     'f2b563999c2ac4a927763a31d564942408c44e036346fb99333763f18d9c3cbb'),
    ('tests/profile_display_sampling_gate_test.py', '054c9f1bd7dfe5bdc18f6c2be0f84b9f1b0ba86e', 54881,
     'd612567c69b17922129bd8f3076b55a440e24c4b2d55f44472f60c7f92fa5a1e'),
    ('tests/profile_gradle_transport_source_compatibility_test.py', '36ab997a7821ca9f26fe9e1a0975615f1770be5b', 7276,
     '7dc62f3fbef23332d7a44cc6db0da0bcf2cc463862d79d3c1d6c413202c967de'),
    ('tests/fixtures/glass-diagnostic-source-deltas.json', 'd527bc8d298a517d3fda168a939ab0fb8a9af9cc', 7772,
     '7c08ced00a0b0ab77306037360f158694b84d3fb4a61e7322122d633e3b21721'),
)


def fixture_root_group(root):
    """Read the existing five whole-byte pins without extending either inventory."""
    path = Path(root) / FIXTURE_ROOT_DECLARATION
    require(path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
            and 0 < path.stat().st_size <= 65536, 'ordinary bounded fixture-root declaration required')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == FIXTURE_ROOT_DECLARATION_SHA256,
            'existing fixture-root declaration bytes differ')
    value = json.loads(raw)
    require(value['baseCommit'] == FIXTURE_ROOT_OWNER and value['baseTree'] == FIXTURE_ROOT_TREE
            and set(value['files']) == FIXTURE_ROOT_PATHS, 'fixed fixture-root owner/tree/paths required')
    group = dict(commit=FIXTURE_ROOT_OWNER, tree=FIXTURE_ROOT_TREE, files={})
    for relative in sorted(FIXTURE_ROOT_PATHS):
        row = value['files'][relative]
        pin = dict(bytes=row['previousBytes'], sha256=row['previousSha256'])
        require(type(pin['bytes']) is int and 0 < pin['bytes'] <= 4 * 1024 * 1024
                and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'bounded fixture-root source pin required')
        group['files'][relative] = pin
    declaration = dict(path=FIXTURE_ROOT_DECLARATION, bytes=len(raw), sha256=FIXTURE_ROOT_DECLARATION_SHA256,
                       commit=FIXTURE_ROOT_OWNER, tree=FIXTURE_ROOT_TREE, sourceView='previous')
    return group, declaration


def supplemental_groups(root):
    fixture_group, declaration = fixture_root_group(root)
    environment_group = dict(commit=ENVIRONMENT_WORKFLOW_OWNER, tree=ENVIRONMENT_WORKFLOW_TREE,
        files={path: dict(blob=blob, bytes=size, sha256=digest)
               for path, blob, size, digest in ENVIRONMENT_WORKFLOW_DIRECT_READS})
    return [fixture_group, environment_group], [declaration]


def verify_supplemental_group(root, group):
    observed = verify_compatibility_group(root, group)
    for row in observed['files']:
        pin = group['files'][row['path']]
        if 'blob' in pin:
            require(row['blob'] == pin['blob'], 'supplemental historical blob identity differs')
    return observed


def prepare_supplemental_history(root=ROOT, *, source_commit, environment=None):
    """Prepare the remaining original reads before any host test is executed."""
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact supplemental checkout source required')
    groups, declarations = supplemental_groups(root)
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'supplemental source differs from actual checkout')
    missing = []
    for group in groups:
        try:
            verify_supplemental_group(root, group)
        except history.MissingHistoricalObject:
            missing.append(group['commit'])
    if missing:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before supplemental fetch')
        try:
            history.checked(root, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                            '--no-filter', 'origin', *missing)
        finally:
            require(history.checkout_state(root) == before,
                    'supplemental fetch changed HEAD, tree, index or tracked bytes')
    observed = [verify_supplemental_group(root, group) for group in groups]
    require(history.checkout_state(root) == before, 'supplemental verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                declarations=declarations, groups=observed, fetchedCommits=missing, checkoutUnchanged=True,
                testsExecuted=False, actualAndroidExecution=False,
                scope='Setup-only five original fixture-root blobs and eight original environment-workflow direct reads; no test/source projection or ref update.')


RELEASED_PROOF_COMMIT = '7383bb1dd82c5d2155ba7c8dcc11b541478f6cfe'
RELEASED_PROOF_TREE = '56be467a913681f60dac48cefeedfce119b0a361'


def released_proof_objects(root):
    """Check fixed ownership and object presence, without walking parent history.

This is a setup completeness check. The explicit historical reader separately
verifies the SHA-1 and path ownership of every blob it actually reads. Merely
being present here is never reported as a passed behavior or source proof.
"""
    commit = compatibility_object_bytes(root, 'commit', RELEASED_PROOF_COMMIT)
    trees = [line[5:].decode() for line in commit.split(b'\n\n', 1)[0].splitlines() if line.startswith(b'tree ')]
    require(trees == [RELEASED_PROOF_TREE], 'released proof commit does not own the fixed tree')
    compatibility_object_bytes(root, 'tree', RELEASED_PROOF_TREE)
    raw = history.checked(root, 'rev-list', '--objects', '--no-object-names',
                          '--missing=print', RELEASED_PROOF_TREE)
    require(len(raw) <= 1024 * 1024, 'released proof object closure exceeds setup bound')
    rows = raw.decode('ascii').splitlines()
    require(0 < len(rows) <= 8192 and len(rows) == len(set(rows))
            and all(re.fullmatch(r'\??[0-9a-f]{40}', row) for row in rows),
            'invalid released proof object closure')
    missing = [row[1:] for row in rows if row.startswith('?')]
    if missing:
        raise history.MissingHistoricalObject('Released proof tree has missing objects: ' + str(len(missing)))
    require(RELEASED_PROOF_TREE in rows, 'released proof closure omitted its root tree')
    return dict(commit=RELEASED_PROOF_COMMIT, tree=RELEASED_PROOF_TREE,
                reachableObjectsPresent=len(rows),
                objectIdentityListSha256=hashlib.sha256(('\n'.join(sorted(rows))+'\n').encode()).hexdigest(),
                commitAndRootTreeSha1Verified=True, objectPresenceOnly=True,
                individualReadBytesVerifiedBy='tests/historical_source_inputs.py')


def prepare_released_history(root=ROOT, *, source_commit, environment=None):
    """Prepare the real release owner independently of the original inventories."""
    root = Path(root).resolve()
    environment = os.environ if environment is None else environment
    require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit),
            'exact released-proof checkout source required')
    before = history.checkout_state(root)
    require(before['sourceCommit'] == source_commit, 'released-proof source differs from actual checkout')
    fetched = []
    try:
        observed = released_proof_objects(root)
    except history.MissingHistoricalObject:
        authorize_fetch(root, source_commit, environment)
        require(history.checkout_state(root) == before, 'checkout changed before released-proof fetch')
        try:
            # Refetch also repairs a partial object set whose owner is already
            # present. No branch, HEAD, index or FETCH_HEAD is updated.
            history.checked(root, 'fetch', '--refetch', '--no-tags', '--depth=1',
                            '--no-write-fetch-head', '--no-filter', 'origin', RELEASED_PROOF_COMMIT)
        finally:
            require(history.checkout_state(root) == before,
                    'released-proof fetch changed HEAD, tree, index or tracked bytes')
        fetched.append(RELEASED_PROOF_COMMIT)
        observed = released_proof_objects(root)
    require(history.checkout_state(root) == before, 'released-proof verification changed checkout')
    return dict(schema=1, status='passed', sourceCommit=source_commit, sourceTree=before['sourceTree'],
                releasedProof=observed, fetchedCommits=fetched, checkoutUnchanged=True,
                testsExecuted=False, actualAndroidExecution=False,
                scope='Setup-only fixed 2.1.4 owner/tree identity and complete object presence; actual historical reads separately verify every input blob; no source projection or ref update.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = prepare_history(args.root, source_commit=args.source_commit)
    value['compatibilityHistory'] = prepare_compatibility_history(args.root, source_commit=args.source_commit)
    value['supplementalHistory'] = prepare_supplemental_history(args.root, source_commit=args.source_commit)
    value['releasedHistory'] = prepare_released_history(args.root, source_commit=args.source_commit)
    raw = json.dumps(value, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw, end='')


if __name__ == '__main__':
    main()
