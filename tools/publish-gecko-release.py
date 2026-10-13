#!/usr/bin/env python3
"""Stage only verified signed APK chunks and public synthetic test evidence."""
import argparse, hashlib, json, os, pathlib, re, shutil, subprocess, urllib.request
from gecko.release_channel_contract import release_tag, requires_manual_acceptance, verify_manual_acceptance


def verify_existing_release_identity(current, previous, tag_source, actual_bytes, actual_sha256):
    assert tag_source==current['sourceCommit'],'Existing release tag belongs to another source; use a new version.'
    assert previous==current,'Existing release manifest differs; a published version is immutable.'
    assert actual_bytes==current['bytes'] and actual_sha256==current['sha256'],'Existing public APK differs; refusing to replace its identity.'


def existing_release_preflight(manifest, repository):
    tag=release_tag(manifest)
    refs=subprocess.check_output(['git','ls-remote','origin','refs/tags/'+tag,'refs/tags/'+tag+'^{}'],cwd=repository,text=True)
    values={name:commit for commit,name in (line.split() for line in refs.splitlines())}
    target=values.get('refs/tags/'+tag+'^{}',values.get('refs/tags/'+tag))
    if target is None:return
    assert target==manifest['sourceCommit'],'Existing release tag belongs to another source; use a new version.'
    # An existing tag without a complete public identity is not permission to
    # create or replace it. Anonymous read failures conservatively stop staging.
    base='https://github.com/Ararataki-number-one/yuanying-chat/releases/download/'+tag+'/'
    with urllib.request.urlopen(base+'release-manifest.json',timeout=60) as response:
        previous=json.loads(response.read(256*1024+1))
    assert previous==manifest,'Existing release manifest differs; a published version is immutable.'
    digest=hashlib.sha256();size=0
    with urllib.request.urlopen(base+manifest['filename'],timeout=60) as response:
        while data:=response.read(1024*1024):digest.update(data);size+=len(data)
    verify_existing_release_identity(manifest,previous,target,size,digest.hexdigest())

root=pathlib.Path(__file__).resolve().parents[1]
settings=(root/'app/build.gradle').read_text()
version=re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'",settings).group(1)
version_code=int(re.search(r'versionCode ([0-9]+)',settings).group(1))
roadmap_release=tuple(map(int,version.split('.'))) >= (1,6,0)
p=argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--apk',type=pathlib.Path,default=root/f'dist/PocketChat-{version}-gecko-arm64.apk')
p.add_argument('--notes',type=pathlib.Path,default=root/f'docs/RELEASE-v{version}.md')
p.add_argument('--evidence',type=pathlib.Path,default=root/'work/gecko-integration')
p.add_argument('--channel',choices=['stable','candidate'],default='stable')
p.add_argument('--candidate-number',type=int)
p.add_argument('--manual-acceptance',type=pathlib.Path)
args=p.parse_args()
channel_identity=dict(version=version,channel=args.channel,candidateNumber=args.candidate_number)
tag=release_tag(channel_identity)
assert re.fullmatch(r'[0-9a-f]{40}',args.source),'A complete source commit is required.'
report=json.loads((args.evidence/'device-results.json').read_text())
assert report['status']=='passed' and report['actualAndroidExecution'] and report['releaseMode']
assert report.get('sourceCommit')==args.source,'Native report belongs to a different source.'
if version_code>=39:
    visual=json.loads((args.evidence/'ui-visual-results.json').read_text())
    assert visual['status']=='passed' and visual['actualAndroidExecution'] and visual['sourceCommit']==args.source,'UI evidence is missing or belongs to a different source.'
if version_code>=40:
    network=json.loads((args.evidence/'network-performance-results.json').read_text())
    assert len(visual.get('networkOptimizationScreens',[]))==3,'Missing compact and large-font low-latency UI checks.'
    assert network.get('independentNetworkService')=='passed','Independent service lifecycle verification is required.'
    assert network['status']=='passed' and network['actualAndroidExecution'] and network['actualMihomoExecution'] and network['sourceCommit']==args.source,'Network evidence is missing or belongs to a different source.'
if version_code>=41:
    image=report.get('desktopImageUpload',{})
    assert all(image.get(k) for k in ['productionChooserOpened','imageMimeAndMultiple','pendingPreserved','noPhantomUpload','desktop']),'Desktop image upload regression is required.'
