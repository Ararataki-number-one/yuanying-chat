#!/usr/bin/env python3
"""Require source-matched Android performance and correctness evidence for publication."""
import argparse
import json
import pathlib
import subprocess
if __package__:
    from .chrome_collapse_contract import verify_auto_collapse
    from .ui_visual_contract import verify_captures
else:
    from chrome_collapse_contract import verify_auto_collapse
    from ui_visual_contract import verify_captures

BASELINE = '835d59991218eda70c7a4fdd73ea9d7ae6052688'
MAIN_IO = ('mainSealedReads', 'mainSealedWrites', 'mainCatalogReads', 'mainHeartbeatWrites')


def verify_performance_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        value = json.loads((directory / name).read_text())
        assert value['status'] == 'passed' and value['actualAndroidExecution'] and value['sourceCommit'] == source, name
        return value

    chrome = android('compact-chrome-results.json')
    reload = chrome['reloadConfirmation']
    assert reload['sourceCommit'] == source and reload['actualAndroidExecution'] and reload['actualGeckoExecution']
    assert len(reload['checks']) == 8 and all(item['pass'] for item in reload['checks'])
    assert all(reload[key] for key in ('cancelMatched', 'noStopNoLoad', 'noSend', 'fullDraftCookieUnchanged', 'explicitConfirmCurrentURI', 'notOldURI', 'idleNoModal'))
    assert [tap['label'] for tap in reload['actualAndroidTaps']] == ['取消', '重新加载', '重新加载']
    for tap in reload['actualAndroidTaps']:
        left, top, right, bottom = tap['bounds']
        assert tap['actualAndroidTap'] and tap['enabled'] and tap['clickable']
        assert left <= tap['x'] < right and top <= tap['y'] < bottom
    initial, cancelled, stale, confirmed, idle = (reload[key] for key in ('initial', 'cancelled', 'stale', 'confirmed', 'idle'))
    assert initial['documents'] == 1 and initial['loads'] == initial['stops'] == 0
    assert all(cancelled[key] == initial[key] for key in ('body', 'draft', 'cookie', 'sendCount', 'document', 'path', 'stops', 'loads'))
    assert stale['path'] == '/c/reload-C' and stale['stops'] == stale['loads'] == 0
    assert all(stale[key] == initial[key] for key in ('body', 'draft', 'cookie', 'sendCount', 'document'))
    assert confirmed['documents'] == 2 and confirmed['loads'] == 1 and confirmed['document'] != initial['document']
    assert confirmed['draftArchived'] and confirmed['cookie'] == initial['cookie']
    assert confirmed['requested'] == initial['currentUrl'] != initial['cachedResumeUrl']
    assert idle['documents'] == 3 and idle['loads'] == 2 and not idle['modal']
    assert idle['requested'] == confirmed['requested'] and confirmed['sendCount'] == idle['sendCount'] == 0
    assert [row['path'] for row in reload['fixtureRequests']] == ['/c/reload-A', '/c/reload-B', '/c/reload-B']
    assert reload['controlledProxyRoutes'] and all(row['accepted'] and row['host'] == '127.0.0.1' and row['port'] == 8765 for row in reload['controlledProxyRoutes'])
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
    verify_captures(captures)
    build = json.loads((directory / 'ui-build-comparison.json').read_text())
    assert build['coreSourceCommit'] == source and build['comparisonMode'] == 'current-only'
    assert build['historicalUIRebuilt'] is False and build['changedForBaseline'] == []
    assert len(build['currentSha256']) == 64
    auto_collapse = verify_auto_collapse(chrome['autoCollapse'], source, build['currentSha256'])
    assert visual['autoCollapse'] == chrome['autoCollapse']

    gecko = android('gecko-performance-results.json')
    source_root = pathlib.Path(__file__).resolve().parents[2]
    source_reader = lambda commit, name: subprocess.check_output(['git', 'show', commit + ':' + name], cwd=source_root)
    if b'from native_input_driver import NativeInputDriver' in source_reader(source, 'tests/gecko/run_gecko_performance.py'):
        if __package__:
            from .native_input_contract import verify_qualification
        else:
            from native_input_contract import verify_qualification
        installed = json.loads((directory / 'gecko-performance-build-identity.json').read_bytes())
        assert installed['sourceCommit'] == source
        verify_qualification(directory, gecko, source, source_reader, installed['integrationApkSha256'], (installed['runId'], installed['runAttempt']))
    manifest_path = directory / 'manifest.json'
    if not manifest_path.exists():
        manifest_path = directory / 'release-manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text())['versionCode'] >= 49:
        summary = gecko['scrollDiagnostics']
        assert summary['schema'] == 1 and summary['actualAndroidFileRead'] is True and summary['phases'] == 2
        scroll = json.loads((directory / 'gecko-scroll-diagnostics.json').read_text())
        assert scroll['schema'] == 1 and scroll['sourceCommit'] == source and scroll['actualAndroidFileRead'] is True
        assert len(scroll['run']) == 32 and all(c in '0123456789abcdef' for c in scroll['run'])
        assert scroll['instrumentationScope'] == summary['instrumentationScope']
        assert [phase['phase'] for phase in scroll['phases']] == ['baseline', 'current']
        for phase in scroll['phases']:
            assert phase['outcome'] == 'passed' and phase['samples'] and phase['nativeTouches']
            before = phase['samples'][0]
            assert before['stage'] == 'before' and len(phase['samples']) <= 256 and len(phase['nativeTouches']) <= 64
            assert any(sample['stage'] == 'after' and sample['dom']['scrollTop'] > before['dom']['scrollTop'] for sample in phase['samples'])
            assert {0, 2} <= {touch['action'] for touch in phase['nativeTouches']}
    assert gecko['actualGeckoExecution'] and gecko['baselineSource'] == BASELINE
    assert gecko['actualAndroidTouchExecution'] and len(gecko['actualAndroidGestures']) == 3
    routes = gecko['controlledProxyRoutes']
    assert routes and all(route['accepted'] and route['host'] == '127.0.0.1' and route['port'] == 8767 for route in routes)
    decisions = [item['value'] for item in gecko['browserDiagnostics']
                 if item['kind'] == 'route' and item['value']['url'].startswith('http://127.0.0.1:8767/performance')]
    assert len(decisions) >= 2 and all(item['guardAllowed'] and item['decision']['type'] == 'socks'
                                     and item['decision']['host'] == '127.0.0.1' and item['decision']['port'] == 1087
                                     for item in decisions), 'Both comparisons must use the existing protected proxy path.'
    assert gecko['checkCount'] == len(gecko['checks']) >= 155 and all(check['pass'] for check in gecko['checks'])
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
        'Actual different official SPA conversation quietly archives its native observation',
        'Quiet conversation archive retains full pending body and original delivery binding',
        'Quiet conversation archive clears stale completion samples and settings busy state',
        'Returning to an archived official conversation does not resurrect its old task',
        'Matching current official conversation retains a new observation',
        'A stale inspected URL cannot archive the current task',
        'A new official conversation still monitors its exact bound user without native submission',
        'An actual login route retains unresolved observation and its original binding',
        'An actual empty homepage hydration shell does not archive a bound conversation',
        'An interactive homepage still displaying a busy operation retains its bound observation',
        'An actual interactive empty official homepage quietly ends the old observation',
        'A genuine same-conversation edited question stays unresolved with its error',
        'Quiet navigation never stops reloads resubmits or changes the browser draft and login',
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
        'Deferred callback race reuses the original encrypted receipt before the new save',
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
            'compactCases': len(chrome['cases']), 'reloadConfirmationChecks': len(reload['checks']),
            'autoCollapse': auto_collapse,
            'currentVisualScreens': len(captures), 'historicalUIRebuilt': False,
            'bridgeResponseBytes': {'baseline': baseline['bridgeResponseBytes'], 'current': current['bridgeResponseBytes']},
            'domReadChars': {'baseline': baseline['domReadChars'], 'current': current['domReadChars']}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_performance_evidence(args.directory, args.source), indent=2))
