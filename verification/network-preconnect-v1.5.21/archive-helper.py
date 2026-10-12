#!/usr/bin/env python3
"""Read-only by default; atomically archive fresh 1.5.21 release evidence."""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
WORK=ROOT/'work/gecko-integration'
VERSION,CODE='1.5.21',47
SIGNER='f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
RECEIPT='third-party/patches/mihomo-v1.19.31-probe-build.json'
SDK='third-party/sdk/geckoview-157.0.1-official.json'
ANDROID=('gecko-performance-results.json','network-performance-results.json','quiet-notification-results.json',
         'compact-chrome-results.json','ui-visual-results.json','device-results.json','update-transfer-results.json',
         'native-probe-results.json','gecko-pool-results.json','update-route-results.json','preconnect-results.json')
HOST={'bridge-host-results.json':18,'reading-host-results.json':39,'cookie-host-results.json':10,
      'region-host-results.json':15,'update-host-results.json':23,'snapshot-host-results.json':14,
      'reply-observation-host-results.json':37,'reply-binding-host-results.json':41,
      'update-transfer-host-results.json':28,'interaction-host-results.json':36,
      'network-pool-host-results.json':54,'latency-probe-host-results.json':70,
      'browser-runtime-policy-host-results.json':54,'original-website-policy-host-results.json':25}
GATES=('check_performance_evidence.py','check_connection_evidence.py','check_interaction_transfer_evidence.py',
       'check_chain_evidence.py','chain_runtime_contract.py','check_client_evidence.py','update_route_contract.py',
       'preconnect_contract.py','verify_official_sdk.py')
LOGS=('native-probe-log.txt','gecko-pool-log.txt','preconnect-log.txt','preconnect-server.json',
      'native-test.log','build.log','update-route-log.txt','update-route-host-wire.json','update-fixture-preparation.log')
