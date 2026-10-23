#!/usr/bin/env python3
"""Exercise production share codec with JSON/YAML libraries, no Android mocks in codec."""
import argparse,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--yaml-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];classes=root/'work/network-sharing-host/classes';classes.mkdir(parents=True,exist_ok=True)
java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java');javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac')
cp=str(a.json_jar.resolve())+':'+str(a.yaml_jar.resolve())
sources=[root/'app/src/main/java/local/pocketchat'/n for n in ['J.java','NetworkShareCodec.java','NetworkShareSchema.java','NetworkShareSnapshot.java']]+list(pathlib.Path(__file__).parent.glob('*.java'))
subprocess.run([javac,'-encoding','UTF-8','-cp',cp,'-d',str(classes),*map(str,sources)],check=True)
subprocess.run([java,'-cp',str(classes)+':'+cp,'local.pocketchat.NetworkShareCodecTest'],cwd=root,check=True)

subprocess.run([java,'-cp',str(classes)+':'+cp,'local.pocketchat.NetworkShareSnapshotTest',str(root/'work/network-sharing-host/snapshot-results.json')],cwd=root,check=True)

flow=['python3',str(pathlib.Path(__file__).parent/'ui_flow.py'),'--json-jar',str(a.json_jar.resolve()),'--yaml-jar',str(a.yaml_jar.resolve())]
if a.java_home:flow+=['--java-home',str(a.java_home.resolve())]
subprocess.run(flow,cwd=root,check=True)

numeric=['python3',str(pathlib.Path(__file__).parent/'numeric_cache.py'),'--json-jar',str(a.json_jar.resolve()),'--yaml-jar',str(a.yaml_jar.resolve())]
if a.java_home:numeric+=['--java-home',str(a.java_home.resolve())]
subprocess.run(numeric,cwd=root,check=True)
