#!/usr/bin/env python3
"""Execute complete current Attachments and real Activity result routing."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


base = module('chooser_boundaries', ROOT / 'tests/browser-files-host/chooser.py')
boundary = module('native_attachment_boundary', HERE / 'android_boundary.py')

MUTATIONS = (
    ('reserve-after-cancellation', 'pending=request;cancel(previous);', 'cancel(previous);pending=request;',
     'Cancellation reentry preserves the newest chooser and rejects the outer request'),
    ('reused-request-id', 'return nextRequest>LAST_REQUEST?-1:nextRequest++;', 'return FIRST_REQUEST;',
     'Successor chooser never reuses the old Android request identifier'),
    ('retired-host', '&&a.remote.displayContext.getBaseContext()==a', '',
     'A replaced Activity cannot reopen its chooser before onDestroy'),
    ('same-url-new-document', 'request.epoch==a.session.navigationEpoch&&', '',
     'A same-URL document replacement rejects the old result'),
    ('stale-result-id', '||request.request!=requestCode', '',
     'Late previous picker result cannot reach a newer same-page callback'),
    ('clear-new-owner', 'if(pending==request)pending=null;', 'pending=null;',
     'Cancellation reentry delivers only to the nested current chooser'),
    ('repeated-terminal-callback', 'ValueCallback<Uri[]> callback=request.callback;request.callback=null;',
     'ValueCallback<Uri[]> callback=request.callback;',
     'Cancellation reentry preserves the newest chooser and rejects the outer request'),
    ('final-provider-document',
     '      if(!current(request)){cancel(request);return true;}\n      deliver(detach(request),selected.toArray(new Uri[0]));',
     '      deliver(detach(request),selected.toArray(new Uri[0]));',
     'Document change during final URI grant rejects the obsolete file'),
    ('detach-after-native-result', 'deliver(detach(request),selected.toArray(new Uri[0]));',
     'deliver(request.callback,selected.toArray(new Uri[0]));detach(request);',
     'Successful native callback is detached before it can open another chooser'),
    ('callback-exception-escapes',
     'try{callback.onReceiveValue(files);}catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser callback failed",failure);}',
     'callback.onReceiveValue(files);',
     'Throwing old cancellation callback cannot strand the admitted replacement'),
    ('close-after-callback',
     '    try{a.finishActivity(request.request);}catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser dismissal failed",failure);}\n    deliver(callback,null);',
     '    deliver(callback,null);\n    try{a.finishActivity(request.request);}catch(RuntimeException failure){android.util.Log.w("PocketChat","File chooser dismissal failed",failure);}',
     'Native prompt releases its Android picker before invoking cancellation'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = [PROD / name for name in ['Attachments.java', 'MainActivity.java', 'J.java']]
    inputs += [HERE / 'ChooserHost.java', HERE / 'android_boundary.py', Path(__file__),
               ROOT / 'tests/browser-files-host/chooser.py']
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    dependency = digest(args.json_jar)
    java = args.java_home / 'bin/java'
    javac = args.java_home / 'bin/javac'
    java_hashes = {str(path): digest(path) for path in [java, javac]}
    activity = (PROD / 'MainActivity.java').read_text()
    selected = {needle: base.member(activity, needle) for needle in [
        '@Override protected void onActivityResult(', 'static boolean chatUrl(']}
    original = (PROD / 'Attachments.java').read_text()
    host = (HERE / 'ChooserHost.java').read_text().replace('/* ACTUAL_ACTIVITY */', '\n'.join(selected.values()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    controls = []
    report = dict(status='failed', compiled=False)

    with tempfile.TemporaryDirectory(prefix='native-attachment-chooser-') as temporary:
        temp = Path(temporary)
        package = temp / 'local/pocketchat'
        package.mkdir(parents=True)
        (package / 'J.java').write_bytes((PROD / 'J.java').read_bytes())
        (package / 'ChooserHost.java').write_text(host)
        for name, text in boundary.stubs(base.STUBS).items():
            path = temp / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

        def execute(source, label):
            (package / 'Attachments.java').write_text(source)
            folder = artifacts / label
            folder.mkdir(exist_ok=True)
            (folder / 'Attachments.java').write_text(source)
            (folder / 'ChooserHost.java').write_text(host)
            classes = temp / ('classes-' + label)
            compile_run = subprocess.run([
                str(javac), '-encoding', 'UTF-8', '--release', '8', '-cp', str(args.json_jar),
                '-d', str(classes), *map(str, sorted(temp.rglob('*.java')))],
                capture_output=True, text=True, timeout=60)
            (folder / 'compile.txt').write_text(compile_run.stdout + compile_run.stderr)
            outcome = dict(compiled=compile_run.returncode == 0, compileReturncode=compile_run.returncode)
            if compile_run.returncode:
                outcome['compileError'] = compile_run.stderr
                return outcome
            run = subprocess.run([str(java), '-cp', str(classes) + os.pathsep + str(args.json_jar),
                                  'local.pocketchat.ChooserHost'], capture_output=True, text=True, timeout=30)
            (folder / 'stdout.txt').write_text(run.stdout)
            (folder / 'stderr.txt').write_text(run.stderr)
            outcome.update(json.loads(run.stdout), returncode=run.returncode)
            return outcome

        report.update(execute(original, 'current'))
        if report['compiled'] and report.get('returncode') == 0:
            for label, before, after, assertion in MUTATIONS:
                if original.count(before) != 1:
                    raise AssertionError('Mutation must identify one current production boundary: ' + label)
                changed = original.replace(before, after, 1)
                counterfeit = execute(changed, label)
                if not counterfeit['compiled']:
                    raise AssertionError('Counterfeit did not compile: ' + label + '\n' + counterfeit['compileError'])
                failed = [check['name'] for check in counterfeit['checks'] if not check['pass']]
                if counterfeit['returncode'] == 0 or assertion not in failed:
                    raise AssertionError('Compiled counterfeit escaped its behavior check: ' + label)
                controls.append(dict(name=label, compiled=True, runtimeRejected=True,
                                     expectedAssertion=assertion,
                                     productionSourceSha256=hashlib.sha256(changed.encode()).hexdigest()))

    unchanged = all(digest(ROOT / name) == value for name, value in hashes.items())
    report.update(
        sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        sourceFiles=hashes,
        selectedActivityMethods={name: hashlib.sha256(source.encode()).hexdigest() for name, source in selected.items()},
        executionInputsUnchanged=unchanged, jsonJarSha256=dependency,
        dependencyUnchanged=digest(args.json_jar) == dependency,
        javaToolsUnchanged=all(digest(Path(path)) == value for path, value in java_hashes.items()),
        javaToolSha256=java_hashes, compiledCounterfeits=controls, actualAndroidExecution=False,
        scope='Complete current Attachments plus exact MainActivity result routing and ChatGPT origin policy. '
              'Synchronous callback/provider/picker/UI boundaries, explicit document epochs and two Activity owners. '
              'No actual DocumentsUI, Gecko renderer/upload, URI grant or process-death restoration claim.')
    if not all(report[key] for key in ['executionInputsUnchanged', 'dependencyUnchanged', 'javaToolsUnchanged']):
        report['status'] = 'invalid-source-changed'
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict({key: report.get(key) for key in [
        'status', 'compiled', 'passed', 'total', 'compileError', 'executionInputsUnchanged']},
        compiledCounterfeits=len(controls)), ensure_ascii=False))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