REMOTE='https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/'
SECRET=re.compile(rb'gh[opsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-|svcacct-)[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
TEST_PATTERN=r'Test(?:Pocket|Preconnect|SelectorPreconnect)\w+'


def require(value,message):
    if not value:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def read(path):
    path=pathlib.Path(path)
    require(path.is_file() and not path.is_symlink(),'Missing/unsafe evidence: '+str(path))
    require(path.stat().st_size<=16_000_000,'Evidence exceeds bounded size: '+path.name)
    raw=path.read_bytes();require(not SECRET.search(raw),'Private credential pattern: '+path.name)
    return raw


def load(path):
    value=json.loads(read(path));require(isinstance(value,dict),'Expected JSON object: '+str(path));return value


def file_sha(path):
    with pathlib.Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def git_bytes(source,path):return subprocess.check_output(['git','show',source+':'+path],cwd=ROOT)


def remote(commit,path):
    require(re.fullmatch('[0-9a-f]{40}',commit) is not None,'Invalid immutable artifact identity')
    require(re.fullmatch(r'[A-Za-z0-9_.\-/]+',path) and '..' not in pathlib.PurePosixPath(path).parts,'Unsafe remote path')
    with urllib.request.urlopen(REMOTE+commit+'/'+path,timeout=40) as response:
        require(response.status==200,'Anonymous artifact fetch failed');raw=response.read(16_000_001)
    require(len(raw)<=16_000_000 and not SECRET.search(raw),'Unsafe remote evidence: '+path);return raw


def expected_tests(patch):
    names=re.findall(r'^\+func ('+TEST_PATTERN+r')\(',patch.decode(),re.MULTILINE)
    require(len(names)==len(set(names))==46,'Committed patch must contain the frozen 46 native tests')
    require(sum(name.startswith('TestPocketProbe') for name in names)==10,'Original ten probe tests are required')
    return set(names)


def same_source_reports(source):
    require(re.fullmatch('[0-9a-f]{40}',source) is not None,'Invalid release source')
    manifest=load(WORK/'manifest.json')
    require(manifest['sourceCommit']==source and manifest['version']==VERSION and manifest['versionCode']==CODE,
            'Waiting for fresh same-source 1.5.21 build manifest')
    settings=git_bytes(source,'app/build.gradle').decode()
    require("versionName '1.5.21'" in settings and re.search(r'versionCode\s+47\b',settings),'Committed app version differs')
    reports={name:load(WORK/name) for name in ANDROID}
    for name,value in reports.items():
        require(value['status']=='passed' and value['sourceCommit']==source and value['actualAndroidExecution'] is True,
                'Waiting for same-source actual Android suite: '+name)
        require(not value.get('diagnosticOnly',False),'Diagnostic report cannot be release acceptance: '+name)
    total=0
    for name,minimum in HOST.items():
        value=load(WORK/name);count=value.get('passed',value.get('checks',0))
        require(type(count) is int and count>=minimum,'Waiting for host suite: '+name)
        require('total' not in value or value['total']==count,'Failed host suite: '+name)
        require('sourceCommit' not in value or value['sourceCommit']==source,'Wrong-source host suite: '+name)
        if isinstance(value.get('checks'),list):require(all(x.get('pass',x.get('passed')) is True for x in value['checks']),'Failed host case: '+name)
        total+=count
    require(total>=464,'Fourteen host suites must retain at least 464 checks')
    for name in GATES:require(read(ROOT/'tools/gecko'/name)==git_bytes(source,'tools/gecko/'+name),'Gate source differs: '+name)
    sys.path.insert(0,str(ROOT/'tools'))
    from gecko.check_performance_evidence import verify_performance_evidence
    from gecko.check_connection_evidence import verify_connection_evidence
    from gecko.check_interaction_transfer_evidence import verify_interaction_transfer_evidence
    from gecko.check_chain_evidence import verify_chain_evidence
    from gecko.check_client_evidence import verify_client_evidence
    from gecko.preconnect_contract import verify_preconnect
    gates={'performance':verify_performance_evidence(WORK,source),'connection':verify_connection_evidence(WORK,source),
           'interactionTransfer':verify_interaction_transfer_evidence(WORK,source),'chain':verify_chain_evidence(WORK,source),
           'originalClient':verify_client_evidence(WORK,source)}
    require(gates['performance']['reloadConfirmationChecks']==8,'Actual reload confirmation must remain passed')
    raw=git_bytes(source,RECEIPT);core=json.loads(raw)
    require(core['recipe']['fixedExitPreconnect'] is True and core['recipe']['version']=='v1.19.31-pocket-preconnect1',
            'Waiting for reviewed preauthentication native build')
    published=load(WORK/'network-core-build.json');require(published.pop('sourceCommit')==source and published==core,'Published native receipt differs')
    require(core['inputs']['patchSha256']==sha(git_bytes(source,core['inputs']['patch'])),'Committed patch digest differs')
    require(core['inputs']['archiveSha256']==sha(git_bytes(source,core['inputs']['archive'])),'Committed upstream archive differs')
    expected_tests(git_bytes(source,core['inputs']['patch']))
    preconnect=verify_preconnect(reports['preconnect-results.json'],core)
    require(preconnect==gates['chain']['fixedExitPreauthentication'],'Standalone/shared preconnect gates differ')
    require(load(WORK/'preconnect-server.json')==reports['preconnect-results.json']['server'],'Raw H2 server evidence differs')
    sdk_raw=git_bytes(source,SDK);require(read(WORK/'official-sdk-input.json')==sdk_raw,'Official SDK input differs')
    sdk=json.loads(sdk_raw);proof=load(WORK/'official-sdk-verification.json')
    require(proof['sourceCommit']==source and proof['status']=='passed' and proof['actualAndroidExecution'] is False
            and proof['receiptSha256']==sha(sdk_raw) and proof['upstreamRevision']==sdk['upstreamRevision'],
            'Waiting for same-source official SDK build input')
    return {'manifest':manifest,'reports':reports,'hostChecks':total,'gates':gates,'preconnect':preconnect,
            'core':core,'receiptRaw':raw,'sdkRaw':sdk_raw}


def independent(source,core,raw):
    directory=ROOT/'work/mihomo-rebuild-final'/source
    proof=load(directory/'validation.json');manifest=load(directory/'manifest.json')
    require(proof['status']==manifest['status']=='passed' and proof['sourceCommit']==manifest['sourceCommit']==source,
            'Waiting for independent exact-source rebuild')
    require(proof['runId']==manifest['runId'] and proof['runAttempt']==manifest['runAttempt']
            and proof['artifactParentsBoundToSource'] is True and proof['actualAndroidExecution'] is False,
            'Independent workflow/source binding differs')
    commit=proof['artifactCommit'];require(remote(commit,'manifest.json')==read(directory/'manifest.json'),'Independent manifest byte mismatch')
    names={'mihomo-rebuild-results.json','mihomo-build-receipt.json','build.log'}
    require(len(manifest['files'])==3 and {x['path'] for x in manifest['files']}==names,'Independent artifact whitelist differs')
    for item in manifest['files']:
        data=read(directory/item['path'])
        require(len(data)==item['bytes'] and sha(data)==item['sha256'] and remote(commit,item['path'])==data,'Independent file mismatch: '+item['path'])
    require(read(directory/'mihomo-build-receipt.json')==raw and proof['receiptSha256']==sha(raw),'Independent receipt differs')
    result=load(directory/'mihomo-rebuild-results.json')
    require(result['sourceCommit']==source and result['runId']==manifest['runId'] and result['runAttempt']==manifest['runAttempt']
            and result['status']=='passed' and result['independentNativeRebuild'] is True
            and result['actualAndroidExecution'] is False and result['exactCommittedBytes'] is True
            and result['receiptSha256']==sha(raw),'Independent rebuild is incomplete')
    require(result['inputs']==core['inputs'] and result['recipe']==core['recipe'],'Independent input/recipe differs')
    require(set(result['buildOutcomes'])=={'NATIVE_PINNED_OUTCOME','NATIVE_REBUILT_OUTCOME'}
            and all(x=='success' for x in result['buildOutcomes'].values()),'Independent build outcomes did not pass')
    expected=expected_tests(git_bytes(source,core['inputs']['patch']))
    passed=re.findall(r'^--- PASS: ('+TEST_PATTERN+r') ',read(directory/'build.log').decode(),re.MULTILINE)
    require(len(passed)==46 and set(passed)==expected==set(result['nativeRegressions'])
            and result['nativeRegressionCount']==46 and result['nativeProbeRegressionCount']==10
            and result['preconnectRegressionCount']==36,'Frozen 36+10 native log/results mismatch')
    require(proof['exactNativeRegressions'] is True and proof['nativeRegressionCount']==46
            and set(proof['nativeRegressions'])==expected,'Independent validation names differ')
    for abi in ('arm64-v8a','x86_64'):
        require(all(result['rebuiltBinaries'][abi][field]==core['binaries'][abi][field] for field in ('sha256','bytes','elf')),
                'Independent ABI mismatch: '+abi)
    return directory,proof


def public_identity(source,data):
    signed=load(ROOT/'dist/gecko-apk-verification.json');name='PocketChat-'+VERSION+'-gecko-arm64.apk';path=ROOT/'dist'/name
    require(signed['version']==VERSION and signed['versionCode']==CODE and signed['file']==name
            and signed['package']=='local.pocketchat' and signed['signerSha256']==SIGNER
            and signed['debuggable'] is False and signed['testActivitiesPresent'] is False,'Wrong final signed APK receipt')
    require(path.is_file() and not path.is_symlink() and path.stat().st_size==signed['bytes'] and file_sha(path)==signed['sha256'],'Signed APK byte mismatch')
    unsigned=[x for x in data['manifest']['artifacts'] if x['abi']=='arm64-v8a']
    require(len(unsigned)==1 and unsigned[0]['signing']=='unsigned' and unsigned[0]['sha256']==signed['unsignedSha256'],'Unsigned source binding differs')
    p=WORK/'production-arm64-unsigned.apk'
    require(p.is_file() and not p.is_symlink() and p.stat().st_size==unsigned[0]['bytes'] and file_sha(p)==signed['unsignedSha256'],'Unsigned APK byte mismatch')
    with zipfile.ZipFile(path) as archive:
        require(not any(x.endswith(('.p12','.jks')) for x in archive.namelist()),'Fixture/signing key in APK')
        with archive.open('lib/arm64-v8a/libmihomo.so') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==data['core']['binaries']['arm64-v8a']['sha256'],'Packaged native bytes differ')
    packaged=load(WORK/'packaged-native-verification.json');native=data['core']['binaries']['arm64-v8a']
    require(packaged['sourceCommit']==source and packaged['apkSha256']==signed['sha256'] and packaged['abi']=='arm64-v8a'
            and packaged['matchesPinnedBuild'] is True and packaged['nativeSha256']==native['sha256'] and packaged['nativeBytes']==native['bytes']
            and packaged['newTestActivityAbsentFromManifestAndDex'] is True,'Packaged-native proof differs')
    download=load(WORK/'public-download-verification.json');feed=load(WORK/'public-update-feed-verification.json');ranges=load(WORK/'public-range-verification.json')
    url='https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v'+VERSION+'-gecko/'+name
    require(download['sourceCommit']==feed['sourceCommit']==ranges['sourceCommit']==source
            and download['sha256']==feed['sha256']==ranges['sha256']==signed['sha256'],'Public proof source/APK differs')
    require(download['anonymousPublicDownload'] is True and download['url']==url and download['bytes']==signed['bytes'],'Anonymous whole download not verified')
    require(feed['anonymousUpdateFeed'] is True and feed['downloadUrl']==url and feed['version']==VERSION
            and feed['versionCode']==CODE and feed['signerSha256']==SIGNER
            and feed['bytes']==signed['bytes'],'Update feed not verified')
    require(ranges['anonymousOfficialCdn'] is True and ranges['url']==url and ranges['totalBytes']==signed['bytes']
            and ranges['rangeSupported'] is True and ranges['ifRangeSupported'] is True and ranges['actualHttpRequests']==2,'Actual CDN resume not verified')
    segments=ranges['segments'];require(len(segments)==2 and all(x['status']==206 and x['matchesSignedApk'] is True
            and x['finalHost']=='release-assets.githubusercontent.com' for x in segments),'Range bytes do not match signed APK')
    require(segments[0]['start']==0 and segments[1]['start']==1024 and segments[0]['bytes']==segments[1]['bytes']==1024
            and segments[1]['ifRange']==segments[0]['etag']==segments[1]['etag'],'Range/If-Range identity differs')
    require(isinstance(segments[0]['etag'],str) and segments[0]['etag']
            and not segments[0]['etag'].startswith('W/'),'Resume proof requires a strong ETag')
    return {'signed':signed,'download':download,'feed':feed,'ranges':ranges}