if version_code>=42:
    quiet=json.loads((args.evidence/'quiet-notification-results.json').read_text())
    chrome=json.loads((args.evidence/'compact-chrome-results.json').read_text())
    assert quiet['status']=='passed' and quiet['actualAndroidExecution'] and quiet['sourceCommit']==args.source and quiet['checkCount']>=24 and all(c['pass'] for c in quiet['checks']),'Quiet service and completion reminder regression is required.'
    assert chrome['status']=='passed' and chrome['actualAndroidExecution'] and chrome['sourceCommit']==args.source and len(chrome['cases'])==3 and all(c['readOnlyStatus'] and len(c['actualAndroidTaps'])==3 for c in chrome['cases']),'Compact chrome and real Android touch regression is required.'
    current_sample={'Automatic display sampling makes no requests while a reply is busy','The current route gets a real first sample after the reply becomes idle'} if version_code>=45 else {'The current route automatically gets a real first sample while reply is busy'}
    required=current_sample|{'External measured response is shown instead of permanently unmeasured','A blocked external route makes no test request or direct fallback'}
    assert required<=set(c['name'] for c in network['checks'] if c['pass']),'Real latency refresh regression is required.'
if version_code>=43:
    from gecko.check_performance_evidence import verify_performance_evidence
    performance=verify_performance_evidence(args.evidence,args.source)
if version_code>=44:
    from gecko.check_connection_evidence import verify_connection_evidence
    connection=verify_connection_evidence(args.evidence,args.source)
if version_code>=45:
    from gecko.check_interaction_transfer_evidence import verify_interaction_transfer_evidence
    interaction_transfer=verify_interaction_transfer_evidence(args.evidence,args.source)
if version_code>=46:
    from gecko.check_chain_evidence import verify_chain_evidence
    chain_performance=verify_chain_evidence(args.evidence,args.source)
    from gecko.check_client_evidence import verify_client_evidence
    client=verify_client_evidence(args.evidence,args.source)
    chain_files=['native-probe-results.json','gecko-pool-results.json','network-core-build.json','network-pool-host-results.json','latency-probe-host-results.json']
    if chain_performance.get('fixedExitPreauthentication'):
        chain_files.append('preconnect-results.json')
    if chain_performance.get('independentNetworkSources'):
        chain_files.extend(['network-catalog-host-results.json','network-source-host-results.json','network-lineage-host-results.json','sealed-file-host-results.json','network-source-results.json','network-source-ui-results.json','network-source-route-results.json','network-safe-idle-results.json','network-safe-idle-trust-host-results.json'])
    for name in chain_files:
        assert json.loads((args.evidence/name).read_text())['sourceCommit']==args.source,'Chain evidence belongs to a different source: '+name
build=json.loads((args.evidence/'manifest.json').read_text())
assert build['sourceCommit']==args.source,'Native evidence does not match the selected source.'
receipt=json.loads((args.apk.parent/'gecko-apk-verification.json').read_text())
assert receipt['unsignedSha256']==next(item['sha256'] for item in build['artifacts'] if item['abi']=='arm64-v8a'),'Signed APK was not built from the selected source.'
assert receipt['signerSha256']=='f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
assert receipt['version']==build['version']==version and receipt['versionCode']==build['versionCode']==version_code
assert receipt['file']==args.apk.name==f'PocketChat-{version}-gecko-arm64.apk'
raw=args.apk.read_bytes()
assert receipt['bytes']==len(raw) and receipt['sha256']==hashlib.sha256(raw).hexdigest()
manifest=dict(receipt,sourceCommit=args.source,filename=args.apk.name,parts=[],
              nativeRegression='passed',googleLogin='not-tested',physicalArmPhone='not-tested')
manifest['channel']=args.channel
if args.channel=='candidate':manifest['candidateNumber']=args.candidate_number
manual_raw=None
if requires_manual_acceptance(manifest):
    assert args.manual_acceptance is not None,'Publish a candidate first; stable roadmap releases require the user physical-phone checklist.'
    manual_raw=args.manual_acceptance.read_bytes()
    manual=verify_manual_acceptance(json.loads(manual_raw),manifest)
    manifest['manualAcceptance']=manual
    manifest['physicalArmPhone']='user-reported-passed'
    manifest['manualAcceptanceArtifact']=dict(file='manual-acceptance.json',bytes=len(manual_raw),sha256=hashlib.sha256(manual_raw).hexdigest())
if version_code>=43:manifest['performanceRegression']=performance
if version_code>=44:manifest['connectionRecoveryRegression']=connection
if version_code>=45:manifest['interactionTransferRegression']=interaction_transfer
if version_code>=46:
    manifest['chainPerformanceRegression']=chain_performance
    manifest['originalClientRegression']=client
if roadmap_release:
    from gecko.check_profile_evidence import verify_profile_evidence
    manifest['environmentProfileRegression']=verify_profile_evidence(args.evidence,args.source)
    prototype=json.loads((args.evidence/'gecko-identity-prototype-results.json').read_text())
    assert prototype['sourceCommit']==args.source and prototype['actualAndroidExecution'] is True
    assert prototype['diagnosticOnly'] is True and prototype['releaseAcceptance'] is False,'SDK capability diagnostics are not fingerprint acceptance.'
    manifest['identityPrototypeScope']='Controlled SDK diagnostic only; no template or physical-device acceptance.'
