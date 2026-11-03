#!/usr/bin/env python3
import argparse,hashlib,json,pathlib,subprocess,shutil
p=argparse.ArgumentParser();p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java');javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac')
work=a.output.parent/'classes';work.mkdir(parents=True,exist_ok=True);sources=[root/'app/src/main/java/local/pocketchat'/name for name in ('J.java','ChatDownloadProgress.java')]+[pathlib.Path(__file__).with_name('ChatDownloadProgressHost.java')]
subprocess.run([javac,'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(work),*map(str,sources)],check=True)
result=subprocess.run([java,'-cp',str(work)+':'+str(a.json_jar),'local.pocketchat.ChatDownloadProgressHost'],capture_output=True,text=True,check=True)
report=json.loads(result.stdout);report['sourceSha256']={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