def exploratory(source,core):
    python=ROOT/'work/exit-preauth-benchmark';p=load(python/'results.json')
    require(p['status']=='passed' and p['actualTcpWireExecution'] is True and p['actualMihomoExecution'] is False
            and p['actualAndroidExecution'] is False and p['productionPoolImplemented'] is False,'Python scope changed')
    require(re.fullmatch('[0-9a-f]{40}',p['sourceCommit']) and p['scriptSha256']==sha(read(python/'benchmark.py')),
            'Original Python source identity differs')
    require(len(p['rows'])==40 and len(p['checks'])==30 and all(x['pass'] for x in p['checks']),'Python wire checks changed')
    go=ROOT/'work/network-preconnect-native';prototype=load(go/'prototype-receipt.json');validation=load(go/'native-validation-receipt.json');clean=load(go/'clean-apply-receipt.json')
    patch=git_bytes(source,core['inputs']['patch']);identity=sha(json.dumps(prototype['files'],sort_keys=True,separators=(',',':')).encode())
    require(prototype['prototypeOnly'] is True and prototype['productionNativeInstalled'] is False
            and validation['prototypeOnly'] is True and validation['androidAcceptance'] is False and validation['wanSpeedClaim'] is False,'Frozen Go scope changed')
    require(prototype['combinedPatchSha256']==validation['combinedPatchSha256']==clean['combinedPatchSha256']==sha(patch)
            and read(go/'mihomo-v1.19.31-preconnect.patch')==patch,'Frozen prototype differs from final committed patch')
    require(identity==prototype['sourceIdentitySha256']==validation['sourceIdentitySha256']
            and prototype['upstreamArchiveSha256']==core['inputs']['archiveSha256'],'Frozen source identity differs')
    require(clean['allFilesByteExact'] is True and set(clean['checks'])==set(prototype['files']) and all(clean['checks'].values()),'Clean-apply receipt incomplete')
    with tarfile.open(ROOT/core['inputs']['archive']) as archive:
        for name,item in prototype['files'].items():
            raw=read(go/'clean-apply'/name);require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Clean-applied source byte mismatch: '+name)
            if item['originalSha256'] is not None:
                require(sha(archive.extractfile('MetaCubeX-mihomo-ab405ba/'+name).read())==item['originalSha256'],'Original upstream byte mismatch: '+name)
    for name,count in [('native-all-test-results.jsonl',36),('native-all-race-results.jsonl',36),('original-probe-regression-results.jsonl',10)]:
        raw=read(go/name);v=validation['results'][name];rows=[json.loads(line) for line in raw.decode().splitlines() if line]
        passed=[x['Test'] for x in rows if x.get('Action')=='pass' and x.get('Test') and '/' not in x['Test']]
        require(v['sha256']==sha(raw) and v['passed'] is True and v['topLevelPassed']==count
                and len(passed)==len(set(passed))==count and not any(x.get('Action')=='fail' for x in rows),'Frozen Go log mismatch: '+name)
    require(validation['controlledBenchmark']['sha256']==sha(read(go/'pool-controlled-benchmark.txt'))
            and validation['controlledBenchmark']['notRealWANOrAndroid'] is True,'Go benchmark scope/hash differs')
    python_files=['benchmark.py','serve.py','README.md','results.json']
    go_files=['prototype-receipt.json','native-validation-receipt.json','clean-apply-receipt.json','source-receipt.json',
              'freeze-prototype.py','mihomo-v1.19.31-preconnect.patch','native-all-test-results.jsonl',
              'native-all-race-results.jsonl','original-probe-regression-results.jsonl','pool-controlled-benchmark.txt']
    files={}
    for parent,names,prefix in [(python,python_files,'exploratory/python'),(go,go_files,'exploratory/go')]:
        for name in names:files[prefix+'/'+name]=read(parent/name)
    return files,{'historicalExploratoryOnly':True,'actualAndroidAcceptance':False,'wanSpeedClaim':False,
                  'pythonOriginalSourceCommit':p['sourceCommit'],'pythonScriptSha256':p['scriptSha256'],
                  'goSourceIdentitySha256':identity,'goCombinedPatchSha256':sha(patch),'goNormalTopLevelTests':36,
                  'goRaceTopLevelTests':36,'originalProbeTopLevelTests':10}


