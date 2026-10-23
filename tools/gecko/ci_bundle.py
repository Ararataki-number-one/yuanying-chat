#!/usr/bin/env python3
"""Transfer one CI build to short Android jobs; preserve exact bytes and run identity."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path('work/gecko-integration')
BUILD_INDEX = OUT / 'ci-build-index.json'
PHASES = ('ui', 'editing', 'files', 'connections', 'profiles')
LOCAL_REPORTS = {'native-test.log', 'emulator.log', 'runner-health.txt', 'adb-transport.txt', 'emulator-bootstrap-results.json', 'android-system-image-results.json', 'android-emulator-package-results.json', 'android-platform-tools-results.json', 'native-adb-setup-results.json'}
INTEGRATION = Path('app/build/outputs/apk/integration/app-x86_64-integration.apk')
RELEASE = Path('app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk')
SDK = Path('work/native-caret-sdk')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def identity(root):
    def git(*parts):
        return subprocess.check_output(['git', *parts], cwd=root, text=True).strip()
    result = dict(sourceCommit=git('rev-parse', 'HEAD'), sourceTree=git('rev-parse', 'HEAD^{tree}'),
                  runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'))
    assert result['runId'].isdigit() and result['runAttempt'].isdigit()
    assert not git('status', '--porcelain'), 'CI bundle requires clean committed source'
    return result


def allowed(name, kind):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name:
        return False
    if path.suffix.lower() in ('.jks', '.p12', '.keystore', '.pem'):
        return False
    if kind == 'build' and name in (str(INTEGRATION), str(RELEASE)):
        return True
    if kind == 'build' and path.parent == PurePosixPath(str(SDK)):
        return path.name in ('geckoview-caret.aar', 'sdk-build-receipt.json') or path.suffix == '.json'
    if path.parent == PurePosixPath(str(OUT)):
        suffixes = ('.json', '.jar', '.apk', '.aar', '.pom', '.log', '.xml') if kind == 'build' else ('.json', '.png', '.xml', '.txt', '.log')
        return path.suffix in suffixes and path.name not in ('ui-current.apk', BUILD_INDEX.name)
    return kind == 'phase' and path.parent in (PurePosixPath(str(OUT / 'caret-compat')), PurePosixPath(str(OUT / 'ui-visuals'))) and path.suffix in ('.json', '.png', '.xml', '.txt', '.log')


def pack(root, target, kind, phase=None):
    current = identity(root)
    assert kind in ('build', 'phase') and (kind == 'build' or phase in PHASES)
    baseline = {}
    if kind == 'phase':
        build_raw = (root / BUILD_INDEX).read_bytes()
        build = json.loads(build_raw)
        assert build['kind'] == 'build' and all(build[key] == value for key, value in current.items())
        baseline = {item['path']: item['sha256'] for item in build['files']}
    candidates = [p for p in (root / OUT).glob('*') if p.is_file()]
    if kind == 'build':
        candidates += [root / INTEGRATION, root / RELEASE]
        candidates += [p for p in (root / SDK).glob('*') if p.is_file()]
        assert all((root / name).is_file() for name in (INTEGRATION, RELEASE, SDK / 'sdk-build-receipt.json', SDK / 'geckoview-caret.aar'))
    else:
        for directory in ('caret-compat', 'ui-visuals'):
            candidates += [p for p in (root / OUT / directory).glob('*') if p.is_file()]
    files = []
    for path in sorted(set(candidates)):
        name = path.relative_to(root).as_posix()
        if not allowed(name, kind):
            continue
        assert not path.is_symlink(), 'CI bundle refuses symbolic links'
        sha = digest(path)
        if baseline.get(name) == sha:
            continue
        files.append(dict(path=name, bytes=path.stat().st_size, sha256=sha))
    manifest = dict(schema=1, kind=kind, **current, files=files)
    if kind == 'phase':
        manifest.update(phase=phase, buildIndexSha256=hashlib.sha256(build_raw).hexdigest())
    raw = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, 'w:gz', compresslevel=1) as archive:
        info = tarfile.TarInfo('_ci_bundle.json'); info.size = len(raw)
        archive.addfile(info, io.BytesIO(raw))
        for item in files:
            archive.add(root / item['path'], arcname=item['path'], recursive=False)
    return manifest


def restore(root, bundle, kind, phase=None):
    current = identity(root)
    with tarfile.open(bundle, 'r:gz') as archive:
        members = archive.getmembers()
        assert len({m.name for m in members}) == len(members), 'Duplicate CI archive path'
        assert all(m.isfile() for m in members), 'CI archive contains a non-regular entry'
        raw = archive.extractfile('_ci_bundle.json').read()
        manifest = json.loads(raw)
        assert type(manifest['schema']) is int and manifest['schema'] == 1 and manifest['kind'] == kind
        assert all(manifest.get(key) == value for key, value in current.items()), 'CI bundle belongs to another source/run/attempt'
        files = manifest['files']
        assert isinstance(files, list) and len(files) <= 5000
        assert len({row['path'] for row in files}) == len(files)
        assert {m.name for m in members} == {'_ci_bundle.json'} | {row['path'] for row in files}
        if kind == 'phase':
            assert phase in PHASES and manifest['phase'] == phase, 'Unexpected Android phase'
            assert manifest['buildIndexSha256'] == digest(root / BUILD_INDEX), 'Android phase used another compiled build'
        # Validate every entry before writing any destination.
        for row in files:
            assert allowed(row['path'], kind), 'CI archive path outside the exact input/evidence roots'
            member = archive.getmember(row['path'])
            assert type(row['bytes']) is int and member.size == row['bytes'] and 0 <= member.size <= 1024 ** 3
            value = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(block)
            assert value.hexdigest() == row['sha256'], 'CI archive byte hash differs'
        for row in files:
            relative = Path(row['path']); targets = [root / relative]
            if kind == 'phase' and relative.parent == OUT and relative.name in LOCAL_REPORTS:
                targets = [root / OUT / 'ci-phases' / phase / relative.name]
                if phase == 'files':
                    targets.append(root / relative)
            for target in targets:
                assert not target.is_symlink()
                if target.exists():
                    assert target.is_file() and digest(target) == row['sha256'], 'Different phases cannot overwrite evidence: ' + str(relative)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(row['path']) as source, target.open('xb') as destination:
                    import shutil
                    shutil.copyfileobj(source, destination, 1024 * 1024)
    if kind == 'build':
        (root / BUILD_INDEX).write_bytes(raw)
        # UI capture installs the exact same integration bytes, without rebuilding.
        import shutil
        shutil.copy2(root / INTEGRATION, root / OUT / 'ui-current.apk')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('pack', 'restore'))
    parser.add_argument('--kind', choices=('build', 'phase'), required=True)
    parser.add_argument('--phase', choices=PHASES)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    manifest = (pack(ROOT, args.bundle, args.kind, args.phase) if args.operation == 'pack'
                else restore(ROOT, args.bundle, args.kind, args.phase))
    print(json.dumps(dict(operation=args.operation, kind=manifest['kind'], phase=manifest.get('phase'),
                         sourceCommit=manifest['sourceCommit'], files=len(manifest['files']),
                         runId=manifest['runId'], runAttempt=manifest['runAttempt'])))


if __name__ == '__main__':
    main()
