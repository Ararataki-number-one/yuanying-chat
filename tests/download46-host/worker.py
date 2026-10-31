#!/usr/bin/env python3
"""Source-bound worker/snapshot scheduling checks; explicit counted host adapters."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat';OLD=ROOT/'tests/download-display-host/stubs';RECOVERY=ROOT/'tests/download-recovery-host/android/os'
def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 names=['J.java','DownloadDisplayCache.java','DownloadDisplaySnapshot.java','DownloadPageWindow.java','DownloadListPolicy.java','DownloadOwnerLabels.java'];inputs=[PROD/n for n in names]+[HERE/'Worker46Cases.java',pathlib.Path(__file__).resolve(),*OLD.rglob('*.java'),RECOVERY/'Handler.java',RECOVERY/'Looper.java'];hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inputs}
 with tempfile.TemporaryDirectory(prefix='download46-worker-')as raw:
  temp=pathlib.Path(raw);pkg=temp/'local/pocketchat';pkg.mkdir(parents=True)
  for name in names:(pkg/name).write_bytes((PROD/name).read_bytes())
  (pkg/'Worker46Cases.java').write_bytes((HERE/'Worker46Cases.java').read_bytes())
  for f in OLD.rglob('*.java'):
   target=temp/f.relative_to(OLD);target.parent.mkdir(parents=True,exist_ok=True);text=f.read_text()
   if f.name=='SQLiteDatabase.java':
    text=text.replace('public int queries,','public String[] ownerProjection;public int mainQueries;public int queries,').replace('queries++;','queries++;if(android.os.Looper.myLooper()==android.os.Looper.getMainLooper())mainQueries++;')
    text=text.replace('new String[]{"files","tasks","deleted_files"})tables','new String[]{"files","tasks","deleted_files","environments"})tables')
    text=text.replace('public void add(String table,JSONObject row){','public void add(String table,JSONObject row){if(table.equals("environments")){Map<String,Object> value=new LinkedHashMap<>();for(String key:new String[]{"slot","name","environment_id","generation","created","deleting","resetting"})value.put(key,row.opt(key));tables.get(table).add(value);return;}')
    text=text.replace('queries++;if(android.os.Looper.myLooper()', 'if(table.equals("environments"))ownerProjection=columns.clone();queries++;if(android.os.Looper.myLooper()',1)
   target.write_text(text)
  (temp/'android/os').mkdir(parents=True,exist_ok=True)
  for name in ['Handler.java','Looper.java']:(temp/'android/os'/name).write_bytes((RECOVERY/name).read_bytes())
  (temp/'android/os/Bundle.java').write_text('package android.os;public final class Bundle{final java.util.Map<String,Object> values=new java.util.HashMap<>();public void putLong(String key,long value){values.put(key,value);}public long getLong(String key){Object v=values.get(key);return v==null?0:((Number)v).longValue();}}')
  classes=temp/'classes';binary=lambda n:str(a.java_home/'bin'/n);compile=subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,temp.rglob('*.java'))],text=True,capture_output=True);(a.output/'compile.stdout.txt').write_text(compile.stdout);(a.output/'compile.stderr.txt').write_text(compile.stderr);compile.check_returncode()
  run=subprocess.run([binary('java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.Worker46Cases'],text=True,capture_output=True,timeout=90);(a.output/'stdout.txt').write_text(run.stdout);(a.output/'stderr.txt').write_text(run.stderr);report=json.loads(run.stdout);report.update(sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items()));(a.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');assert run.returncode==0 and report['status']=='passed'and report['executionInputsUnchanged'],report
  print(json.dumps({'status':report['status'],'checks':report['total'],'output':str(a.output)}))
if __name__=='__main__':main()
