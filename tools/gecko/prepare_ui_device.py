#!/usr/bin/env python3
"""Bounded, observed HOME preparation for the disposable UI emulator only."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time


def component(value):
    match = re.fullmatch(r'([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)', value)
    if match is None:
        raise ValueError('One actual Android component required: ' + repr(value))
    package, activity = match.groups()
    return package + '/' + (package + activity if activity.startswith('.') else activity)


def home_component(raw):
    values = re.findall(r'^\s*([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)\s*$', raw, re.M)
    if len(values) != 1:
        raise ValueError('One actual default HOME component required')
    return component(values[0])


def resumed_activities(raw):
    # Match only current AMS fields, following run_chrome_collapse's strict parser.
    values = set()
    for line in raw.splitlines():
        field = re.fullmatch(r'\s*(?:mResumedActivity|topResumedActivity)\s*[:=]\s*(.*)', line)
        if field is None or field[1] == 'null':
            continue
        match = re.fullmatch(r'ActivityRecord\{[^{}]*?\bu([0-9]+)\s+([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)(?:\s+[^{}]*)?\}', field[1])
        if match is None:
            raise ValueError('Unrecognized current resumed activity')
        values.add((int(match[1]), component(match[2])))
    return values


def current_focus(raw):
    # Historical window/error mentions cannot authorize or reject preparation.
    values = re.findall(r'^\s*mCurrentFocus=(Window\{[^\n]+\}|null)\s*$', raw, re.M)
    if len(values) != 1:
        raise ValueError('One actual current input focus required')
    return values[0]


def ready_observation(home, activity, window):
    focus = current_focus(window)
    if any(value in focus for value in ('Application Not Responding:', 'Application Error:', 'SYSTEM_ERROR')):
        raise ValueError('Actual system/application error window owns input focus: ' + focus)
    resumed = resumed_activities(activity)
    match = re.fullmatch(r'Window\{[^{}]*\bu0\s+([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)(?:\s+[^{}]*)?\}', focus)
    focused = component(match[1]) if match else None
    transitional = 'FallbackHome' in home or 'ImmersiveModeConfirmation' in focus
    ready = not transitional and resumed == {(0, home)} and focused == home
    return dict(home=home, resumed=sorted(resumed), focus=focus, ready=ready)


def prepare(adb, serial, output, timeout=45):
    if serial != 'emulator-5554' or not 1 <= timeout <= 45:
        raise ValueError('Fixed disposable emulator and a 1..45 second preparation budget required')
    started = time.monotonic()
    deadline = started + timeout
    record = dict(schema=1, status='failed', serial=serial, timeoutSeconds=timeout,
                  startedAtMonotonic=started, deadlineMonotonic=deadline,
                  commands=[], observations=[], homeNavigations=0,
                  actualAndroidCommands=False, applicationAcceptance=False,
                  runId=os.environ.get('GITHUB_RUN_ID'), runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
                  scope='Device HOME/input-focus precondition only; no application, glass or browser acceptance')
    output = Path(output)

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('Bounded UI device HOME preparation expired')
        return value

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')

    def command(parts, *, device=True):
        argv = [adb, '-s', serial, *parts] if device else list(parts)
        row = dict(command=argv, startedAtMonotonic=time.monotonic())
        record['commands'].append(row)
        try:
            row['timeoutSeconds'] = min(5, remaining())
            result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, errors='replace', timeout=row['timeoutSeconds'])
            row.update(exitCode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            record['actualAndroidCommands'] |= device
            result.check_returncode()
            remaining()
        except Exception as error:
            if isinstance(error, subprocess.TimeoutExpired):
                decode = lambda value: value.decode('utf-8', 'replace') if isinstance(value, bytes) else value
                row.update(timedOut=True, stdout=decode(error.stdout), stderr=decode(error.stderr))
            row.update(errorType=type(error).__name__, error=str(error), completedAtMonotonic=time.monotonic())
            save()
            raise
        row['completedAtMonotonic'] = time.monotonic()
        save()
        remaining()
        return result.stdout

    try:
        record['sourceCommit'] = command(['git', 'rev-parse', 'HEAD'], device=False).strip()
        record['sourceTree'] = command(['git', 'rev-parse', 'HEAD^{tree}'], device=False).strip()
        if any(re.fullmatch('[0-9a-f]{40}', record[key]) is None for key in ('sourceCommit', 'sourceTree')):
            raise ValueError('Exact Git source identity required')
        if command(['shell', 'getprop', 'ro.kernel.qemu']).strip() != '1':
            raise ValueError('Target is not a confirmed emulator')
        if command(['shell', 'am', 'get-current-user']).strip() != '0':
            raise ValueError('Actual Android User 0 required')
        previous = None
        while True:
            resolved = command(['shell', 'cmd', 'package', 'resolve-activity', '--brief', '--user', '0',
                                '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME'])
            home = home_component(resolved)
            remaining()
            activity = command(['shell', 'dumpsys', 'activity', 'activities'])
            window = command(['shell', 'dumpsys', 'window', 'displays'])
            observed = ready_observation(home, activity, window)
            remaining()
            record['observations'].append(observed)
            if record['homeNavigations'] == 0 and 'FallbackHome' not in home:
                record['homeNavigations'] = 1  # Failed input must never be retried.
                command(['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
                previous = None
            elif observed['ready'] and observed == previous:
                record.update(status='prepared', completedAtMonotonic=time.monotonic())
                save()
                remaining()
                return record
            else:
                previous = observed if observed['ready'] else None
            save()
            time.sleep(min(.2, remaining()))
    except Exception as error:
        record.update(status='failed', errorType=type(error).__name__, error=str(error),
                      completedAtMonotonic=time.monotonic())
        save()  # Failure evidence is retained even when the preparation budget expired.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=float, default=45)
    args = parser.parse_args()
    result = prepare(args.adb, args.serial, args.output, args.timeout)
    print(json.dumps({key:result[key] for key in ('status', 'sourceCommit', 'sourceTree', 'applicationAcceptance')}))


if __name__ == '__main__':
    main()
