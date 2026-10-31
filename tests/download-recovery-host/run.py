#!/usr/bin/env python3
"""Production download race checks with explicit host-only Android service doubles."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import importlib.util

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--json-jar', type=Path, required=True)
parser.add_argument('--java-home', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
output = args.output or root / 'work/plan-repairs/download-race/host-results.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.unlink(missing_ok=True)
classes = output.parent / 'classes'
classes.mkdir(exist_ok=True)
sources = [root / 'app/src/main/java/local/pocketchat' / name for name in (
    'J.java', 'DownloadTaskRevisions.java', 'DownloadTasks.java', 'DownloadResumePolicy.java', 'DefaultDownloads.java',
    'SavedFilePublication.java', 'SavedFileDeletion.java', 'SealedFileIo.java')]
sources += [root / 'app/src/main/java/local/pocketchat/DownloadMetadataValues.java']
sources += sorted(Path(__file__).parent.rglob('*.java'))
sources += [root / 'tests/sealed-file-host/android/util/AtomicFile.java']
hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
adapter_path=root/'tests/download46-host/legacy_support.py'
hashes[str(adapter_path.relative_to(root))]=hashlib.sha256(adapter_path.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('download46_legacy_boundary',adapter_path)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
extra,adapter_hashes=adapter.emit(output.parent/'generated-adapters/local/pocketchat');sources += extra
javac = str(args.java_home / 'bin/javac') if args.java_home else shutil.which('javac')
java = str(args.java_home / 'bin/java') if args.java_home else shutil.which('java')
if not javac or not java:
    parser.error('Provide --java-home or make java and javac available on PATH')
subprocess.run([javac, '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()),
                '-d', str(classes), *map(str, sources)], check=True)
run = subprocess.run([java, '-cp', str(classes) + ':' + str(args.json_jar.resolve()),
                      'local.pocketchat.DownloadRecoveryHostTest'], capture_output=True, text=True, timeout=60)
(output.parent / 'host-stdout.txt').write_text(run.stdout)
(output.parent / 'host-stderr.txt').write_text(run.stderr)
try:
    receipt = json.loads(run.stdout)
except ValueError:
    receipt = {'status': 'failed', 'error': 'Host process did not return a JSON receipt'}
receipt.update(sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
               newMetadataProviderBoundaryAdapters=adapter_hashes,
               sourceDirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)),
               sourceFiles=hashes, jsonJarSha256=hashlib.sha256(args.json_jar.read_bytes()).hexdigest(),
               exitCode=run.returncode, stderr=run.stderr)
output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
run.check_returncode()
assert receipt['status'] == 'passed'
assert receipt['total'] == receipt['executed'] == len(receipt['checks']) == 42
assert len({check['name'] for check in receipt['checks']}) == 42
assert all(check['pass'] is True for check in receipt['checks'])
assert all(hashlib.sha256((root / path).read_bytes()).hexdigest() == digest for path, digest in hashes.items())
print(json.dumps({'status': 'passed', 'checks': 42, 'actualAndroidExecution': False, 'report': str(output)}))
