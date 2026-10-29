"""Publish an immutable CI tree without overwriting a concurrent artifact writer."""
import re
import subprocess
import sys


def _remote_ref_conflict(stderr, ref, commit):
    """Recognize only a failed remote CAS for this exact push destination."""
    if not re.search(r"(?m)^error: failed to push some refs to '[^'\r\n]+'$", stderr):
        return False
    destination = r'(?:' + re.escape(ref) + '|' + re.escape(ref.removeprefix('refs/heads/')) + ')'
    status = re.search(r'(?m)^[ \t]*![ \t]+\[remote rejected\][ \t]+' + re.escape(commit)
                       + r'[ \t]+->[ \t]+' + destination + r' \(([^\r\n]*)\)$', stderr)
    if status is None:
        return False
    cas = r"cannot lock ref '" + re.escape(ref) + r"': is at ([0-9a-f]{40}) but expected ([0-9a-f]{40})"
    conflict = re.fullmatch(cas, status[1])
    if status[1] == 'failed to update ref':
        conflict = re.search(r'(?m)^remote: error: ' + cas + '$', stderr)
    return conflict is not None and conflict[1] != conflict[2]


def push_tree(*, root, source, tree, branch, env, message, attempts=3):
    if not re.fullmatch(r'[0-9a-f]{40}', source) or not re.fullmatch(r'[0-9a-f]{40}', tree):
        raise ValueError('Exact source and artifact tree required')
    if not re.fullmatch(r'apk/[A-Za-z0-9_.-]+', branch) or type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError('Bounded CI artifact ref publication required')
    ref = 'refs/heads/' + branch
    for attempt in range(attempts):
        previous = subprocess.check_output(['git', 'ls-remote', 'origin', ref], cwd=root, text=True).split()
        parents = ['-p', source]
        if previous:
            if len(previous) != 2 or previous[1] != ref or not re.fullmatch(r'[0-9a-f]{40}', previous[0]):
                raise ValueError('Exact observed artifact ref identity required')
            # Fetch the observed immutable commit. Another writer may advance
            # the ref between ls-remote and fetch; a later non-fast-forward push
            # still takes the original bounded retry path without rerunning
            # the application workload or changing its verified artifact tree.
            subprocess.run(['git', 'fetch', '--depth=1', '--no-tags', 'origin', previous[0]], cwd=root, check=True)
            fetched = subprocess.check_output(['git', 'rev-parse', 'FETCH_HEAD'], cwd=root, text=True).strip()
            if fetched != previous[0]:
                raise RuntimeError('Fetched artifact commit differs from its immutable identity')
            parents += ['-p', fetched]
        commit = subprocess.check_output(['git', 'commit-tree', tree, *parents, '-m', message],
                                         cwd=root, env=env, text=True).strip()
        command = ['git', '-c', 'http.postBuffer=524288000', 'push', 'origin', commit + ':' + ref]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        if result.returncode == 0:
            return commit
        print(result.stderr, file=sys.stderr, end='')
        # Only retry an actual non-fast-forward or remote CAS ref conflict. The same already
        # verified tree is reused; no build or application workload is rerun.
        conflict = '[rejected]' in result.stderr and any(
            marker in result.stderr for marker in ('fetch first', 'non-fast-forward'))
        conflict = conflict or _remote_ref_conflict(result.stderr, ref, commit)
        if not conflict or attempt + 1 == attempts:
            raise subprocess.CalledProcessError(result.returncode, command,
                                                output=result.stdout, stderr=result.stderr)
    raise RuntimeError('CI artifact ref publication exhausted')
