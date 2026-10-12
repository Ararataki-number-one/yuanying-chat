#!/usr/bin/env python3
"""Actual patched Android Mihomo, two authenticated local SOCKS hops, native cancellation."""
import argparse
import json
import pathlib
import re
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'tools'))
from gecko.chain_runtime_contract import verify_native_probe

OUT = ROOT / 'work/gecko-integration'


def verify(report):
    receipt = json.loads((ROOT / 'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text())
    return verify_native_probe(report, receipt)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', default='emulator-5554')
    p.add_argument('--timeout', type=int, default=150)
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ['native-probe-results.json', 'native-probe-log.txt', 'native-probe-failure-log.txt']:
        (OUT / name).unlink(missing_ok=True)

    def adb(*parts, check=True):
        result = subprocess.run([args.adb, '-s', args.serial, *parts], text=True,
                                capture_output=True, timeout=30, check=check)
        return result.stdout

    def failure_log():
        (OUT / 'native-probe-failure-log.txt').write_text(adb('logcat', '-d', check=False))

    adb('shell', 'am', 'force-stop', 'local.pocketchat.test')
    adb('shell', 'pm', 'clear', 'local.pocketchat.test')
    adb('logcat', '-c')
    adb('shell', 'am', 'start', '-W', '-n',
        'local.pocketchat.test/local.pocketchat.NativeProbeIntegrationActivity')
    until = time.monotonic() + args.timeout
    while time.monotonic() < until:
        raw = adb('exec-out', 'content', 'read', '--uri',
                  'content://local.pocketchat.test.evidence/native-probe', check=False)
        if raw.strip().startswith('{'):
            report = json.loads(raw)
            report['sourceCommit'] = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            (OUT / 'native-probe-results.json').write_text(json.dumps(report, indent=2) + '\n')
            (OUT / 'native-probe-log.txt').write_text(adb('logcat', '-d', '-s',
                'PocketNativeProbe:I', 'AndroidRuntime:E', '*:S'))
            try:
                verify(report)
            except Exception:
                failure_log()
                raise
            print(json.dumps({'status': report['status'], 'sourceCommit': report['sourceCommit'],
                              'checkCount': len(report['checks']),
                              'webSocketEchoes': report['webSocketEchoes'],
                              'cancellations': report['cancellations'],
                              'startupSearches': report['startupSearches']}, indent=2), flush=True)
            return
        log = adb('logcat', '-d', '-s', 'PocketNativeProbe:I', 'AndroidRuntime:E', '*:S')
        if 'FATAL EXCEPTION' in log:
            failure_log()
            raise AssertionError(log)
        time.sleep(1)
    failure_log()
    raise TimeoutError('No complete native probe evidence from actual Android')


if __name__ == '__main__':
    main()
