#!/usr/bin/env python3
"""Execute production collection sharing with declared, counted app/storage adapters."""
import argparse,hashlib,json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat'
def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',type=pathlib.Path,required=True);p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 inputs=[PROD/'DownloadCollection.java',PROD/'DownloadCollectionShare.java',HERE/'ShareCases.java',pathlib.Path(__file__).resolve(),*sorted((HERE/'share-stubs').rglob('*.java'))];hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inputs}
 with tempfile.TemporaryDirectory(prefix='download-share-')as raw:
  classes=pathlib.Path(raw)/'classes';compile=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,[f for f in inputs if f.suffix=='.java'])],text=True,capture_output=True);(a.output/'compile.stdout.txt').write_text(compile.stdout);(a.output/'compile.stderr.txt').write_text(compile.stderr);compile.check_returncode()
  run=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.ShareCases'],text=True,capture_output=True,timeout=60);(a.output/'stdout.txt').write_text(run.stdout);(a.output/'stderr.txt').write_text(run.stderr);run.check_returncode();report=json.loads(run.stdout);report['sourceFiles']=hashes;report['executionInputsUnchanged']=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items());(a.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');assert report['executionInputsUnchanged'];print(json.dumps({'status':report['status'],'checks':report['checks'],'output':str(a.output)}))
if __name__=='__main__':main()