def historical_process(source,core):
    """A full Linux process run is still not final-source Android acceptance."""
    parent=ROOT/'work/native-preconnect-process-benchmark';manifest=load(parent/'manifest.json')
    result=load(parent/'results.json');origin=manifest['sourceCommit']
    require(origin=='140a9d840d42af21754d6791c1e6e2dde8a01559' and result['sourceCommit']==origin,
            'Original full-process benchmark source changed')
    require(manifest['passed'] is True and manifest['notAndroidOrWAN'] is True
            and result['passed'] is True and result['fullActualLinuxCoreProcess'] is True
            and result['androidAcceptance'] is False and result['wanClaim'] is False,
            'Linux process investigation scope changed')
    require(git_bytes(origin,RECEIPT)==git_bytes(source,RECEIPT)
            and result['nativeInputs']==core['inputs'] and result['nativeRecipe']==core['recipe']
            and manifest['nativeRecipe']==core['recipe'] and manifest['patchSha256']==core['inputs']['patchSha256'],
            'Historical Linux run used another native component')
    require(result['core']['sha256']==manifest['coreSha256']
            and file_sha(ROOT/'work/mihomo-build/bin/mihomo-linux-amd64')==manifest['coreSha256'],
            'Actual local Linux binary differs from the recorded execution')
    files={'exploratory/linux-process/manifest.json':read(parent/'manifest.json')}
    for name,item in manifest['files'].items():
        require(re.fullmatch(r'[A-Za-z0-9_.\-/]+',name) and '..' not in pathlib.PurePosixPath(name).parts
                and pathlib.Path(name).suffix in {'.json','.txt','.py','.md'},'Unsafe Linux investigation file')
        raw=read(parent/name);require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Linux file hash differs: '+name)
        files['exploratory/linux-process/'+name]=raw
    for name,item in manifest['preservedFailedAttempts'].items():
        raw=read(parent/name/'results.json');failed=json.loads(raw)
        require(item['passed'] is False and failed['passed'] is False and sha(raw)==item['sha256'],
                'A failed Linux investigation attempt was omitted or relabeled')
        files['exploratory/linux-process/'+name+'/results.json']=raw
    focused=load(parent/'focused-unified/results.json')
    require(focused['passed'] is True and manifest['focusedUnifiedDelay']['passed'] is True,
            'Focused unified probe investigation did not pass')
    return files,{'historicalExploratoryOnly':True,'countsAsFinalAndroidAcceptance':False,'wanSpeedClaim':False,
                  'originalSourceCommit':origin,'nativeComponentBytesIdenticalToFinalSource':True,
                  'actualFullLinuxCoreProcess':True,'executedLinuxSha256':manifest['coreSha256'],
                  'independentLinuxReproducibleBuildClaim':False,'failedAttemptsPreserved':len(manifest['preservedFailedAttempts'])}


