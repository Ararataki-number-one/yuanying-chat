#!/usr/bin/env python3
"""Compile changed native Java against real Android APIs and explicit app boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'app/src/main/java/local/pocketchat'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', required=True, type=Path)
    parser.add_argument('--android-jar', required=True, type=Path)
    parser.add_argument('--json-jar', type=Path, help='Optional supplemental JSON library; real Android APIs take precedence.')
    parser.add_argument('--classpath-jar', type=Path, action='append', default=[], help='Actual additional dependency jar, repeatable; no synthetic SDK classes.')
    parser.add_argument('--output', type=Path, default=ROOT / 'work/ux-native-check')
    args = parser.parse_args()
    java = args.java_home.resolve() / 'bin'
    android = args.android_jar.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    names = json.loads((HERE / 'production-sources.json').read_text())
    if not isinstance(names, list) or not names or len(set(names)) != len(names):
        raise ValueError('Expected a nonempty unique production source list')
    if any(Path(name).name != name or not name.endswith('.java') for name in names):
        raise ValueError('Production source names must be direct Java files')
    dependencies = ([args.json_jar.resolve()] if args.json_jar else []) + [path.resolve() for path in args.classpath_jar]
    dependency_hashes = {str(path): digest(path) for path in dependencies if path.is_file()}
    for source in [android, java / 'javac', java / 'java', *dependencies, *(SOURCE / name for name in names)]:
        if not source.is_file():
            raise FileNotFoundError(source)
    app_sources = sorted(SOURCE.glob('*.java'))
    input_paths = [HERE / 'BoundaryGenerator.java', HERE / 'production-sources.json', Path(__file__).resolve(), *app_sources]
    input_hashes = {str(path.relative_to(ROOT)): digest(path) for path in input_paths}
    version = subprocess.check_output([str(java / 'javac'), '-version'], stderr=subprocess.STDOUT, text=True).strip()
    if not version.startswith('javac 17.'):
        raise ValueError('The native compilation check requires JDK 17')
    for folder in ['classes', 'generator-classes', 'stubs']:
        shutil.rmtree(out / folder, ignore_errors=True)
    subprocess.run([str(java / 'javac'), '-d', str(out / 'generator-classes'), str(HERE / 'BoundaryGenerator.java')], check=True, cwd=ROOT)
    subprocess.run([str(java / 'java'), '-cp', str(out / 'generator-classes'), 'BoundaryGenerator',
                    str(SOURCE), str(out / 'stubs/local/pocketchat'), *names], check=True, cwd=ROOT)
    classpath = [str(android)]
    classpath.extend(map(str, dependencies))
    command = [str(java / 'javac'), '-encoding', 'UTF-8', '-Xmaxerrs', '300', '-cp', ':'.join(classpath),
               '-sourcepath', str(out / 'stubs'), '-d', str(out / 'classes'), *[str(SOURCE / name) for name in names]]
    with (out / 'javac.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    boundaries = sorted((out / 'stubs').rglob('*.java'))
    try:
        source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    except subprocess.CalledProcessError:
        source_commit, dirty = None, None
    changed_inputs = [str(path.relative_to(ROOT)) for path in input_paths if not path.is_file() or digest(path) != input_hashes[str(path.relative_to(ROOT))]]
    changed_inputs.extend(str(path) for path in dependencies if not path.is_file() or digest(path) != dependency_hashes[str(path)])
    report = dict(
        status='source-changed' if changed_inputs else 'passed' if result.returncode == 0 else 'failed',
        scope='Complete listed production native Java sources compile together against actual Android APIs and source-derived, compilation-only application boundaries. Boundary bodies throw and are never executed. This does not compile or supply Gecko SDK classes.',
        fullAppBuild=False, actualAndroidExecution=False, geckoSdkProvided=False,
        sourceCommit=source_commit, dirtySource=dirty, javaVersion=version,
        executionInputsUnchanged=not changed_inputs, changedInputs=changed_inputs,
        applicationBoundarySourceFiles=[dict(path=str(path.relative_to(ROOT)), sha256=input_hashes[str(path.relative_to(ROOT))]) for path in app_sources if path.name not in names],
        androidJar=dict(path=str(android), sha256=digest(android)),
        supplementalClasspathJars=[dict(path=str(path),sha256=dependency_hashes[str(path)]) for path in dependencies],
        actualProductionSources=[dict(path=str((SOURCE / name).relative_to(ROOT)), sha256=digest(SOURCE / name)) for name in names],
        applicationBoundaryFiles=len(boundaries),
        applicationBoundaryErasures=[dict(owner='GeckoWebView',field='surface',compilationType='android.view.View',scope='Inherited Android View input-fence API only'),dict(owner='GeckoWebView',field='current',compilationType='java.lang.Object',scope='Opaque app session identity comparisons only')],
        boundaryGeneratorSha256=digest(HERE / 'BoundaryGenerator.java'),
        command=command, exitCode=result.returncode,
    )
    (out / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], productionFiles=len(names), applicationBoundaryFiles=len(boundaries),
                         fullAppBuild=False, actualAndroidExecution=False)))
    if result.returncode:
        print((out / 'javac.log').read_text())
    return result.returncode or (1 if changed_inputs else 0)


if __name__ == '__main__':
    sys.exit(main())
