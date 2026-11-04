#!/usr/bin/env python3
"""Run verbatim AOSP name-grammar methods on manifest literals, outside Android."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
NAMESPACE='{http://schemas.android.com/apk/res/android}'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--java-home',type=pathlib.Path);parser.add_argument('--output',type=pathlib.Path,default=ROOT/'work/browser-manifest-host/results.json');args=parser.parse_args()
 tool=lambda name:str(args.java_home/'bin'/name)if args.java_home else shutil.which(name)
 if not tool('java')or not tool('javac'):parser.error('A real JDK is required')
 java=HERE/'AospManifestNames.java';provenance=HERE/'aosp-provenance.json';pinned=json.loads(provenance.read_text());assert digest(java)==pinned['excerptFileSha256'],'AOSP excerpt changed'
 paths=[ROOT/'app/src/main/AndroidManifest.xml',ROOT/'tests/gecko/AndroidManifest.xml',ROOT/'tests/gecko/update-fixture.xml',ROOT/'tests/native-input-driver/AndroidManifest.xml']
 generated=ROOT/'app/build/generated/gecko/AndroidManifest.xml'
 if generated.is_file():paths.append(generated)
 build_script=ROOT/'app/build.gradle';assert build_script.read_text().count("applicationIdSuffix '.test'")==1,'Integration package context changed'
 main_package=ET.parse(paths[0]).getroot().get('package');assert main_package
 inputs=paths+[java,provenance,build_script,pathlib.Path(__file__).resolve()];hashes={str(p.relative_to(ROOT)):digest(p)for p in inputs}
 rows=[];expected=[];labels=[]
 def add(kind,pkg,value,valid,label):
  assert all('\t'not in x and '\n'not in x and '\r'not in x for x in (kind,pkg,value));rows.append('\t'.join((kind,pkg,value)));expected.append(valid);labels.append(label)
 for path in paths:
  xml=ET.parse(path).getroot();pkg=xml.get('package')or(main_package+'.test'if path==ROOT/'tests/gecko/AndroidManifest.xml'else main_package);add('package',pkg,pkg,True,str(path.relative_to(ROOT))+':package')
  for item in xml.iter():
   for kind in ('taskAffinity','process'):
    value=item.get(NAMESPACE+kind)
    if value is not None:add(kind,pkg,value,True,str(path.relative_to(ROOT))+':'+item.get(NAMESPACE+'name',item.tag)+':'+kind)
 controls=[('taskAffinity','local.pocketchat.test.browser_probe',True),('taskAffinity','local.pocketchat.test.browser-probe',False),('taskAffinity','',True),('taskAffinity',':probe',True),('taskAffinity',':probe-bad',False),('taskAffinity',':',False),('taskAffinity','local.pocketchat/bad',False),('process',':profile1',True),('process',':profile_one',True),('process',':profile-one',False),('process',':1profile',False),('process','local.pocketchat.profile1',True),('package','local.pocketchat.test',True),('package','local.pocketchat-test',False),('package','local.pocketchat bad',False)]
 for kind,value,valid in controls:add(kind,'local.pocketchat.test',value,valid,'control:'+kind+':'+repr(value))
 with tempfile.TemporaryDirectory(prefix='manifest-name-host-')as directory:
  work=pathlib.Path(directory);cases=work/'cases.tsv';cases.write_text('\n'.join(rows)+'\n');classes=work/'classes'
  compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-d',str(classes),str(java)],text=True,capture_output=True,timeout=30)
  if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
  ran=subprocess.run([tool('java'),'-cp',str(classes),'AospManifestNames',str(cases)],text=True,capture_output=True,timeout=30)
  if ran.returncode:raise RuntimeError(ran.stdout+ran.stderr)
 observed=ran.stdout.splitlines();assert len(observed)==len(expected),'Incomplete name grammar execution'
 checks=[dict(name=label,expectedValid=valid,observed=result,passed=(result=='VALID')==valid)for label,valid,result in zip(labels,expected,observed)]
 unchanged=all(p.is_file()and digest(p)==hashes[str(p.relative_to(ROOT))]for p in inputs);passed=all(c['passed']for c in checks)and unchanged
 report=dict(status='passed'if passed else'failed',passed=sum(c['passed']for c in checks),total=len(checks),manifestCount=len(paths),checks=checks,sourceFiles=hashes,executionInputsUnchanged=unchanged,aospSource=pinned,actualAospNameMethodJvmExecution=True,actualAndroidExecution=False,actualPackageManagerExecution=False,scope='Verbatim AOSP Android15 validateName/buildCompoundName/buildTaskAffinityName methods on a JVM with explicit unused filename boundary. Validates literal package/process/taskAffinity grammar only; not a complete manifest parse or APK/device-install acceptance.')
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in ('status','passed','total','manifestCount','actualAndroidExecution','actualPackageManagerExecution')}));return 0 if passed else 1
if __name__=='__main__':sys.exit(main())