for number,offset in enumerate(range(0,len(raw),60_000_000)):
    part=raw[offset:offset+60_000_000];name=f'{args.apk.name}.part{number:02d}'
    manifest['parts'].append({'file':name,'bytes':len(part),'sha256':hashlib.sha256(part).hexdigest()})
existing_release_preflight(manifest,root)
stage=root/'work/gecko-integration/signed-public'
if stage.exists():shutil.rmtree(stage)
stage.mkdir(parents=True)
for number,part in enumerate(manifest['parts']):(stage/part['file']).write_bytes(raw[number*60_000_000:(number+1)*60_000_000])
(stage/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if manual_raw is not None:(stage/'manual-acceptance.json').write_bytes(manual_raw)
(stage/'device-results.json').write_text(json.dumps(report,indent=2)+'\n')
if version_code>=40:shutil.copy2(args.evidence/'network-performance-results.json',stage/'network-performance-results.json')
if version_code>=42:
    for name in ['quiet-notification-results.json','compact-chrome-results.json']:shutil.copy2(args.evidence/name,stage/name)
performance_files=['gecko-performance-results.json','snapshot-host-results.json','reply-observation-host-results.json','ui-visual-results.json','ui-build-comparison.json'] if version_code>=43 else []
if version_code>=44:performance_files.append('reply-binding-host-results.json')
if version_code>=45:performance_files.extend(['update-transfer-results.json','update-transfer-host-results.json','interaction-host-results.json'])
if version_code>=49:performance_files.extend(['reading-host-results.json','reading-focus-host-results.json','gecko-scroll-diagnostics.json','gecko-scroll-diagnostic-log.json'])
if roadmap_release:performance_files.extend(['environment-spec-results.json','environment-intent-results.json','profile-host-results.json','environment-intent-host-results.json','gecko-identity-prototype-results.json','environment-spec-runner-log.json','environment-intent-runner-log.json','gecko-identity-prototype-runner-log.json'])
if version_code>=46:performance_files.extend(chain_files+['browser-runtime-policy-host-results.json','original-website-policy-host-results.json','update-route-results.json','official-sdk-verification.json','official-sdk-input.json'])
for name in performance_files:shutil.copy2(args.evidence/name,stage/name)
shutil.copy2(args.notes,stage/'RELEASE.md')
workflow=stage/'.github/workflows/publish-gecko-release.yml';workflow.parent.mkdir(parents=True)
shutil.copy2(root/'.github/workflows/publish-gecko-release.yml',workflow)
(stage/'tools').mkdir(exist_ok=True)
shutil.copy2(root/'tools/publish-update-feed.py',stage/'tools/publish-update-feed.py')
if version_code>=43:
    (stage/'tools/gecko').mkdir(exist_ok=True)
    shutil.copy2(root/'tools/gecko/check_performance_evidence.py',stage/'tools/gecko/check_performance_evidence.py')
shutil.copy2(root/'tools/gecko/release_channel_contract.py',stage/'tools/gecko/release_channel_contract.py')
if roadmap_release:
    for name in ['check_profile_evidence.py','profile_invocation_contract.py']:shutil.copy2(root/'tools/gecko'/name,stage/'tools/gecko'/name)
if version_code>=44:shutil.copy2(root/'tools/gecko/check_connection_evidence.py',stage/'tools/gecko/check_connection_evidence.py')
if version_code>=45:shutil.copy2(root/'tools/gecko/check_interaction_transfer_evidence.py',stage/'tools/gecko/check_interaction_transfer_evidence.py')
if version_code>=46:
    for name in ['check_chain_evidence.py','chain_runtime_contract.py','preconnect_contract.py','network_sources_contract.py','check_client_evidence.py','update_route_contract.py']:shutil.copy2(root/'tools/gecko'/name,stage/'tools/gecko'/name)
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
subprocess.run(['git','add','-f','--','.github','tools','release-manifest.json','RELEASE.md','device-results.json',*(['manual-acceptance.json'] if manual_raw is not None else []),*(['network-performance-results.json'] if version_code>=40 else []),*(['quiet-notification-results.json','compact-chrome-results.json'] if version_code>=42 else []),*performance_files,*[x['file'] for x in manifest['parts']]],cwd=root,env=env,check=True)
tree=subprocess.check_output(['git','write-tree'],cwd=root,env=env,text=True).strip()
commit=subprocess.check_output(['git','commit-tree',tree,*parents,'-m','Publish original-signed production Gecko APK'],cwd=root,env=env,text=True).strip()
subprocess.run(['git','-c','http.postBuffer=524288000','push','origin',commit+':refs/heads/'+branch],cwd=root,check=True)
print(json.dumps({'artifactCommit':commit,'channel':args.channel,'sha256':manifest['sha256'],'download':f'https://github.com/Ararataki-number-one/yuanying-chat/releases/download/{tag}/'+args.apk.name}))
