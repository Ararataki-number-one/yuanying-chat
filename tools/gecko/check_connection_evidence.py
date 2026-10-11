#!/usr/bin/env python3
"""Require current-source Android evidence for binding and proxy continuity fixes."""
import argparse
import json
import pathlib


def verify_connection_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        report = json.loads((directory / name).read_text())
        assert report['sourceCommit'] == source and report['status'] == 'passed'
        assert report['actualAndroidExecution'], name
        assert all(check['pass'] for check in report['checks']), name
        return report

    gecko = android('gecko-performance-results.json')
    assert gecko['actualGeckoExecution'] and gecko['actualGeckoBindingRegressionExecution']
    assert gecko['checkCount'] == len(gecko['checks']) >= 125
    names = {check['name'] for check in gecko['checks']}
    assert {
        'Same-route empty DOM waits without losing the confirmed task or accumulating terminal samples',
        'Virtualizing only the bound user waits even while other historical messages remain',
        'Homepage allocation rejects the same user ID when its prompt no longer matches',
        'Homepage conversation allocation preserves the exact user identity and persists the new route',
        'A genuine different conversation is rejected even if its visible message IDs match',
        'A neutral homepage shell during restoration waits without declaring another conversation',
        'SPA restoration and websocket faults never resubmit and preserve the typed draft and synthetic login',
        'Actual native inspection recognizes the website socket fault before polling and resets terminal stability',
        'A rendered historical reply socket alert and retry control do not invalidate the current task',
        'Website errors clear native stable samples and never finish or clear the persisted task',
        'A restored bound reply completes only after three fresh actual samples and two seconds',
        'Manual website recovery durably archives its captured draft before checking newer typing',
        'Typing while manual recovery saves aborts reload and preserves the newer draft and original pending task',
        'Manual website recovery durably archives its captured draft even when the pending task changes',
        'Changing the pending task while manual recovery saves aborts stale reload and preserves the new task',
        'Connection invalidation resets native terminal samples without submitting or clearing browser data',
    } <= names, 'Actual Gecko loading and route binding regression is required.'

    network = android('network-performance-results.json')
    assert network['actualMihomoExecution']
    assert len(network['checks']) >= 126
    names = {check['name'] for check in network['checks']}
    assert {
        'The live core and selected route have a successful exit verification receipt',
        'A real WSS connection carries continuous frames through both Mihomo SOCKS hops',
        'A temporary exit HTTP failure preserves the same WSS core and fixed route',
        'A real exit read timeout leaves the existing WSS tunnel responsive',
        'An invalid exit service response preserves only the previously verified route',
        'Exit verification failure schedules bounded retry without claiming fresh success',
        'Exit verification backoff makes no repeated IP requests or WebSocket replacement',
        'Send preflight reports unavailable verification without closing an already verified WSS',
        'A recovered exit service renews proof and resets the retry state',
        'All temporary verification faults retain one WebSocket and one core generation',
        "An actual entry change invalidates the previous route's verification receipt",
        'An unverified changed route fails closed when the exit service is unavailable',
        'A new core has no inherited in-memory verification receipt',
        'First connection requires actual exit verification and never accepts an outage',
        'A confirmed exit IP mismatch still blocks recovery and closes the real WebSocket',
        'Independent network service retains the same WSS and core during exit HTTP failure',
        'Independent network service retains the same WSS and core during a real exit timeout',
        'Independent network service retains the same WSS and core during invalid exit response',
        'Independent network service renews exit proof without replacing the original WebSocket',
        'Cancelled maintenance fails closed after an actual unverified entry change',
        'A confirmed service exit mismatch still stops the core when maintenance is concurrently cancelled',
    } <= names, 'Real protected WebSocket continuity and unknown-route rejection are required.'

    host = json.loads((directory / 'reply-binding-host-results.json').read_text())
    assert host['passed'] == host['total'] >= 41 and all(check['pass'] for check in host['checks'])
    names = {check['name'] for check in host['checks']}
    assert {
        'A visible historical assistant alert cannot interrupt the current healthy reply',
        'A user-quoted alert cannot become an active website failure during inspection',
        'A real current-turn alert beside its reply body remains recoverable',
        'Read-only waiting, recovery and assignment never resend the question',
    } <= names, 'Current website errors must remain distinct from historical or quoted content.'
    return {'actualAndroidExecution': True, 'actualGeckoExecution': True,
            'actualMihomoExecution': True, 'geckoChecks': gecko['checkCount'],
            'networkChecks': len(network['checks']), 'bindingHostChecks': host['total']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_connection_evidence(args.directory, args.source), indent=2))
