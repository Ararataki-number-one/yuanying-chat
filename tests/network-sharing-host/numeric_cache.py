#!/usr/bin/env python3
"""Full numeric candidate/catalogue chain with explicit host storage boundaries."""
import argparse,pathlib,subprocess,shutil
p=argparse.ArgumentParser();p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--yaml-jar',type=pathlib.Path,required=True);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];prod=root/'app/src/main/java/local/pocketchat';work=root/'work/network-share-numeric-cache';work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java');javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac');cp=f'{a.json_jar.resolve()}:{a.yaml_jar.resolve()}'
sources=[prod/x for x in ['J.java','NetworkCatalog.java','NetworkSubscriptionCatalogPolicy.java','NetworkShareCodec.java','NetworkShareSchema.java','NetworkShareSnapshot.java']]
sources += [f for f in (root/'tests/network-catalog-host').rglob('*.java') if f.name!='NetworkCatalogHostTest.java']
sources += list((pathlib.Path(__file__).parent/'numeric').glob('*.java'))
subprocess.run([javac,'-encoding','UTF-8','-cp',cp,'-d',str(classes),*map(str,sources)],check=True)
out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True)
subprocess.run([java,'-cp',f'{classes}:{cp}','local.pocketchat.NetworkShareNumericCacheTest',str(out)],check=True)