def historical_android_failure():
    origin='140a9d840d42af21754d6791c1e6e2dde8a01559'
    commit='9d171079bbbeef4f2d8c4c7956999c672d87374e'
    parent=WORK/'immutable-evidence'/origin/commit
    proof=load(parent/'fetch-verification.json');manifest=load(parent/'manifest.json')
    require(proof['sourceCommit']==manifest['sourceCommit']==origin and proof['artifactCommit']==commit
            and proof['artifactFirstParentBoundToSource'] is True and proof['allSelectedGitBlobsVerified'] is True
            and proof['allReportsPresent'] is True and proof['allReportsPassed'] is False,
            'Original failed Android artifact binding differs')
    require(proof['manifestSha256']==sha(read(parent/'manifest.json')),'Original failed manifest digest differs')
    names=[*ANDROID,'manifest.json','preconnect-log.txt','preconnect-failure-log.txt','preconnect-server.json',
           'preconnect-server-failure.json','network-core-build.json']
    records={row['path']:row for row in proof['records']}
    def fetch(name):
        raw=read(parent/name)
        if name!='manifest.json':
            row=records[name];require(len(raw)==row['bytes'] and sha(raw)==row['sha256'],'Failed artifact hash differs: '+name)
        require(remote(commit,name)==raw,'Failed artifact remote bytes differ: '+name)
        return 'historical-failures/android-140a/'+name,raw
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=dict(pool.map(fetch,names))
    failed=load(parent/'preconnect-results.json')
    require(failed['sourceCommit']==origin and failed['status']=='failed' and failed['actualAndroidExecution'] is True
            and len(failed['checks'])==7 and 'NoSuchMethodError' in failed['error'] and 'readString' in failed['error'],
            'Original seven-check Android fixture API failure was relabeled')
    for name in ANDROID[:-1]:
        report=load(parent/name);require(report['sourceCommit']==origin and report['status']=='passed',
                                        'Original legacy pass status changed: '+name)
    files['historical-failures/android-140a/fetch-verification.json']=read(parent/'fetch-verification.json')
    return files,{'historicalFailureOnly':True,'countsAsFinalAndroidAcceptance':False,'sourceCommit':origin,
                  'artifactCommit':commit,'runId':manifest['runId'],'legacySuitesPassed':10,
                  'preconnectStatus':'failed','completedPreconnectChecks':7,
                  'reason':'Android Files.readString NoSuchMethodError; original report/logs retained'}


