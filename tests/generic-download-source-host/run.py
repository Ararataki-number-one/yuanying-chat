#!/usr/bin/env python3
"""Execute actual FileDownloads source-metadata consumers on controlled JVM input."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat'
extractor=ROOT/'tests/gecko-navigation-host/run.py'
spec=importlib.util.spec_from_file_location('generic_download_source_members',extractor)
members=importlib.util.module_from_spec(spec);spec.loader.exec_module(members)
NEEDLES=('String downloadSource(','void acceptResponse(','void accept(','static boolean https(','void newTask(','boolean sameSource(','boolean valid(','static String safeName(','static String type(','static String imageExtension(')
MUTATIONS=(
 ('native-task','void acceptResponse(','newTask("","",source)','newTask("","",a.conversation)','native','Native task records the current generic page: http://example.com/downloads'),
 ('native-source','void acceptResponse(','sourceUrl=source','sourceUrl=a.conversation','native','Native in-memory source uses the same captured page: http://example.com/downloads'),
 ('url-task','void accept(','newTask("","",source)','newTask("","",a.conversation)','url','URL task records the current generic page: https://www.wikipedia.org/wiki/Download'),
 ('url-source','void accept(','sourceUrl=source','sourceUrl=a.conversation','url','URL in-memory source uses the same captured page: https://www.wikipedia.org/wiki/Download'),
 ('stale-helper','String downloadSource(','return MainActivity.chatUrl(current)?a.conversation:current==null?"":current;','return a.conversation;','native','Native task records the current generic page: http://example.com/downloads'),
 ('http-activation','void accept(','if(!https(url)&&!url.startsWith("blob:https://"))','if(false)','http','URL activation still refuses HTTP or unsafe address: http://cdn.example.com/controlled.bin'),
)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 def binary(name):
  selected=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
  if not selected:p.error('Provide --java-home containing '+name)
  return selected
 production=PROD/'FileDownloads.java';template=HERE/'DownloadSourceHost.java.in';complete=[PROD/'J.java',PROD/'BrowserRuntimePolicy.java']
 files=[production,template,Path(__file__).resolve(),extractor]+complete;hashes={str(path.relative_to(ROOT)):sha(path) for path in files};json_hash=sha(a.json_jar)
 raw=production.read_text();selected={needle:members.member_at(raw,raw.index(needle)) for needle in NEEDLES}
 def generate(values):
  body='\n'.join(values.values()).replace('org.mozilla.geckoview.WebResponse','ResponseBoundary').replace('Uri u=Uri.parse(url)','URI u=URI.create(url)').replace('System.currentTimeMillis()','Clock.wallMillis()')
  return template.read_text().replace('@PRODUCTION_MEMBERS@',body)
 a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(parents=True,exist_ok=True)
 generated=generate(selected);(artifacts/'DownloadSourceHost.java').write_text(generated);controls=[]
 with tempfile.TemporaryDirectory(prefix='generic-download-source-host-') as temporary:
  work=Path(temporary)
  def run(text,label,focus=None):
   folder=work/label;folder.mkdir(parents=True);source=folder/'DownloadSourceHost.java';source.write_text(text);classes=folder/'classes';logs=artifacts/label;logs.mkdir(parents=True,exist_ok=True);(logs/'DownloadSourceHost.java').write_text(text)
   cmd=[binary('javac'),'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(classes),str(source)]+[str(path) for path in complete]
   compiled=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(logs/'compile.command.json').write_text(json.dumps(cmd)+'\n');(logs/'compile.stdout.log').write_text(compiled.stdout);(logs/'compile.stderr.log').write_text(compiled.stderr)
   if compiled.returncode:raise RuntimeError(compiled.stderr)
   cmd=[binary('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.DownloadSourceHost']+([] if focus is None else [focus]);ran=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
   (logs/'run.command.json').write_text(json.dumps(cmd)+'\n');(logs/'run.stdout.log').write_text(ran.stdout);(logs/'run.stderr.log').write_text(ran.stderr);return ran
  ran=run(generated,'current')
  if ran.returncode:raise RuntimeError(ran.stdout+ran.stderr)
  report=json.loads(ran.stdout)
  for label,needle,before,after,focus,assertion in MUTATIONS:
   pristine=run(generated,'pristine-'+label,focus)
   if pristine.returncode or json.loads(pristine.stdout)['status']!='passed':raise AssertionError('Pristine schedule failed: '+label+pristine.stderr)
   if selected[needle].count(before)!=1:raise ValueError('Review exact source-metadata negative control: '+label)
   changed=dict(selected);changed[needle]=changed[needle].replace(before,after,1);mutant=generate(changed);rejected=run(mutant,'mutation-'+label,focus)
   if rejected.returncode==0 or 'AssertionError: '+assertion not in rejected.stderr:raise AssertionError('Expected original focused assertion did not reject mutant: '+label+rejected.stderr)
   controls.append(dict(case=label,productionMember=needle,removed=before,replacement=after,pristinePassed=True,mutantRejected=True,expectedAssertion=assertion,mutantGeneratedSha256=hashlib.sha256(mutant.encode()).hexdigest()))
 unchanged=all(sha(path)==hashes[str(path.relative_to(ROOT))] for path in files) and sha(a.json_jar)==json_hash
 report.update(status='passed' if unchanged else 'source-changed',sourceFiles=hashes,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),productionMembers=NEEDLES,selectedMethodsSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in selected.items()},negativeControls=controls,jsonJarSha256=json_hash,generatedSourceSha256=hashlib.sha256(generated.encode()).hexdigest(),executionInputsUnchanged=unchanged,boundarySubstitutions=['WebResponse type → ResponseBoundary with explicitly supplied synthetic body/headers/status and timeout recording; no Gecko SDK package is defined','Android Uri parse → JVM URI.create only inside actual https predicate','System.currentTimeMillis() → fixed deterministic clock','MainActivity.chatUrl delegates to actual BrowserRuntimePolicy.official with JVM URI','Download task storage, filename/MIME lookup, network admission, Handler/worker queues and sealed lease are declared controlled JVM boundaries','Native response body copies use real temporary host files and synthetic bytes; publication/URL client/blob/DOM execution are boundaries rather than Android/network acceptance'],scope='Actual FileDownloads downloadSource, acceptResponse, accept, newTask, sameSource and supporting predicates with actual J/org.json/BrowserRuntimePolicy. Controlled JVM browser/storage/admission/queue interfaces, native-response stream consumer and temporary synthetic bytes. No Android, Gecko SDK, sockets, TLS, public website or user-file acceptance.')
 if not report['checks'] or not all(row['pass'] is True for row in report['checks']):raise AssertionError('Download source checks failed')
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],negativeControls=len(controls),executionInputsUnchanged=unchanged,output=str(a.output))))
 if not unchanged:raise SystemExit(1)


if __name__=='__main__':main()
