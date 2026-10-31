#!/usr/bin/env python3
"""Execute exact 46 apply/bind code without altering historical source guards."""
import argparse,hashlib,importlib.util,json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat';NAMES=ROOT/'tests/download-names-host'
spec=importlib.util.spec_from_file_location('names46_readonly',NAMES/'run.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter);member=adapter.member
def main():
 p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 texts={name:(PROD/name).read_text()for name in ['DesignDownloads.java','DownloadTasks.java','ProfileCatalog.java','Profiles.java','Attachments.java','J.java','DownloadDisplaySnapshot.java']};selected={}
 def part(file,needle):value=member(texts[file],needle);selected[file+':'+needle]=hashlib.sha256(value.encode()).hexdigest();return value
 fixture=(NAMES/'DownloadNamesHost.java.in').read_text();fixture=fixture.replace(member(fixture,'public static void main('),(HERE/'Display46Cases.java.in').read_text())
 fixture=fixture.replace('/* CATALOG */','\n'.join(part('ProfileCatalog.java',n)for n in ['JSONObject item(','static JSONObject row(','String name(int slot)','Map<Integer,String> names()','static String displayName('])).replace('/* PROFILES_DISPLAY */',part('Profiles.java','static String display('))
 time=part('DesignDownloads.java','static String timeLabel(');fixture=fixture.replace('/* DOWNLOAD_HELPERS */','\n'.join(part('DesignDownloads.java',n)for n in ['static String key(','static boolean busy(','static boolean matches('])+'\n'+time.replace('static String timeLabel(JSONObject row){','static String timeLabel(JSONObject row){Meter.formats++;',1))
 fixture=fixture.replace('/* CONTROLLER_APPLY */',part('DesignDownloads.java','void apply(JSONArray data,'));
 bind=part('DesignDownloads.java','void bind(JSONObject row,');fixture=fixture.replace('/* ROW_BIND */',bind.replace('void bind(JSONObject row,long now,String environmentName){','void bind(JSONObject row,long now,String environmentName){Meter.binds++;',1)).replace('/* ROW_TEXT */',part('DesignDownloads.java','static void text(TextView')).replace('/* ROW_VISIBLE */',part('DesignDownloads.java','static void visible(View'))
 
 fixture=fixture.replace(member(fixture,'class DownloadTasks{'),'class DownloadTasks{'+part('DownloadTasks.java','static void put(')+part('DownloadTasks.java','static String label(')+part('DownloadTasks.java','static String amount(')+part('DownloadTasks.java','static String progress(')+'}')
 fixture=fixture.replace('void setText(String value){text=value;}','void setText(String value){text=value;if(Meter.resize!=null&&value.startsWith("resized-name")){Runnable change=Meter.resize;Meter.resize=null;change.run();}}')
 fixture=fixture.replace('for(int i=0;i<children.size();i++)children.get(i).top=i*100;','int top=0;for(int i=0;i<children.size();i++){children.get(i).top=top;top+=children.get(i).height;}')
 fixture+='\nclass DownloadDisplaySnapshot{'+part('DownloadDisplaySnapshot.java','static Map<Integer,DownloadOwnerLabels.Owner> owners(')+'}\n'
 fixture=fixture.replace(member(fixture,'class J{'),'class J{'+part('J.java','static JSONObject obj(')+'}')
 for method in ['counts','freshnessAndFallbacks','filteringAndDuplicates','anchors']:fixture=fixture.replace('static void '+method+'(){','static void '+method+'()throws Exception{')
 fixture+='\nclass Meter{static int binds,formats;static Runnable resize;static void reset(){binds=formats=0;}}\nclass Attachments{'+part('Attachments.java','static String sizeLabel(')+'}\n'
 names=['DownloadMetadataValues.java','DownloadTaskRevisions.java','DownloadPageWindow.java','DownloadListPolicy.java','DownloadRowBinding.java','DownloadOwnerLabels.java'];inputs=[HERE/'Display46Cases.java.in',pathlib.Path(__file__).resolve(),NAMES/'DownloadNamesHost.java.in',NAMES/'run.py',*[PROD/n for n in names],*[PROD/n for n in texts],*NAMES.glob('stubs/**/*.java')];hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inputs}
 with tempfile.TemporaryDirectory(prefix='download46-display-')as raw:
  temp=pathlib.Path(raw);pkg=temp/'local/pocketchat';pkg.mkdir(parents=True);(pkg/'DownloadNamesHost.java').write_text(fixture)
  for name in names:(pkg/name).write_bytes((PROD/name).read_bytes())
  classes=temp/'classes';binary=lambda n:str(a.java_home/'bin'/n);compile=subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,pkg.glob('*.java')),*map(str,NAMES.glob('stubs/**/*.java'))],text=True,capture_output=True);(a.output/'compile.stdout.txt').write_text(compile.stdout);(a.output/'compile.stderr.txt').write_text(compile.stderr);compile.check_returncode()
  run=subprocess.run([binary('java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.DownloadNamesHost'],text=True,capture_output=True,timeout=60);(a.output/'stdout.txt').write_text(run.stdout);(a.output/'stderr.txt').write_text(run.stderr);report=json.loads(run.stdout)
  report.update(sourceFiles=hashes,selectedMembers=selected,fixtureSha256=hashlib.sha256(fixture.encode()).hexdigest(),executionInputsUnchanged=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items()));(a.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');assert run.returncode==0 and report['status']=='passed'and report['executionInputsUnchanged'],report
  print(json.dumps({'status':report['status'],'checks':report['total'],'output':str(a.output)}))
if __name__=='__main__':main()
