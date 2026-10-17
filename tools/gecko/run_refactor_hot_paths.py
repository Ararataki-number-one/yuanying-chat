#!/usr/bin/env python3
"""Compare actual git baseline classes with current code; host evidence only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', default='7e0247939dd4029ba994c3d6fd8be1965d42f8fe')
p.add_argument('--json-jar', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
baseline = subprocess.check_output(['git', 'rev-parse', '--verify', a.baseline + '^{commit}'], cwd=ROOT, text=True).strip()
current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
with tempfile.TemporaryDirectory(prefix='pocketchat-refactor-') as temporary:
    work = Path(temporary)
    baseline_hashes = {}
    sources = []
    for name in ('AppUpdatePolicy', 'DownloadListPolicy', 'NetworkSourceSelection'):
        path = 'app/src/main/java/local/pocketchat/' + name + '.java'
        original = subprocess.check_output(['git', 'show', baseline + ':' + path], cwd=ROOT)
        baseline_hashes[path] = hashlib.sha256(original).hexdigest()
        destination = work / ('Baseline' + name + '.java')
        destination.write_text(original.decode().replace(name, 'Baseline' + name))
        sources.append(destination)
    names = ('Sha256', 'AppUpdatePolicy', 'DownloadListPolicy', 'NetworkSourceSelection',
             'J', 'NetworkCatalog', 'NetworkSubscriptionCatalogPolicy', 'EntrySelection',
             'NetworkDraft', 'NetworkChanges', 'NetworkOptimizationPolicy')
    inputs = [SOURCE / (name + '.java') for name in names]
    inputs += sorted((ROOT / 'tests/network-source-host').rglob('*.java'))
    inputs.append(ROOT / 'tests/refactor-host/RefactorHotPaths.java')
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    sources += inputs
    classes = work / 'classes'
    classes.mkdir()
    subprocess.run([shutil.which('javac'), '-encoding', 'UTF-8', '-cp', str(a.json_jar.resolve()), '-d', str(classes), *map(str, sources)], check=True)
    run = subprocess.run([shutil.which('java'), '-Xmx256m', '-cp', str(classes) + ':' + str(a.json_jar.resolve()), 'local.pocketchat.RefactorHotPaths'], check=True, text=True, capture_output=True)
    report = json.loads(run.stdout)
    for path, digest in hashes.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Source changed during comparison: ' + path)
    report.update(baselineCommit=baseline, currentCommit=current, sourceDirty=bool(status.strip()),
                  baselineFiles=baseline_hashes, currentFiles=hashes,
                  javaVersion=subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True).strip(),
                  jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'compatibilityChecks': report['compatibilityChecks'], 'report': str(a.output)}))
