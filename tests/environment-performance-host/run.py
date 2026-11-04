#!/usr/bin/env python3
"""Count actual production refresh-queue work with controlled executor adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/ux-environment-performance/results.json')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    production=ROOT/'app/src/main/java/local/pocketchat/EnvironmentRefreshQueue.java'
    inputs=[production,HERE/'queue_host.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    with tempfile.TemporaryDirectory(prefix='environment-performance-host-') as temporary:
        classes=Path(temporary)/'classes'
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-d',str(classes),str(production),str(HERE/'queue_host.java')],text=True,capture_output=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        ran=subprocess.run([tool('java'),'-cp',str(classes),'local.pocketchat.EnvironmentRefreshQueueHost'],text=True,capture_output=True)
        if ran.returncode:raise RuntimeError(ran.stderr)
        report=json.loads(ran.stdout)
    unchanged=all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path.relative_to(ROOT))] for path in inputs)
    report.update(sourceCommit=commit,sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        sourceFiles=hashes,executionInputsUnchanged=unchanged,actualAndroidExecution=False,actualSqliteExecution=False,
        actualDevicePerformanceMeasurement=False,syntheticExecutorScheduling=True,
        scope='Complete production EnvironmentRefreshQueue compiled and executed with manually advanced worker/main Executor queues and explicit read/delivery adapters. Counts queued reads and applied snapshots under bursts, lifecycle epochs, close, callback reentrancy and failures. No Android frame, SQLite, disk, network or wall-clock performance measurement.')
    if not unchanged:report['status']='source-changed'
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'burstRequests':100,'burstWorkerReads':2,'actualAndroidExecution':False,'output':str(args.output)},ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
