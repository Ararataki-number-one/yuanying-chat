#!/usr/bin/env python3
"""Run the production pure-Java event journal, including a separate JVM restart."""
import argparse,hashlib,json,pathlib,shutil,subprocess,tempfile

p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path);p.add_argument('--java-home',type=pathlib.Path);args=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
work=root/'work/plan-repairs/network-core';work.mkdir(parents=True,exist_ok=True)
java=str(args.java_home/'bin/java') if args.java_home else shutil.which('java')
javac=str(args.java_home/'bin/javac') if args.java_home else shutil.which('javac')
if not java or not javac:p.error('A JDK is required')
run=pathlib.Path(tempfile.mkdtemp(prefix='diagnostics-host-',dir=work));classes=run/'classes';classes.mkdir()
production=root/'app/src/main/java/local/pocketchat/NetworkDiagnostics.java'
fixture=pathlib.Path(__file__).with_name('NetworkDiagnosticsHostTest.java')
runner=pathlib.Path(__file__).resolve()
def source_identity():
    def git(*command):
        return subprocess.run(['git',*command],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
    status=git('status','--porcelain')
    return {'commit':git('rev-parse','HEAD'),'dirty':bool(status),'status':status.splitlines(),
            'sha256':{str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (production,fixture,runner)}}
before=source_identity()
subprocess.run([javac,'-encoding','UTF-8','-d',str(classes),str(production),str(fixture)],check=True)
reports=[]
for extra in ([],['restart']):
    result=subprocess.run([java,'-cp',str(classes),'local.pocketchat.NetworkDiagnosticsHostTest',str(run/'records'),*extra],capture_output=True,text=True,check=True,timeout=60)
    reports.append(json.loads(result.stdout))
after=source_identity()
unchanged=before['commit']==after['commit'] and before['sha256']==after['sha256']
report={'status':'passed' if unchanged else 'invalid-source-changed','actualAndroidExecution':False,'actualMihomoExecution':False,'productionClass':'NetworkDiagnostics','passed':sum(r['passed'] for r in reports),'runs':reports,
        'sourceBefore':before,'sourceAfter':after,'executionInputsUnchanged':unchanged}
target=args.output or work/'diagnostics-host-results.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'passed':report['passed'],'report':str(target)}))
if not unchanged:raise SystemExit(1)
