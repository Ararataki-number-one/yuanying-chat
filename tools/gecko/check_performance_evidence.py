#!/usr/bin/env python3
"""Require source-matched Android performance and correctness evidence for publication."""
import argparse
import json
import pathlib

BASELINE = '835d59991218eda70c7a4fdd73ea9d7ae6052688'
MAIN_IO = ('mainSealedReads', 'mainSealedWrites', 'mainCatalogReads', 'mainHeartbeatWrites')


def verify_performance_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        value = json.loads((directory / name).read_text())
        assert value['status'] == 'passed' and value['actualAndroidExecution'] and value['sourceCommit'] == source, name
        return value

    chrome = android('compact-chrome-results.json')
    assert len(chrome['cases']) == 3, 'All compact and large-font cases are required.'
    for case in chrome['cases']:
        assert case['readOnlyStatus'] and len(case['actualAndroidTaps']) == 3
        assert {tap['control'] for tap in case['actualAndroidTaps']} == {'drawer', 'environment', 'more'}
        layout = case['layout']
        assert layout['geckoOnly'] and layout['pageMode'] and layout['noNativeChat'] and layout['systemWebViews'] == 0
        assert [control['name'] for control in layout['controls']] == ['drawer', 'environment', 'more']
        perf = case['performance']
        for phase in ('burst', 'background', 'periodic'):
            assert all(perf[phase][key] == 0 for key in MAIN_IO), (phase, perf[phase])
        assert perf['burst']['metricsRefreshes'] == perf['burst']['chromeUpdates'] == 1
        for phase in ('burst', 'periodic'):
            assert perf[phase]['chromeTextChanges'] == perf[phase]['chromeBackgroundChanges'] == 0
        assert perf['background']['starDraws'] == 100 and perf['background']['stablePixels'] and perf['background']['plainBackground']
        assert perf['periodic']['metricsRefreshes'] == 5 and perf['periodic']['durationMs'] >= 6000
        original = perf['originalOnly']
        assert perf['rename'] and original['chromeBackgroundChanges'] == 0
        assert all(original[key] for key in ('sameSurface', 'sameSdkSession', 'sameUrl', 'pageMode', 'noNativeChat'))
        assert all(original[key] == 0 for key in MAIN_IO)

    visual = android('ui-visual-results.json')
    assert visual['comparisonMode'] == 'current-only' and visual['historicalUIRebuilt'] is False
    captures = visual['screenshots']
    assert len(captures) == 19 and all(item['variant'] == 'current' for item in captures)
    assert {(item['logicalViewport'], item['fontScale'], item['scene']) for item in captures} == {
        (viewport, 1, scene)
        for viewport in ('360x640', '412x640')
        for scene in ('chat', 'environments', 'network', 'proxy', 'entries', 'browser', 'preferences')
    } | {('360x640', 2, scene) for scene in ('chat', 'proxy', 'entries', 'browser', 'preferences')}
    build = json.loads((directory / 'ui-build-comparison.json').read_text())
    assert build['coreSourceCommit'] == source and build['comparisonMode'] == 'current-only'
    assert build['historicalUIRebuilt'] is False and build['changedForBaseline'] == []
    assert len(build['currentSha256']) == 64

    gecko = android('gecko-performance-results.json')
    assert gecko['actualGeckoExecution'] and gecko['baselineSource'] == BASELINE
    assert gecko['actualAndroidTouchExecution'] and len(gecko['actualAndroidGestures']) == 3
    routes = gecko['controlledProxyRoutes']
    assert routes and all(route['accepted'] and route['host'] == '127.0.0.1' and route['port'] == 8767 for route in routes)
    decisions = [item['value'] for item in gecko['browserDiagnostics']
                 if item['kind'] == 'route' and item['value']['url'].startswith('http://127.0.0.1:8767/performance')]
    assert len(decisions) >= 2 and all(item['guardAllowed'] and item['decision']['type'] == 'socks'
                                     and item['decision']['host'] == '127.0.0.1' and item['decision']['port'] == 1087
                                     for item in decisions), 'Both comparisons must use the existing protected proxy path.'
    assert gecko['checkCount'] == len(gecko['checks']) >= 142 and all(check['pass'] for check in gecko['checks'])
    names = {check['name'] for check in gecko['checks']}
    assert {
        'Actual Gecko streaming bridge payload is reduced by at least 95 percent',
        'Actual growing-body DOM read work is reduced by at least 95 percent',
        'Streaming metadata never rebuilds markdown or files',
        'Text mutations preserve the cached message topology',
        'First terminal capture keeps the entire 105k reply, both stream tails, code and file',
        'The third stable actual body is accepted after at least two seconds',
        'Reusing a stable message ID on a new node cannot retain the previous body',
        'Generated file changes invalidate terminal markdown and attachment metadata',
        'Earlier response copy controls cannot complete the current reply',
        'Semantic checks preserve the synthetic login, draft and no-send invariant',
        'Production stable lightweight samples finish and persist the actual reply task',
        'The complete final body is durably saved by the production transcript worker',
        'Actual Android tap and keyboard input preserve the existing composer draft',
        'Sibling generated file cards invalidate the actual Gecko reply revision',
        'Sibling file cards appear in incremental transcript downloads',
        'Renaming a sibling file card refreshes actual Gecko metadata and transcript downloads',
        'Removing a sibling file card invalidates the actual Gecko reply metadata',
        'Reattaching an edited cached body refreshes actual Gecko terminal text and transcript',
        'Original-only bridge starts with the actual existing Gecko document',
        'Retired native actions leave the entire website DOM, composer, selection, route and login unchanged',
    } <= names, 'Long-reply correctness regression is required.'
    for action in ('fill', 'submit', 'model-open', 'model-select', 'message-regenerate-submit', 'page-navigate'):
        assert 'Public native bridge rejects retired action ' + action in names
        assert 'Actual Gecko observation asset rejects retired action ' + action in names
    measurements = {case['variant']: case for case in gecko['measurements']}
    assert set(measurements) == {'baseline', 'current'}
    assert all(case['samples'] == 12 for case in measurements.values())
    baseline, current = measurements['baseline'], measurements['current']
    assert current['bridgeResponseBytes'] * 20 < baseline['bridgeResponseBytes']
    assert current['domReadChars'] * 20 < baseline['domReadChars']
    assert current['observationAfter']['derivedBuilt'] == current['observationBefore']['derivedBuilt']

    network = android('network-performance-results.json')
    passed = {check['name'] for check in network['checks'] if check['pass']}
    assert {
        'Eight encrypted environment regions stay isolated across alternating reads',
        'Repeated multi-window reads reuse decrypted region snapshots',
        'Replacing one sealed region updates only that environment',
        'Deleting a sealed region clears its cached identity',
        'Network list reads pending draft metadata on its background reader',
        'Network list refresh sees draft removal without a global pending cache',
        'Actual Android main-thread region and cold latency reads complete',
        'Region and latency UI snapshots cause no main-thread disk reads or writes',
        'Cold profile metadata paths resolve without Android main-thread directory access',
        'Background cold-path resolution restores the correct eight environment snapshots',
        'Deferred callback race reaches both real encrypted candidate writes',
        'An older deferred callback does not clear the newer sealed candidate',
        'An older deferred callback keeps the newer request saving state',
        'An older deferred callback does not apply the replaced candidate',
        'Intervening non-saving network operations preserve the newest save ownership',
        'The latest network candidate is applied once after the stale callback is ignored',
    } <= passed, 'Multi-profile cache and main-thread disk regression is required.'
    for name, count in [('snapshot-host-results.json', 14), ('reply-observation-host-results.json', 37)]:
        report = json.loads((directory / name).read_text())
        assert report['passed'] == report['total'] >= count, name
    return {'actualAndroidExecution': True, 'actualGeckoExecution': True, 'geckoChecks': gecko['checkCount'],
            'compactCases': len(chrome['cases']), 'currentVisualScreens': len(captures), 'historicalUIRebuilt': False,
            'bridgeResponseBytes': {'baseline': baseline['bridgeResponseBytes'], 'current': current['bridgeResponseBytes']},
            'domReadChars': {'baseline': baseline['domReadChars'], 'current': current['domReadChars']}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_performance_evidence(args.directory, args.source), indent=2))
