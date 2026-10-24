#!/usr/bin/env python3
"""Exact default selection/deletion methods with transactional host DB adapters."""
import argparse,hashlib,json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent

def member(text,needle):
 start=text.index(needle);opened=text.index('{',start);depth=0;quote=None;escape=False;line=False;block=False;i=opened
 while i<len(text):
  c=text[i];n=text[i:i+2]
  if line:
   if c=='\n':line=False
  elif block:
   if n=='*/':block=False;i+=1
  elif quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c==quote:quote=None
  elif n=='//':line=True;i+=1
  elif n=='/*':block=True;i+=1
  elif c in ('"',"'"):quote=c
  elif c=='{':depth+=1
  elif c=='}':
   depth-=1
   if depth==0:return text[start:i+1]
  i+=1
 raise ValueError(needle)

def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--before-ref');p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();prod=ROOT/'app/src/main/java/local/pocketchat'
 names=['AppSettings.java','ProfileCatalog.java','EnvironmentSpec.java','BrandLaunchActivity.java','WorkspaceNavigation.java','WindowHomeActivity.java'];source={n:(subprocess.check_output(['git','show',a.before_ref+':app/src/main/java/local/pocketchat/'+n],cwd=ROOT) if a.before_ref else (prod/n).read_bytes()) for n in names}
 inputs=[prod/n for n in names]+sorted(HERE.rglob('*.java'))+[pathlib.Path(__file__).resolve()];hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
 catalog=['JSONObject item(','static JSONObject row(','JSONArray list(','EnvironmentSpec.Identity identity(','boolean available(','void opened(','void beginDelete(']
 text=(HERE/'DefaultEnvironmentHost.java').read_text().replace('/* CATALOG */','\n'.join(member(source['ProfileCatalog.java'].decode(),x) for x in catalog)).replace('/* IDENTITY */',member(source['EnvironmentSpec.java'].decode(),'static final class Identity')).replace('/* BRAND */',member(source['BrandLaunchActivity.java'].decode(),'void route(')).replace('/* OPEN_WINDOW */',member(source['WindowHomeActivity.java'].decode(),'void openWindow('))
 with tempfile.TemporaryDirectory(prefix='default-environment-host-') as raw:
  tmp=pathlib.Path(raw);base=tmp/'local/pocketchat';base.mkdir(parents=True);(base/'DefaultEnvironmentHost.java').write_text(text);(base/'AppSettings.java').write_bytes(source['AppSettings.java']);(base/'WorkspaceNavigation.java').write_bytes(source['WorkspaceNavigation.java']);classes=tmp/'classes';files=[*base.glob('*.java'),*HERE.glob('stubs/**/*.java')]
  subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)],check=True)
  result=subprocess.run([str(a.java_home/'bin/java'),'-Dbefore='+str(bool(a.before_ref)).lower(),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.DefaultEnvironmentHost'],text=True,capture_output=True)
  if not result.stdout:raise RuntimeError(result.stderr)
  report=json.loads(result.stdout);report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),selectedProductionRef=a.before_ref or 'working-tree',selectedProductionSha256={n:hashlib.sha256(raw).hexdigest() for n,raw in source.items()},sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),actualAndroidExecution=False,scope='Complete production AppSettings and exact ProfileCatalog deletion/item/list/identity plus exact EnvironmentSpec.Identity, launcher route, window open, and full WorkspaceNavigation. Controlled transactional database adapter and actual Java threads; no Android SQLite or deletion of real files.')
  if not report['executionInputsUnchanged']:report['status']='source-changed'
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'output':str(a.output)}))
  if result.returncode or report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
