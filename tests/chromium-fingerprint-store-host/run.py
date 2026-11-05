#!/usr/bin/env python3
"""Execute full Chromium fingerprint storage with real files and separate JVMs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path)
    parser.add_argument('--json-jar',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/chromium-fingerprint-store-host/results.json',help='JSON report file')
    args=parser.parse_args()
    def tool(name):
        selected=str(args.java_home/'bin'/name) if args.java_home else shutil.which(name)
        if not selected:parser.error('Provide --java-home containing '+name)
        return selected
    sources=[PRODUCTION/name for name in ['ChromiumFingerprintStore.java','EnvironmentSpec.java','J.java']]
    inputs=sources+[HERE/'ChromiumFingerprintStoreHost.java',Path(__file__).resolve()]
    hashes={str(path.relative_to(ROOT)):digest(path) for path in inputs}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    results=[]
    with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-store-host-') as temporary:
        work=Path(temporary);classes=work/'classes';context=work/'android/content/Context.java';context.parent.mkdir(parents=True)
        context.write_text('package android.content;import java.io.File;public abstract class Context {public abstract Context getApplicationContext();public abstract File getNoBackupFilesDir();}\n')
        compiled=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(args.json_jar.resolve()),'-d',str(classes),*[str(path) for path in sources],str(HERE/'ChromiumFingerprintStoreHost.java'),str(context)],capture_output=True,text=True)
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        for phase in ['main','restart-seed','restart-check']:
            executed=subprocess.run([tool('java'),'-cp',str(classes)+':'+str(args.json_jar.resolve()),'local.pocketchat.ChromiumFingerprintStoreHost',phase,str(work/'state')],capture_output=True,text=True,timeout=30)
            if executed.returncode:raise RuntimeError(phase+' failed:\n'+executed.stderr)
            results.append(json.loads(executed.stdout))
    unchanged=all(path.is_file() and digest(path)==hashes[str(path.relative_to(ROOT))] for path in inputs)
    total=sum(result['passed'] for result in results)
    report=dict(status='passed' if unchanged else 'source-changed',passed=total,total=total,sourceCommit=commit,sourceFiles=hashes,
        executionInputsUnchanged=unchanged,jsonJarSha256=digest(args.json_jar),phases=results,separateJvmRestartExecuted=True,
        actualAndroidExecution=False,actualChromiumExecution=False,actualSqliteExecution=False,actualAesExecution=False,
        actualAndroidAtomicFileExecution=False,
        scope='Complete production ChromiumFingerprintStore, EnvironmentSpec and J. Real JVM SecureRandom, temporary filesystem, RandomAccessFile/FileLock and concurrent callers; explicit Context, catalog identity gate and atomic plain-file SecretStore adapters with prepublication/read failure injection. Separate JVMs share only temporary durable fixture bytes to verify process nonce invalidation after identical binding reactivation. No Android, actual AES-GCM/keystore/AtomicFile, SQLite transaction, WebView setting or page/worker fingerprint behavior execution. No seed or raw persisted receipt is exported in the report.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=total,total=total,separateJvmRestartExecuted=True,actualAndroidExecution=False,output=str(args.output)),ensure_ascii=False))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
