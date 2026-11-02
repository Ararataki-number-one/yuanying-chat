#!/usr/bin/env python3
"""Run the actual update catalogue and downloader policy against local HTTP fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--java-home', required=True, type=Path)
parser.add_argument('--json-jar', required=True, type=Path)
parser.add_argument('--published-manifest', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
work = root / 'work/update-channels-host'
classes = work / 'classes'
classes.mkdir(parents=True, exist_ok=True)
production = root / 'app/src/main/java/local/pocketchat'
sources = [production / (name + '.java') for name in ('AppUpdateCatalog', 'AppUpdateInfo', 'AppUpdatePolicy', 'AppUpdateTransfer', 'Sha256', 'ReleaseNotes')]
sources.append(Path(__file__).with_name('UpdateChannelsHost.java'))
manager = (production / 'AppUpdateManager.java').read_text()
def member(needle):
    start = manager.index(needle)
    opening = manager.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        if manager[end] == '{':
            depth += 1
        elif manager[end] == '}':
            depth -= 1
        end += 1
    return manager[start:end]
methods = '\n'.join(member(needle) for needle in ('String selectedChannel()', 'synchronized boolean canChangeChannel()', 'synchronized Bundle selectChannel('))
state_source = work / 'ChannelStateHost.java'
state_source.write_text(Path(__file__).with_name('ChannelStateHost.java.in').read_text().replace('@CHANNEL_METHODS@', methods))
sources.append(state_source)
subprocess.run([str(args.java_home / 'bin/javac'), '--add-modules', 'jdk.httpserver', '-encoding', 'UTF-8', '-cp', str(args.json_jar), '-d', str(classes), *map(str, sources)], check=True)
command = [str(args.java_home / 'bin/java'), '--add-modules', 'jdk.httpserver', '-cp', str(classes) + ':' + str(args.json_jar), 'local.pocketchat.UpdateChannelsHost']
if args.published_manifest:
    command.append(str(args.published_manifest))
result = subprocess.run(command, text=True, capture_output=True, timeout=60)
if result.returncode:
    raise RuntimeError(result.stdout + result.stderr)
report = json.loads(result.stdout)
assert report['status'] == 'passed' and report['passed'] == len(report['checks']) > 0
report['sourceSha256'] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
(work / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'passed': report['passed'], 'report': str(work / 'results.json')}))
state = subprocess.run([str(args.java_home / 'bin/java'), '-cp', str(classes) + ':' + str(args.json_jar), 'local.pocketchat.ChannelStateHost'], text=True, capture_output=True, timeout=30)
if state.returncode:
    raise RuntimeError(state.stdout + state.stderr)
state_report = json.loads(state.stdout)
assert state_report['status'] == 'passed' and state_report['passed'] > 0
state_report['productionMethodsSha256'] = hashlib.sha256(methods.encode()).hexdigest()
(work / 'state-results.json').write_text(json.dumps(state_report, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'passed': state_report['passed'], 'report': str(work / 'state-results.json')}))
