#!/usr/bin/env python3
"""Execute current Gecko UI attachment/retirement and real background client delegation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
sys.path.insert(0, str(ROOT / 'tests/gecko-navigation-host'))
from run import member_at as declaration_at
from android_boundary import STUBS

MUTATIONS = (
    ('retained-client', 'binding', 'if(web.client==client)web.setWebViewClient(backgroundClient);', '', 'retention', 'Retained page client releases destroyed Activity'),
    ('retained-chooser', 'binding', 'if(web.chrome==chrome)web.setWebChromeClient(null);', '', 'retention', 'Retained chooser client releases destroyed Activity'),
    ('retained-download', 'binding', 'if(web.download==download)web.setDownloadListener(null);', '', 'retention', 'Retained download callback releases destroyed Activity'),
    ('retained-response', 'binding', 'if(web.responseDownload==responseDownload)web.responseDownload=null;', '', 'retention', 'Late native response uses body-closing default without destroyed Activity callbacks'),
    ('background-client', 'binding', 'web.setWebViewClient(backgroundClient)', 'web.setWebViewClient(null)', 'retention', 'Session page client survives UI retirement'),
    ('callback-identity', 'binding', 'if(web.client==client)', 'if(true)', 'independent', 'Cleanup only removes callback instances installed by its own UI binding'),
    ('parent-identity', 'binding', 'if(web.getParent()==parent)parent.removeView(web);', 'if(web.getParent()!=null)((ViewGroup)web.getParent()).removeView(web);', 'parent', 'Retirement cannot remove a parent it did not install'),
    ('release-host-identity', 'web', 'if(activity==null||displayContext.getBaseContext()!=activity)return;', 'if(activity==null)return;', 'detach', 'Detach callback cannot be followed by clearing newer context'),
    ('release-before-dismissal', 'web', 'displayContext.setBaseContext(owner.context);\n    blockedPopups.invalidate();', 'blockedPopups.invalidate();\n    displayContext.setBaseContext(owner.context);', 'popup', 'Popup invalidation callback retains newly bound host'),
    ('auxiliary-host-identity', 'web', 'if(displayContext.getBaseContext()==owner.context)closeExitIpPage();', 'closeExitIpPage();', 'popup', 'Old host release cannot close auxiliary page opened during popup invalidation'),
    ('destroy-auxiliary-owner', 'main', 'if(browserUi!=null)browserUi.close();', 'if(browserUi!=null)browserUi.close();ExitIpPageUi.close(this);', 'replacement', 'Old Activity destruction preserves newer host auxiliary page'),
    ('pause-host-identity', 'main', 'if(session==null||session.deleted||browserUi==null||!browserUi.current())return;', 'if(session==null||session.deleted||browserUi==null)return;', 'pause', 'Old Activity pause cannot close newer host auxiliary page'),
    ('pause-auxiliary-reentry', 'main', 'ExitIpPageUi.close(this);\n    if(!browserUi.current())return;', 'ExitIpPageUi.close(this);', 'pause-reentry', 'Pause cannot stop newer traffic observation after auxiliary-close reentry'),
    ('pause-traffic-reentry', 'main', 'NativeNetwork.get(this).traffic.watch(false);\n    if(!browserUi.current())return;', 'NativeNetwork.get(this).traffic.watch(false);', 'pause-traffic', 'Pause cannot cancel audit after traffic callback transfers UI ownership'),
    ('pause-audit-reentry', 'main', 'session.audit.cancel();\n    if(!browserUi.current())return;', 'session.audit.cancel();', 'pause-audit', 'Pause cannot clear keyboard or foreground after audit callback binds a newer host'),
    ('pause-reading-reentry', 'main', 'session.reading.keyboard(false);\n    if(!browserUi.current())return;', 'session.reading.keyboard(false);', 'pause-keyboard', 'Pause cannot background a newer host created by reading callback'),
    ('pause-observer-ownership', 'main', 'if(session!=null)session.remove(sessionObserver);\n    if(session==null', 'if(browserUi!=null&&browserUi.current()&&session!=null)session.remove(sessionObserver);\n    if(session==null', 'pause', 'Old pause removes only its exact observer even after host replacement'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def member_at(source, signature):
    return declaration_at(source, source.index(signature))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', required=True, type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sources = {name: (PROD / name).read_text() for name in ['MainActivity.java', 'GeckoWebView.java', 'ChatSession.java', 'Attachments.java', 'FileDownloads.java']}
    members = {
        'ACTUAL_MAIN_METHODS': '\n'.join(member_at(sources['MainActivity.java'], signature) for signature in ['void createChatUi(', 'WebViewClient remoteClient(', 'static boolean chatUrl(', '@Override protected void onResume(', '@Override protected void onPause(', '@Override protected void onDestroy(']),
        'ACTUAL_WEB_MEMBERS': '\n'.join(member_at(sources['GeckoWebView.java'], signature) for signature in ['void setHost(', 'public void setWebViewClient(', 'public void setWebChromeClient(', 'public void setDownloadListener(']),
        'ACTUAL_EXTERNAL_RESPONSE': member_at(sources['GeckoWebView.java'], '@Override public void onExternalResponse('),
        'ACTUAL_SESSION_CLIENT': member_at(sources['ChatSession.java'], 'WebViewClient client('),
        # Keep the actual request fields/Pending class and every helper used by
        # chooser admission/retirement. Result/legacy-preview paths have their
        # own complete-class host; no synthetic cancellation helper is used.
        'ACTUAL_ATTACHMENT_DECLARATION': sources['Attachments.java'][sources['Attachments.java'].index('final class Attachments {'):sources['Attachments.java'].index('  static Intent chooserIntent(')] + '\n'.join(member_at(sources['Attachments.java'], signature) for signature in ['static Intent chooserIntent(', 'private boolean live(', 'private boolean samePage(', 'private boolean current(', 'private ValueCallback<Uri[]> detach(', 'private static void deliver(', 'private void cancel(', 'private void fail(', 'private void reject(', 'void cancelChooser(', 'void destroy(', 'boolean blocked(']) + '\n}',
        'ACTUAL_DOWNLOAD_MEMBERS': '\n'.join(member_at(sources['FileDownloads.java'], signature) for signature in ['FileDownloads(MainActivity', 'void destroy(']),
        'BINDING_DECLARATION': '',
    }
    binding_path = PROD / 'GeckoUiBinding.java'
    binding = binding_path.read_text() if binding_path.is_file() else None
    if binding is not None:
        members['BINDING_DECLARATION'] = 'GeckoUiBinding browserUi;'
        members['ACTUAL_WEB_MEMBERS'] += '\n' + member_at(sources['GeckoWebView.java'], 'void releaseHost(')
    template = (HERE / 'LifecycleHost.java.in').read_text()

    def generate(values):
        result = template
        for label, value in values.items():
            result = result.replace('/*' + label + '*/', value)
        return result
    inputs = [PROD / name for name in sources] + [Path(__file__), HERE / 'android_boundary.py', HERE / 'LifecycleHost.java.in', ROOT / 'tests/gecko-navigation-host/run.py']
    if binding is not None:
        inputs.append(binding_path)
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    java = args.java_home / 'bin/java'
    javac = args.java_home / 'bin/javac'
    dependency = digest(args.json_jar)
    java_hashes = {str(path): digest(path) for path in [java, javac]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    report = dict(status='failed', compiled=False, sourceSha256=hashes, dependencySha256=dependency, javaToolSha256=java_hashes,
                  scope='Whole current createChatUi/remoteClient/onResume/onPause/onDestroy and session client, exact FileDownloads installation/destroy, Attachments chooser/destroy, Gecko callback setters/host release and native response dispatch; whole GeckoUiBinding when present. Explicit Android view hierarchy, native auxiliary page, file-transfer I/O and session-state side-effect boundaries. Deterministic strong-reference traversal, not a device heap or renderer test.')
    controls = []
    with tempfile.TemporaryDirectory(prefix='gecko-ui-host-') as temporary:
        work = Path(temporary)
        platform_paths = []
        for relative, value in STUBS.items():
            path = work / relative;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(value);platform_paths.append(path)

        def build(values, binding_source, label):
            folder = artifacts / label;folder.mkdir(exist_ok=True)
            generated = folder / 'LifecycleHost.java';generated.write_text(generate(values));java_paths = platform_paths + [generated]
            if binding_source is not None:
                generated_binding = folder / 'GeckoUiBinding.java';generated_binding.write_text(binding_source);java_paths.append(generated_binding)
            classes = work / label
            command = [str(javac), '-encoding', 'UTF-8', '--release', '8', '-cp', str(args.json_jar), '-d', str(classes), *map(str, java_paths)]
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (folder / 'compile.command.json').write_text(json.dumps(command) + '\n')
            (folder / 'compile.stdout.log').write_text(compiled.stdout)
            (folder / 'compile.stderr.log').write_text(compiled.stderr)
            return classes, compiled

        def execute(classes, label, focus='all'):
            folder = artifacts / label;folder.mkdir(exist_ok=True)
            command = [str(java), '-cp', str(classes) + os.pathsep + str(args.json_jar), 'local.pocketchat.LifecycleHost', focus]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            (folder / 'run.command.json').write_text(json.dumps(command) + '\n')
            (folder / 'run.stdout.log').write_text(result.stdout)
            (folder / 'run.stderr.log').write_text(result.stderr)
            return result

        classes, compiled = build(members, binding, 'current')
        report.update(compiled=compiled.returncode == 0, compileReturncode=compiled.returncode)
        if compiled.returncode == 0:
            result = execute(classes, 'current')
            report.update(json.loads(result.stdout), returncode=result.returncode)
            if result.returncode == 0 and binding is not None:
                for label, target, before, after, focus, assertion in MUTATIONS:
                    pristine = execute(classes, 'pristine-' + label, focus)
                    if pristine.returncode:
                        raise AssertionError('Current focused behavior failed: ' + label + '\n' + pristine.stdout)
                    changed = dict(members);changed_binding = binding
                    if target == 'binding':
                        if changed_binding.count(before) != 1:raise ValueError('Changed mutation anchor: ' + label)
                        changed_binding = changed_binding.replace(before, after, 1)
                    else:
                        key = 'ACTUAL_MAIN_METHODS' if target == 'main' else 'ACTUAL_WEB_MEMBERS'
                        if changed[key].count(before) != 1:raise ValueError('Changed mutation anchor: ' + label)
                        changed[key] = changed[key].replace(before, after, 1)
                    mutant, compilation = build(changed, changed_binding, 'mutation-' + label)
                    if compilation.returncode:
                        raise AssertionError('Counterfeit did not compile: ' + label + '\n' + compilation.stderr)
                    failed = execute(mutant, 'mutation-' + label, focus)
                    if failed.returncode == 0 or assertion not in json.loads(failed.stdout).get('failures', []):
                        raise AssertionError('Compiled counterfeit escaped its behavioral assertion: ' + label + '\n' + failed.stdout + failed.stderr)
                    controls.append(dict(name=label, compiled=True, pristinePassed=True, runtimeRejected=True, expectedAssertion=assertion,
                                         generatedHostSha256=hashlib.sha256(generate(changed).encode()).hexdigest(),
                                         generatedBindingSha256=hashlib.sha256(changed_binding.encode()).hexdigest()))
        else:
            report['compileError'] = compiled.stderr
    report.update(executionInputsUnchanged=all(digest(path) == hashes[str(path.relative_to(ROOT))] for path in inputs),
                  dependencyUnchanged=digest(args.json_jar) == dependency,
                  javaToolsUnchanged=all(digest(Path(path)) == value for path, value in java_hashes.items()), compiledCounterfeits=controls)
    if not all(report[key] for key in ['executionInputsUnchanged', 'dependencyUnchanged', 'javaToolsUnchanged']):
        report['status'] = 'input-changed'
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict({key: report.get(key) for key in ['status', 'compiled', 'checks', 'passed', 'failures', 'compileError']}, compiledCounterfeits=len(controls)), ensure_ascii=False))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
