"""Publish an immutable CI tree without overwriting a concurrent artifact writer."""
import re
import subprocess
import sys


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
            subprocess.run(['git', 'fetch', '--depth=1', '--no-tags', 'origin', ref], cwd=root, check=True)
            fetched = subprocess.check_output(['git', 'rev-parse', 'FETCH_HEAD'], cwd=root, text=True).strip()
            if fetched != previous[0]:
                raise RuntimeError('Public artifact branch changed during bounded fetch')
            parents += ['-p', fetched]
        commit = subprocess.check_output(['git', 'commit-tree', tree, *parents, '-m', message],
                                         cwd=root, env=env, text=True).strip()
        command = ['git', '-c', 'http.postBuffer=524288000', 'push', 'origin', commit + ':' + ref]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        if result.returncode == 0:
            return commit
        print(result.stderr, file=sys.stderr, end='')
        # Only retry an actual non-fast-forward ref conflict. The same already
        # verified tree is reused; no build or application workload is rerun.
        conflict = '[rejected]' in result.stderr and any(
            marker in result.stderr for marker in ('fetch first', 'non-fast-forward'))
        if not conflict or attempt + 1 == attempts:
            raise subprocess.CalledProcessError(result.returncode, command,
                                                output=result.stdout, stderr=result.stderr)
    raise RuntimeError('CI artifact ref publication exhausted')
