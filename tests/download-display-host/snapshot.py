#!/usr/bin/env python3
"""Compile the entire actual snapshot and exact prior read methods against counted DB adapters."""
import argparse,hashlib,importlib.util,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat';BASE='3e3be57bd26e0cfaaee636749a3e4b76c8ab56fc'
spec=importlib.util.spec_from_file_location('snapshot_member',ROOT/'tests/download-names-host/run.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter);member=adapter.member;sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 legacy_raw=(HERE/'legacy31-read-members.json').read_bytes();assert sha(legacy_raw)=='5d6256b7933ac17ea7eda77a619fb6c1a5965dcf47d4503461fa44c4fdcc4927', 'Pinned original31 read members changed';legacy=json.loads(legacy_raw);assert legacy['source']==BASE
 methods,display=legacy['libraryMembers'],legacy['displayMembers'];fixture=(HERE/'SnapshotCases.java.in').read_text().replace('/* LEGACY_MEMBERS */',methods).replace('/* LEGACY_DISPLAY */',display)
 inputs=[Path(__file__).resolve(),HERE/'legacy31-read-members.json',HERE/'SnapshotCases.java.in',*HERE.glob('stubs/**/*.java'),*[PROD/n for n in ['DownloadDisplaySnapshot.java','DownloadListPolicy.java','J.java']]];hashes={str(x.relative_to(ROOT)):sha(x.read_bytes())for x in inputs}
 with tempfile.TemporaryDirectory(prefix='snapshot38-host-')as raw:
  temp=Path(raw);pkg=temp/'local/pocketchat';pkg.mkdir(parents=True);(pkg/'SnapshotCases.java').write_text(fixture)
  for n in ['DownloadDisplaySnapshot.java','DownloadListPolicy.java','J.java']:(pkg/n).write_bytes((PROD/n).read_bytes())
  classes=temp/'classes';run=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,pkg.glob('*.java')),*map(str,HERE.glob('stubs/**/*.java'))],text=True,capture_output=True,timeout=40);assert run.returncode==0,run.stdout+run.stderr
  run=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.SnapshotCases'],text=True,capture_output=True,timeout=40);assert run.stdout,run.stderr;report=json.loads(run.stdout)
 report.update(base=BASE,exactLegacyMembersSha256=sha(methods.encode()),exactLegacyDisplaySha256=sha(display.encode()),inputsSha256=hashes,executionInputsUnchanged=all(sha((ROOT/x).read_bytes())==h for x,h in hashes.items()),actualAndroidExecution=False,actualSqliteExecution=False,phonePerformanceMeasured=False,scope='Entire production snapshot class/DownloadListPolicy/J plus byte-exact prior library list/tasks/prune and display rows/ordered. Database boundary counts query/cursor calls and deterministically models a statement snapshot; no Android/real SQLite scheduling or I/O trace.')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(a.output),'sha256':sha(a.output.read_bytes())}));assert run.returncode==0 and report['status']=='passed' and report['executionInputsUnchanged'],run.stderr
if __name__=='__main__':main()
