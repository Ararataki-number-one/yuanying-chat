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
for name in ['build.log', 'native-test.log', 'update-fixture-preparation.log', 'bridge-host-results.json', 'reading-host-results.json', 'reading-focus-host-results.json', 'cookie-host-results.json', 'update-host-results.json', 'update-transfer-host-results.json', 'update-transfer-results.json', 'region-host-results.json', 'update-ui.xml', 'update-installer-ui.xml', 'update-ui.png', 'device-results.json', 'device-route-trace.json', 'device-native-events.txt', 'device-screen.png', 'last-device-log.txt', 'production-ui.xml', 'failure-screen.png', 'failure-ui.xml']:
    if (out / name).exists():
        shutil.copy2(out / name, stage / name)
for name in ['network-performance-results.json','network-performance-failure-log.txt','quiet-notification-results.json','quiet-notification-failure-log.txt','compact-chrome-results.json','ui-visual-results.json','ui-build-comparison.json','ui-visual-log.txt','ui-visual-failure.png','ui-visual-failure.xml','snapshot-host-results.json','reply-observation-host-results.json','reply-binding-host-results.json','interaction-host-results.json','gecko-performance-results.json','gecko-performance-failure-log.txt','gecko-performance-screen.png','network-pool-host-results.json','latency-probe-host-results.json','native-probe-results.json','native-probe-log.txt','native-probe-failure-log.txt','gecko-pool-results.json','gecko-pool-server.json','gecko-pool-server-failure.json','gecko-pool-log.txt','gecko-pool-failure-log.txt','browser-runtime-policy-host-results.json','original-website-policy-host-results.json','update-route-results.json','update-route-log.txt','update-route-failure-log.txt','update-route-host-wire.json']:
    if (out/name).exists():shutil.copy2(out/name,stage/name)
for name in ['preconnect-results.json','preconnect-log.txt','preconnect-failure-log.txt','preconnect-server.json','preconnect-server-failure.json']:
    if (out/name).exists():shutil.copy2(out/name,stage/name)
for name in ['emulator-bootstrap-results.json','profile-host-results.json','identity-controller-host-results.json','deferred-browser-host-results.json','identity-bridge-host-results.json','environment-intent-host-results.json','gecko-proxy-route-host-results.json','environment-spec-results.json','environment-intent-results.json','gecko-identity-prototype-results.json','gecko-template-results.json','gecko-template-runner-log.json','environment-spec-runner-log.json','environment-intent-runner-log.json','gecko-identity-prototype-runner-log.json']:
    if (out/name).exists():shutil.copy2(out/name,stage/name)
for pattern in ['environment-spec-*.txt','environment-intent-*.txt','gecko-identity-prototype-*.txt','gecko-template-*.txt']:
    for item in out.glob(pattern):shutil.copy2(item,stage/item.name)
for pattern in ['network-catalog-host-results.json','network-source-host-results.json','network-lineage-host-results.json','sealed-file-host-results.json','network-source-*.json','network-source-*.txt','network-source-*.png','network-source-*.xml','network-safe-idle-*.json','network-safe-idle-*.txt','network-safe-idle-*.png','network-safe-idle-*.xml']:
    for item in out.glob(pattern):shutil.copy2(item,stage/item.name)
if (out/'ui-visuals').exists():shutil.copytree(out/'ui-visuals',stage/'ui-visuals',dirs_exist_ok=True)
if (out/'official-sdk-verification.json').exists():shutil.copy2(out/'official-sdk-verification.json',stage/'official-sdk-verification.json')
sdk_receipt=root/'third-party/sdk/geckoview-157.0.1-official.json'
if sdk_receipt.exists():
    shutil.copy2(sdk_receipt,out/'official-sdk-input.json')
    shutil.copy2(sdk_receipt,stage/'official-sdk-input.json')
core_receipt=root/'third-party/patches/mihomo-v1.19.31-probe-build.json'
if core_receipt.exists():
    core=json.loads(core_receipt.read_text())
    core['sourceCommit']=source
    (out/'network-core-build.json').write_text(json.dumps(core,indent=2)+'\n')
    shutil.copy2(out/'network-core-build.json',stage/'network-core-build.json')
for screenshot in out.glob('reading-*.png'):
    shutil.copy2(screenshot, stage / screenshot.name)
for pattern in ['gecko-scroll-*.json','gecko-performance-failure-*.png','gecko-performance-failure-*.xml','gecko-performance-failure-*.txt']:
    for item in out.glob(pattern):shutil.copy2(item,stage/item.name)
for pattern in ['network-latency-*.png','network-latency-*.xml']:
    for item in out.glob(pattern):shutil.copy2(item,stage/item.name)
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
