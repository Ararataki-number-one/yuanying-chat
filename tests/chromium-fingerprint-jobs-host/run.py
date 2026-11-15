#!/usr/bin/env python3
"""Run whole Chromium fingerprint jobs, store and spec against explicit I/O queues."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    def tool(name):
        selected = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not selected:
            parser.error('Provide --java-home containing ' + name)
        return selected

    sources = [PRODUCTION / name for name in [
        'ChromiumFingerprintJobs.java', 'ChromiumFingerprintStore.java',
        'ChromiumFingerprintSpec.java', 'EnvironmentSpec.java', 'J.java']]
    adapter = ROOT / 'tests/chromium-fingerprint-store-host/ChromiumFingerprintStoreHost.java'
    host = HERE / 'ChromiumFingerprintJobsHost.java'
    inputs = sources + [adapter, host, Path(__file__).resolve()]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    dependency_hash = digest(args.json_jar)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    controls = []

    with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-jobs-host-') as temporary:
        work = Path(temporary)
        context = work / 'android/content/Context.java'
        context.parent.mkdir(parents=True)
        context.write_text('package android.content;import java.io.File;public abstract class Context {public abstract Context getApplicationContext();public abstract File getNoBackupFilesDir();public final android.content.res.AssetManager assets=new android.content.res.AssetManager();public android.content.res.AssetManager getAssets(){return assets;}}\n')
        assets = work / 'android/content/res/AssetManager.java'
        assets.parent.mkdir(parents=True)
        assets.write_text('package android.content.res;import java.io.*;import java.nio.charset.StandardCharsets;public class AssetManager {public String script="host-script";public boolean failRead;public int opens,closes;public InputStream open(String name)throws IOException{opens++;if(failRead)throw new IOException("Injected asset read failure");if(!name.equals("chromium-fingerprint.js"))throw new IOException("Unexpected asset");return new ByteArrayInputStream(script.getBytes(StandardCharsets.UTF_8)){public void close()throws IOException{closes++;super.close();}};}}\n')
        classes = work / 'classes'

        def compile_sources(selected):
            result = subprocess.run([tool('javac'), '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                                     '-cp', str(args.json_jar.resolve()), '-d', str(classes),
                                     *map(str, selected), str(adapter), str(host), str(context), str(assets)],
                                    capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError('Compilation failed:\n' + result.stderr)

        def execute(state):
            return subprocess.run([tool('java'), '-cp', str(classes) + ':' + str(args.json_jar.resolve()),
                                   'local.pocketchat.ChromiumFingerprintJobsHost', str(state)],
                                  capture_output=True, text=True, timeout=60)

        compile_sources(sources)
        executed = execute(work / 'state')
        if executed.returncode:
            raise RuntimeError('Jobs host failed:\n' + executed.stderr)
        result = json.loads(executed.stdout)

        original = sources[0].read_text()
        mutants = [
            ('Closed Activity still receives queued result', 'if(!closed)result.run();', 'result.run();',
             'Close suppresses a result already queued for UI'),
            ('Policy write captures mutable caller object',
             ':ChromiumFingerprintStore.save(context,expected.identity,expected.revision,new JSONObject(snapshot));',
             ':ChromiumFingerprintStore.save(context,expected.identity,expected.revision,desired);',
             'Queued save uses submitted specification snapshot'),
            ('Validation ignores complete stored policy', 'if(!samePolicy(actual,expected))', 'if(false)',
             'Validation rejects changed seed with identical revision'),
            ('Rejected worker task disappears', 'failure.failed(rejected);', '/* dropped rejection */',
             'Rejected load reports one failure immediately'),
        ]
        for index, (label, before, after, assertion) in enumerate(mutants):
            if original.count(before) != 1:
                raise AssertionError('Review mutation boundary: ' + label)
            mutant = work / 'ChromiumFingerprintJobs.java'
            mutant.write_text(original.replace(before, after, 1))
            compile_sources([mutant] + sources[1:])
            failed = execute(work / ('negative-' + str(index)))
            if failed.returncode == 0 or 'AssertionError: ' + assertion not in failed.stderr:
                raise AssertionError('Compiled negative control missed its intended assertion: ' + label + '\n' + failed.stderr)
            controls.append(dict(label=label, compiled=True, executed=True, expectedAssertion=assertion))

    unchanged = all(path.is_file() and digest(path) == hashes[str(path.relative_to(ROOT))] for path in inputs)
    dependency_unchanged = digest(args.json_jar) == dependency_hash
    report = dict(status='passed' if unchanged and dependency_unchanged else 'input-changed',
                  sourceCommit=commit, sourceFiles=hashes, jsonJarSha256=dependency_hash,
                  executionInputsUnchanged=unchanged, dependencyUnchanged=dependency_unchanged,
                  passed=result['passed'], total=result['total'], checks=result['checks'],
                  negativeControls=controls, actualAndroidExecution=False, actualChromiumExecution=False,
                  actualAesExecution=False,
                  scope='Whole production ChromiumFingerprintJobs, ChromiumFingerprintStore, ChromiumFingerprintSpec, EnvironmentSpec and J. Real temporary files and file locks with existing plain-file vault/catalog adapters; explicit worker/UI queues and asset stream. Covers detached input snapshots, ordered state/receipt work, revision and full-policy checks, I/O errors, immediate executor rejection, drain-on-close and late delivery suppression. Four successfully compiled behavioral mutants must fail their specified assertion. No Android lifecycle, WebView/native traffic, cryptography, or device execution.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], passed=result['passed'], negativeControls=len(controls), output=str(args.output))))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
