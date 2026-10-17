#!/usr/bin/env python3
"""Require same-source native cancellation and actual Gecko H2 pool evidence."""
import argparse
import json
import pathlib

if __package__:
    from .chain_runtime_contract import verify_native_probe, verify_gecko_pool
else:
    from chain_runtime_contract import verify_native_probe, verify_gecko_pool


def verify_chain_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        report = json.loads((directory / name).read_text())
        assert report['sourceCommit'] == source and report['actualAndroidExecution'], name
        assert not report.get('diagnosticOnly', False), name
        return report

    native = android('native-probe-results.json')
    core = json.loads((directory / 'network-core-build.json').read_text())
    assert core['sourceCommit'] == source, 'native build evidence belongs to another source'
    assert core['schema'] == 1 and set(core['binaries']) == {'arm64-v8a', 'x86_64'}
    preconnect_enabled = core['recipe'].get('fixedExitPreconnect', False)
    assert isinstance(preconnect_enabled, bool)
    manifest_path = directory / 'manifest.json'
    if not manifest_path.is_file():
        manifest_path = directory / 'release-manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        assert manifest['sourceCommit'] == source
        if manifest['versionCode'] >= 47:
            assert preconnect_enabled, 'This release requires the real preauthentication pool build'
    subscriptions_enabled = core['recipe'].get('roleSpecificExitProvider', False)
    assert isinstance(subscriptions_enabled, bool)
    if manifest_path.is_file() and manifest['versionCode'] >= 49:
        assert subscriptions_enabled and core['recipe'].get('nodeFingerprint') is True, 'This release requires independent subscription providers and native node identities'
    assert core['recipe']['version'] == ('v1.19.31-pocket-burst1' if core['recipe'].get('fixedExitBurstCapacity') == 4 else 'v1.19.31-pocket-subscriptions1' if subscriptions_enabled else 'v1.19.31-pocket-preconnect1' if preconnect_enabled else 'v1.19.31-pocket-probe1')
    assert core['recipe']['androidApi'] == 26 and core['recipe']['goModuleFlags'] == 'readonly'
    verify_native_probe(native, core)
    pool = android('gecko-pool-results.json')
    verify_gecko_pool(pool, pool['server'])
    for name, minimum in [('network-pool-host-results.json', 54), ('latency-probe-host-results.json', 70)]:
        report = json.loads((directory / name).read_text())
        assert report['sourceCommit'] == source, name
        assert report['passed'] >= minimum, name
    result = {'actualAndroidExecution': True, 'actualMihomoExecution': True,
            'actualGeckoHttp2Execution': True, 'nativeProbeChecks': len(native['checks']),
            'poolChecks': len(pool['checks']), 'actualNativeCancellationCases': len(native['cancellations']),
            'executedNativeSha256': native['coreSha256'],
            'healthyRecoveryReusesSameHttp2Connection': True,
            'changedRoutePartitionsConnections': True,
            'unknownNetworkAndMissingReceiptBlockRequests': True}
    if preconnect_enabled:
        if __package__:
            from .preconnect_contract import verify_preconnect
        else:
            from preconnect_contract import verify_preconnect
        result['fixedExitPreauthentication'] = verify_preconnect(android('preconnect-results.json'), core)
    if subscriptions_enabled:
        if __package__:
            from .network_sources_contract import verify_network_sources
        else:
            from network_sources_contract import verify_network_sources
        result['independentNetworkSources'] = verify_network_sources(directory, source, core)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_chain_evidence(args.directory, args.source), indent=2))
