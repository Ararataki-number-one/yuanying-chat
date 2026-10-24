#!/usr/bin/env python3
"""Exact production download continuation/retirement paths with host-only services."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent

def member(text,needle):
 start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
 while i<len(text):
  c=text[i];n=text[i:i+2]
  if line:
   if c=='\n':line=False
  elif block:
   if n=='*/':block=False;i+=1
  elif quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c==quote:quote=None
  elif n=='//':line=True;i+=1
  elif n=='/*':block=True;i+=1
  elif c in ('"',"'"):quote=c
  elif c=='{':depth+=1
  elif c=='}':
   depth-=1
   if depth==0:return text[start:i+1]
  i+=1
 raise ValueError(needle)

def main():
 p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--before-ref');p.add_argument('--before-writer-ref');p.add_argument('--before-range-ref');p.add_argument('--before-load-ref');a=p.parse_args()
 if sum(bool(x) for x in (a.before_ref,a.before_writer_ref,a.before_range_ref,a.before_load_ref))>1:p.error('Select one before reproduction')
 source=ROOT/'app/src/main/java/local/pocketchat';old=ROOT/'tests/download-recovery-host'
 names=['J.java','DownloadTasks.java','DownloadTaskRevisions.java','DownloadResumePolicy.java','DownloadRange.java','SavedFileDeletion.java','SavedFilePublication.java','DefaultDownloads.java','SealedFileIo.java']
 needles=['void taskActions(','boolean requestAvailable(','String continuationAction(','void requestRedownload(','void discardForRedownload(','boolean loadTask(','void newTask(','void updateTask(','void mark(','boolean valid(','void acceptResponse(','void retry(','void fail(','void pause(','void destroy(','void download(','void readChunk(']
 files=[source/n for n in names]+[source/'FileDownloads.java',HERE/'DownloadResumeHost.java',pathlib.Path(__file__).resolve(),old/'local/pocketchat/Support.java',ROOT/'tests/sealed-file-host/android/util/AtomicFile.java']+list((old/'android').rglob('*.java'))+list((HERE/'stubs').rglob('*.java'))
 hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();before=subprocess.check_output(['git','rev-parse',a.before_ref+'^{commit}'],cwd=ROOT,text=True).strip() if a.before_ref else None
 writer_before=subprocess.check_output(['git','rev-parse',a.before_writer_ref+'^{commit}'],cwd=ROOT,text=True).strip() if a.before_writer_ref else None
 range_before=subprocess.check_output(['git','rev-parse',a.before_range_ref+'^{commit}'],cwd=ROOT,text=True).strip() if a.before_range_ref else None
 load_before=subprocess.check_output(['git','rev-parse',a.before_load_ref+'^{commit}'],cwd=ROOT,text=True).strip() if a.before_load_ref else None
 text=(source/'FileDownloads.java').read_text();parts=[member(text,n) for n in needles]
 if before:
  previous=subprocess.check_output(['git','show',before+':app/src/main/java/local/pocketchat/FileDownloads.java'],cwd=ROOT,text=True)
  parts[0]=member(previous,needles[0])
 if writer_before:
  previous=subprocess.check_output(['git','show',writer_before+':app/src/main/java/local/pocketchat/FileDownloads.java'],cwd=ROOT,text=True);parts[needles.index('void acceptResponse(')]=member(previous,'void acceptResponse(')
 if range_before:
  previous=subprocess.check_output(['git','show',range_before+':app/src/main/java/local/pocketchat/FileDownloads.java'],cwd=ROOT,text=True);parts[needles.index('void download(')]=member(previous,'void download(')
 if load_before:
  previous=subprocess.check_output(['git','show',load_before+':app/src/main/java/local/pocketchat/FileDownloads.java'],cwd=ROOT,text=True);parts[needles.index('boolean loadTask(')]=member(previous,'boolean loadTask(')
 with tempfile.TemporaryDirectory(prefix='download-resume-host-') as temporary:
  temp=pathlib.Path(temporary);package=temp/'local/pocketchat';package.mkdir(parents=True)
  for n in names:(package/n).write_bytes((source/n).read_bytes())
  (package/'DownloadResumeHost.java').write_text((HERE/'DownloadResumeHost.java').read_text().replace('/* FILEDOWNLOADS */','\n'.join(parts)))
  support=(old/'local/pocketchat/Support.java').read_text();support=support.replace('final class FileDownloads {static String safeName(String name){return name;}}','');(package/'Support.java').write_text(support)
  stubs=[]
  for f in (old/'android').rglob('*.java'):
   target=temp/f.relative_to(old);target.parent.mkdir(parents=True,exist_ok=True);raw=f.read_text()
   if f.name=='Context.java':raw=raw.replace('public final class Context','public class Context')
   if f.name=='Handler.java':raw=raw.replace('public boolean post(Runnable r)', 'public boolean postDelayed(Runnable r,long delay){return post(r);}public boolean post(Runnable r)')
   target.write_text(raw);stubs.append(target)
  java=[*package.glob('*.java'),*stubs,ROOT/'tests/sealed-file-host/android/util/AtomicFile.java',*list((HERE/'stubs').rglob('*.java'))]
  binary=lambda name:str(a.java_home/'bin'/name) if a.java_home else name
  subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(temp),*map(str,java)],check=True)
  result=subprocess.run([binary('java'),'-Dbefore='+str(bool(before)).lower(),'-DbeforeWriter='+str(bool(writer_before)).lower(),'-DbeforeRange='+str(bool(range_before)).lower(),'-DbeforeLoad='+str(bool(load_before)).lower(),'-cp',str(temp)+os.pathsep+str(a.json_jar.resolve()),'local.pocketchat.DownloadResumeHost'],capture_output=True,text=True,timeout=45)
  if not result.stdout.strip():raise RuntimeError(result.stderr)
  report=json.loads(result.stdout);unchanged=all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
  report.update(sourceCommit=commit,beforeRef=before,beforeWriterRef=writer_before,beforeRangeRef=range_before,beforeLoadRef=load_before,sourceFiles=hashes,executionInputsUnchanged=unchanged,selectedTaskActionsSha256=hashlib.sha256(parts[0].encode()).hexdigest(),selectedAcceptResponseSha256=hashlib.sha256(parts[needles.index('void acceptResponse(')].encode()).hexdigest(),selectedDownloadSha256=hashlib.sha256(parts[needles.index('void download(')].encode()).hexdigest(),selectedLoadTaskSha256=hashlib.sha256(parts[needles.index('boolean loadTask(')].encode()).hexdigest(),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(),actualAndroidExecution=False,productionClasses=names,productionMethods=needles,scope='Complete production DownloadTasks/revision/continuation/publication classes plus exact FileDownloads methods, controlled UI/Android/Gecko response adapters, real JVM workers and synthetic files. Not actual Android, native Gecko, network or user-file execution.')
  if result.stderr:report['stderr']=result.stderr
  if not unchanged:report['status']='invalid-source-changed'
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','passed','total','executionInputsUnchanged']}))
  if result.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
