#!/usr/bin/env python3
"""Publish source-matched independent network diagnostics; no APKs or private data."""
import argparse,hashlib,json,os,pathlib,re,shutil,subprocess
from chain_runtime_contract import verify_native_probe,verify_gecko_pool
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'work/gecko-integration'
BRANCH='apk/gecko-chain-diagnostics'
BASE='e4a4a08202cf50ce60d36dd86a625366de9bb2f4'
REPORTS={'native':'native-probe-results.json','pool':'gecko-pool-results.json'}
ARTIFACTS=('build.log','integration-badging.txt','native-probe-results.json','native-probe-log.txt','native-probe-failure-log.txt','native-probe-runner.log','gecko-pool-results.json','gecko-pool-log.txt','gecko-pool-failure-log.txt','gecko-pool-runner.log','gecko-pool-server.json','gecko-pool-server-failure.json','chain-native-status.json','chain-pool-status.json')

def git(*args,env=None):return subprocess.check_output(['git',*args],cwd=ROOT,env=env,text=True).strip()
def regular(path):return path.is_file() and path.resolve().is_relative_to(OUT.resolve()) and not any(p.is_symlink() for p in (path,*path.parents) if p==OUT or OUT in p.parents)
def stamp_case(case,exit_code,source,run_id,attempt):
 report_path=OUT/REPORTS[case]
 if regular(report_path):
  value=json.loads(report_path.read_text());assert value['sourceCommit']==source and value['actualAndroidExecution'],'Report source or execution mismatch'
  value.update(diagnosticOnly=True,releaseAcceptance=False,runId=run_id,runAttempt=attempt)
  report_path.write_text(json.dumps(value,indent=2)+'\n')
 status={'case':case,'sourceCommit':source,'runId':run_id,'runAttempt':attempt,'exitCode':exit_code,'status':'passed' if exit_code==0 else 'failed','diagnosticOnly':True,'releaseAcceptance':False}
 (OUT/('chain-'+case+'-status.json')).write_text(json.dumps(status,indent=2)+'\n')

def stage_evidence(source,run_id,attempt,outcomes):
 assert re.fullmatch(r'[0-9a-f]{40}',source) and run_id.isdecimal() and attempt.isdecimal()
 try:
  base=git('rev-parse','--verify',BASE+'^{commit}')
 except subprocess.CalledProcessError:
  git('fetch','--no-tags','--depth=1','origin',BASE)
  base=git('rev-parse','--verify',BASE+'^{commit}')
 changed=git('diff','--name-only',base,source,'--','app','libs','third-party','build.gradle','settings.gradle','gradle.properties').splitlines()
 mutation='app/src/main/java/local/pocketchat/NativeNetwork.java'
 assert changed==[mutation],'Only the explicit Java startup cancellation candidate may change; SDK and native core remain pinned'
 original=subprocess.check_output(['git','show',base+':'+mutation],cwd=ROOT)
 candidate=subprocess.check_output(['git','show',source+':'+mutation],cwd=ROOT)
 stage=OUT/'chain-public'
 if stage.exists():shutil.rmtree(stage)
 stage.mkdir(parents=True)
 core=json.loads((ROOT/'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text());core['sourceCommit']=source
 (stage/'network-core-build.json').write_text(json.dumps(core,indent=2)+'\n')
 manifest={'sourceCommit':source,'productionBaseCommit':base,'runId':run_id,'runAttempt':attempt,'diagnosticOnly':True,'releaseAcceptance':False,'productionCodeAndOfficialSdkUnchanged':False,'productionCodeUnchanged':False,'officialSdkAndNativeCoreUnchanged':True,'productionMutation':{'file':mutation,'baseSha256':hashlib.sha256(original).hexdigest(),'sourceSha256':hashlib.sha256(candidate).hexdigest()},'stepOutcomes':outcomes,'cases':{},'reports':{},'artifacts':[],'warnings':[]}
 complete={}
 for name in ARTIFACTS:
  path=OUT/name
  if not regular(path):continue
  raw=path.read_bytes()
  if name in REPORTS.values() or name.startswith('chain-'):
   value=json.loads(raw);assert value['sourceCommit']==source and value['diagnosticOnly'] is True and value['releaseAcceptance'] is False,name
   assert value['runId']==run_id and value['runAttempt']==attempt,name
   if name in REPORTS.values():
    case=next(k for k,v in REPORTS.items() if v==name);assert value['actualAndroidExecution'],name
    passed=False
    if value.get('status')=='passed':
     try:
      if case=='native':verify_native_probe(value,core)
      else:verify_gecko_pool(value,value['server'])
      passed=True
     except Exception as error:manifest['warnings'].append(name+': '+str(error))
    complete[case]=passed;manifest['reports'][name]={'sourceCommit':source,'status':value.get('status'),'actualAndroidExecution':True,'checkCount':len(value.get('checks',[])),'completeDiagnosticPassed':passed}
   else:manifest['cases'][value['case']]=value
  (stage/name).write_bytes(raw)
 for path in sorted(stage.iterdir()):
  raw=path.read_bytes();manifest['artifacts'].append({'file':path.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 badging=(stage/'integration-badging.txt').read_text() if (stage/'integration-badging.txt').is_file() else ''
 manifest['compiledIntegrationNonDebuggable']="package: name='local.pocketchat.test'" in badging and 'application-debuggable' not in badging
 manifest['allDiagnosticsPassed']=manifest['compiledIntegrationNonDebuggable'] and outcomes.get('android') not in ('failure','cancelled','skipped') and set(complete)==set(REPORTS) and all(complete.values()) and set(manifest['cases'])==set(REPORTS) and all(v['exitCode']==0 for v in manifest['cases'].values()) and not manifest['warnings']
 (stage/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return stage,manifest

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=REPORTS);parser.add_argument('--exit-code',type=int);a=parser.parse_args()
 source=git('rev-parse','HEAD');assert source==os.environ['GITHUB_SHA'],'GitHub source mismatch'
 run_id=os.environ['GITHUB_RUN_ID'];attempt=os.environ.get('GITHUB_RUN_ATTEMPT','1');OUT.mkdir(parents=True,exist_ok=True)
 if a.case is not None:
  assert a.exit_code is not None;stamp_case(a.case,a.exit_code,source,run_id,attempt)
 outcomes={name:os.environ.get('CHAIN_'+name.upper()+'_OUTCOME','running') for name in ('setup','build','android')}
 stage,manifest=stage_evidence(source,run_id,attempt,outcomes)
 env=dict(os.environ,GIT_INDEX_FILE=str(OUT/'chain-public-index'),GIT_WORK_TREE=str(stage),GIT_AUTHOR_NAME='PocketChat chain diagnostics',GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',GIT_COMMITTER_NAME='PocketChat chain diagnostics',GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
 parents=['-p',source];previous=git('ls-remote','origin','refs/heads/'+BRANCH).split()
 if previous:git('fetch','origin','refs/heads/'+BRANCH);parents+=['-p',previous[0]]
 git('read-tree','--empty',env=env);git('add','-f','--','manifest.json',*[row['file'] for row in manifest['artifacts']],env=env);tree=git('write-tree',env=env);commit=git('commit-tree',tree,*parents,'-m','Publish independent synthetic chain diagnostics only',env=env);git('push','origin',commit+':refs/heads/'+BRANCH)
 print(json.dumps({'sourceCommit':source,'evidenceCommit':commit,'runId':run_id,'diagnosticOnly':True,'allDiagnosticsPassed':manifest['allDiagnosticsPassed']}))
if __name__=='__main__':main()
