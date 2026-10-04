#!/usr/bin/env python3
"""Advance the small public update channel only after an anonymous full APK verification."""
import hashlib,json,os,pathlib,re,subprocess,time,urllib.request

ROOT=pathlib.Path.cwd()
def metadata(m,notes):
    assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',m['version'])
    assert isinstance(m['versionCode'],int) and m['versionCode']>0
    assert m['package']=='local.pocketchat'
    assert m['signerSha256']=='f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
    assert m['filename']==f"PocketChat-{m['version']}-gecko-arm64.apk"
    assert m['nativeRegression']=='passed' and len(notes)<12000
    return dict(schema=1,package=m['package'],version=m['version'],versionCode=m['versionCode'],
        abi='arm64-v8a',minSdk=26,bytes=m['bytes'],sha256=m['sha256'],signerSha256=m['signerSha256'],
        downloadUrl=f"https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v{m['version']}-gecko/{m['filename']}",
        notes=notes,sourceCommit=m['sourceCommit'])

def main():
    m=json.loads((ROOT/'release-manifest.json').read_text());feed=metadata(m,(ROOT/'RELEASE.md').read_text().strip())
    for attempt in range(5):
        try:
            digest=hashlib.sha256();size=0
            with urllib.request.urlopen(feed['downloadUrl'],timeout=60) as response:
                while data:=response.read(1024*1024):digest.update(data);size+=len(data)
            assert size==m['bytes'] and digest.hexdigest()==m['sha256'],'Anonymous public APK does not match verified release'
            break
        except Exception:
            if attempt==4:raise
            time.sleep(10)
    branch='app-updates';previous=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+branch],text=True).split();parents=[]
    if previous:
        subprocess.run(['git','fetch','origin','refs/heads/'+branch],check=True)
        old=json.loads(subprocess.check_output(['git','show',previous[0]+':latest.json'],text=True))
        assert old['versionCode']<=feed['versionCode'],'Refusing to roll back update channel'
        if old['versionCode']==feed['versionCode']:assert old['sha256']==feed['sha256'],'Same version cannot change APK identity'
        parents=['-p',previous[0]]
    stage=ROOT/'work/update-feed';stage.mkdir(parents=True,exist_ok=True)
    (stage/'latest.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n')
    env=dict(os.environ,GIT_INDEX_FILE=str(stage/'index'),GIT_WORK_TREE=str(stage),
        GIT_AUTHOR_NAME='PocketChat release',GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
        GIT_COMMITTER_NAME='PocketChat release',GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
    subprocess.run(['git','read-tree','--empty'],check=True,env=env)
    subprocess.run(['git','add','-f','--','latest.json'],check=True,env=env)
    tree=subprocess.check_output(['git','write-tree'],text=True,env=env).strip()
    commit=subprocess.check_output(['git','commit-tree',tree,*parents,'-m',f"Publish verified update {m['version']}"],text=True,env=env).strip()
    subprocess.run(['git','push','origin',commit+':refs/heads/'+branch],check=True)
    print(json.dumps(dict(updateCommit=commit,version=feed['version'],sha256=feed['sha256'])))

if __name__=='__main__':main()
