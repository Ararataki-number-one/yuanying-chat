#!/usr/bin/env python3
"""Run production catalogue logic with explicit host-only storage fixtures."""
import argparse
import json
import pathlib
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--json-jar', required=True, type=pathlib.Path)
parser.add_argument('--java-home', type=pathlib.Path)
parser.add_argument('--output', type=pathlib.Path)
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[2]
work = root / 'work/network-catalog-host'
classes = work / 'classes'
classes.mkdir(parents=True, exist_ok=True)
java = str(args.java_home / 'bin/java') if args.java_home else shutil.which('java')
javac = str(args.java_home / 'bin/javac') if args.java_home else shutil.which('javac')
if not java or not javac:
    parser.error('Provide --java-home or install a JDK on PATH')
jar = args.json_jar.resolve()
if not jar.is_file():
    parser.error('--json-jar must point to an org.json JAR')
sources = [root / 'app/src/main/java/local/pocketchat' / name for name in (
    'J.java', 'NetworkCatalog.java','NetworkShareSnapshot.java', 'NetworkSubscriptionCatalogPolicy.java')]
sources += sorted(pathlib.Path(__file__).parent.rglob('*.java'))
subprocess.run([javac, '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(classes),
                *map(str, sources)], check=True)
result = subprocess.run([java, '-cp', f'{classes}:{jar}',
                         'local.pocketchat.NetworkCatalogHostTest'],
                        check=True, stdout=subprocess.PIPE, text=True)
receipt = json.loads(result.stdout)
assert receipt['passed'] == receipt['total'] >= 113
assert receipt['actualCrossProcessFileLocks']
assert not receipt['actualAndroidExecution']
output = args.output or work / 'results.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': receipt['passed'], 'total': receipt['total'],
                  'actualCrossProcessFileLocks': True, 'actualAndroidExecution': False,
                  'report': str(output)}, ensure_ascii=False))
