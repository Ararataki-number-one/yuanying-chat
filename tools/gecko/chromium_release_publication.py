#!/usr/bin/env python3
"""Carry same-bundle Chromium bytes through the original Gecko release gate."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from urllib.request import urlopen
from zipfile import ZipFile

from caret_build_identity import digest, strict_json
from release_channel_contract import CHUNK_BYTES, MAX_MANIFEST_BYTES, MAX_TAIL_BYTES, release_tag, require
from stage_chromium_module import check_payload, manifest_role, read_set, verify_detached

REPOSITORY = 'Ararataki-number-one/yuanying-chat'
PUBLISH_BRANCH = 'refs/heads/apk/gecko-release-20261003'
ABI = 'arm64-v8a'
RUNTIME_REPORT = 'chromium-ondemand-device-results.json'
SIGNED_TAIL = 'chromium-signed-tail.bin'
APK_SET = {'base-master.apk': '', 'chromium-master.apk': 'chromium'}
RUNTIME_CHECKS = ('initWithoutChromium', 'appendInstall', 'baseDataRetained',
                  'nativeRenderer', 'systemWebViewUnavailable', 'offlineRouteRejectedBeforeNativeInitialization',
                  'actualLocalRouteLoss')
PROXY_MODES = ('protectedHttpProxy', 'protectedHttpsProxy', 'protectedSocksProxy')
INTEGRATION_SCOPE = {'vpn': 'integration-clean-source-android-tun',
                     'internal': 'integration-clean-source-android-internal'}
INTEGRATION_CHECKS = {
    'vpn': ('vpnRouteVerified', 'vpnTunPacketObserved', 'vpnDescriptorClosed',
            'vpnBrowserRetired', 'vpnLateNavigationBlocked'),
    'internal': ('internalRouteVerified', 'internalMockPageRendered', 'internalCoreRetired',
                 'internalHeldSocketClosed', 'internalBrowserRetired', 'internalLateNavigationBlocked'),
}
INTEGRATION_COUNTERS = {'vpn': ('vpnGeneration', 'vpnDestinationPort'),
                        'internal': ('internalAuthorizedCircuits', 'internalHeldConnectionsClosed')}
SHA = re.compile(r'[0-9a-f]{64}')
APK_SIGNATURE = re.compile(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))', re.I)


def required(version_code):
    return type(version_code) is int and version_code >= 115


def github_identity(key):
    return os.environ[key]


def git(*parts):
    return subprocess.check_output(['git', *parts], text=True).strip()


def identity(path):
    require(path.is_file() and not path.is_symlink(), f'Missing regular release file: {path.name}')
    return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path)}


def read_json(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_MANIFEST_BYTES,
            f'Missing or oversized JSON release file: {path.name}')
    return strict_json(path.read_bytes())


def apk_contents(path):
    """Bind every APK member and its compression independently of APK signing blocks."""
    result = hashlib.sha256()
    with ZipFile(path) as package:
        entries = package.infolist()
        require(len(entries) == len({entry.filename for entry in entries}), 'Duplicate APK members')
        for entry in sorted(entries, key=lambda item: item.filename):
            if APK_SIGNATURE.fullmatch(entry.filename):
                continue
            with package.open(entry) as stream:
                child = hashlib.file_digest(stream, 'sha256').hexdigest()
            row = [entry.filename, entry.file_size, entry.compress_type, child]
            result.update((json.dumps(row, ensure_ascii=True, separators=(',', ':')) + '\n').encode('ascii'))
    return result.hexdigest()


def assert_unsigned(apksigner, path):
    verified = subprocess.run([str(apksigner), 'verify', str(path)], capture_output=True, text=True)
    require(verified.returncode != 0 and 'Missing META-INF/MANIFEST.MF' in verified.stderr,
            f'Unsigned build contains a signing identity or has an unexpected verification failure: {path.name}')
    with ZipFile(path) as package:
        require(not any(APK_SIGNATURE.fullmatch(name) for name in package.namelist()), 'Unsigned APK contains a signature entry')


def record(args):
    source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    require(source == github_identity('GITHUB_SHA') and not git('status', '--porcelain'), 'Build requires exact clean source')
    require(github_identity('GITHUB_REPOSITORY') == REPOSITORY, 'Unexpected CI repository')
    settings = Path('app/build.gradle').read_text()
    version = re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'", settings)[1]
    version_code = int(re.search(r'versionCode ([0-9]+)', settings)[1])
    require(required(version_code) and set(path.name for path in args.unsigned.glob('*.apk')) == set(APK_SET),
            'Release requires exactly one base and one same-bundle arm64 Chromium feature APK')
    outputs = {}
    for filename, role in APK_SET.items():
        path = args.unsigned / filename
        actual, requires_splits, _ = manifest_role(args.tools / 'aapt2', path, version, version_code, ABI)
        require(actual == role and not requires_splits, f'Unexpected selected split role: {filename}')
        assert_unsigned(args.tools / 'apksigner', path)
        require(check_payload(path, role, ABI) is bool(role), f'Unexpected native Chromium placement: {filename}')
        outputs[filename] = dict(identity(path), contentsSha256=apk_contents(path))
    result = dict(schema=1, sourceCommit=source, sourceTree=tree, runId=github_identity('GITHUB_RUN_ID'),
                  runAttempt=github_identity('GITHUB_RUN_ATTEMPT'), abi=ABI, minSdk=26, version=version,
                  versionCode=version_code, bundle=identity(args.bundle), apks=outputs)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


def validate_build(build, release, build_commit):
    require(re.fullmatch(r'[0-9a-f]{40}', build_commit), 'Missing immutable Chromium CI artifact commit')
    parent = git('rev-parse', build_commit + '^1')
    require(parent == release['sourceCommit'], 'Chromium build transport is not parented to the tested source')
    evidence_object = build_commit + ':manifest.json'
    require(0 < int(git('cat-file', '-s', evidence_object)) <= MAX_MANIFEST_BYTES, 'Oversized immutable build manifest')
    immutable = strict_json(git('show', evidence_object))
    require(immutable.get('chromiumBuild') == build, 'Chromium bundle proof differs from the exact CI artifact')
    expected = {'schema': 1, 'sourceCommit': release['sourceCommit'],
                'sourceTree': git('rev-parse', release['sourceCommit'] + '^{tree}'),
                'runId': release['buildRunId'], 'runAttempt': release['buildRunAttempt'], 'minSdk': 26,
                'abi': ABI, 'version': release['version'], 'versionCode': release['versionCode']}
    require(all(type(build.get(k)) is type(v) and build[k] == v for k, v in expected.items()),
            'Chromium build identity differs from original acceptance')
    require(set(build['apks']) == set(APK_SET) and SHA.fullmatch(build['bundle']['sha256'])
            and build['apks']['base-master.apk']['sha256'] == release['unsignedSha256'],
            'Chromium bundle does not contain the accepted unsigned Gecko base')
    for filename, item in build['apks'].items():
        require(item['file'] == filename and SHA.fullmatch(item['sha256']) and SHA.fullmatch(item['contentsSha256'])
                and type(item['bytes']) is int and 0 < item['bytes'] <= 512 * 1024 * 1024,
                'Unexpected unsigned APK identity')
    return validate_feature_chunks(build, immutable['chromiumFeatureChunks'])


def runtime_summary(path, release, build):
    runtime = read_json(path)
    expected = {'status': 'passed', 'sourceCommit': build['sourceCommit'], 'sourceTree': build['sourceTree'],
                'versionCode': release['versionCode'], 'package': 'local.pocketchat', 'actualAndroidExecution': True,
                'sourceDirty': False, 'actualOnlineSignedMetadataDownload': False,
                'actualSystemInstallerConsent': False,
                'testScope': 'combined-debug-candidate-local-install-and-renderer',
                **dict.fromkeys(RUNTIME_CHECKS, True)}
    require(all(type(runtime.get(k)) is type(v) and runtime[k] == v for k, v in expected.items()),
            'No passing source-matched Android evidence for installing and running native Chromium')
    require(runtime.get('abi') == 'x86_64' and type(runtime.get('sdk')) is int and runtime['sdk'] == 33,
            'Complete Chromium route acceptance requires the Android 13 x86_64 emulator')
    apk_digests = {name: runtime.get(name) for name in ('baseSha256', 'featureSha256', 'rendererTranscriptSha256')}
    require(all(type(value) is str and SHA.fullmatch(value) for value in apk_digests.values()),
            'Android runtime evidence must identify the installed base and feature APK bytes')
    require(type(runtime.get('nativeRendererCount')) is int and runtime['nativeRendererCount'] > 0
            and runtime.get('chromiumVersion') == '156.0.8078.96', 'Missing actual approved Chromium rendering')
    proxy_reports = normalize_proxy_modes(runtime)
    integration = normalize_integration_modes(runtime.get('integrationRoutes'), runtime)
    return dict(expected, abi=runtime['abi'], sdk=runtime['sdk'], nativeRendererCount=runtime['nativeRendererCount'],
                chromiumVersion=runtime['chromiumVersion'], integrationRoutes=integration,
                tlsFixtureVerified=True, originTlsVerified=False, **proxy_reports, **apk_digests)


def normalize_proxy_modes(report):
    require(report.get('tlsFixtureVerified') is True and report.get('originTlsVerified') is False,
            'Required HTTPS evidence is for the controlled signed proxy hop')
    result = {}
    for name in PROXY_MODES:
        item = report.get(name)
        require(type(item) is dict, 'Missing controlled proxy proof: ' + name)
        positive = ('handshakes', 'pages', 'tlsHandshakes') if name == 'protectedHttpsProxy' else ('handshakes', 'pages')
        require(all(type(item.get(k)) is int and item[k] > 0 for k in positive)
                and type(item.get('heldConnectionsClosed')) is int and item['heldConnectionsClosed'] == 1
                and type(item.get('privateTrapAccepted')) is int and item['privateTrapAccepted'] == 0,
                'Controlled proxy route lacks rendered, revoked, and no-fallback evidence: ' + name)
        result[name] = {key: item[key] for key in (*positive, 'heldConnectionsClosed', 'privateTrapAccepted')}
    return result


def normalize_integration_modes(reports, debug):
    require(type(reports) is dict and set(reports) == set(INTEGRATION_SCOPE), 'Missing actual VPN or built-in route evidence')
    result = {}
    identity = {k: debug[k] for k in ('sourceCommit', 'sourceTree', 'versionCode', 'sdk', 'abi')}
    for route, report in reports.items():
        expected = dict(identity, package='local.pocketchat.test', scope=INTEGRATION_SCOPE[route],
                        androidExecution=True, noSystemWebViewProvider=True, **dict.fromkeys(INTEGRATION_CHECKS[route], True))
        require(all(type(report.get(key)) is type(value) and report[key] == value for key, value in expected.items()),
                'Integration route did not prove exact source, selection and revocation: ' + route)
        digests = ['baseSha256', 'featureSha256', 'transcriptSha256']
        if route == 'internal':
            digests.append('internalCoreSha256')
        require(all(type(report.get(key)) is str and SHA.fullmatch(report[key]) for key in digests),
                'Integration route must identify exact app, engine and proof bytes')
        fields = INTEGRATION_COUNTERS[route]
        require(all(type(report.get(key)) is int and report[key] > 0 for key in fields),
                'Integration route lacks wire activity or route removal')
        result[route] = dict(expected, **{key: report[key] for key in (*fields, *digests)})
        if route == 'vpn':
            require(report.get('androidVpnConsentVerified') is False and 1 <= report['vpnDestinationPort'] <= 65535,
                    'Controlled TUN verification cannot claim Android VPN consent or an invalid destination port')
            result[route]['androidVpnConsentVerified'] = False
    require(all(result['vpn'][key] == result['internal'][key] for key in ('baseSha256', 'featureSha256')),
            'VPN and built-in trials did not execute the same exact integration APK pair')
    return result


def parse_route_transcript(path, route, debug, args):
    raw = path.read_bytes()
    require(0 < len(raw) <= MAX_MANIFEST_BYTES, 'Missing or oversized Android route transcript')
    output = raw.decode('utf-8')
    require(re.findall(r'(?m)^INSTRUMENTATION_CODE:\s*(-?[0-9]+)\s*$', output) == ['-1'],
            'Android route instrumentation did not finish successfully: ' + route)
    values = {}
    for line in output.splitlines():
        if line.startswith('INSTRUMENTATION_RESULT: '):
            key, separator, value = line.removeprefix('INSTRUMENTATION_RESULT: ').partition('=')
            if separator and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', key):
                require(key not in values, 'Duplicate Android route field: ' + key)
                values[key] = value
    expected = {k: str(debug[k]) for k in ('sourceCommit', 'sourceTree', 'versionCode', 'sdk', 'abi')}
    expected.update(scope=INTEGRATION_SCOPE[route], package='local.pocketchat.test', runNonce=args.nonce,
                    baseSha256=args.base_sha, featureSha256=args.feature_sha)
    booleans = ('androidExecution', 'noSystemWebViewProvider', *INTEGRATION_CHECKS[route])
    require(all(values.get(k) == v for k, v in expected.items()) and all(values.get(k) == 'true' for k in booleans),
            'Android route transcript does not bind the exact installed APKs, source, nonce and results: ' + route)
    fields = INTEGRATION_COUNTERS[route]
    require(all(re.fullmatch(r'[1-9][0-9]*', values.get(key, '')) for key in fields), 'Missing positive Android wire count: ' + route)
    result = {k: debug[k] for k in ('sourceCommit', 'sourceTree', 'versionCode', 'sdk', 'abi')}
    result.update(scope=values['scope'], package=values['package'], baseSha256=args.base_sha,
                  featureSha256=args.feature_sha, transcriptSha256=hashlib.sha256(raw).hexdigest(),
                  **dict.fromkeys(booleans, True), **{key: int(values[key]) for key in fields})
    if route == 'vpn':
        require(values.get('androidVpnConsentVerified') == 'false', 'Synthetic TUN test may not assert user consent')
        result['androidVpnConsentVerified'] = False
    else:
        require(values.get('internalCoreSha256') == args.core_sha, 'Built-in Chromium used a different installed core')
        result['internalCoreSha256'] = args.core_sha
    return result


def join_routes(args):
    debug = read_json(args.debug)
    require(debug.get('runNonce') == args.nonce and re.fullmatch(r'[0-9a-f]{32}', args.nonce)
            and all(SHA.fullmatch(value) for value in (args.base_sha, args.feature_sha, args.core_sha)),
            'Incomplete Chrome debug/Integration artifact identity')
    require(git('rev-parse', 'HEAD') == debug.get('sourceCommit')
            and git('rev-parse', 'HEAD^{tree}') == debug.get('sourceTree') and not git('status', '--porcelain'),
            'Chrome debug acceptance does not match the exact clean repository')
    require(not args.output.exists(), 'Route acceptance output already exists')
    report = dict(debug, integrationRoutes={route: parse_route_transcript(getattr(args, route), route, debug, args)
                         for route in INTEGRATION_SCOPE})
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    try:
        runtime_summary(args.output, report, report)
    except Exception:
        args.output.unlink(missing_ok=True)
        raise


def public_names(release):
    stem = f"PocketChat-{release['version']}-chromium-{ABI}"
    return stem + '--chromium.apk', stem + '.json', stem + '.sig'


def verify_signed_files(release, build, signed_base, directory, android_tools):
    apk_name, manifest_name, signature_name = public_names(release)
    module = directory / apk_name
    require(identity(signed_base)['sha256'] == release['sha256'], 'Wrong signed Gecko base APK')
    for source, apk in (('base-master.apk', signed_base), ('chromium-master.apk', module)):
        require(apk_contents(apk) == build['apks'][source]['contentsSha256'], f'{source} differs from unsigned CI package')
    settings = SimpleNamespace(aapt2=android_tools / 'aapt2', apksigner=android_tools / 'apksigner',
                               version=release['version'], version_code=release['versionCode'],
                               abi=ABI, candidate=release.get('candidateNumber'))
    with tempfile.TemporaryDirectory(prefix='chromium-original-pair-') as folder:
        root = Path(folder)
        # The verifying pair contains only exact release bytes and no private key.
        shutil.copyfile(signed_base, root / signed_base.name)
        shutil.copyfile(module, root / module.name)
        payload, roles, cert = read_set(settings, root, signed_base)
        require(set(roles) == {'', 'chromium'}, 'This release requires a single same-ABI Chromium feature APK')
        require((directory / manifest_name).read_bytes() == payload, 'Detached Chromium manifest does not bind these exact APKs')
        verify_detached('openssl', root, payload, directory / signature_name, cert)
    return [identity(directory / name) for name in public_names(release)]


def feature_chunk_prefix(build):
    return f"PocketChat-{build['version']}-chromium-{ABI}-unsigned.apk.part"


def write_feature_chunks(build, feature, stage):
    expected = {k: v for k, v in build['apks']['chromium-master.apk'].items() if k != 'contentsSha256'}
    require(identity(feature) == expected, 'Unsigned Chromium changed before immutable CI transport')
    parts = []
    with feature.open('rb') as apk:
        while raw := apk.read(CHUNK_BYTES):
            path = stage / f'{feature_chunk_prefix(build)}{len(parts):02d}'
            path.write_bytes(raw)
            parts.append(identity(path))
    return validate_feature_chunks(build, parts)


def validate_feature_chunks(build, parts):
    require(type(parts) is list and 1 <= len(parts) <= 9, 'Invalid unsigned Chromium part count')
    for index, item in enumerate(parts):
        require(type(item) is dict and set(item) == {'file', 'bytes', 'sha256'}
                and item['file'] == f'{feature_chunk_prefix(build)}{index:02d}'
                and type(item['bytes']) is int and 0 < item['bytes'] <= CHUNK_BYTES
                and (index == len(parts) - 1 or item['bytes'] == CHUNK_BYTES)
                and type(item['sha256']) is str and SHA.fullmatch(item['sha256']),
                'Invalid unsigned Chromium part identity')
    require(sum(part['bytes'] for part in parts) == build['apks']['chromium-master.apk']['bytes'],
            'Unsigned Chromium part sizes differ from the exact build')
    return parts


def unsigned_feature_blocks(build, commit, parts):
    full_hash = hashlib.sha256()
    for item in parts:
        object_name = commit + ':' + item['file']
        require(int(git('cat-file', '-s', object_name)) == item['bytes'], 'Immutable Chromium part length differs')
        raw = subprocess.check_output(['git', 'cat-file', 'blob', object_name])
        require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'],
                'Immutable Chromium part bytes differ')
        full_hash.update(raw)
        for offset in range(0, len(raw), 1024 * 1024):
            yield raw[offset:offset + 1024 * 1024]
    require(full_hash.hexdigest() == build['apks']['chromium-master.apk']['sha256'], 'Unsigned Chromium full hash differs')


def signature_tail(signed, stage, build, build_commit, parts):
    prefix = 0
    equal = True
    with signed.open('rb') as apk:
        for raw in unsigned_feature_blocks(build, build_commit, parts):
            if equal:
                other = apk.read(len(raw))
                if raw == other:
                    prefix += len(raw)
                else:
                    prefix += next((i for i, pair in enumerate(zip(raw, other)) if pair[0] != pair[1]), len(other))
                    equal = False
        require(prefix > 0 and 0 < signed.stat().st_size - prefix <= MAX_TAIL_BYTES,
                'Original signing changed more than the bounded Chromium signature tail')
        apk.seek(prefix)
        path = stage / SIGNED_TAIL
        path.write_bytes(apk.read(MAX_TAIL_BYTES + 1))
    return {'kind': 'unsigned-prefix-tail-v1', 'prefixBytes': prefix, 'tail': identity(path)}


def prepare_delivery(release, build, build_commit, runtime, signed_base, directory, stage, android_tools):
    parts = validate_build(build, release, build_commit)
    summary = runtime_summary(runtime, release, build)
    files = verify_signed_files(release, build, signed_base, directory, android_tools)
    module, metadata, signature = public_names(release)
    for name in (metadata, signature):
        shutil.copyfile(directory / name, stage / name)
    transport = signature_tail(directory / module, stage, build, build_commit, parts)
    return dict(schema=1, buildCommit=build_commit, build=build, runtime=summary, files=files, apkTransport=transport)


def restore_feature(delivery, module, build, build_commit, parts):
    transport = delivery['apkTransport']
    require(type(transport) is dict and set(transport) == {'kind', 'prefixBytes', 'tail'}
            and transport['kind'] == 'unsigned-prefix-tail-v1', 'Invalid Chromium APK transport')
    prefix = transport['prefixBytes']
    expected = delivery['files'][0]
    path = module.parent / SIGNED_TAIL
    require(type(prefix) is int and 0 < prefix <= build['apks']['chromium-master.apk']['bytes']
            and 0 < transport['tail']['bytes'] <= MAX_TAIL_BYTES and identity(path) == transport['tail']
            and expected['file'] == module.name and expected['bytes'] == prefix + transport['tail']['bytes'],
            'Chromium signed tail or exact APK identity differs')
    tail = path.read_bytes()
    require(len(tail) == transport['tail']['bytes'] and hashlib.sha256(tail).hexdigest() == transport['tail']['sha256'],
            'Chromium signature tail changed during reconstruction')
    require(not module.exists(), 'Chromium reconstruction target already exists')
    with tempfile.TemporaryDirectory(prefix='.chromium-transport-', dir=module.parent) as folder:
        staged = Path(folder) / module.name
        remaining = prefix
        with staged.open('xb') as output:
            for raw in unsigned_feature_blocks(build, build_commit, parts):
                take = min(remaining, len(raw))
                output.write(raw[:take])
                remaining -= take
            require(remaining == 0, 'Chromium signed prefix incomplete')
            output.write(tail)
        require(identity(staged) == expected, 'Recreated Chromium APK does not match the original-signed bytes')
        staged.rename(module)


def verify_hosted_acceptance(release, authenticate=True):
    run_id, attempt = release['buildRunId'], release['buildRunAttempt']
    require(all(type(value) is str and re.fullmatch(r'[1-9][0-9]{0,15}', value)
                for value in (run_id, attempt)), 'Invalid hosted acceptance run identity')
    url = f'repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}'
    if authenticate:
        result = strict_json(subprocess.check_output(['gh', 'api', url]))
    else:
        with urlopen('https://api.github.com/' + url, timeout=20) as response:
            result = strict_json(response.read(MAX_MANIFEST_BYTES + 1))
    require(result['head_sha'] == release['sourceCommit'] and result['status'] == 'completed'
            and result['conclusion'] == 'success' and result['run_attempt'] == int(attempt)
            and result['path'] == '.github/workflows/browser-2_1-acceptance.yml',
            'Exact-source GitHub Android acceptance did not pass')


def restore_verified(release, directory, android_tools):
    require(github_identity('GITHUB_REPOSITORY') == REPOSITORY and github_identity('GITHUB_REF') == PUBLISH_BRANCH,
            'Optional Chromium production verification belongs to the exact production repository and release branch')
    verify_hosted_acceptance(release)
    delivery = release['chromiumDelivery']
    commit = delivery['buildCommit']
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'Invalid immutable Chromium CI artifact commit')
    subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', '--filter=blob:none', 'origin', commit], check=True)
    require(git('rev-parse', 'FETCH_HEAD^{commit}') == commit, 'Fetched another Chromium artifact commit')
    parts = validate_build(delivery['build'], release, commit)
    runtime = directory / RUNTIME_REPORT
    require(runtime_summary(runtime, release, delivery['build']) == delivery['runtime'], 'Runtime proof differs from staged result')
    module = directory / public_names(release)[0]
    restore_feature(delivery, module, delivery['build'], commit, parts)
    require(verify_signed_files(release, delivery['build'], directory / release['filename'], directory, android_tools)
            == delivery['files'], 'Chromium public files differ from staged original-signed APKs')


def download_verified(url, expected):
    sha, size = hashlib.sha256(), 0
    with urlopen(url, timeout=60) as response:
        require(response.status == 200, 'Public Chromium download did not return 200')
        while raw := response.read(1024 * 1024):
            sha.update(raw)
            size += len(raw)
            require(size <= expected['bytes'], 'Public Chromium asset exceeded expected length')
    require(size == expected['bytes'] and sha.hexdigest() == expected['sha256'],
            f"Public Chromium bytes differ: {expected['file']}")


def verify_public(release):
    if required(release['versionCode']):
        url = f'https://github.com/{REPOSITORY}/releases/download/{release_tag(release)}/'
        for item in release['chromiumDelivery']['files']:
            download_verified(url + item['file'], item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    builder = subcommands.add_parser('record')
    for name in ('bundle', 'unsigned', 'tools', 'output'):
        builder.add_argument('--' + name, type=Path, required=True)
    joiner = subcommands.add_parser('join-routes')
    for name in ('debug', 'vpn', 'internal', 'output'):
        joiner.add_argument('--' + name, type=Path, required=True)
    for name in ('nonce', 'base-sha', 'feature-sha', 'core-sha'):
        joiner.add_argument('--' + name, required=True)
    args = parser.parse_args()
    return record(args) if args.command == 'record' else join_routes(args)


if __name__ == '__main__':
    main()