def immutable(source,data):
    words=subprocess.check_output(['git','ls-remote','origin','refs/heads/apk/gecko-integration-build-20261003'],cwd=ROOT,text=True).split()
    require(words,'Missing normal CI artifact');commit=words[0]
    raw=remote(commit,'manifest.json');require(raw==read(WORK/'manifest.json'),'Normal immutable manifest SHA/source binding differs')
    names=[*ANDROID,*HOST,*LOGS,'manifest.json','network-core-build.json','official-sdk-input.json','official-sdk-verification.json','ui-build-comparison.json',
           'gecko-performance-screen.png','update-ui.png']
    def fetch(name):
        value=remote(commit,name);require(value==read(WORK/name),'Immutable CI bytes differ: '+name);return name,value
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=dict(pool.map(fetch,names))
    visual=data['reports']['ui-visual-results.json']
    require(len(visual['screenshots'])==19 and all(x['variant']=='current' for x in visual['screenshots']),'Expected nineteen current-only UI captures')
    for shot in visual['screenshots']+visual.get('networkOptimizationScreens',[])+visual.get('compactChromeScreens',[]):
        for field in ['image','xml']:
            name=shot[field];require(re.fullmatch(r'current-(360x640|412x640)-font[12]-(chat|environments|network|proxy|entries|browser|preferences)\.(png|xml)|network-latency-(360-font[12]|412-font1)\.(png|xml)|compact-chrome-(360-font[12]|412-font1)\.(png|xml)',name),'Unsafe screenshot path')
            relative=name if name.startswith('network-latency-') else 'ui-visuals/'+name
            value=remote(commit,relative);require(value==read(WORK/relative),'Immutable capture differs: '+name)
            files['ui-visuals/'+name]=value
    return commit,sha(raw),files


