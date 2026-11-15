#!/usr/bin/env python3
"""Complete production texture adapter with fixed official/actual SDK behavior."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'app/src/main/java/local/pocketchat/GeckoTextureSurface.java'
GECKO_VIEW = ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java'
CARET = ROOT / 'tests/gecko/GeckoCaretCompatibilityIntegrationActivity.java'
MEMBER_READER = ROOT / 'tests/gecko-navigation-host/run.py'
FIXTURE = HERE / 'fixtures/SurfaceViewWrapper.java'
RECOVERY_FIXTURE = HERE / 'fixtures/GeckoView-requestNewSurface.java.txt'
PROVENANCE = HERE / 'fixtures/provenance.json'
OFFICIAL = ROOT / 'third-party/sdk/geckoview-157.0.1-official.json'
SELECTED = ROOT / 'third-party/sdk/geckoview-157.0.1-editable-selection.json'
FIXTURE_SHA256 = '04793bc514498254421d59886c84788700e08874d28eba5e39bbd7b7e8e620d4'
RECOVERY_SHA256 = '506de1424826ab85a0c7939917d42aea3401c139c390a5ac7f88bf2fcec5d7bb'


def require(value, message):
    if not value:
        raise ValueError('Gecko texture surface: ' + message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ordinary(path, name):
    require(path.is_file() and not path.is_symlink(), 'ordinary ' + name + ' is required: ' + str(path))


def load_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(path.read_text(), object_pairs_hook=unique)


def sdk_input(args, base, dependencies, provenance):
    """Resolve only actual, receipt-bound classes; never substitute the fixture."""
    receipt_path = args.sdk_receipt or ROOT / 'work/native-caret-sdk/sdk-build-receipt.json'
    ordinary(receipt_path, 'SDK build receipt')
    dependencies[str(receipt_path.resolve())] = sha(receipt_path)
    receipt = load_json(receipt_path)
    selected = load_json(SELECTED)
    for key in ('sdkBuildKind', 'sdkRuntimeCoordinate', 'sdkInputAarSha256',
                'sdkAarSha256', 'sdkClassesJarSha256', 'upstreamRevision'):
        require(receipt.get(key) == selected[key], 'SDK receipt differs from selected runtime: ' + key)
    require(receipt['sdkBuildKind'] == 'source-derived-java', 'source-derived runtime receipt required')
    if args.sdk_classes is not None:
        jar = args.sdk_classes
        ordinary(jar, 'SDK classes JAR')
        dependencies[str(jar.resolve())] = sha(jar)
    else:
        aar = ROOT / 'work/native-caret-sdk/geckoview-caret.aar'
        ordinary(aar, 'built SDK AAR')
        dependencies[str(aar.resolve())] = sha(aar)
        require(dependencies[str(aar.resolve())] == receipt['sdkAarSha256'], 'SDK AAR differs from receipt')
        with ZipFile(aar) as archive:
            require(archive.namelist().count('classes.jar') == 1
                    and archive.getinfo('classes.jar').file_size <= 24 * 1024 * 1024,
                    'one bounded SDK classes member is required')
            jar = base / 'actual-sdk-classes.jar'
            jar.write_bytes(archive.read('classes.jar'))
    expected = receipt['sdkClassesJarSha256']
    require(sha(jar) == expected, 'actual SDK classes differ from receipt/selected runtime')
    with ZipFile(jar) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate SDK archive entry')
        for name, expected_class in provenance['actualClassSha256'].items():
            require(names.count(name) == 1 and hashlib.sha256(archive.read(name)).hexdigest() == expected_class,
                    'actual runtime wrapper class differs from pinned fixture provenance: ' + name)
    return jar, dict(classesJarSha256=expected, runtimeCoordinate=receipt['sdkRuntimeCoordinate'],
                     receiptSource=receipt.get('sourceCommit', receipt.get('sdkBuildSource')),
                     classSha256=provenance['actualClassSha256'])


MUTATIONS = [
    ('forward-every-frame', 'if(!replacementRequested&&texture==value&&width==w&&height==h)return;', ''),
    ('drop-size-delivery', 'remember(value,w,h);delegate.onSurfaceTextureSizeChanged(value,w,h);',
     'remember(value,w,h);'),
    ('drop-replacement-delivery', 'remember(value,w,h);delegate.onSurfaceTextureUpdated(value);',
     'remember(value,w,h);'),
    ('destroy-loses-release-result', 'remember(null,0,0);return delegate.onSurfaceTextureDestroyed(value);',
     'remember(null,0,0);delegate.onSurfaceTextureDestroyed(value);return false;'),
    ('close-overwrites-successor',
     'if(view.getSurfaceTextureListener()==this)view.setSurfaceTextureListener(delegate);',
     'view.setSurfaceTextureListener(delegate);'),
    ('accept-old-texture-frame',
     'if(!current(view)||!view.isAvailable()||view.getSurfaceTexture()!=value)return;',
     'if(!current(view)||!view.isAvailable())return;'),
    ('install-replaces-live-binding', 'if(previous!=null&&previous.current(target))return previous;', ''),
    ('destroy-loses-reentrant-ownership', 'remember(null,0,0);return delegate.onSurfaceTextureDestroyed(value);',
     'boolean release=delegate.onSurfaceTextureDestroyed(value);remember(null,0,0);return release;'),
    ('drop-explicit-recovery-request', 'if(binding.current(target))binding.replacementRequested=true;', ''),
    ('resize-consumes-replacement-request', 'remember(value,w,h);delegate.onSurfaceTextureSizeChanged(value,w,h);',
     'replacementRequested=false;remember(value,w,h);delegate.onSurfaceTextureSizeChanged(value,w,h);'),
    ('update-erases-newer-request', 'replacementRequested=false;remember(value,w,h);delegate.onSurfaceTextureUpdated(value);',
     'remember(value,w,h);delegate.onSurfaceTextureUpdated(value);replacementRequested=false;'),
    ('available-erases-newer-request', 'replacementRequested=false;remember(value,w,h);delegate.onSurfaceTextureAvailable(value,w,h);',
     'remember(value,w,h);delegate.onSurfaceTextureAvailable(value,w,h);replacementRequested=false;'),
    ('request-forgets-owned-texture', 'if(binding.current(target))binding.replacementRequested=true;',
     'if(binding.current(target)){binding.replacementRequested=true;binding.texture=null;}'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-sdk', action='store_true')
    parser.add_argument('--sdk-classes', type=Path)
    parser.add_argument('--sdk-receipt', type=Path)
    args = parser.parse_args()
    actual_sdk = args.require_sdk or args.sdk_classes is not None or args.sdk_receipt is not None
    java, javac = args.java_home / 'bin/java', args.java_home / 'bin/javac'
    for path, name in ((java, 'JDK java'), (javac, 'JDK javac'), (args.json_jar, 'JSON JAR')):
        ordinary(path, name)
    files = [SOURCE, GECKO_VIEW, CARET, MEMBER_READER,
             OFFICIAL, SELECTED, *sorted(path for path in HERE.rglob('*')
                                        if path.is_file() and '__pycache__' not in path.parts)]
    before = {str(path.relative_to(ROOT)): sha(path) for path in files}
    dependencies = {str(path.resolve()): sha(path) for path in (java, javac, args.json_jar)}
    provenance, official = load_json(PROVENANCE), load_json(OFFICIAL)
    require(sha(FIXTURE) == FIXTURE_SHA256 == provenance['sha256']
            and FIXTURE.stat().st_size == provenance['bytes']
            and len(FIXTURE.read_bytes().splitlines()) == provenance['lines'],
            'complete unmodified official wrapper fixture required')
    require(provenance['sourceArchiveSha256'] == official['sources']['sha256']
            and provenance['upstreamRevision'] == official['upstreamRevision'],
            'fixture must belong to the existing pinned official source archive')
    require(sha(RECOVERY_FIXTURE) == RECOVERY_SHA256 == provenance['recoveryMethod']['fragmentSha256'],
            'complete unchanged official public recovery method required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location('texture_android_boundaries', HERE / 'stubs.py')
    stubs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stubs)
    reader_spec = importlib.util.spec_from_file_location('texture_current_members', MEMBER_READER)
    reader = importlib.util.module_from_spec(reader_spec)
    reader_spec.loader.exec_module(reader)
    hooks = {}
    for name, path in (('production', GECKO_VIEW), ('caret', CARET)):
        text = path.read_text()
        signature = 'public void requestNewSurface('
        require(text.count(signature) == 1, 'unique current public recovery hook required: ' + name)
        hooks[name] = reader.member_at(text, text.index(signature))
    raw = SOURCE.read_text()
    with tempfile.TemporaryDirectory(prefix='gecko-texture-surface-') as temporary:
        base = Path(temporary)
        jar, sdk = sdk_input(args, base, dependencies, provenance) if actual_sdk else (None, None)
        sources = []
        for name, body in stubs.SOURCES.items():
            path = base / 'android-boundaries' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body + '\n')
            sources.append(path)
        if not actual_sdk:
            sources.append(FIXTURE)
        sources.extend([HERE / 'AdapterHost.java', HERE / 'CauseHost.java'])
        empty = base / 'empty-sourcepath'
        empty.mkdir()
        dependency_classpath = os.pathsep.join(str(path) for path in (jar, args.json_jar) if path is not None)

        def compile_and_run(label, production, main_class='local.pocketchat.AdapterHost', selected_hooks=None):
            folder = base / label
            folder.mkdir()
            classes = folder / 'classes'
            current = folder / 'GeckoTextureSurface.java'
            current.write_text(production)
            chosen = selected_hooks or hooks
            recovery = folder / 'RecoveryHost.java'
            recovery.write_text((HERE / 'RecoveryHost.java.in').read_text()
                                .replace('@@SDK_RECOVERY@@', RECOVERY_FIXTURE.read_text())
                                .replace('@@PRODUCTION_HOOK@@', chosen['production'])
                                .replace('@@CARET_HOOK@@', chosen['caret']))
            command = [str(javac), '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-proc:none',
                       '-sourcepath', str(empty), '-cp', dependency_classpath, '-d', str(classes),
                       str(current), str(recovery), *(str(path) for path in sources)]
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=45)
            (artifacts / (label + '-compile.log')).write_text(compiled.stdout + compiled.stderr)
            require(compiled.returncode == 0, 'complete production/host compile failed: ' + label + '\n' + compiled.stderr[-4000:])
            if actual_sdk:
                require(not list((classes / 'org/mozilla/gecko').glob('SurfaceViewWrapper*.class')),
                        'actual SDK mode must not emit replacement wrapper classes')
            run_classpath = str(classes) + os.pathsep + dependency_classpath
            def execute(name):
                executed = subprocess.run([str(java), '-XX:-UsePerfData', '-cp', run_classpath, name],
                                          capture_output=True, text=True, timeout=20)
                (artifacts / (label + '-' + name.rsplit('.', 1)[-1] + '-run.log')).write_text(executed.stdout + executed.stderr)
                require(bool(executed.stdout.strip()), 'host produced no behavior result: ' + label + '\n' + executed.stderr[-4000:])
                return executed.returncode, json.loads(executed.stdout)
            code, value = execute(main_class)
            if main_class != 'local.pocketchat.AdapterHost':
                return code, value
            recovery_code, recovery_value = execute('local.pocketchat.RecoveryHost')
            checks = value['checks'] + recovery_value['checks']
            passed = sum(item['pass'] for item in checks)
            return max(code, recovery_code), dict(status='passed' if passed == len(checks) else 'failed',
                passed=passed, total=len(checks), checks=checks,
                sections=dict(lifecycle=dict(passed=value['passed'], total=value['total']),
                              sdkRecovery=dict(passed=recovery_value['passed'], total=recovery_value['total'])))

        red_result, red = compile_and_run('upstream-cause', raw, 'local.pocketchat.CauseHost')
        require(red_result == 1 and red['status'] == 'failed'
                and red['contentFramesPresented'] == 12 and red['extraSurfaceNotifications'] == 12
                and red['extraSurfaceAllocations'] == 12 and red['textureIdentityUnchanged']
                and red['dimensionsUnchanged'], 'the fixed SDK causal regression did not reproduce')
        result, report = compile_and_run('current', raw)
        require(result == 0 and report['status'] == 'passed',
                'current adapter behavior failed: ' + json.dumps(report))
        controls = []
        for name, original, replacement in MUTATIONS:
            require(raw.count(original) == 1, 'unique semantic mutation required: ' + name)
            failed, value = compile_and_run(name, raw.replace(original, replacement, 1))
            require(failed == 1 and value['status'] == 'failed', 'compiled mutation escaped: ' + name)
            controls.append(dict(name=name, compileSucceeded=True, runtimeRejected=True,
                                 failedChecks=[item['name'] for item in value['checks'] if not item['pass']]))
        for name, hook, old in [('production-recovery-skips-sdk-post', 'production', 'super.requestNewSurface();'),
                                ('caret-recovery-skips-request-signal', 'caret', 'GeckoTextureSurface.requestNewSurface(this);')]:
            require(hooks[hook].count(old) == 1, 'unique actual recovery-hook mutation required: ' + name)
            changed_hooks = dict(hooks)
            changed_hooks[hook] = changed_hooks[hook].replace(old, '', 1)
            failed, value = compile_and_run(name, raw, selected_hooks=changed_hooks)
            require(failed == 1 and value['status'] == 'failed', 'compiled recovery-hook mutation escaped: ' + name)
            controls.append(dict(name=name, compileSucceeded=True, runtimeRejected=True,
                                 failedChecks=[item['name'] for item in value['checks'] if not item['pass']]))
        if actual_sdk:
            require(sha(jar) == sdk['classesJarSha256'], 'actual SDK classes changed during execution')
    stable = all((ROOT / name).is_file() and sha(ROOT / name) == value for name, value in before.items())
    stable = stable and all(Path(name).is_file() and sha(Path(name)) == value for name, value in dependencies.items())
    report.update(schema=1, sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  sourceFiles=before, dependencies=dependencies, executionInputsUnchanged=stable,
                  compileSucceeded=True, completeProductionClass=True, negativeControls=controls,
                  upstreamRegression=dict(compileSucceeded=True, expectedFailureObserved=True, **red),
                  sdk=sdk, fixedOfficialSourceFixture=not actual_sdk, actualSdkBytecodeExecuted=actual_sdk,
                  actualSdkGeckoViewExecution=False, actualAndroidExecution=False,
                  actualGeckoExecution=False, actualNativeCompositorExecution=False,
                  currentRecoveryHooks=hooks, completeSdkRecoveryMethod=True,
                  scope='Complete current production adapter and unchanged pinned SDK wrapper behavior. '
                        'The actual application and caret recovery overrides execute with the complete fixed SDK public requestNewSurface method. '
                        'Android/graphics, surrounding GeckoView and MagnifiableSurfaceView are declared boundaries. '
                        'Normal destroy follows callback-before-retirement order; separately labelled direct adapter reentry is synthetic. '
                        'Strict mode executes receipt-bound SDK bytecode without compiling its source fixture. '
                        'No Gecko engine, Android/GPU rendering, native compositor, or device idle acceptance is claimed.')
    if not stable:
        report['status'] = 'source-changed'
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'passed', 'total', 'executionInputsUnchanged', 'actualSdkBytecodeExecuted')},
                     ensure_ascii=False))
    require(stable, 'source/dependency inputs changed during execution')


if __name__ == '__main__':
    main()
