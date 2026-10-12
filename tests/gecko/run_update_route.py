#!/usr/bin/env python3
"""Real managed profile 0/7 update routing, lease invalidation, signed APK resume."""
import argparse, base64, hashlib, http.server, json, pathlib, re, subprocess, threading, time, uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'
ETAG = '"route-fixture-v1"'


def verify(report):
    receipt = json.loads((ROOT / 'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text())
    assert report['status'] == 'passed', report.get('error')
    assert report['actualAndroidExecution'] and report['actualManagedCoreExecution'] and report['actualProfileProcesses']
    assert report['productionLeaseEndpoints'] and report['testOnlySingletonFixtures'] and not report['productionProviderTestHooks']
    assert report['publicNetworkTraffic'] is False and report['internalDirectFallbackCalls'] == 0 and report['directFactoryCalls'] == 2
    assert report['cleanupRestoredProfiles']
    assert len(report['checks']) >= 32 and all(c['pass'] for c in report['checks'])
    zero, seven = report['initialProfiles']
    assert [zero['slot'], seven['slot']] == [0, 7]
    assert zero['processPid'] != seven['processPid'] and zero['corePid'] != seven['corePid']
    assert zero['proxyPort'] != seven['proxyPort'] and zero['verified'] and seven['verified']
    for row in [zero, seven]:
        assert row['corePid'] > 1 and row['servicePid'] > 1
        assert row['coreSha256'] == receipt['binaries']['x86_64']['sha256']
        assert row['entryDenied'] == row['fixedExitDenied'] == 0
    initial, restored = report['initialLease'], report['restoredLease']
    assert initial['slot'] == restored['slot'] == 7 and initial['sourceType'] == restored['sourceType'] == 'internal'
    assert initial['environmentGeneration'] == restored['environmentGeneration']
    assert re.fullmatch('[a-f0-9]{64}', initial['lease']) and re.fullmatch('[a-f0-9]{64}', restored['lease'])
    assert initial['lease'] != restored['lease'] and initial['proxyPort'] == seven['proxyPort']
    restarted = report['restoredProfile7']
    assert restarted['corePid'] != seven['corePid'] and restored['proxyPort'] == restarted['proxyPort']
    assert report['profileAfterNetworkInvalidation']['corePid'] == seven['corePid']
    assert report['profileAfterNetworkInvalidation']['ready'] and report['injectedDefaultNetwork']['injectedEvent']
    assert report['injectedDefaultNetwork']['afterRevision'] > report['injectedDefaultNetwork']['beforeRevision']
    assert report['partialBeforeInvalidation'] == report['partialAfterInvalidation'] == report['partialWhileDefaultIsDirect']
    partial = report['partialBeforeInvalidation']
    assert partial['bytes'] == 262144 and partial['etag'] == ETAG and re.fullmatch('[a-f0-9]{64}', partial['sha256'])
    modes = {row['name']: row for row in report['invalidations']}
    assert set(modes) == {'default-network-revision', 'core-lifetime', 'wrong-slot', 'wrong-environment-generation', 'deleted-environment', 'recreated-generation', 'direct-source-change', 'direct-deleted-generation'}
    assert len(modes) == len(report['invalidations']) and all(row['rejected'] for row in modes.values())
    active_zero, active_seven = report['activeProfiles']
    assert active_zero['entryCircuits'] == zero['entryCircuits'] and active_zero['fixedExitCircuits'] == zero['fixedExitCircuits']
    assert active_seven['entryCircuits'] > seven['entryCircuits'] and active_seven['fixedExitCircuits'] > seven['fixedExitCircuits']
    assert active_seven['entryAuthenticated'] == active_seven['entryCircuits'] and active_seven['fixedExitAuthenticated'] == active_seven['fixedExitCircuits']
    assert active_seven['corePid'] == seven['corePid'] and active_seven['coreGeneration'] == seven['coreGeneration'] and active_seven['routeSerial'] == seven['routeSerial'] and active_seven['verified']
    assert len(report['opens']) == 3 and report['opens'][0]['officialUrl'].endswith('/latest.json')
    for row in report['opens']:
        assert row['type'] == 'HTTP' and row['host'] == '127.0.0.1' and row['port'] in {initial['proxyPort'], restored['proxyPort']}
    archive = report['verifiedArchive']
    assert archive['bytes'] > 1024 * 1024 and archive['sameInstalledSigner'] and not archive['installed']
    wire = report['serverTrace']
    requests = [row for row in wire if row['path'] == '/update-route.apk']
    assert len(requests) == 2 and requests[0]['connection'] != requests[1]['connection']
    first, resumed = requests
    assert first['status'] == 200 and first['range'] == '' and first['bytesSent'] == 262144
    assert first['peerClosed'] and first['serverClosedBeforePeerEof'] is False and first['nextByte'] == -1
    assert first['stalledAfterBytes'] == 262144 and first['declaredBytes'] == archive['bytes']
    assert resumed['status'] == 206 and resumed['range'] == 'bytes=262144-' and resumed['ifRange'] == ETAG
    assert resumed['contentRange'] == f"bytes 262144-{archive['bytes'] - 1}/{archive['bytes']}"
    assert resumed['bytesSent'] == archive['bytes'] - 262144 and resumed['completed']
    assert all(not row['personalCredentialsSeen'] for row in wire)
    assert all(row['etag'] == ETAG for row in requests)
    assert report['directScope']['sourceType'] == 'direct' and report['directScope']['slot'] == 0
    assert report['directPartialBeforeSourceChange'] == report['directPartialAfterSourceChange']
    assert report['directPartialBeforeSourceChange']['bytes'] == 262144
    assert report['directPartialBeforeGenerationChange'] == report['directPartialAfterGenerationChange']
    assert report['directPartialBeforeGenerationChange']['bytes'] == 327680
    direct_wire = [r for r in wire if r['path'] == '/direct-route.apk']
    assert len(direct_wire) == 2
    for row, status, count in [(direct_wire[0], 200, 262144), (direct_wire[1], 206, 65536)]:
        assert row['status'] == status and row['bytesSent'] == count and row['peerClosed'] and row['nextByte'] == -1
        assert not row['serverClosedBeforePeerEof'] and not row['completed']
    assert direct_wire[0]['range'] == '' and direct_wire[1]['range'] == 'bytes=262144-' and direct_wire[1]['ifRange'] == ETAG
    assert report['sourceCommit'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--timeout', type=int, default=160)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    payload = (OUT / 'update-fixture.apk').read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    code = int(re.search(r'versionCode ([0-9]+)', (ROOT / 'app/build.gradle').read_text()).group(1)) + 1
    metadata = dict(schema=1, package='local.pocketchat', version='99.0.0', versionCode=code,
                    bytes=len(payload), sha256=digest,
                    signerSha256=re.search(r'SIGNER="([a-f0-9]+)"', (ROOT / 'app/src/main/java/local/pocketchat/AppUpdatePolicy.java').read_text()).group(1),
                    downloadUrl='https://github.com/Ararataki-number-one/yuanying-chat/releases/download/v99.0.0-gecko/PocketChat-99.0.0-gecko-arm64.apk',
                    abi='arm64-v8a', minSdk=26, notes='Synthetic controlled route fixture; never installed.')
    wire, lock = [], threading.Lock()
    connections = [0]
    for name in ['update-route-results.json', 'update-route-log.txt', 'update-route-failure-log.txt', 'update-route-host-wire.json']:
        (OUT / name).unlink(missing_ok=True)

    class Fixture(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *args): pass
        def do_GET(self):
            with lock:
                connections[0] += 1
                row = dict(path=self.path, connection=connections[0], range=self.headers.get('Range', ''),
                           ifRange=self.headers.get('If-Range', ''), personalCredentialsSeen=bool(self.headers.get('Cookie') or self.headers.get('Authorization')),
                           bytesSent=0, startedAt=time.monotonic(), completed=False, etag=ETAG)
                wire.append(row)
            if self.path == '/feed':
                body = json.dumps(metadata).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.send_header('Connection', 'close'); self.end_headers()
                self.wfile.write(body); self.wfile.flush(); row.update(bytesSent=len(body), completed=True); return
            if self.path not in ['/update-route.apk', '/direct-route.apk']:
                self.send_error(404); return
            offset = 0
            if row['range']:
                match = re.fullmatch(r'bytes=(\d+)-', row['range'])
                if not match: self.send_error(400); return
                offset = int(match.group(1))
            row.update(status=206 if offset else 200, declaredBytes=len(payload))
            self.send_response(row['status']); self.send_header('Content-Length', str(len(payload) - offset)); self.send_header('ETag', ETAG); self.send_header('Connection', 'close')
            if offset:
                row['contentRange'] = f'bytes {offset}-{len(payload)-1}/{len(payload)}'
                self.send_header('Content-Range', row['contentRange'])
            self.end_headers()
            try:
                if not offset or self.path == '/direct-route.apk':
                    first = payload[offset:offset+(65536 if offset else 262144)]
                    self.wfile.write(first); self.wfile.flush(); row.update(bytesSent=len(first), stalledAfterBytes=len(first))
                    self.connection.settimeout(12)
                    next_byte = self.connection.recv(1)
                    row.update(nextByte=-1 if not next_byte else next_byte[0], peerClosed=not next_byte,
                               serverClosedBeforePeerEof=False, peerEofAt=time.monotonic())
                else:
                    for pos in range(offset, len(payload), 65536):
                        block = payload[pos:pos+65536]; self.wfile.write(block); self.wfile.flush(); row['bytesSent'] += len(block)
                    row['completed'] = True
            except Exception as error:
                row['error'] = type(error).__name__
            finally:
                row['endedAt'] = time.monotonic()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8767), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    def adb(*parts, check=True):
        return subprocess.run([args.adb, '-s', args.serial, *parts], text=True, capture_output=True, check=check, timeout=30).stdout
    fixture_token = uuid.uuid4().hex
    try:
        adb('shell', 'am', 'force-stop', 'local.pocketchat.test'); adb('shell', 'pm', 'clear', 'local.pocketchat.test'); adb('logcat', '-c'); adb('reverse', 'tcp:8767', 'tcp:8767')
        adb('shell', 'am', 'start', '-W', '-n', 'local.pocketchat.test/local.pocketchat.AppUpdateRouteIntegrationActivity', '--es', 'fixtureToken', fixture_token, '--es', 'updateHash', digest, '--el', 'updateBytes', str(len(payload)))
        until = time.monotonic() + args.timeout
        while time.monotonic() < until:
            raw = adb('logcat', '-d', '-s', 'PocketUpdateRoute:I', 'AndroidRuntime:E', '*:S')
            parts, total, complete = {}, None, False
            for line in raw.splitlines():
                if 'PocketUpdateRoute' not in line or '{' not in line: continue
                try: value = json.loads(line[line.index('{'):])
                except json.JSONDecodeError: continue
                if value.get('token') != fixture_token: continue
                if value.get('kind') == 'reportPart': parts[value['index']] = value['data']; total = value['total']
                elif value.get('kind') == 'complete': complete = True
            if complete and total is not None and len(parts) == total:
                report = json.loads(base64.b64decode(''.join(parts[i] for i in range(total))))
                report.update(sourceCommit=source, androidSdk=35, serverTrace=list(wire), fixtureApkSha256=digest,
                              diagnosticOnly=True, releaseAcceptance=False)
                (OUT / 'update-route-results.json').write_text(json.dumps(report, indent=2)+'\n')
                (OUT / 'update-route-log.txt').write_text(raw)
                (OUT / 'update-route-host-wire.json').write_text(json.dumps(dict(sourceCommit=source, actualHttpExecution=True, requests=wire), indent=2)+'\n')
                verify(report)
                print(json.dumps(dict(status=report['status'], sourceCommit=source, checks=len(report['checks']), actualProfileProcesses=True, resumedRange='bytes=262144-', directFactoryCalls=report['directFactoryCalls']), indent=2), flush=True)
                return
            if 'FATAL EXCEPTION' in raw: raise AssertionError(raw)
            time.sleep(1)
        raise TimeoutError('No complete actual Android update-route report')
    except Exception:
        (OUT / 'update-route-failure-log.txt').write_text(adb('logcat', '-d', check=False))
        (OUT / 'update-route-host-wire.json').write_text(json.dumps(dict(sourceCommit=source, actualHttpExecution=True, requests=wire), indent=2)+'\n')
        raise
    finally:
        server.shutdown(); server.server_close(); adb('reverse', '--remove', 'tcp:8767', check=False)


if __name__ == '__main__': main()
