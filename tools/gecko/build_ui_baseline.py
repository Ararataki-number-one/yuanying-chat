#!/usr/bin/env python3
"""Stage the current original-only app for real Android visual acceptance.

The previous UI exposed the removed system engine and simple conversation mode.
Rebuilding its Java against current browser contracts would reintroduce obsolete
behavior. Historical screenshots remain in their immutable CI artifacts; this
run intentionally captures only the actual current product.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess

root = pathlib.Path(__file__).resolve().parents[2]
out = root / 'work/gecko-integration'
p = argparse.ArgumentParser()
# Preserve the workflow interface. This step does not rebuild or rewrite source.
p.add_argument('--gradle', required=True)
p.add_argument('--key', required=True)
args = p.parse_args()
out.mkdir(parents=True, exist_ok=True)
current = root / 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
shutil.copy2(current, out / 'ui-current.apk')
record = {
    'comparisonMode': 'current-only',
    'historicalUIRebuilt': False,
    'coreSourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'changedForBaseline': [],
    'currentSha256': hashlib.sha256(current.read_bytes()).hexdigest(),
    'scope': 'Actual current GeckoView-only app and official original-page shell; historical UI is not rebuilt or counted as current-source evidence.',
}
(out / 'ui-build-comparison.json').write_text(json.dumps(record, indent=2) + '\n')
