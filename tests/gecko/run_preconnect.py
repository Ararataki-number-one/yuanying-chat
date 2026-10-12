#!/usr/bin/env python3
"""Actual Android/official Gecko cold H2 through managed SOCKS preauthentication."""
import argparse
import json
import pathlib
import select
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from gecko.preconnect_contract import verify_preconnect
from run_gecko_pool import NODE as BASE_NODE

OUT = ROOT / 'work/gecko-integration'
PORT = 9878
PACKAGE = 'local.pocketchat.test'
# The same genuine Node TLS/H2 implementation, in a separate controlled listener.
NODE = BASE_NODE.replace('port=9877', 'port=9878')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--timeout', type=int, default=360)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ['preconnect-results.json', 'preconnect-log.txt', 'preconnect-failure-log.txt',
                 'preconnect-server.json', 'preconnect-server-failure.json']:
        (OUT / name).unlink(missing_ok=True)

    def adb(*parts, check=True):
        result = subprocess.run([args.adb, '-s', args.serial, *parts], text=True,
                                capture_output=True, timeout=30, check=check)
        return result.stdout

    def log():
        return adb('logcat', '-d', '-s', 'PocketPreconnect:I', 'AndroidRuntime:E', '*:S')

    with tempfile.TemporaryDirectory(prefix='pocket-preconnect-') as temporary:
        directory = pathlib.Path(temporary)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                        '-days', '1', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
                        '-keyout', str(directory / 'key.pem'), '-out', str(directory / 'cert.pem')],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (directory / 'fixture.js').write_text(NODE)
        process = subprocess.Popen(['node', str(directory / 'fixture.js'), str(directory / 'key.pem'),
                                    str(directory / 'cert.pem'), str(directory / 'server.json')],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([process.stdout], [], [], 10)
            assert ready and json.loads(process.stdout.readline()) == {'ready': True, 'port': PORT, 'protocol': 'h2'}
            adb('reverse', 'tcp:' + str(PORT), 'tcp:' + str(PORT))
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'pm', 'clear', PACKAGE)
            adb('logcat', '-c')
            adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/local.pocketchat.PreconnectIntegrationActivity')
            deadline = time.monotonic() + args.timeout
            report = None
            while time.monotonic() < deadline:
                raw = log()
                if 'FATAL EXCEPTION' in raw:
                    raise AssertionError(raw)
                if any('PocketPreconnect' in line and '"kind":"complete"' in line for line in raw.splitlines()):
                    value = adb('exec-out', 'content', 'read', '--uri',
                                'content://local.pocketchat.test.evidence/preconnect')
                    report = json.loads(value)
                    break
                time.sleep(1)
            if report is None:
                raise TimeoutError('No complete actual Android preauthentication report')
            report['sourceCommit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            report['androidSdk'] = int(adb('shell', 'getprop', 'ro.build.version.sdk').strip())
            server = json.loads((directory / 'server.json').read_text())
            report['server'] = server
            (OUT / 'preconnect-results.json').write_text(json.dumps(report, indent=2) + '\n')
            (OUT / 'preconnect-log.txt').write_text(raw)
            (OUT / 'preconnect-server.json').write_text(json.dumps(server, indent=2) + '\n')
            receipt = json.loads((ROOT / 'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text())
            verify_preconnect(report, receipt)
            print(json.dumps({'status': report['status'], 'checks': len(report['checks']),
                              'pairedTrials': len(report['pairedTrials']), 'sourceCommit': report['sourceCommit'],
                              'controlledSavingsMs': [row['savedMs'] for row in report['pairedTrials']],
                              'actualColdHttp2Requests': len(report['requests'])}), flush=True)
        except BaseException:
            (OUT / 'preconnect-failure-log.txt').write_text(adb('logcat', '-d', check=False))
            if (directory / 'server.json').exists():
                (OUT / 'preconnect-server-failure.json').write_bytes((directory / 'server.json').read_bytes())
            raise
        finally:
            adb('shell', 'am', 'force-stop', PACKAGE, check=False)
            adb('reverse', '--remove', 'tcp:' + str(PORT), check=False)
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == '__main__':
    main()
