#!/usr/bin/env python3
"""Export clean, source-bound sequential review patches; never build or publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
BASE = '6a1bab77f1bcc70f0fc4f990b287fec08ec54412'
VERSIONS = [('1.6.0', 'codex/v1.6-network-environments'),
            ('1.7.0', 'codex/v1.7-templates-audit'),
            ('2.0.0', 'codex/v2.0-maintenance-capabilities')]
EVIDENCE_FILES = {'profile-host-results.json', 'native-capability-host-results.json',
                  'resource-policy-host-results.json', 'inventory-results.json',
                  'review-source-verification.json'}


def git(*args, root=ROOT):
    return subprocess.check_output(['git', *args], cwd=root)


def release_argument(value):
    version, separator, reference = value.partition('=')
    if not separator or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or not reference or reference.startswith('-'):
        raise argparse.ArgumentTypeError('Use VERSION=REF, for example 1.6.0=codex/v1.6-network-environments')
    return version, reference


def validate_output(root, output):
    root, output = root.resolve(), output.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError('Output must not contain or replace the source repository')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output must be new or empty; a previous export is never reused')
    return output


def evidence_record(path, commits):
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get('sourceCommit') not in commits:
        raise ValueError('Evidence is not bound to an exported source commit: ' + path.name)
    if value.get('sourceDirty') is not False or value.get('sourceTree') != commits[value['sourceCommit']]:
        raise ValueError('Evidence requires the exact clean exported source tree: ' + path.name)
    if value.get('actualAndroidExecution') is not False:
        raise ValueError('This host review package accepts only explicitly scoped host evidence: ' + path.name)
    return value


def export(root, output, baseline, releases, evidence_dir=None):
    output = validate_output(root, output)
    if len(releases) != 3 or len({version for version, _ in releases}) != 3:
        raise ValueError('Exactly three distinct sequential release versions are required')
    baseline_commit = git('rev-parse', '--verify', baseline + '^{commit}', root=root).decode().strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='profile-upgrades-stage-', dir=output.parent) as temp:
        staging = Path(temp) / 'export'
        staging.mkdir()
        files = []
        def write(name, data):
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe export path')
            destination = staging / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
            files.append(path.as_posix())
        prior = baseline_commit
        baseline_settings = git('show', baseline_commit + ':app/build.gradle', root=root).decode()
        code_match = re.search(r'versionCode ([0-9]+)', baseline_settings)
        if not code_match:
            raise ValueError('Baseline app versionCode is missing')
        prior_code = int(code_match.group(1))
        release_records = []
        for version, branch in releases:
            commit = git('rev-parse', '--verify', branch + '^{commit}', root=root).decode().strip()
            git('merge-base', '--is-ancestor', prior, commit, root=root)
            settings = git('show', commit + ':app/build.gradle', root=root).decode()
            name_match = re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'", settings)
            code_match = re.search(r'versionCode ([0-9]+)', settings)
            if not name_match or name_match.group(1) != version or not code_match or int(code_match.group(1)) <= prior_code:
                raise ValueError('Release version metadata differs or does not advance: ' + version)
            version_code = int(code_match.group(1))
            patch = git('format-patch', '--stdout', prior + '..' + commit, root=root)
            if not patch:
                raise ValueError('Missing implementation commits for ' + version)
            name = 'patches/' + version + '.patch'
            write(name, patch)
            release_records.append({'version': version, 'versionCode': version_code, 'branch': branch, 'commit': commit,
                                    'tree': git('rev-parse', commit + '^{tree}', root=root).decode().strip(),
                                    'parent': prior, 'patch': name})
            prior = commit
            prior_code = version_code
        changed = git('diff', '--name-only', '--diff-filter=ACMRT', '-z', baseline_commit, prior, root=root).decode().split('\0')
        for name in filter(None, changed):
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or any(part in {'work', 'private', 'secrets', 'dist', 'deliverables'} for part in path.parts):
                raise ValueError('Unsafe source export path: ' + name)
            write('source-delta/' + name, git('show', prior + ':' + name, root=root))
        deleted = git('diff', '--name-only', '--diff-filter=D', '-z', baseline_commit, prior, root=root).decode().split('\0')
        write('deleted-files.json', json.dumps(list(filter(None, deleted)), ensure_ascii=False, indent=2) + '\n')
        if evidence_dir:
            evidence = evidence_dir.resolve()
            commits = {record['commit']: record['tree'] for record in release_records}
            for name in sorted(EVIDENCE_FILES):
                path = evidence / name
                if path.is_file():
                    evidence_record(path, commits)
                    write('verification/' + name, path.read_bytes())
        tag = 'v1.5.23-gecko' if baseline_commit == BASE else baseline_commit
        readme = f'''PocketChat 1.6 → 1.7 → 2.0 候选源码交付\n\n基线 {tag}，源码 {baseline_commit}；未合并主分支、未发布 APK。\n在干净分支执行：\n  git switch -c review/profile-upgrades {tag}\n'''
        readme += ''.join('  git am /交付目录/' + record['patch'] + '\n' for record in release_records)
        readme += '''\n补丁按顺序应用，source-delta 是累计源码变更。请审查各版本实施和合并验收说明。\nverification 只包含绑定本包源码提交的主机报告，不代替官方 SDK 完整构建、\nAndroid/ARM 真机、真实登录、网页指纹或网络性能验收。\n2.0 仍使用官方 GeckoView：深层独立时区、Canvas/WebGL/音频/字体自定义\n原生控制未实现；可选原型证据和资源预算不会自动启用后端。\n请保留原签名和数据目录；升级 versionCode 必须高于已发布/安装版本。\n重新导出必须使用新目录，不覆盖或混入旧包。\n'''
        write('README.txt', readme)
        manifest = {'schema': 2, 'baseline': baseline_commit, 'releases': release_records,
                    'published': False, 'actualAndroidExecution': False,
                    'files': {name: hashlib.sha256((staging / name).read_bytes()).hexdigest() for name in sorted(files)}}
        write('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        archive = staging / 'PocketChat-1.6-1.7-2.0-review.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
            for name in sorted(files):
                bundle.write(staging / name, 'PocketChat-profile-upgrades/' + name)
        archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        (staging / (archive.name + '.sha256')).write_text(archive_hash + '  ' + archive.name + '\n')
        result = {'archive': str(output / archive.name), 'bytes': archive.stat().st_size,
                  'sha256': archive_hash, 'releases': release_records}
        # An existing empty output can be atomically replaced; no user files are deleted.
        os.replace(staging, output)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/profile-upgrades')
    parser.add_argument('--evidence-dir', type=Path)
    parser.add_argument('--baseline', default=BASE)
    parser.add_argument('--release', action='append', type=release_argument, dest='releases')
    args = parser.parse_args()
    try:
        result = export(ROOT, args.output, args.baseline, args.releases or VERSIONS, args.evidence_dir)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Profile export failed: ' + str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
