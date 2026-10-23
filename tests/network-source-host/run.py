#!/usr/bin/env python3
"""Production draft/reference/snapshot logic with explicit non-Android storage fixtures."""
import argparse,json,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];work=root/'work/network-source-host';classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java');javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac')
if not java or not javac or not a.json_jar.is_file():p.error('Provide an org.json JAR and a working JDK')
sources=[root/'app/src/main/java/local/pocketchat'/n for n in ('Sha256.java','J.java','NetworkCatalog.java','NetworkShareSnapshot.java','NetworkSubscriptionCatalogPolicy.java','NetworkSourceSelection.java','EntrySelection.java','NetworkDraft.java','NetworkChanges.java','NetworkOptimizationPolicy.java')]
sources+=sorted(pathlib.Path(__file__).parent.rglob('*.java'))
subprocess.run([javac,'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(classes),*map(str,sources)],check=True)
result=subprocess.run([java,'-cp',f'{classes}:{a.json_jar.resolve()}','local.pocketchat.NetworkSourcesHostTest'],check=True,stdout=subprocess.PIPE,text=True,timeout=120)
receipt=json.loads(result.stdout);assert receipt['passed']==receipt['total']>=94 and receipt['actualCrossProcessSourceLease'] and receipt['actualCrossProcessActiveSnapshotLease'] and not receipt['actualAndroidExecution'] and not receipt['actualNativeExecution'];output=a.output or work/'results.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':receipt['passed'],'total':receipt['total'],'report':str(output)}))
