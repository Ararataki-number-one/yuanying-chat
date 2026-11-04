#!/usr/bin/env python3
"""Execute full production presentation/search workloads; UI dispatch methods extracted verbatim."""
import argparse,hashlib,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];here=pathlib.Path(__file__).resolve().parent;work=a.output.parent;classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
def member(text,needle):
    start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False
    for i in range(opened,len(text)):
        c=text[i]
        if quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c==quote:quote=None
        elif c in ('"',"'"):quote=c
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return text[start:i+1]
    raise ValueError(needle)
source=root/'app/src/main/java/local/pocketchat/WindowHomeActivity.java'
text=source.read_text()
baseline_commit='5900426428e00a95acf5126f6154f34ff2d46930'
baseline=subprocess.run(['git','show',baseline_commit+':app/src/main/java/local/pocketchat/WindowHomeActivity.java'],cwd=root,capture_output=True,text=True,check=True).stdout
parts={'CURRENT_SHOW_PROBLEM':member(text,'void showProblem(String message)'),'CURRENT_ACCEPT':member(text,'void acceptSnapshot(EnvironmentHomeSnapshot value)'),'CURRENT_RENDER':member(text,'void renderCached()'),'CURRENT_SCHEDULE':member(text,'void scheduleSearch()'),'CURRENT_CALLBACK':member(text,'public void onTextChanged(CharSequence s,int x,int b,int c)'),'BASELINE_CALLBACK':member(baseline,'public void onTextChanged(CharSequence s,int x,int b,int c)')}
template=here/'SearchDispatchHost.java.in';generated=work/'SearchDispatchHost.java';content=template.read_text()
for key,value in parts.items():content=content.replace(key,value)
generated.write_text(content)
names=['J.java' ,'EnvironmentWorkspacePolicy.java','EnvironmentPresentation.java','EnvironmentSearchIndex.java'];sources=[root/'app/src/main/java/local/pocketchat'/name for name in names]+[here/'PresentationHost.java',generated]
javac=a.java_home/'bin/javac';java=a.java_home/'bin/java'
subprocess.run([str(javac),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,sources)],check=True)
r=subprocess.run([str(java),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.PresentationHost'],capture_output=True,text=True,check=True);report=json.loads(r.stdout)
dispatch=subprocess.run([str(java),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.SearchDispatchHost'],capture_output=True,text=True,check=True)
report['searchDispatch']=json.loads(dispatch.stdout)
report['sourceCallbackExtraction']={'baselineCommit':baseline_commit,'methodsSha256':{key:hashlib.sha256(value.encode()).hexdigest() for key,value in parts.items()},'boundaries':'Controlled Handler, cached snapshot and render target; source callbacks extracted verbatim. Baseline refresh boundary counts its direct catalog read, excludes additional default-slot reads.'}
report['scope']='Complete production display stamps/binding and normalized search index on deterministic 8-environment workloads. No Android layout, frame timing, allocation tracing, or device execution.'
report['sourceSha256']={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources if path.is_relative_to(root)}
report['sourceSha256'][str(source.relative_to(root))]=hashlib.sha256(source.read_bytes()).hexdigest()
report['sourceSha256'][str(template.relative_to(root))]=hashlib.sha256(template.read_bytes()).hexdigest()
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
