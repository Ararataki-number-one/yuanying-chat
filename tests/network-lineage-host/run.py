#!/usr/bin/env python3
"""Controlled production pending-baseline lineage regression, explicitly host only."""
import argparse,json,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args();root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/network-lineage-host';classes=out/'classes';classes.mkdir(parents=True,exist_ok=True);report=a.output if a.output else out/'results.json';report.parent.mkdir(parents=True,exist_ok=True)
java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java');javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac')
if not java or not javac or not a.json_jar.is_file():p.error('A JDK and explicit org.json JAR are required')
production=[root/'app/src/main/java/local/pocketchat'/n for n in ('Sha256.java','J.java','NetworkCatalog.java','NetworkSubscriptionCatalogPolicy.java','NetworkSourceSelection.java','EntrySelection.java','NetworkDraft.java','NetworkChanges.java','NetworkOptimizationPolicy.java')]
fixtures=sorted((root/'tests/network-source-host').rglob('*.java'))+sorted(pathlib.Path(__file__).parent.rglob('*.java'))
subprocess.run([javac,'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(classes),*map(str,production+fixtures)],check=True)
result=subprocess.run([java,'-cp',f'{classes}:{a.json_jar.resolve()}','local.pocketchat.NetworkLineageHostTest'],text=True,stdout=subprocess.PIPE,check=True);receipt=json.loads(result.stdout);assert receipt['passed']==receipt['total']>=26 and not receipt['actualAndroidExecution'];report.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':receipt['passed'],'total':receipt['total'],'report':str(report)}))
