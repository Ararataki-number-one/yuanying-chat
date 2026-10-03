#!/usr/bin/env python3
"""Publish only isolated probe artifacts with the CI's ordinary repository token.

No original APK signing keys, production data, dependency caches or logs with real
accounts are accepted. This branch contains synthetic fixtures only.
"""
import hashlib, json, os, pathlib, shutil, subprocess

root = pathlib.Path(__file__).resolve().parents[2]
source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
out = root / 'work/gecko-sdk-validation'
stage = root / 'work/engine-probe-public'
stage.mkdir(parents=True, exist_ok=True)
report = {'sourceCommit': source, 'runId': os.environ['GITHUB_RUN_ID'],
          'sdk': json.loads((root / 'engine-probe/sdk-lock.json').read_text()),
          'googleLogin': 'not-tested', 'productionMigration': 'not-enabled', 'artifacts': []}
for abi in ['arm64-v8a', 'x86_64']:
    apk = root / f'engine-probe/app/build/outputs/apk/debug/app-{abi}-debug.apk'
    if apk.exists():
        if apk.stat().st_size >= 104_000_000:
            report['artifacts'].append({'file': apk.name, 'bytes': apk.stat().st_size,
                'published': False, 'reason': 'exceeds conservative Git blob size limit'})
            continue
        target = stage / f'PocketChat-GeckoProbe-0.1.0-{abi}.apk'
        shutil.copy2(apk, target)
        report['artifacts'].append({'file': target.name, 'bytes': target.stat().st_size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'signing': 'CI debug, independent applicationId'})
for name in ['device-results.json', 'device-route-trace.json', 'device-native-events.txt', 'build.log', 'native-test.log',
             'device-screen.png', 'emulator.log', 'last-device-log.txt']:
    if (out / name).exists():
        shutil.copy2(out / name, stage / name)
verification = root / 'engine-probe/gradle/verification-metadata.xml'
if verification.exists():
    shutil.copy2(verification, stage / verification.name)
(stage / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
(stage / 'README.md').write_text('独立 GeckoView SDK 技术验证包，**不是正式版本、不是 Google 登录修复版**。\n'
    '只允许受控 loopback 测试，不继承正式应用网络和登录，原应用不会被覆盖。\n'
    'debug 签名来自 CI；原版签名密钥没有上传。验收结论以 device-results.json 为准，缺失代表未执行。\n'
    'GeckoView 采用 [MPL-2.0](https://www.mozilla.org/MPL/2.0/)，对应源码版本见 '
    '[Mozilla 官方 release](https://hg.mozilla.org/releases/mozilla-release/rev/8eb25af4acf031ab1e06abf1a912275083c820ed)。\n')
# Use the original checkout and ordinary Git authorization; do not extract tokens.
branch = 'apk/gecko-sdk-probe-20261003'
process_env = dict(os.environ, GIT_INDEX_FILE=str(out / 'public-index'), GIT_WORK_TREE=str(stage),
    GIT_AUTHOR_NAME='PocketChat engine validation', GIT_AUTHOR_EMAIL='engine-probe@users.noreply.github.com',
    GIT_COMMITTER_NAME='PocketChat engine validation', GIT_COMMITTER_EMAIL='engine-probe@users.noreply.github.com')
parents = ['-p', source]
previous = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/' + branch], text=True).split()
if previous:
    subprocess.run(['git', 'fetch', 'origin', 'refs/heads/' + branch], check=True)
    parents += ['-p', previous[0]]
subprocess.run(['git', 'read-tree', '--empty'], check=True, env=process_env)
subprocess.run(['git', 'add', '-f', '--', *[str(p.relative_to(stage)) for p in stage.iterdir()]],
    check=True, env=process_env)
tree = subprocess.check_output(['git', 'write-tree'], text=True, env=process_env).strip()
commit = subprocess.check_output(['git', 'commit-tree', tree, *parents, '-m', 'Publish isolated SDK probe artifacts'],
    text=True, env=process_env).strip()
subprocess.run(['git', '-c', 'http.postBuffer=524288000', 'push', 'origin', commit + ':refs/heads/' + branch], check=True)
