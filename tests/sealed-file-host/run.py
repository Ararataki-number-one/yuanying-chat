#!/usr/bin/env python3
"""Run production leases with honest host-only AtomicFile behavior reports."""
import argparse
import json
import pathlib
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--java-home', type=pathlib.Path)
parser.add_argument('--output', type=pathlib.Path)
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[2]
classes = root / 'work/sealed-file-host/classes'
classes.mkdir(parents=True, exist_ok=True)
output = args.output or root / 'work/sealed-file-host/results.json'
output.parent.mkdir(parents=True, exist_ok=True)
# A failed compilation/run must never leave an earlier successful receipt.
output.unlink(missing_ok=True)
java = str(args.java_home / 'bin/java') if args.java_home else shutil.which('java')
javac = str(args.java_home / 'bin/javac') if args.java_home else shutil.which('javac')
if not java or not javac:
    parser.error('Provide --java-home or install a JDK on PATH')
sources = [root / 'app/src/main/java/local/pocketchat/SealedFileIo.java']
sources += sorted(pathlib.Path(__file__).parent.rglob('*.java'))
subprocess.run([javac, '-encoding', 'UTF-8', '-d', str(classes), *map(str, sources)], check=True)
result = subprocess.run([java, '-cp', str(classes), 'local.pocketchat.SealedFileIoHostTest'],
                        text=True, stdout=subprocess.PIPE, timeout=120)
receipt = json.loads(result.stdout)
output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
result.check_returncode()
assert receipt['status'] == 'passed'
assert receipt['passed'] == receipt['total'] == receipt['executed'] == len(receipt['checks']) == 32
assert all(row['pass'] is True for row in receipt['checks'])
assert len({row['name'] for row in receipt['checks']}) == receipt['total']
assert receipt['actualCrossJvmStorageLease'] is True
assert receipt['actualAtomicFileBehaviorStub'] is True
assert receipt['actualAndroidExecution'] is False and receipt['actualKeystoreEncryption'] is False
print(json.dumps({'passed': receipt['passed'], 'total': receipt['total'], 'report': str(output)}))
