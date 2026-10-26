#!/usr/bin/env python3
"""Fault injection through exact production download UI methods and publication/recovery classes."""
import argparse, hashlib, importlib.util, json, os, pathlib, re, subprocess, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
ADAPTER = ROOT / 'tests/download-resume-host'
RECOVERY = ROOT / 'tests/download-recovery-host'
spec = importlib.util.spec_from_file_location('download_resume_adapter', ADAPTER / 'run.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--json-jar', type=pathlib.Path, required=True)
    p.add_argument('--java-home', type=pathlib.Path)
    p.add_argument('--output', type=pathlib.Path, required=True)
    p.add_argument('--before-ref')
    a = p.parse_args()
    before = subprocess.check_output(['git', 'rev-parse', a.before_ref + '^{commit}'], cwd=ROOT, text=True).strip() if a.before_ref else None
    def source(name):
        path = 'app/src/main/java/local/pocketchat/' + name
        return subprocess.check_output(['git', 'show', before + ':' + path], cwd=ROOT, text=True) if before else (ROOT / path).read_text()
    names = ['J.java', 'DownloadTasks.java', 'DownloadTaskRevisions.java', 'DownloadResumePolicy.java', 'DownloadRange.java', 'SavedFileDeletion.java', 'SavedFilePublication.java', 'DefaultDownloads.java', 'SealedFileIo.java']
    text = source('FileDownloads.java')
    old_needles = ['void taskActions(', 'boolean requestAvailable(', 'String continuationAction(', 'void requestRedownload(', 'void discardForRedownload(', 'boolean loadTask(', 'void newTask(', 'void updateTask(', 'void mark(', 'boolean valid(', 'void acceptResponse(', 'void retry(', 'void fail(', 'void pause(', 'void destroy(', 'void download(', 'void readChunk(']
    extra = ['void transferProgress(', 'void cancel(']
    optional = ['boolean saveTask(', 'void persistenceFailed(', 'boolean claimTask(']
    needles = old_needles + extra + [n for n in optional if n in text]
    parts = [adapter.member(text, n) for n in needles]
    inputs = [ADAPTER / 'DownloadResumeHost.java', ADAPTER / 'run.py', HERE / 'FailureCases.java.in', pathlib.Path(__file__).resolve(), RECOVERY / 'local/pocketchat/Support.java', ROOT / 'tests/sealed-file-host/android/util/AtomicFile.java'] + list((RECOVERY / 'android').rglob('*.java')) + list((ADAPTER / 'stubs').rglob('*.java'))
    hashes = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(inputs)}
    selected = {'app/src/main/java/local/pocketchat/' + n: hashlib.sha256(source(n).encode()).hexdigest() for n in names + ['FileDownloads.java']}
    with tempfile.TemporaryDirectory(prefix='download-persistence-host-') as temporary:
        temp = pathlib.Path(temporary)
        package = temp / 'local/pocketchat'
        package.mkdir(parents=True)
        for n in names:
            (package / n).write_text(source(n))
        fixture = (ADAPTER / 'DownloadResumeHost.java').read_text()
        fixture = fixture.replace(adapter.member(fixture, 'public static void main('), (HERE / 'FailureCases.java.in').read_text())
        fixture = fixture.replace('void transferProgress(){}', '')
        fixture = fixture.replace('boolean awaitingPicker,', 'boolean persistenceBlocked,awaitingPicker,')
        fixture = fixture.replace('static final long MAX=', 'static final long PROGRESS_SAVE_INTERVAL=' + re.search(r'PROGRESS_SAVE_INTERVAL=(\d+)', text).group(1) + ';static final long MAX=')
        fixture = fixture.replace('/* FILEDOWNLOADS */', '\n'.join(parts))
        (package / 'DownloadResumeHost.java').write_text(fixture)
        support = (RECOVERY / 'local/pocketchat/Support.java').read_text().replace('final class FileDownloads {static String safeName(String name){return name;}}', '')
        (package / 'Support.java').write_text(support)
        stubs = []
        for f in (RECOVERY / 'android').rglob('*.java'):
            target = temp / f.relative_to(RECOVERY)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = f.read_text()
            if f.name == 'Context.java':
                raw = raw.replace('public final class Context', 'public class Context')
            if f.name == 'Handler.java':
                raw = raw.replace('public boolean post(Runnable r)', 'public boolean postDelayed(Runnable r,long delay){return post(r);}public boolean post(Runnable r)')
            if f.name == 'SharedPreferences.java':
                raw = raw.replace('public volatile boolean failNextCommit', 'public volatile boolean failEveryCommit,throwEveryCommit;public volatile boolean failNextCommit')
                raw = raw.replace('commitAttempts++;', 'commitAttempts++;if(throwEveryCommit)throw new IllegalStateException("Injected storage exception");if(failEveryCommit){memory.putAll(changes);return false;}')
            target.write_text(raw)
            stubs.append(target)
        sources = [*package.glob('*.java'), *stubs, ROOT / 'tests/sealed-file-host/android/util/AtomicFile.java', *list((ADAPTER / 'stubs').rglob('*.java'))]
        binary = lambda name: str(a.java_home / 'bin' / name) if a.java_home else name
        subprocess.run([binary('javac'), '-encoding', 'UTF-8', '-cp', str(a.json_jar.resolve()), '-d', str(temp), *map(str, sources)], check=True)
        run = subprocess.run([binary('java'), '-cp', str(temp) + os.pathsep + str(a.json_jar.resolve()), 'local.pocketchat.DownloadResumeHost'], capture_output=True, text=True, timeout=60)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.with_suffix('.stdout.txt').write_text(run.stdout)
        a.output.with_suffix('.stderr.txt').write_text(run.stderr)
        report = json.loads(run.stdout)
        assert len(report['checks']) == len({row['name'] for row in report['checks']}) == report['total']
        unchanged = all(hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == digest for n, digest in hashes.items())
        if not before:
            unchanged = unchanged and all(hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == digest for n, digest in selected.items())
        report.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), beforeRef=before, selectedProductionSourceFiles=selected, adapterSourceFiles=hashes, selectedProductionMethods=needles, jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest(), executionInputsUnchanged=unchanged, actualAndroidExecution=False, actualExternalProviderExecution=False, scope='Exact production FileDownloads callback methods and full production task/publication/recovery classes; JVM UI queue, controlled storage faults, host files and provider double. No phone or real provider claim.')
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: report[k] for k in ['status', 'passed', 'total', 'executionInputsUnchanged']}))
        if run.returncode or report['status'] != 'passed' or not unchanged:
            raise SystemExit(1)

if __name__ == '__main__':
    main()