def prepare(source):
    data=same_source_reports(source)
    native_dir,native=independent(source,data['core'],data['receiptRaw'])
    public=public_identity(source,data)
    exploration,exploratory_proof=exploratory(source,data['core'])
    linux_files,linux_proof=historical_process(source,data['core'])
    failure_files,failure_proof=historical_android_failure()
    commit,manifest_sha,files=immutable(source,data)
    projection=load(WORK/'current-evidence-verification.json')
    require(projection['sourceCommit']==source and projection['artifactCommit']==commit
            and projection['runId']==data['manifest']['runId'] and projection['manifestSha256']==manifest_sha
            and projection['artifactFirstParentBoundToSource'] is True and projection['allSelectedGitBlobsVerified'] is True
            and projection['manifestArtifactsVerified'] is True and projection['allReportsPresent'] is True
            and projection['allReportsPassed'] is True,'Strict current projection/source proof differs')
    source_proofs=WORK/'immutable-evidence'/source
    gate_proof=load(source_proofs/'final-five-gate-results.json')
    tree_proof=load(source_proofs/'final-projection-verification.json')
    require(gate_proof['sourceCommit']==tree_proof['sourceCommit']==source
            and gate_proof['artifactCommit']==tree_proof['artifactCommit']==commit
            and gate_proof['allFiveGatesPassed'] is True and gate_proof['allElevenActualAndroidReportsPassed'] is True
            and tree_proof['allElevenReportsPassed'] is True and gate_proof['manifestSha256']==manifest_sha
            and gate_proof['unsignedSha256']==tree_proof['projectedUnsignedSha256']==public['signed']['unsignedSha256'],
            'Frozen five-gate/projection summary differs')
    files['projection/current-evidence-verification.json']=read(WORK/'current-evidence-verification.json')
    files['projection/current-evidence-files.json']=read(WORK/'current-evidence-files.json')
    files['projection/final-five-gate-results.json']=read(source_proofs/'final-five-gate-results.json')
    files['projection/final-projection-verification.json']=read(source_proofs/'final-projection-verification.json')
    files['archive-helper.py']=read(pathlib.Path(__file__))
    for name in ('manifest.json','mihomo-rebuild-results.json','mihomo-build-receipt.json','build.log','validation.json'):
        files['independent-native-rebuild/'+name]=read(native_dir/name)
    for name in ('packaged-native-verification.json','public-download-verification.json','public-update-feed-verification.json','public-range-verification.json'):
        files[name]=read(WORK/name)
    files['apk-verification.json']=read(ROOT/'dist/gecko-apk-verification.json')
    files.update(exploration)
    files.update(linux_files);files.update(failure_files)
    for name in GATES:files['release-gates/'+name]=git_bytes(source,'tools/gecko/'+name)
    for name in (RECEIPT,data['core']['inputs']['patch'],'third-party/patches/mihomo-v1.19.31-probe.md','tools/build-mihomo.py',SDK):
        files['source-inputs/'+pathlib.Path(name).name]=git_bytes(source,name)
    evidence={'schema':1,'status':'passed','version':VERSION,'versionCode':CODE,'sourceCommit':source,
              'runId':data['manifest']['runId'],'artifactCommit':commit,'immutableManifestSha256':manifest_sha,
              'normalAndroidSuites':11,'hostSuites':14,'hostChecks':data['hostChecks'],'releaseGates':data['gates'],
              'strictSourceFirstParentAndProjectionVerified':True,'projectionTreeFiles':tree_proof['gitTreeFilesVerifiedAndProjected'],
              'actualAndroidPreconnect':data['preconnect'],'independentNative':native,'exploratory':exploratory_proof,
              'historicalLinuxProcess':linux_proof,'historicalAndroidFailure':failure_proof,
              'signedApkSha256':public['signed']['sha256'],'originalSignerSha256':SIGNER,
              'publicRangeAndIfRangeVerified':True,'privateKeysOrLargeBinariesArchived':False,
              'files':{name:{'bytes':len(raw),'sha256':sha(raw)} for name,raw in sorted(files.items())}}
    return files,evidence,public


