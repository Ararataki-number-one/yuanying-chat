#!/usr/bin/env python3
"""Compile current saved-copy callbacks and real URI/file leases against faulting streams."""
import argparse, hashlib, importlib.util, json, os, pathlib, subprocess, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PRODUCTION=ROOT/'app/src/main/java/local/pocketchat'
spec=importlib.util.spec_from_file_location('download_member',ROOT/'tests/download-resume-host/run.py')
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
NAMES=['J.java','SavedFileBytes.java','SavedFileDeletion.java','SealedFileIo.java']
METHODS=['void export(','void result(','static boolean delete(','void close(']

def read_host_report(run, output):
    """Keep the actual JVM outcome visible even when it could not emit JSON."""
    output.with_suffix('.stdout.txt').write_text(run.stdout)
    output.with_suffix('.stderr.txt').write_text(run.stderr)
    diagnostic={'exitCode':run.returncode,'stdout':run.stdout,'stderr':run.stderr}
    output.with_suffix('.run.log').write_text(json.dumps(diagnostic,ensure_ascii=False)+'\n')
    try:
        report=json.loads(run.stdout)
        if not isinstance(report,dict):raise ValueError('Expected a JSON object')
    except ValueError as error:
        raise RuntimeError('Saved-copy JVM report is not a JSON object: '+json.dumps(diagnostic,ensure_ascii=False)) from error
    if run.returncode:report['status']='failed'
    report['jvmExitCode']=run.returncode
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=pathlib.Path)
    parser.add_argument('--json-jar',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    shared=ROOT/'tests/download-recovery-host'
    support=[shared/'android'/name for name in ['os/Handler.java','os/Looper.java','net/Uri.java','database/Cursor.java','provider/OpenableColumns.java']]
    support.append(ROOT/'tests/sealed-file-host/android/util/AtomicFile.java')
    inputs=[PRODUCTION/name for name in NAMES+['SavedFileActions.java','DownloadMetadataValues.java']]+list(HERE.rglob('*.java'))+support+[pathlib.Path(__file__).resolve(),ROOT/'tests/download-resume-host/run.py']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)}
    callbacks=(PRODUCTION/'SavedFileActions.java').read_text()
    selected={name:extract.member(callbacks,name) for name in METHODS}
    metadata=(PRODUCTION/'DownloadMetadataValues.java').read_text()
    with tempfile.TemporaryDirectory(prefix='saved-copy-host-') as temporary:
        temp=pathlib.Path(temporary);package=temp/'local/pocketchat';package.mkdir(parents=True)
        for name in NAMES:(package/name).write_bytes((PRODUCTION/name).read_bytes())
        host=(HERE/'CopyHost.java').read_text().replace('/* SAVEDFILEACTIONS */','\n'.join(selected.values())).replace('/* METADATA */','\n'.join(extract.member(metadata,name) for name in ['static String name(','static String mime(']))
        (package/'CopyHost.java').write_text(host)
        for stub in [*support,*list((HERE/'stubs').rglob('*.java'))]:
            relative=pathlib.Path('android')/str(stub).split('/android/',1)[1]
            target=temp/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(stub.read_bytes())
        binary=lambda name:str(args.java_home/'bin'/name) if args.java_home else name
        compile_run=subprocess.run([binary('javac'),'-encoding','UTF-8','-cp',str(args.json_jar.resolve()),'-d',str(temp),*map(str,temp.rglob('*.java'))],capture_output=True,text=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.with_suffix('.compile.txt').write_text(compile_run.stdout+compile_run.stderr)
        if compile_run.returncode:raise RuntimeError(compile_run.stderr)
        run=subprocess.run([binary('java'),'-cp',str(temp)+os.pathsep+str(args.json_jar.resolve()),'local.pocketchat.CopyHost'],capture_output=True,text=True,timeout=45)
        report=read_host_report(run,args.output)
        unchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
        report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,selectedMethods={name:hashlib.sha256(code.encode()).hexdigest() for name,code in selected.items()},executionInputsUnchanged=unchanged,jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),actualAndroidExecution=False,actualExternalProviderExecution=False,scope='Exact production SavedFileActions export/result/delete/close, metadata accessors, full SavedFileBytes/SavedFileDeletion/SealedFileIo. Real JVM workers, file leases and files; controlled provider streams and UI. No Android device, external provider durability, saved-index database or global exactly-once claim.')
        if not unchanged:report['status']='invalid-source-changed'
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({key:report[key] for key in ['status','passed','total','executionInputsUnchanged']}))
        if run.returncode or report['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
