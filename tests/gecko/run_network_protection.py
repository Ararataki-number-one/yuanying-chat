#!/usr/bin/env python3
"""One actual-AVD VPN boundary observation; completed never means leak-free."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from profile_invocation_contract import expected_build, verify_installed

PACKAGE = 'local.pocketchat.test'
PHASES = ['warmup', 'full-vpn', 'split-vpn', 'vpn-removed']
ORIGIN = 'https://10.0.2.2:9889'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile_controls(native, server, nonce):
    """Check experiment controls, without turning observed traffic into safety."""
    if server.get('runNonce') != nonce or server.get('dropped') != 0:
        raise ValueError('Wrong observer nonce or missing observer events')
    events = server['events']
    if [row.get('index') for row in events] != list(range(1, len(events) + 1)):
        raise ValueError('Server event sequence is incomplete')
    connections = {row['connection'] for row in events if row['kind'] == 'tls-open'}
    for row in events:
        if row['kind'] in ['http', 'ws-open', 'ws-frame'] and row.get('connection') not in connections:
            raise ValueError('Arrival lacks an independently observed TLS connection')
    rows = {row['phase']: row for row in native['phases']}
    probe_observations = []
    for phase in PHASES:
        probe = rows[phase]['probe']
        for name in ['fetch', 'newWebSocket', 'existingWebSocket', 'dedicatedWorker']:
            value = probe[name]
            if phase == 'warmup' and value.get('ok') is not True:
                raise ValueError('Positive control failed: ' + phase + '/' + name)
            if value.get('ok') is not True:
                probe_observations.append(dict(phase=phase, probe=name,
                    status='no-success-observed-not-a-safety-pass', originalResult=value))
                continue
            if name in ['newWebSocket', 'existingWebSocket']:
                echo = value['echo']
                if not any(e['kind'] == 'ws-frame' and e.get('phase') == phase
                           and e.get('payload') == echo.get('payload') and e.get('connection') == echo.get('connection')
                           for e in events):
                    raise ValueError('Page WSS echo has no matching original server frame')
            else:
                result = value['value']
                path = '/probe' if name == 'fetch' else '/worker-probe'
                if not any(e['kind'] == 'http' and e.get('phase') == phase and e.get('path') == path
                           and e.get('connection') == result.get('connection')
                           and e.get('serial') == result.get('serial') for e in events):
                    raise ValueError('Page fetch/Worker response lacks original server arrival')
            probe_observations.append(dict(phase=phase, probe=name,
                status='successful-observation-matched-independent-server'))
    full, split = rows['full-vpn'], rows['split-vpn']
    full_state, split_state = full['after'], split['before']
    vpn = full_state['vpnFixture']
    if (vpn.get('mode') != 'full' or vpn.get('runNonce') != nonce or vpn.get('forwardsTraffic') is not False
            or split_state['vpnFixture'].get('mode') != 'split'
            or split_state['vpnFixture'].get('runNonce') != nonce
            or split_state['vpnFixture'].get('configuredRoutes') != ['198.18.0.0/15']
            or split_state['vpnFixture'].get('forwardsTraffic') is not False):
        raise ValueError('Actual owned non-forwarding full/split VPN fixture identity differs')
    if native.get('routesDropped') != 0 or native.get('eventsDropped') != 0:
        raise ValueError('Native route/phase evidence was truncated')
    route_observations = []
    for phase in PHASES:
        matched = [row for row in native['routes']
                   if parse_qs(urlsplit(row.get('url', '')).query).get('phase') == [phase]]
        direct = [row for row in matched if row.get('route', {}).get('type') == 'direct']
        denied = [row for row in matched if row.get('route', {}).get('type') == 'socks'
                  and row['route'].get('host') == '127.0.0.1' and row['route'].get('port') == 9]
        route_observations.append(dict(phase=phase, admittedDirect=len(direct), denied=len(denied),
            otherOrUnknown=len(matched) - len(direct) - len(denied), originalEntries=matched,
            status='observed-route-decisions' if matched else 'unverified-no-current-route-decision'))
    full_routes = next(row for row in route_observations if row['phase'] == 'full-vpn')
    before_packets = full['before']['vpnFixture'].get('targetIpv4Packets', 0)
    after_packets = vpn.get('targetIpv4Packets', 0)
    packet_delta = after_packets - before_packets
    full_control = dict(vpnTransport=full_state.get('vpnTransport'), guardVpnActive=full_state.get('guardVpnActive'),
        actualIpv4DefaultRoute=any(r.get('default') is True and r.get('destination') == '0.0.0.0/0' for r in full_state['routes']),
        targetTunPacketsBefore=before_packets, targetTunPacketsAfter=after_packets, targetTunPacketsDuringPhase=packet_delta,
        status='target-tun-observed' if packet_delta > 0 else
            'app-route-denial-observed-target-transport-unverified' if full_routes['denied'] and not full_routes['admittedDirect'] else
            'unverified-target-transport', safetyAcceptance=False)
    split_socket = split['probe']['existingWebSocket']
    removed_socket = rows['vpn-removed']['probe']['existingWebSocket']
    split_id = split_socket.get('serverConnection')
    live_split = split_socket.get('ok') is True
    if live_split and removed_socket.get('serverConnection') != split_id:
        raise ValueError('Post-STOP WSS ownership changed')
    existing_control = dict(status='live-before-stop-observed' if live_split else 'unverified',
        reason='actual-split-echo-matched-server' if live_split else 'no-live-split-control',
        splitWebSocketServerConnection=split_id, afterStopEchoObserved=removed_socket.get('ok') is True,
        safetyAcceptance=False)
    return dict(warmupPositiveControlsMatchedServer=True, probeObservations=probe_observations,
                routeObservations=route_observations, fullVpnControlObservation=full_control,
                existingConnectionAfterRemoval=existing_control,
                networkProtectionAcceptance=False, safetyVerdict='Not granted; inspect all actual arrivals and paths')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554', choices=['emulator-5554'])
    parser.add_argument('--apk', type=Path, default=ROOT / 'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    args = parser.parse_args()
    out = ROOT / 'work/network-protection-audit/device'
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'runner.json').exists():
        raise ValueError('Archive previous observation before another invocation')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('Exact clean committed source required')
    gradle = (ROOT / 'app/build.gradle').read_text()
    expected = expected_build(args.apk.resolve(), source, tree,
        re.search(r"versionName '([^']+)'", gradle).group(1), int(re.search(r'versionCode (\d+)', gradle).group(1)))
    nonce = uuid.uuid4().hex
    observations = []
    wrapper = dict(schema=1, status='failed', sourceCommit=source, sourceTree=tree, runNonce=nonce,
        buildIdentity=expected, runId=str(__import__('os').environ.get('GITHUB_RUN_ID', '')),
        runAttempt=str(__import__('os').environ.get('GITHUB_RUN_ATTEMPT', '')), origin=ORIGIN,
        fixtureInvocationCount=0, automaticRetryPerformed=False, actualAndroidFixtureAttempted=False,
        networkProtectionAcceptance=False, releaseAcceptance=False, physicalPhoneAcceptance=False,
        publicNetworkTraffic=False, observations=observations,
        unverified=['IPv6 actual path', 'physical Wi-Fi/mobile handoff', 'Shared Worker', 'Service Worker',
                    'public ChatGPT route', 'full application connection initialization'])
    deadline = time.monotonic() + 180

    def adb(*parts, check=True, cleanup=False):
        remaining = deadline - time.monotonic()
        if remaining <= 0 and not cleanup:
            raise TimeoutError('Single180s diagnostic invocation deadline expired')
        command = [args.adb, '-s', args.serial, *parts]
        index = len(observations) + 1
        try:
            result = subprocess.run(command, capture_output=True, timeout=10 if cleanup else min(20, remaining))
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b'', error.stderr or b'', None
        row = dict(index=index, command=command, returnCode=code, cleanupOnly=cleanup,
                   observedAtUnixMs=int(time.time() * 1000), observedAtMonotonicNs=time.monotonic_ns(), streams={})
        for label, raw in [('stdout', stdout), ('stderr', stderr)]:
            path = out / ('adb-%04d-%s.raw' % (index, label))
            path.write_bytes(raw)
            row['streams'][label] = dict(path=path.name, bytes=len(raw), sha256=digest(path))
        observations.append(row)
        if check and code != 0:
            raise RuntimeError('Actual ADB command failed: ' + repr(row))
        return stdout.decode('utf-8', errors='strict')

    process = None
    native = None
    try:
        with tempfile.TemporaryDirectory(prefix='network-protection-tls-') as temporary:
            temp = Path(temporary)
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '1',
                '-subj', '/CN=10.0.2.2', '-addext', 'subjectAltName=IP:10.0.2.2',
                '-keyout', str(temp / 'key.pem'), '-out', str(temp / 'cert.pem')], check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            certificate = subprocess.check_output(['openssl', 'x509', '-in', str(temp / 'cert.pem'), '-outform', 'DER'])
            wrapper['testOnlyCertificateSha256'] = hashlib.sha256(certificate).hexdigest()
            wrapper['testOnlyCertificateScope'] = 'Temporary test origin only; certificate/key never installed into production or uploaded'
            process = subprocess.Popen(['node', str(ROOT / 'tests/gecko/assets/network-protection.cjs'),
                str(temp / 'key.pem'), str(temp / 'cert.pem'), str(out / 'server.json'), nonce,
                str(out / 'server-events.jsonl')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ready, _, _ = select.select([process.stdout], [], [], 10)
            if not ready or json.loads(process.stdout.readline()) != dict(ready=True, port=9889, runNonce=nonce):
                raise ValueError('Independent HTTPS server did not become ready')
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'pm', 'clear', PACKAGE)
            before = adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity')
            verify_installed(json.loads(before), expected)
            wrapper['installedBeforeSha256'] = hashlib.sha256(before.encode()).hexdigest()
            uid = adb('shell', 'cmd', 'package', 'list', 'packages', '-U', PACKAGE)
            values = re.findall(r'^package:' + re.escape(PACKAGE) + r' uid:(\d+)\s*$', uid, re.M)
            if len(values) != 1:
                raise ValueError('Exact integration UID missing')
            wrapper['packageUid'] = int(values[0])
            wrapper['androidSdk'] = int(adb('shell', 'getprop', 'ro.build.version.sdk').strip())
            adb('shell', 'appops', 'set', PACKAGE, 'ACTIVATE_VPN', 'allow')
            wrapper['vpnPermissionAppOpsRaw'] = adb('shell', 'appops', 'get', PACKAGE, 'ACTIVATE_VPN')
            adb('logcat', '-c')
            wrapper['actualAndroidFixtureAttempted'] = True
            wrapper['fixtureInvocationCount'] = 1
            adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/local.pocketchat.NetworkProtectionIntegrationActivity',
                '--es', 'origin', ORIGIN, '--es', 'sourceCommit', source, '--es', 'runNonce', nonce)
            while time.monotonic() < deadline:
                raw = adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/network-protection', check=False)
                if raw.lstrip().startswith('{'):
                    candidate = json.loads(raw)
                    if candidate.get('runNonce') == nonce and candidate.get('status') in ['completed', 'failed']:
                        native = candidate
                        (out / 'native-report.json').write_bytes(raw.encode())
                        break
                time.sleep(.4)
            if native is None:
                raise TimeoutError('No terminal current-invocation native report')
            if native.get('sourceCommit') != source or native.get('sourceTree') != tree:
                raise ValueError('Native report source/tree mismatch')
            verify_installed(native['buildIdentity'], expected)
            if native.get('actualAndroidExecution') is not True or native.get('actualGeckoExecution') is not True:
                raise ValueError('Actual Android and Gecko observations required')
            after = adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity')
            verify_installed(json.loads(after), expected)
            wrapper['installedAfterSha256'] = hashlib.sha256(after.encode()).hexdigest()
            wrapper['nativeReportSha256'] = digest(out / 'native-report.json')
            if native['status'] != 'completed':
                raise ValueError('Native diagnostic did not complete: ' + str(native.get('error', 'unknown')))
            rows = native.get('phases', [])
            if [row.get('phase') for row in rows] != PHASES:
                raise ValueError('Exact ordered4 phases required')
            for row in rows:
                probe = row['probe']
                if probe.get('phase') != row['phase'] or probe.get('runNonce') != nonce or probe.get('done') is not True:
                    raise ValueError('Page phase/nonce/result mismatch')
                if probe.get('noAutomaticReconnect') is not True:
                    raise ValueError('Existing WebSocket must not be automatically replaced')
            # Execution completed is intentionally independent of route safety.
            wrapper.update(status='completed', diagnosticExecutionComplete=True, actualAndroidExecution=True,
                           actualGeckoExecution=native.get('actualGeckoExecution') is True,
                           scope='Actual controlled VPN/CM/Gecko observations; root must assess server/TUN paths, not this completion flag')
            baseline = rows[0]['probe']
            wrapper['warmupAllProbesSucceeded'] = all(baseline.get(name, {}).get('ok') is True
                for name in ['fetch', 'newWebSocket', 'existingWebSocket', 'dedicatedWorker'])
            if not wrapper['warmupAllProbesSucceeded']:
                raise ValueError('All four warmup probes must establish actual positive controls')
            split, removed = rows[2]['probe'], rows[3]['probe']
            if (split.get('explicitPositiveControlReseed') is not True
                    or split['existingWebSocket'].get('socketGeneration') != 2
                    or removed.get('explicitPositiveControlReseed') is not False
                    or removed['existingWebSocket'].get('socketGeneration') != 2):
                raise ValueError('STOP must follow one explicit generation2 WSS attempt, with no later replacement')
    except Exception as error:
        wrapper.update(status='failed', errorType=type(error).__name__, error=str(error))
        raise
    finally:
        # Cleanup has its own bounded command timeout, never another workload
        # attempt. A UID check prevents stopping a replaced/unowned package.
        try:
            wrapper['finalLogcat'] = adb('logcat', '-d', '-s', 'PocketNetworkProtection:I', 'AndroidRuntime:E', '*:S', check=False, cleanup=True)
        except Exception as error:
            wrapper['logcatCaptureError'] = type(error).__name__ + ': ' + str(error)
        try:
            if 'packageUid' in wrapper:
                current = adb('shell', 'cmd', 'package', 'list', 'packages', '-U', PACKAGE, cleanup=True)
                found = re.findall(r'^package:' + re.escape(PACKAGE) + r' uid:(\d+)\s*$', current, re.M)
                if found != [str(wrapper['packageUid'])]:
                    raise ValueError('Cleanup refused: test package UID changed or vanished')
                wrapper['ownedPackageForceStop'] = dict(package=PACKAGE, uid=wrapper['packageUid'],
                    output=adb('shell', 'am', 'force-stop', PACKAGE, cleanup=True), actualCommandRecorded=True)
            else:
                wrapper['ownedPackageCleanup'] = 'Not started: installed test UID was never confirmed'
        except Exception as error:
            wrapper['ownedPackageCleanupError'] = type(error).__name__ + ': ' + str(error)
            if wrapper['actualAndroidFixtureAttempted']:
                wrapper['status'] = 'failed'
        if process is not None:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill(); stdout, stderr = process.communicate(timeout=5)
            (out / 'server.stdout.log').write_text(stdout)
            (out / 'server.stderr.log').write_text(stderr)
            wrapper['serverExitCode'] = process.returncode
            if process.returncode != 0:
                wrapper.update(status='failed', serverProcessError='Independent server exited abnormally')
        server_path = out / 'server.json'
        if server_path.is_file():
            server = json.loads(server_path.read_bytes())
            wrapper['serverSha256'] = digest(server_path)
            wrapper['serverDroppedEvents'] = server.get('dropped')
            wrapper['serverObservations'] = [dict(phase=phase,
                http=[row for row in server['events'] if row.get('phase') == phase and row['kind'] == 'http'],
                webSocketOpens=[row for row in server['events'] if row.get('phase') == phase and row['kind'] == 'ws-open'],
                frames=[row for row in server['events'] if row.get('phase') == phase and row['kind'] == 'ws-frame']) for phase in PHASES]
            wrapper['observedArrivalsAfterVpnRemoval'] = [row for row in server['events']
                if row.get('phase') == 'vpn-removed' and row['kind'] in ['http', 'ws-open', 'ws-frame']]
            wrapper['observedArrivalsDuringSplitVpn'] = [row for row in server['events']
                if row.get('phase') == 'split-vpn' and row['kind'] in ['http', 'ws-open', 'ws-frame']]
            if server.get('runNonce') != nonce or server.get('dropped') != 0:
                wrapper.update(status='failed', serverEvidenceError='Wrong nonce or missing server events')
            if wrapper['status'] == 'completed':
                try:
                    wrapper['controlReconciliation'] = reconcile_controls(native, server, nonce)
                except Exception as error:
                    wrapper.update(status='failed', controlReconciliationError=type(error).__name__ + ': ' + str(error))
        else:
            wrapper.update(status='failed', serverEvidenceError='Original independent server report missing')
        (out / 'runner.json').write_text(json.dumps(wrapper, indent=2) + '\n')
    if wrapper['status'] != 'completed':
        raise ValueError('Diagnostic evidence incomplete; see original runner.json')
    print(json.dumps(dict(status='completed', networkProtectionAcceptance=False, sourceCommit=source,
                         nativeReportSha256=wrapper['nativeReportSha256'], serverSha256=wrapper['serverSha256'])))


if __name__ == '__main__':
    main()