def write_archive(source,files,evidence,public):
    target=ROOT/'verification/network-preconnect-v1.5.21'
    require(not target.exists() and not target.is_symlink(),'Archive exists; refusing overwrite')
    stage=pathlib.Path(tempfile.mkdtemp(prefix='.archive-preconnect-',dir=WORK))
    try:
        for name,raw in files.items():
            path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        (stage/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        (stage/'README.md').write_text(f'''# 1.5.21 · 固定出口连接预认证

源码 `{source}`。11 套同源码实际 Android 报告、14 套主机报告 {evidence['hostChecks']} 项检查和五组既有发布门槛通过；新增预认证由 [真实 Gecko/SOCKS/H2 报告](preconnect-results.json) 与共享 wire contract 验证。[不可变构建 manifest](manifest.json) 的原始 SHA 为 `{evidence['immutableManifestSha256']}`；完整文件身份见 [evidence.json](evidence.json)。

[原始 Git blob 与首父源码绑定](projection/current-evidence-verification.json)、[严格投影](projection/final-projection-verification.json)、[五门槛摘要](projection/final-five-gate-results.json) 和 [本次 helper 快照](archive-helper.py) 保留归档过程；本目录没有复制 APK 分块或大型二进制。

准备阶段只完成固定出口的 SOCKS 方法与认证，不连接网站。一条连接只交付一次；实际请求仍完成目标 CONNECT、TLS 与 H2 响应。报告保留三组成对冷请求及真实 wire 时间、网络/入口代际清理、过期、错误认证、在途取消、测速绕过和原 WSS 持续收发。准备工作仍消耗网络、内存和电量；此处合成延时下的收益不代表用户 WAN 413 ms 或网站 3416 ms 已降低。

[独立 native 重建](independent-native-rebuild/mihomo-rebuild-results.json) 使用同源码、原始上游与提交补丁，两个 ABI 字节相同，36 项预认证及原 10 项探测回归各通过一次。它是重建/本地原生证明，不代替 Android 运行证据。官方 Firefox 157.0.1 SDK 的 receipt 与实际 Gradle AAR 相同，未做私有 SDK 改写。

[Python wire 调查](exploratory/python/results.json) 保留原源码 `{evidence['exploratory']['pythonOriginalSourceCommit']}`，未运行生产 Mihomo/Android；[Go normal/race 调查](exploratory/go/native-validation-receipt.json) 保留冻结 source identity、日志 SHA、36 normal /36 race/原10与 clean-apply receipt，仅为受控机制调查，不计入本版 11 套 Android，也不作为公网速度结论。旧 1.5.20 归档和 200/52 基线未改写。

[完整 Linux 进程调查](exploratory/linux-process/manifest.json) 保留原 `140a9d8`、实际 Linux 二进制 SHA、wire、失败尝试及原时序定义；该 native 组件与最终源码字节相同，但不是最终源码 Android 验收或独立 Linux 可复现重建。[此前 Android 失败](historical-failures/android-140a/preconnect-results.json) 保留原不可变 artifact：十套既有回归通过，新预认证完成七项后遇到 Files.readString API 异常；没有改为通过或借给本次源码验收。网络代际用受控事件注入，未实测手机 Wi-Fi 切换蜂窝。

[下载 APK]({public['download']['url']})：1.5.21 / code47，SHA `{public['signed']['sha256']}`，原签名 `{SIGNER}`。[完整公网下载](public-download-verification.json)、[更新源](public-update-feed-verification.json)、[官方 CDN Range/If-Range](public-range-verification.json) 与原签名 APK 一致，支持覆盖安装。环境登录、固定出口和失败拒绝保护保留，没有自动重发或直连回退。

验收使用 Android x86_64 模拟器与合成节点。尚未验证用户 ARM 真机、真实账号、现场冷启动/电量、不同运营商及同 Wi-Fi 的手机电脑对照；既有偶发输入边界不因本次网络改动而宣称修复。未归档证书私钥、签名密钥、API 令牌或大型 SDK/native/APK 文件。
''',encoding='utf-8')
        # Fresh principal source/gate identities before the one-way directory rename.
        again=same_source_reports(source)
        require(again['manifest']==load(stage/'manifest.json') and again['gates']==evidence['releaseGates'],'Evidence changed during staging')
        require(public_identity(source,again)==public,'Signed/public identity changed during staging')
        require(all(file_sha(stage/name)==item['sha256'] for name,item in evidence['files'].items()),'Staged evidence changed')
        require(not target.exists() and not target.is_symlink(),'Concurrent archive exists')
        stage.rename(target);return target
    finally:
        if stage.exists():shutil.rmtree(stage)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--check',action='store_true');mode.add_argument('--write',action='store_true')
    args=parser.parse_args()
    try:
        files,evidence,public=prepare(args.source)
        result={'ready':True,'archived':False,'sourceCommit':args.source,'normalAndroidSuites':11,
                'hostChecks':evidence['hostChecks'],'preconnect':evidence['actualAndroidPreconnect']}
        if args.write:result.update(archived=True,archive=str(write_archive(args.source,files,evidence,public)))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (AssertionError,ValueError,KeyError,OSError,subprocess.CalledProcessError) as error:
        print(json.dumps({'ready':False,'archived':False,'sourceCommit':args.source,'requiredVersion':VERSION,
                          'requiredVersionCode':CODE,'requiredNormalAndroidSuites':11,'requiredHostSuites':14,
                          'minimumHostChecks':464,'requiredSharedGates':5,'requiredPreconnectWireContract':True,
                          'requiredIndependentNativeTests':46,'blocked':str(error)},ensure_ascii=False));raise SystemExit(2)


if __name__=='__main__':main()
