#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--java-home',type=Path,default=Path(os.environ.get('JAVA_HOME',root/'work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64')))
parser.add_argument('--output',type=Path,default=root/'work/chromium-route-host/report.json')
args=parser.parse_args()
output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
work=output.parent/(output.stem+'-work');work.mkdir(parents=True,exist_ok=True)
java=args.java_home.resolve()/'bin'
sources=[root/'app/src/main/java/local/pocketchat'/name for name in ['ChromiumRoutePolicy.java','ChromiumRouteLease.java','EnvironmentBrowserData.java','BrowserAddressPolicy.java']]+[Path(__file__).parent/'local/pocketchat/ChromiumRouteCases.java']
delete_source=root/'app/src/main/java/local/pocketchat/EnvironmentDeleteActivity.java'
delete_text=delete_source.read_text()
prefs=next(line.strip() for line in delete_text.splitlines() if 'File[] prefs=new File(data,"shared_prefs")' in line)
databases=next(line.strip() for line in delete_text.splitlines() if 'if(slot>0){File[] dbs=' in line)
erase=next(line.strip() for line in delete_text.splitlines() if 'static void erase(File f)' in line)
prefix=next(line.strip() for line in delete_text.splitlines() if line.strip().startswith('String prefix=slot==0?'))
selection=work/'DeletePreferenceSelection.java'
selection.write_text('package local.pocketchat; import java.io.*; final class DeletePreferenceSelection { static void clear(File data,int slot)throws IOException { Object c=null;\n'+prefix+'\n'+prefs+'\n'+databases+'\n}\n'+erase+'\n}\n')
sources += [selection,Path(__file__).parent/'local/pocketchat/DeletePreferenceCases.java']
reset_source=root/'app/src/main/java/local/pocketchat/EnvironmentResetActivity.java'
reset_call=next(line.strip() for line in reset_source.read_text().splitlines() if 'EnvironmentBrowserData.clear(profile.getNoBackupFilesDir(),profile.getCacheDir())' in line)
delete_call=next(line.strip() for line in delete_text.splitlines() if 'EnvironmentBrowserData.clear(profile.getNoBackupFilesDir(),profile.getCacheDir())' in line)
clear_entry=work/'BrowserDataClearEntry.java'
clear_entry.write_text('package local.pocketchat; import java.io.*; final class BrowserDataClearEntry { static void reset(ProfileFixture profile)throws IOException { '+reset_call+' } static void delete(ProfileFixture profile)throws IOException { '+delete_call+' } }')
sources += [clear_entry,Path(__file__).parent/'local/pocketchat/DownloadPartCleanupCases.java',Path(__file__).parent/'local/pocketchat/RouteLeaseCases.java']


subprocess.run([str(java/'javac'),'-encoding','UTF-8','-d',str(work),*map(str,sources)],check=True)
result=subprocess.run([str(java/'java'),'-cp',str(work),'local.pocketchat.ChromiumRouteCases'],capture_output=True,text=True,check=True)
delete_result=subprocess.run([str(java/'java'),'-cp',str(work),'local.pocketchat.DeletePreferenceCases'],capture_output=True,text=True,check=True)
cleanup_result=subprocess.run([str(java/'java'),'-cp',str(work),'local.pocketchat.DownloadPartCleanupCases'],capture_output=True,text=True,check=True)
lease_result=subprocess.run([str(java/'java'),'-cp',str(work),'local.pocketchat.RouteLeaseCases'],capture_output=True,text=True,check=True)
inputs=[p for p in sources if p not in [selection,clear_entry]]+[delete_source,reset_source,Path(__file__).resolve()]
report={'status':'passed','scope':'Execute production route callback state machine, global proxy mutation queue, exact data-directory erasure, universal address policy, and verbatim production preference/database deletion loops plus reset/delete partial-download cleanup against temporary files. No Android WebView execution claimed.','output':result.stdout.strip()+'\n'+delete_result.stdout.strip()+'\n'+cleanup_result.stdout.strip()+'\n'+lease_result.stdout.strip(),'downloadClearEntrySha256':hashlib.sha256(clear_entry.read_bytes()).hexdigest(),'deleteSelectionSha256':hashlib.sha256(selection.read_bytes()).hexdigest(),'sources':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'javaVersion':subprocess.check_output([str(java/'java'),'-version'],stderr=subprocess.STDOUT,text=True).strip(),'actualAndroidExecution':False}
output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(result.stdout+delete_result.stdout+cleanup_result.stdout+lease_result.stdout,end='')
