#!/usr/bin/env python3
"""Stage only verified signed APK chunks and public synthetic test evidence."""
import argparse, hashlib, json, os, pathlib, re, shutil, subprocess

root=pathlib.Path(__file__).resolve().parents[1]
settings=(root/'app/build.gradle').read_text()
version=re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",settings).group(1)
version_code=int(re.search(r'versionCode ([0-9]+)',settings).group(1))
p=argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--apk',type=pathlib.Path,default=root/f'dist/PocketChat-{version}-gecko-arm64.apk')
p.add_argument('--notes',type=pathlib.Path,default=root/f'docs/RELEASE-v{version}.md')
p.add_argument('--evidence',type=pathlib.Path,default=root/'work/gecko-integration')
args=p.parse_args()
report=json.loads((args.evidence/'device-results.json').read_text())
assert report['status']=='passed' and report['actualAndroidExecution'] and report['releaseMode']
assert report.get('sourceCommit')==args.source,'Native report belongs to a different source.'
build=json.loads((args.evidence/'manifest.json').read_text())
assert build['sourceCommit']==args.source,'Native evidence does not match the selected source.'
receipt=json.loads((args.apk.parent/'gecko-apk-verification.json').read_text())
assert receipt['unsignedSha256']==next(item['sha256'] for item in build['artifacts'] if item['abi']=='arm64-v8a'),'Signed APK was not built from the selected source.'
assert receipt['signerSha256']=='f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
assert receipt['version']==build['version']==version and receipt['versionCode']==build['versionCode']==version_code
assert receipt['file']==args.apk.name==f'PocketChat-{version}-gecko-arm64.apk'
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
shutil.copy2(args.notes,stage/'RELEASE.md')
workflow=stage/'.github/workflows/publish-gecko-release.yml';workflow.parent.mkdir(parents=True)
shutil.copy2(root/'.github/workflows/publish-gecko-release.yml',workflow)
(stage/'tools').mkdir(exist_ok=True)
shutil.copy2(root/'tools/publish-update-feed.py',stage/'tools/publish-update-feed.py')
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
subprocess.run(['git','add','-f','--','.github','tools','release-manifest.json','RELEASE.md','device-results.json',*[x['file'] for x in manifest['parts']]],cwd=root,env=env,check=True)
tree=subprocess.check_output(['git','write-tree'],cwd=root,env=env,text=True).strip()
commit=subprocess.check_output(['git','commit-tree',tree,*parents,'-m','Publish original-signed production Gecko APK'],cwd=root,env=env,text=True).strip()
subprocess.run(['git','-c','http.postBuffer=524288000','push','origin',commit+':refs/heads/'+branch],cwd=root,check=True)
print(json.dumps({'artifactCommit':commit,'sha256':manifest['sha256'],'download':f'https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v{version}-gecko/'+args.apk.name}))
