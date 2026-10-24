#!/usr/bin/env python3
"""One extra sampling pass after all formal baseline samples; never an iteration.

No installation, input gesture, retry, product source change, or formal timed
iteration is performed here. The extra saves have separate diagnostic clocks;
every original trace/event/failure remains in its own folder.
"""
import argparse
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import experience_scenarios as scenarios
import experience_save_trace as tracing
from profile_invocation_contract import expected_build, verify_installed

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.ExperienceBenchmarkActivity'
CONTROL = PACKAGE + '.EXPERIENCE_BENCHMARK'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_expected(build):
    tracing.require(sha(build['apk']) == build['apkSha256'] and Path(build['apk']).stat().st_size == build['apkBytes'], 'selected baseline APK bytes changed')
    return expected_build(Path(build['apk']), build['sourceCommit'], build['sourceTree'], build['version'], build['versionCode'])


def load_benchmark():
    spec = importlib.util.spec_from_file_location('post_baseline_event_reader', ROOT / 'tests/gecko/run_experience_benchmark.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def start_servers(adb):
    # Exact existing loopback document/server inputs, copied without changing the
    # formal runner. A host control checks this block against the original.
    spec = importlib.util.spec_from_file_location('experience_loopback', ROOT / 'engine-probe/tests/run_device.py')
    loopback = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loopback)

    class Document(http.server.BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_GET(self):
            if self.path != '/c/reload-collapse':
                self.send_error(404)
                return
            marker = uuid.uuid4().hex
            history = ''.join('<article data-message-author-role="user" data-message-id="user-%d">Historical question %d</article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="reply-%d"><div class="markdown"><p>%s</p></div></div></section>' % (i, i, i, ('Historical reply %d. ' % i) * 12) for i in range(120))
            body = ('<!doctype html><html data-reload-document="' + marker + '"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font:18px sans-serif;margin:0;padding:12px}p{overflow-wrap:anywhere}#composer{position:fixed;bottom:0;left:0;right:0;padding:8px;background:inherit}textarea{width:90%;height:60px}html{background:#fff;color:#111}@media(prefers-color-scheme:dark){html{background:#101010;color:#eee}}</style><main>' + history + '<article data-message-author-role="user" data-message-id="benchmark-question">Fixed experience workload</article><section data-turn="assistant"><div data-message-author-role="assistant" data-message-id="benchmark-answer"><div class="markdown"><p id="benchmark-reply">' + 'preserved reply line ' * 5000 + '</p><pre><code>const keep = 1;</code></pre></div></div></section></main><form id="composer"><textarea id="prompt-textarea">unsent benchmark draft 中文 code()</textarea><button type="button" data-testid="send-button" aria-label="Send" onclick="document.getElementById(\'send-count\').textContent=Number(document.getElementById(\'send-count\').textContent)+1">Send</button></form><output id="send-count" hidden>0</output><script>document.cookie="session=synthetic-experience; Path=/";</script></html>').encode()
            loopback.TRACE.append({'kind': 'http', 'path': self.path, 'documentMarker': marker, 'bytes': len(body)})
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    servers = [http.server.ThreadingHTTPServer(('127.0.0.1', 8765), Document), loopback.ThreadedSocks(('127.0.0.1', 1080), loopback.Socks)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    for port in (8765, 1080):
        adb('reverse', 'tcp:' + str(port), 'tcp:' + str(port))
    return loopback, servers


def run(args):
    plan = json.loads(args.plan.read_text()); build = plan['inputs']['A']
    tracing.require(plan['mode'] == 'baseline' and plan['scenarioManifest']['name'].startswith('download-history-'), 'only a completed history baseline may request this diagnostic')
    tracing.require(plan['scenarioManifest'] == scenarios.manifest(plan['scenarioManifest']['name']), 'fixed diagnostic scenario differs')
    tracing.require(Path(build['root']).resolve() == ROOT and subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == build['sourceCommit'], 'selected diagnostic source checkout differs')
    expected = source_expected(build)
    observers = {name: sha(ROOT / name) for name in tracing.OBSERVERS}
    tracing.require(observers == {name: plan['protocol'][name] for name in tracing.OBSERVERS}, 'actual diagnostic runner/imported observer differs from the plan')
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema=1, status='in_progress', diagnosticOnly=True, performanceComparisonAllowed=False,
                  sourceCommit=build['sourceCommit'], selectedRole='A',
                  selectedBuild={name: build[name] for name in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'apkSha256', 'apkBytes')},
                  planSha256=sha(args.plan), scenarioManifest=plan['scenarioManifest'], observerFiles=observers,
                  formalIterationsAdded=0, formalActionsAdded=0, timedSaveSamplesAdded=0,
                  additionalRealSaveCalls=None, additionalSaveCountComplete=False, actualAndroidExecution=False,
                  physicalDeviceAcceptance=False, realChatGptAcceptance=False, releaseAcceptance=False,
                  limits=list(tracing.LIMITS))
    nonce, seed_nonce = uuid.uuid4().hex, uuid.uuid4().hex
    report.update(runNonce=nonce, seedNonce=seed_nonce)
    def persist():
        report['rawEvidence'] = [dict(path=str(path.relative_to(args.out)), bytes=path.stat().st_size, sha256=sha(path))
                                 for path in sorted(args.out.rglob('*')) if path.is_file() and path.name != tracing.RESULT_FILE]
        (args.out / tracing.RESULT_FILE).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    def adb(*parts, binary=False, timeout=30):
        if parts and parts[0] == 'shell': parts = ('shell', shlex.join(parts[1:]))
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=not binary,
                                       stderr=subprocess.STDOUT, timeout=timeout)
    def control(command, name):
        return adb('shell', 'am', 'broadcast', '-a', CONTROL, '-p', PACKAGE,
                   '--es', 'eventNonce', nonce, '--es', 'benchmarkCommand', command, '--es', 'sampleName', name)
    def export_original():
        # The URI is derived from our nonce, never a report-supplied file path.
        raw = adb('exec-out', 'content', 'read', '--uri',
                  'content://' + PACKAGE + '.evidence/experience-sampling/' + nonce, binary=True)
        tracing.require(len(raw) <= tracing.MAX_FILE_BYTES, 'original trace exceeds host bound')
        (args.out / tracing.TRACE_FILE).write_bytes(raw)
    loopback, servers, benchmark, captured = None, [], load_benchmark(), False
    persist()
    try:
        before = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity'))
        verify_installed(before, expected); report['buildIdentity'] = before; persist()
        loopback, servers = start_servers(adb)
        extras = ['--es', 'scenarioManifest', scenarios.encoded(plan['scenarioManifest']),
                  '--es', 'scenarioSha256', scenarios.digest(plan['scenarioManifest'])]
        adb('shell', 'am', 'force-stop', PACKAGE); adb('logcat', '-c')
        seed_events = benchmark.make_events(adb, expected, seed_nonce, 'experienceSeed', args.out)
        seeded = adb('shell', 'am', 'start', '-W', '-n', COMPONENT + '$Seed', '--es', 'eventNonce', seed_nonce, *extras, timeout=180)
        (args.out / 'diagnostic-seed-am-start.txt').write_text(seeded)
        report['seed'] = seed_events('seeded'); persist()
        adb('shell', 'am', 'force-stop', PACKAGE); adb('logcat', '-c')
        events = benchmark.make_events(adb, expected, nonce, tracing.ACTION, args.out)
        launched = adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'eventNonce', nonce,
                       '--ez', 'historySaveSamplingDiagnostic', 'true', *extras, timeout=60)
        (args.out / 'diagnostic-am-start.txt').write_text(launched)
        report['ready'] = events('ready'); report['readySnapshot'] = events('snapshot', 'ready')
        report['actualAndroidExecution'] = True; persist()
        control('diagnostic-history-sampling', 'extra-history-save-sampling')
        report['traceReceipt'] = events('samplingFinished', seconds=120); persist()
        report['scenarioWindow'] = events('scenarioFinished', 'diagnostic-history-save-sampling')
        report['saves'] = [events('scenarioSave', 'history-save-' + str(number)) for number in range(1, 9)]
        report['additionalRealSaveCalls'] = len(report['saves']); report['additionalSaveCountComplete'] = True; persist()
        control('snapshot', 'diagnostic-final')
        report['finalSnapshot'] = events('snapshot', 'diagnostic-final')
        export_original(); captured = True
        receipt = report['traceReceipt']
        report['traceAnalysis'] = tracing.parse_trace((args.out / tracing.TRACE_FILE).read_bytes(),
            expected_pid=receipt['pid'], main_tid=receipt['mainTid'], main_thread_name=receipt['mainThreadName'])
        report['installedAfter'] = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity'))
        verify_installed(report['installedAfter'], expected)
        tracing.require(len([row for row in loopback.TRACE if row['kind'] == 'http']) == 1, 'extra diagnostic reloaded its document')
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', errorType=type(error).__name__, error=str(error))
        raise
    finally:
        if not captured:
            try:
                (args.out / 'diagnostic-stop-command.txt').write_text(control('diagnostic-stop-sampling', 'diagnostic-abort'))
            except BaseException as error:
                (args.out / 'diagnostic-stop-error.txt').write_text(type(error).__name__ + ': ' + str(error))
            try: export_original()
            except BaseException as error:
                (args.out / 'trace-read-error.txt').write_text(type(error).__name__ + ': ' + str(error))
        if loopback is not None:
            (args.out / 'diagnostic-loopback-trace.json').write_text(json.dumps(loopback.TRACE, indent=2) + '\n')
        for server in servers:
            server.shutdown(); server.server_close()
        report['executionInputsUnchanged'] = all(sha(ROOT / name) == value for name, value in observers.items())
        persist()
        try: adb('shell', 'am', 'force-stop', PACKAGE)
        except BaseException as error:
            (args.out / 'diagnostic-cleanup-error.txt').write_text(type(error).__name__ + ': ' + str(error)); persist()
    try:
        tracing.verify_diagnostic(report, expected, plan['protocol'], plan['scenarioManifest'], args.out, build)
    except BaseException as error:
        report.update(status='failed', errorType=type(error).__name__, error=str(error)); persist(); raise
    print(json.dumps(dict(status=report['status'], diagnosticOnly=True, additionalRealSaveCalls=8,
                          performanceComparisonAllowed=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554', choices=('emulator-5554',))
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args())


if __name__ == '__main__': main()
