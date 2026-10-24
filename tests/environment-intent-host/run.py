#!/usr/bin/env python3
"""Production intent publication/reconciliation with explicit JVM fault doubles."""
import argparse, hashlib, json, pathlib, re, shutil, subprocess
p = argparse.ArgumentParser()
p.add_argument('--json-jar', required=True, type=pathlib.Path)
p.add_argument('--java-home', type=pathlib.Path)
p.add_argument('--output', type=pathlib.Path)
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parents[2]
work = root / 'work/environment-intent-host'
classes = work / 'classes'
classes.mkdir(parents=True, exist_ok=True)
java = str(a.java_home / 'bin/java') if a.java_home else shutil.which('java')
javac = str(a.java_home / 'bin/javac') if a.java_home else shutil.which('javac')
if not java or not javac or not a.json_jar.is_file():
    p.error('An explicit org.json jar and JDK are required')
names = ('Sha256.java','J.java', 'EnvironmentSpec.java', 'EnvironmentSpecMigration.java',
         'EnvironmentSpecRuntime.java', 'NetworkChanges.java', 'NetworkCatalog.java','NetworkShareSnapshot.java','NetworkShareJson.java',
         'NetworkSubscriptionCatalogPolicy.java', 'NetworkSourceSelection.java',
         'EntrySelection.java', 'NetworkDraft.java', 'NetworkOptimizationPolicy.java', 'SealedFileIo.java')
production = [root / 'app/src/main/java/local/pocketchat' / name for name in names]
fixtures = sorted(pathlib.Path(__file__).parent.rglob('*.java'))
# Execute the actual production validator instead of a permissive proxy double.
# Only the Android URI parser has a JVM adapter; device checks use Android itself.
main_source = root / 'app/src/main/java/local/pocketchat/MainActivity.java'
main_text = main_source.read_text()
opening = re.search(r'static boolean validProxy\(String value\)\s*\{', main_text)
if opening is None:
    raise ValueError('Production proxy validator was not found')
depth = 1
end = opening.end()
while end < len(main_text) and depth:
    if main_text[end] == '{': depth += 1
    elif main_text[end] == '}': depth -= 1
    end += 1
if depth:
    raise ValueError('Production proxy validator is incomplete')
validator = main_text[opening.start():end]
generated = work / 'generated/local/pocketchat/MainActivity.java'
generated.parent.mkdir(parents=True, exist_ok=True)
generated.write_text('package local.pocketchat;\nimport android.net.Uri;\nimport java.util.Arrays;\nfinal class MainActivity {' + validator + '}\n')
shared = [root / 'tests/network-source-host/local/pocketchat/Profiles.java']
shared.append(root / 'tests/sealed-file-host/android/util/AtomicFile.java')
subprocess.run([javac, '-J-XX:ActiveProcessorCount=2', '-encoding', 'UTF-8',
                '-cp', str(a.json_jar.resolve()), '-d', str(classes),
                *map(str, production + shared + fixtures + [generated])], check=True)
result = subprocess.run([java, '-XX:ActiveProcessorCount=2', '-cp',
                         f'{classes}:{a.json_jar.resolve()}',
                         'local.pocketchat.EnvironmentIntentHostTest'],
                        stdout=subprocess.PIPE, text=True, check=True, timeout=120)
receipt = json.loads(result.stdout)
assert receipt['status'] == 'passed' and receipt['passed'] == receipt['total'] == receipt['executed'] == len(receipt['checks'])
assert len({row['name'] for row in receipt['checks']}) == receipt['total'] and all(row['pass'] is True for row in receipt['checks'])
assert receipt['actualCrossProcessIntentLease'] and not receipt['actualAndroidExecution']
receipt['files'] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in production + shared + fixtures + [main_source]}
receipt['proxyValidation'] = {'productionMethodExtractedVerbatim': True,
    'methodSha256': hashlib.sha256(validator.encode()).hexdigest(),
    'uriParser': 'JVM java.net.URI adapter; actual Android URI covered separately'}
output = a.output or work / 'results.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': receipt['passed'], 'total': receipt['total'], 'report': str(output)}))
