#!/usr/bin/env python3
"""Publish unsigned APK chunks and strictly synthetic evidence; never signing keys."""
import hashlib, json, os, pathlib, re, shutil, subprocess
root = pathlib.Path(__file__).resolve().parents[2]
out = root / 'work/gecko-integration'
stage = out / 'public'
stage.mkdir(parents=True, exist_ok=True)
source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
settings=(root/'app/build.gradle').read_text()
version=re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",settings).group(1)
version_code=int(re.search(r'versionCode ([0-9]+)',settings).group(1))
manifest = {'sourceCommit': source, 'runId': os.environ['GITHUB_RUN_ID'], 'version':version,'versionCode':version_code,'googleLogin': 'not-tested', 'artifacts': []}
for abi in ['arm64-v8a']:
    apk = root / f'app/build/outputs/apk/release/app-{abi}-release-unsigned.apk'
    if not apk.exists():
        continue
    data = apk.read_bytes()
    artifact = {'abi': abi, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'signing': 'unsigned', 'chunks': []}
    for index, offset in enumerate(range(0, len(data), 60_000_000)):
        part = data[offset:offset+60_000_000]
        name = f'PocketChat-{version}-{abi}.apk.part{index:02d}'
        (stage / name).write_bytes(part)
        artifact['chunks'].append({'file': name, 'bytes': len(part), 'sha256': hashlib.sha256(part).hexdigest()})
    manifest['artifacts'].append(artifact)
for name in ['build.log', 'native-test.log', 'bridge-host-results.json', 'device-results.json', 'device-route-trace.json', 'device-native-events.txt', 'device-screen.png', 'last-device-log.txt', 'production-ui.xml']:
    if (out / name).exists():
        shutil.copy2(out / name, stage / name)
(stage / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
branch = 'apk/gecko-integration-build-20261003'
env = dict(os.environ, GIT_INDEX_FILE=str(out/'public-index'), GIT_WORK_TREE=str(stage),
    GIT_AUTHOR_NAME='PocketChat build', GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
    GIT_COMMITTER_NAME='PocketChat build', GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
parents = ['-p', source]
previous = subprocess.check_output(['git','ls-remote','origin','refs/heads/'+branch], text=True).split()
if previous:
    subprocess.run(['git','fetch','origin','refs/heads/'+branch], check=True)
    parents += ['-p', previous[0]]
subprocess.run(['git','read-tree','--empty'], check=True, env=env)
subprocess.run(['git','add','-f','--',*[p.name for p in stage.iterdir()]], check=True, env=env)
tree = subprocess.check_output(['git','write-tree'], text=True, env=env).strip()
commit = subprocess.check_output(['git','commit-tree',tree,*parents,'-m','Publish unsigned Gecko integration build and synthetic checks'], text=True, env=env).strip()
subprocess.run(['git','-c','http.postBuffer=524288000','push','origin',commit+':refs/heads/'+branch], check=True)
