#!/usr/bin/env python3
"""Prepare only the fixed synthetic emulator; preserve every original UI oracle."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'com.google.android.googlesdksetup'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True, choices=['emulator-5554'])
    args = parser.parse_args()
    out = ROOT / 'work/gecko-integration/emulator-bootstrap-results.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    record = dict(schema=1, sourceCommit=source, status='failed', serial=args.serial,
                  exactSetupPackage=PACKAGE, commands=[], actualAndroidCommands=False,
                  actualApplicationExecution=False, physicalPhone=False,
                  applicationOrInputPolicyModified=False, gestureReplayed=False,
                  scope='Fixed synthetic Android emulator bootstrap only; no app or phone acceptance')

    def adb(*parts):
        command = [args.adb, '-s', args.serial, *parts]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=30)
        except subprocess.TimeoutExpired as error:
            output = error.output or ''
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='replace')
            record['commands'].append(dict(command=command, exitCode=None, timedOut=True,
                                           output=output, observedAt=time.monotonic()))
            raise
        record['commands'].append(dict(command=command, exitCode=result.returncode,
                                       output=result.stdout, observedAt=time.monotonic()))
        result.check_returncode()
        record['actualAndroidCommands'] = True
        return result.stdout.replace('\r', '').strip()

    try:
        # Never execute package mutations on a phone or an unspecified adb target.
        if adb('shell', 'getprop', 'ro.kernel.qemu') != '1':
            raise ValueError('The fixed adb target is not a confirmed emulator')
        present = adb('shell', 'pm', 'list', 'packages', PACKAGE).splitlines()
        record['packagePresent'] = 'package:' + PACKAGE in present
        if record['packagePresent']:
            # This exact setup package caused a captured system ANR to steal
            # the test Activity focus. Do not dismiss arbitrary app dialogs.
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'pm', 'disable-user', '--user', '0', PACKAGE)
            disabled = adb('shell', 'pm', 'list', 'packages', '-d', PACKAGE).splitlines()
            if 'package:' + PACKAGE not in disabled:
                raise ValueError('Setup-package disabled state was not confirmed')
            record['disabledStateConfirmed'] = True
        else:
            record['disabledStateConfirmed'] = False
        record['status'] = 'passed'
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        record['failureType'] = type(error).__name__
        record['reason'] = str(error)
        raise
    finally:
        temporary = out.with_suffix('.partial')
        temporary.write_text(json.dumps(record, indent=2) + '\n')
        temporary.replace(out)
    print(json.dumps({key: record[key] for key in
                     ['sourceCommit', 'status', 'packagePresent', 'disabledStateConfirmed',
                      'actualApplicationExecution', 'physicalPhone']}))


if __name__ == '__main__':
    main()
