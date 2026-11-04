#!/usr/bin/env python3
"""Run production workspace policy and full saved-view adapter with host preference storage."""
import argparse, hashlib, json, pathlib, shutil, subprocess
def member(text,needle):
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
    while i<len(text):
        c=text[i];pair=text[i:i+2]
        if line:
            if c=='\n':line=False
        elif block:
            if pair=='*/':block=False;i+=1
        elif quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif pair=='//':line=True;i+=1
        elif pair=='/*':block=True;i+=1
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
        i+=1
    raise ValueError(needle)
p=argparse.ArgumentParser()
p.add_argument('--java-home',type=pathlib.Path)
p.add_argument('--json-jar',required=True,type=pathlib.Path)
p.add_argument('--output',required=True,type=pathlib.Path)
a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java')
javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac')
work=a.output.parent/'classes';work.mkdir(parents=True,exist_ok=True)
here=pathlib.Path(__file__).resolve().parent
sources=[root/'app/src/main/java/local/pocketchat'/name for name in ('J.java','EnvironmentWorkspacePolicy.java','EnvironmentSavedViews.java')]+sorted(here.rglob('*.java'))
switcher=root/'app/src/main/java/local/pocketchat/EnvironmentSwitcherUi.java'
generated=work.parent/'EnvironmentSwitcherUi.java'
generated.write_text('package local.pocketchat;\nimport android.app.Activity;\nimport android.content.Intent;\nimport android.os.Build;\nimport org.json.JSONObject;\nfinal class EnvironmentSwitcherUi {\n'+member(switcher.read_text(),'static boolean open(')+'\n}\n')
subprocess.run([javac,'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(work),*map(str,sources),str(generated)],check=True)
result=subprocess.run([java,'-cp',str(work)+':'+str(a.json_jar),'local.pocketchat.EnvironmentWorkspaceHost'],capture_output=True,text=True,check=True)
report=json.loads(result.stdout)
report['scope']='Complete production EnvironmentWorkspacePolicy and EnvironmentSavedViews plus verbatim extracted EnvironmentSwitcherUi.open; minimal Context/SharedPreferences use in-memory host storage and navigation boundaries use Activity/Intent/Build/catalog doubles. No Android execution, browser APIs or disk SharedPreferences lifecycle.'
report['sourceSha256']={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [*sources,switcher]}
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
