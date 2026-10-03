#!/usr/bin/env python3
"""Stage only verified signed APK chunks and public synthetic test evidence."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess

root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--apk',type=pathlib.Path,default=root/'dist/PocketChat-1.5.7-gecko-arm64.apk')
p.add_argument('--evidence',type=pathlib.Path,default=root/'work/gecko-integration')
args=p.parse_args()
report=json.loads((args.evidence/'device-results.json').read_text())
assert report['status']=='passed' and report['actualAndroidExecution'] and report['releaseMode']
build=json.loads((args.evidence/'manifest.json').read_text())
assert build['sourceCommit']==args.source,'Native evidence does not match the selected source.'
receipt=json.loads((args.apk.parent/'gecko-apk-verification.json').read_text())
assert receipt['signerSha256']=='f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
raw=args.apk.read_bytes()
assert receipt['bytes']==len(raw) and receipt['sha256']==hashlib.sha256(raw).hexdigest()
stage=root/'work/gecko-integration/signed-public'
if stage.exists():shutil.rmtree(stage)
stage.mkdir(parents=True)
manifest=dict(receipt,sourceCommit=args.source,filename=args.apk.name,parts=[],
              nativeRegression='passed',googleLogin='not-tested',physicalArmPhone='not-tested')
for number,offset in enumerate(range(0,len(raw),60_000_000)):
    part=raw[offset:offset+60_000_000];name=f'{args.apk.name}.part{number:02d}'
    (stage/name).write_bytes(part)
    manifest['parts'].append({'file':name,'bytes':len(part),'sha256':hashlib.sha256(part).hexdigest()})
(stage/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(stage/'device-results.json').write_text(json.dumps(report,indent=2)+'\n')
(stage/'RELEASE.md').write_text('''正式应用 1.5.7，原版签名，versionCode 33。适用于 ARM64 Android 手机，可覆盖同签名正式版，无需卸载。

真实网页改由 Mozilla 官方 GeckoView 加载，沿用原有环境数据和每个环境的网络配置。加载失败时显示重试和内核切换入口。

新内核首次需要重新登录；原系统内核的登录数据保留。可在“会话 → 更多 → 浏览器内核”切回系统内核。原有未完成回复会暂时保留系统内核以避免中断。

Android 15 原生回归已验证两个同时运行的环境、Cookie（含 HttpOnly）/LocalStorage/IndexedDB/Cache/ServiceWorker 隔离、独立 HTTP/SOCKS 代理、远端 DNS、Worker/WebSocket、重启恢复、原生清理和系统内核切换。

真实 Google/ChatGPT 登录与 ARM 手机尚待用户设备验证，本发布不承诺已经解除 Google 的浏览器登录限制。没有加入 Chrome 扩展安装功能。新内核的保护功能覆盖跟踪保护及 WebRTC 禁用；旧 WebView 指纹脚本和自检未移植。
''')
workflow=stage/'.github/workflows/publish-gecko-release.yml';workflow.parent.mkdir(parents=True)
shutil.copy2(root/'.github/workflows/publish-gecko-release.yml',workflow)
branch='apk/gecko-release-20261003'
env=dict(os.environ,GIT_INDEX_FILE=str(root/'work/gecko-integration/signed-index'),GIT_WORK_TREE=str(stage),
    GIT_AUTHOR_NAME='PocketChat release',GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
    GIT_COMMITTER_NAME='PocketChat release',GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
parents=['-p',args.source]
previous=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+branch],cwd=root,text=True).split()
if previous:
    subprocess.run(['git','fetch','origin','refs/heads/'+branch],cwd=root,check=True)
    parents+=['-p',previous[0]]
subprocess.run(['git','read-tree','--empty'],cwd=root,env=env,check=True)
subprocess.run(['git','add','-f','--','.github','release-manifest.json','RELEASE.md','device-results.json',*[x['file'] for x in manifest['parts']]],cwd=root,env=env,check=True)
tree=subprocess.check_output(['git','write-tree'],cwd=root,env=env,text=True).strip()
commit=subprocess.check_output(['git','commit-tree',tree,*parents,'-m','Publish original-signed production Gecko APK'],cwd=root,env=env,text=True).strip()
subprocess.run(['git','-c','http.postBuffer=524288000','push','origin',commit+':refs/heads/'+branch],cwd=root,check=True)
print(json.dumps({'artifactCommit':commit,'sha256':manifest['sha256'],'download':'https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v1.5.7-gecko/'+args.apk.name}))
