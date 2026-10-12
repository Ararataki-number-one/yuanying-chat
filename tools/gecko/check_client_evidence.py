#!/usr/bin/env python3
"""Require current-source original-page and quiet-completion acceptance."""
import argparse
import json
import pathlib

try:
    from .update_route_contract import verify_update_route
except ImportError:
    from update_route_contract import verify_update_route

QUIET_CHECKS = {
    'Background completion reminders are off by default',
    'A visible Activity is proved by real started lifecycle count',
    'An already running default process exposes real zero-Activity lifecycle over private IPC',
    'A private visibility endpoint rejects an obsolete process PID',
    'Real Home is proved by stopped Activity lifecycle despite browser process priority',
    'Browser and network child processes cannot count as visible UI',
    'Foreground replies and downloads stay quiet even after opting in',
    'Real Home leaves the UI in background while required services keep running',
    'Background completion stays quiet until the user opts in',
    'Foreground completions never become delayed background alerts',
    'Opted-in background file completion opens the exact saved task',
    'The notified local file is fully published and readable',
    'Opting out removes completion cards across environments',
}


def verify_client_evidence(directory, source):
    directory = pathlib.Path(directory)

    def report(name):
        value = json.loads((directory / name).read_text())
        assert value['sourceCommit'] == source and value['status'] == 'passed', name
        return value

    host = report('browser-runtime-policy-host-results.json')
    website = report('original-website-policy-host-results.json')
    assert host['passed'] == host['total'] == len(host['checks']) >= 49
    assert all(item['pass'] for item in host['checks'])
    assert website['passed'] == website['total'] == len(website['checks']) >= 25
    assert all(item['pass'] for item in website['checks'])

    quiet = report('quiet-notification-results.json')
    assert quiet['actualAndroidExecution'] and quiet['checkCount'] == len(quiet['checks']) >= 39
    assert all(item['pass'] for item in quiet['checks'])
    assert QUIET_CHECKS <= {item['name'] for item in quiet['checks']}
    foreground, home = quiet['foregroundEvidence'], quiet['homeEvidence']
    assert foreground['known'] and foreground['foreground']
    assert any(row['visible'] and row['process'] == 'local.pocketchat.test:profile7'
               for row in foreground['processes'])
    assert home['known'] and not home['foreground'] and all(not row['visible'] for row in home['processes'])
    assert foreground['visibilitySource'] == home['visibilitySource'] == 'activity-start-stop'
    assert foreground['actualActivityStartedCount'] > 0 and home['actualActivityStartedCount'] == 0
    for evidence in (foreground, home):
        assert all(row['known'] and row['visible'] == (row['actualActivityStartedCount'] > 0) for row in evidence['processes'])
        main = next(row for row in evidence['processes'] if row['process'] == 'local.pocketchat.test')
        profile = next(row for row in evidence['processes'] if row['process'] == 'local.pocketchat.test:profile7')
        assert main['pid'] > 0 and main['pid'] != profile['pid']
        assert main['known'] and main['actualActivityStartedCount'] == 0 and not main['visible']

    route = report('update-route-results.json')
    assert route['diagnosticOnly'] is False and route['releaseAcceptance'] is True
    core = json.loads((directory / 'network-core-build.json').read_text())
    assert core['sourceCommit'] == source
    update = verify_update_route(route, source, core['binaries']['x86_64']['sha256'])
    return {'geckoOnly': True, 'originalWebsiteOnly': True,
            'runtimeHostChecks': host['total'], 'websiteHostChecks': website['total'],
            'quietAndroidChecks': quiet['checkCount'], 'updateRoute': update}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_client_evidence(args.directory, args.source), indent=2))
