#!/usr/bin/env python3
"""Execute complete production route/verification method bodies with explicit adapters."""
import argparse,hashlib,json,pathlib,subprocess,shutil
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--yaml-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
java=str(a.java_home/'bin/java') if a.java_home else shutil.which('java');javac=str(a.java_home/'bin/javac') if a.java_home else shutil.which('javac')
if not java or not javac:p.error('Provide a JDK or --java-home')
root=pathlib.Path(__file__).resolve().parents[2];prod=root/'app/src/main/java/local/pocketchat';work=root/'work/network-share-ui-flow';work.mkdir(parents=True,exist_ok=True)
s=(prod/'NetworkShareUi.java').read_text()
def member(start):
 i=s.index(start);brace=s.index('{',i);depth=1;j=brace+1;quote=None;escape=False;line=False;block=False
 while depth:
  c=s[j];n=s[j+1:j+2]
  if line:
   if c=='\n':line=False
  elif block:
   if c=='*' and n=='/':block=False;j+=1
  elif quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c==quote:quote=None
  elif c=='/' and n=='/':line=True;j+=1
  elif c=='/' and n=='*':block=True;j+=1
  elif c in ['"',"'"]:quote=c
  elif c=='{':depth+=1
  elif c=='}':depth-=1
  j+=1
 return s[i:j]
needles=['interface RouteLoad','static final class Prepared','static String side(','static String readFailure(','static JSONObject selected(','static void nodeMenu(','static void route(','static void verifyPrepared(']
source=(pathlib.Path(__file__).parent/'NetworkShareUiFlowHost.java.in').read_text().replace('@PRODUCTION_MEMBERS@','\n'.join(member(x) for x in needles));fixture=work/'NetworkShareUiFlowHost.java';fixture.write_text(source)
files=[prod/x for x in ['J.java','NetworkShareCodec.java','NetworkShareSchema.java','NetworkShareSnapshot.java','NetworkShareJson.java']];cp=f'{a.json_jar.resolve()}:{a.yaml_jar.resolve()}';classes=work/'classes';classes.mkdir(exist_ok=True)
subprocess.run([javac,'-encoding','UTF-8','-cp',cp,'-d',str(classes),*map(str,files),str(fixture)],check=True)
r=subprocess.run([java,'-cp',f'{classes}:{cp}','local.pocketchat.NetworkShareUiFlowHost'],text=True,capture_output=True,check=True);d=json.loads(r.stdout);d['productionSourceSha256']=hashlib.sha256((prod/'NetworkShareUi.java').read_bytes()).hexdigest();d['members']=needles
out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(d,ensure_ascii=False))
