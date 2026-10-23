#!/usr/bin/env python3
"""Fixed actual-app workload; measurements are never release-acceptance substitutes.

Install each source-derived integration APK outside this runner, then invoke the
identical runner in ABBA order on one fresh emulator. --label is descriptive only.
This runner never installs APKs, clears app data, changes animation settings, or
replays a failed iteration. All requested repetitions and their raw records stay.
"""
import argparse
import hashlib
import http.server
import importlib.util
import json
import pathlib
import re
import shlex
import statistics
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.ExperienceBenchmarkActivity'
ACTION = PACKAGE + '.EXPERIENCE_BENCHMARK'
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from integration_event_contract import EventTransfer, parse_receipt_line
from profile_invocation_contract import expected_build, verify_installed


def error_output(error):
    raw = getattr(error, 'output', None)
    return raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw


def parse_proc_stat(raw):
    """Handle process names containing spaces/parentheses without shifting fields."""
    left, right = raw.find('('), raw.rfind(')')
    if left < 0 or right <= left:
        raise ValueError('Invalid proc stat')
    fields = raw[right + 2:].split()
    if len(fields) < 22:
        raise ValueError('Truncated proc stat')
    return {'pid': int(raw[:left].strip()), 'name': raw[left + 1:right],
            'ppid': int(fields[1]), 'userTicks': int(fields[11]),
            'systemTicks': int(fields[12]), 'startTicks': int(fields[19]),
            'rssPages': int(fields[21])}


def cpu_summary(samples, hz):
    """Include newly born processes; disclose any unobserved termination tail."""
    usable = [s for s in samples if s.get('available')]
    if len(usable) < 2 or not hz:
        return {'available': False, 'reason': 'Insufficient actual process observations'}
    first, last = {}, {}
    for sample in usable:
        for row in sample['processes']:
            key = (row['pid'], row['startTicks'])
            first.setdefault(key, (sample['uptimeSeconds'], row))
            last[key] = (sample['uptimeSeconds'], row)
    if not first:
        return {'available': False, 'reason': 'No actual app process CPU counters were observable'}
    start, end = usable[0]['uptimeSeconds'], usable[-1]['uptimeSeconds']
    ticks = 0
    ended = []
    for key, (at, row) in first.items():
        final_at, final = last[key]
        initial = 0 if row['startTicks'] / hz >= start else row['userTicks'] + row['systemTicks']
        ticks += final['userTicks'] + final['systemTicks'] - initial
        if final_at < end:
            ended.append({'pid': key[0], 'startTicks': key[1], 'lastObservedAt': final_at})
    seconds = end - start
    return {'available': seconds > 0, 'cpuSecondsObserved': ticks / hz,
            'wallSeconds': seconds, 'percentOfOneCore': 100 * ticks / hz / seconds if seconds > 0 else None,
            'completeProcessLifetimeCoverage': False,
            'observedProcessEndsCovered': not ended and all(s.get('available') for s in samples),
            'terminatedBeforeFinalObservation': ended,
            'scope': 'All observed package-name processes plus descendants, including isolated Gecko processes. Sampling can miss processes born and terminated between observations and CPU tails after the last observation of a terminated process. Totals are observed lower bounds, never proof of complete lifetime coverage.'}


def summary(values):
    if not values:
        return {'count': 0}
    ordered = sorted(values)
    return {'count': len(values), 'median': statistics.median(values),
            'p95': ordered[min(len(ordered) - 1, int((len(ordered) - 1) * .95 + .999))],
            'max': max(values), 'raw': values}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', default='emulator-5554')
    p.add_argument('--apk', type=pathlib.Path, required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--out', type=pathlib.Path, required=True)
    p.add_argument('--repetitions', type=int, default=3)
    args = p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.source) or not re.fullmatch('[A-Za-z0-9_-]{1,60}', args.label) or not 1 <= args.repetitions <= 10:
        p.error('Require full source SHA, safe label, and 1..10 predeclared repetitions')
    args.out.mkdir(parents=True, exist_ok=False)

    def adb(*parts, binary=False, timeout=30):
        # adb joins shell arguments before the device shell evaluates them;
        # quote the nested Seed component's literal '$' and every other token.
        if parts and parts[0] == 'shell':
            parts = ('shell', shlex.join(parts[1:]))
        return subprocess.check_output([args.adb, '-s', args.serial, *parts], text=not binary,
                                       stderr=subprocess.STDOUT, timeout=timeout)

    source_tree = subprocess.check_output(['git', 'rev-parse', args.source + '^{tree}'], cwd=ROOT, text=True).strip()
    gradle = subprocess.check_output(['git', 'show', args.source + ':app/build.gradle'], cwd=ROOT, text=True)
    expected = expected_build(args.apk.resolve(), args.source, source_tree,
                              re.search(r"versionName '([^']+)'", gradle).group(1), int(re.search(r'versionCode (\d+)', gradle).group(1)))
    installed = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity'))
    verify_installed(installed, expected)
    animations = {key: adb('shell', 'settings', 'get', 'global', key).strip()
                  for key in ('window_animation_scale', 'transition_animation_scale', 'animator_duration_scale')}
    assert all(float(value) == 1 for value in animations.values()), 'Dedicated performance device must use animation scales 1: ' + str(animations)
    assert adb('get-state').strip() == 'device'
    environment = {'serial': args.serial, 'androidSdk': adb('shell', 'getprop', 'ro.build.version.sdk').strip(),
                   'abi': adb('shell', 'getprop', 'ro.product.cpu.abi').strip(),
                   'viewport': adb('shell', 'wm', 'size').strip(), 'density': adb('shell', 'wm', 'density').strip(),
                   'fontScale': adb('shell', 'settings', 'get', 'system', 'font_scale').strip(),
                   'animationScales': animations}
    try:
        environment['cpuCount'] = int(adb('shell', 'getconf', '_NPROCESSORS_ONLN').strip())
    except (ValueError, subprocess.SubprocessError) as error:
        environment['cpuCountUnavailable'] = str(error)
    try:
        hz = int(adb('shell', 'getconf', 'CLK_TCK').strip())
    except (ValueError, subprocess.SubprocessError):
        hz = None
    environment['clockTicksPerSecond'] = hz

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

    def process_sample():
        try:
            # A fixed shell program, no credential paths or user configuration.
            listing = adb('shell', 'ps', '-A', '-o', 'PID,PPID,UID,NAME')
            rows = []
            for line in listing.splitlines()[1:]:
                fields = line.split(None, 3)
                if len(fields) == 4:
                    rows.append({'pid': int(fields[0]), 'ppid': int(fields[1]), 'uid': fields[2], 'process': fields[3]})
            selected = {r['pid'] for r in rows if r['process'] == PACKAGE or r['process'].startswith(PACKAGE + ':')}
            for _ in range(len(rows)):
                descendants = {r['pid'] for r in rows if r['ppid'] in selected}
                if descendants <= selected:
                    break
                selected |= descendants
            uptime = float(adb('exec-out', 'cat', '/proc/uptime').split()[0])
            values, errors = [], []
            for row in rows:
                if row['pid'] not in selected:
                    continue
                try:
                    value = parse_proc_stat(adb('exec-out', 'cat', '/proc/%d/stat' % row['pid']))
                    value.update(process=row['process'], uid=row['uid'])
                    values.append(value)
                except (ValueError, subprocess.SubprocessError) as error:
                    errors.append({'pid': row['pid'], 'error': str(error), 'raw': error_output(error)})
            return {'available': not errors, 'uptimeSeconds': uptime, 'processes': values, 'errors': errors,
                    'discoveredProcesses': [row for row in rows if row['pid'] in selected], 'discoveryAvailable': True,
                    'hostObservedMonotonic': time.monotonic()}
        except (ValueError, subprocess.SubprocessError) as error:
            return {'available': False, 'discoveryAvailable': False, 'error': str(error),
                    'raw': error_output(error), 'hostObservedMonotonic': time.monotonic()}

    def memory_sample():
        processes = process_sample()
        rows = []
        for row in processes.get('discoveredProcesses', []):
            raw = None
            try:
                raw = adb('shell', 'dumpsys', 'meminfo', str(row['pid']), timeout=20)
                matched = re.search(r'^\s*TOTAL PSS:\s*(\d+)', raw, re.M) or re.search(r'^\s*TOTAL\s+(\d+)\s', raw, re.M)
                if not matched:
                    raise ValueError('PSS row unavailable')
                rows.append({'pid': row['pid'], 'process': row['process'], 'pssKb': int(matched.group(1)), 'raw': raw})
            except (ValueError, subprocess.SubprocessError) as error:
                rows.append({'pid': row['pid'], 'process': row['process'], 'error': str(error),
                             'raw': raw if raw is not None else error_output(error)})
        complete = bool(rows) and processes.get('discoveryAvailable') and all('pssKb' in row for row in rows)
        return {'available': bool(complete), 'totalPssKb': sum(row['pssKb'] for row in rows) if complete else None,
                'processes': rows, 'scope': 'Serial actual dumpsys PSS observations of every discovered app/isolated-Gecko/descendant process; not an atomic snapshot.'}

    report = {'schema': 1, 'status': 'in_progress', 'label': args.label, 'sourceCommit': args.source,
              'buildIdentity': installed, 'runnerSha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
              'activitySha256': hashlib.sha256((ROOT / 'tests/gecko/ExperienceBenchmarkActivity.java').read_bytes()).hexdigest(),
              'environment': environment, 'predeclaredRepetitions': args.repetitions, 'iterations': [],
              'physicalDeviceAcceptance': False, 'realChatGptAcceptance': False, 'releaseAcceptance': False,
              'protocol': 'Untimed provisioning; process-cold fixture Activity launch and normal production connection; network→chat→downloads→chat→settings→chat; compact expand/upward swipe; settings dark/light via real taps; return chat; HOME and retained warm resume. Same deterministic 240-message/105k reply, no send. All actions are actual Android input; all raw samples retained.',
              'measurementLimits': ['Loopback document loading is not ChatGPT or WAN latency.', 'Cold means process-cold; OS filesystem caches are not purged.', 'Activity fixture startup excludes explicit provisioning and APK hashing, but includes test observation overhead.', 'Native response ends at View draw, not display/compositor presentation.', 'Choreographer resets on Activity pause/resume; HWUI measures actual submitted native frames. Neither fully observes Gecko compositor jank.', 'Page RAF resets on document visibility changes; snapshots identify native tabs and document visibility, so intervals spanning hidden native panels are not visible-page jank evidence.', 'CPU includes the fixed test evidence/observation overhead; terminated process tails are disclosed.', 'Fixture theme uses real CSS prefers-color-scheme and observed computed background via Gecko color preference; the ChatGPT-only native appearance bridge is outside this localhost flow and retains its separate release regression.', 'Normal timers and polling remain enabled, but ChatGPT-origin-only resource/reply observer messages are unavailable on this static localhost page; streaming replies and uploads are not measured.', 'No vendor keyboard, real account, upload or physical-device benchmark in this flow.']}

    def persist():
        (args.out / 'experience-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def make_events(nonce, action, iteration):
        transfer = EventTransfer(identity=expected, nonce=nonce, slot=0, action=action,
                                 fetch=lambda uri: adb('exec-out', 'content', 'read', '--uri', uri, binary=True))
        seen, events = set(), []

        def wait(kind, name=None, seconds=50):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                raw = adb('logcat', '-d', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S')
                (iteration / (action + '-log.txt')).write_text(raw)
                assert 'FATAL EXCEPTION' not in raw, raw[-5000:]
                for line in raw.splitlines():
                    receipt = parse_receipt_line(line)
                    if receipt is None or receipt.get('runNonce') != nonce:
                        continue
                    assert receipt.get('kind') != 'eventTransportError', receipt
                    sequence = receipt['sequence']
                    if sequence not in seen:
                        value = transfer.read(receipt)
                        seen.add(sequence);events.append(value)
                        (iteration / (action + '-events.json')).write_text(json.dumps(events, ensure_ascii=False, indent=2) + '\n')
                        assert value['kind'] != 'error', value
                for value in events:
                    if value['kind'] == kind and (name is None or value['result'].get('name') == name):
                        return value['result']
                time.sleep(.1)
            raise TimeoutError((kind, name, 'No owned benchmark event'))
        return wait

    try:
        for index in range(args.repetitions):
            directory = args.out / ('iteration-%02d' % (index + 1));directory.mkdir()
            row = {'index': index + 1, 'status': 'in_progress', 'actions': []};report['iterations'].append(row);persist()
            adb('shell', 'am', 'force-stop', PACKAGE);adb('logcat', '-c')
            seed_nonce = uuid.uuid4().hex
            seed_events = make_events(seed_nonce, 'experienceSeed', directory)
            adb('shell', 'am', 'start', '-W', '-n', COMPONENT + '$Seed', '--es', 'eventNonce', seed_nonce)
            seed_events('seeded')
            adb('shell', 'am', 'force-stop', PACKAGE);adb('logcat', '-c')
            nonce = uuid.uuid4().hex;events = make_events(nonce, 'experienceBenchmark', directory)
            samples = [process_sample()];stop = threading.Event()

            def sample_cpu():
                while not stop.wait(1):
                    samples.append(process_sample())

            sampler = threading.Thread(target=sample_cpu, daemon=True);sampler.start()
            try:
                started = time.monotonic()
                start_output = adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'eventNonce', nonce, timeout=60)
                (directory / 'cold-am-start.txt').write_text(start_output)
                ready = events('ready');snapshot = events('snapshot', 'ready')
                row['startup'] = dict(ready, hostCommandToReadyEventMs=(time.monotonic() - started) * 1000,
                                      amStartMs={k: int(v) for k, v in re.findall(r'^(ThisTime|TotalTime|WaitTime):\s*(\d+)', start_output, re.M)})
                row['memoryReady'] = memory_sample()
                initial = snapshot

                def send(command, name, target=None):
                    values = ['shell', 'am', 'broadcast', '-a', ACTION, '-p', PACKAGE, '--es', 'eventNonce', nonce,
                              '--es', 'benchmarkCommand', command, '--es', 'sampleName', name]
                    if target is not None:
                        values += ['--es', 'target', target]
                    adb(*values)

                def preserve(value):
                    assert all(value[k] == initial[k] for k in ('surface', 'session', 'attachedSession')), 'Native browser identity changed'
                    assert all(value['page'][k] == initial['page'][k] for k in ('document', 'draft', 'cookie', 'replyFingerprint', 'sendCount', 'path')), 'Website state changed'
                    assert value['visibleDocument'] and value['networkReady']

                def measure(name, target, perform):
                    nonlocal snapshot
                    send('arm', name, target);events('armed', name)
                    perform()
                    result = events('measurement', name, seconds=20)
                    snapshot = events('snapshot', name);preserve(snapshot)
                    if 'webThemeResponseUpperBoundMs' in snapshot:
                        result['webThemeResponseUpperBoundMs'] = snapshot['webThemeResponseUpperBoundMs']
                    row['actions'].append(result);persist()

                def tap_point(point):
                    adb('shell', 'input', 'tap', str(point[0]), str(point[1]))

                def label_point(label):
                    adb('shell', 'uiautomator', 'dump', '/sdcard/experience-ui.xml')
                    raw = adb('exec-out', 'cat', '/sdcard/experience-ui.xml')
                    tree = ET.fromstring(raw)
                    nodes = [n for n in tree.iter('node') if n.get('text') == label and n.get('enabled') == 'true']
                    assert nodes, ('Visible control missing', label)
                    left, top, right, bottom = map(int, re.findall(r'\d+', nodes[0].get('bounds')))
                    assert right > left and bottom > top
                    return [(left + right) // 2, (top + bottom) // 2]

                for destination in ('network', 'downloads', 'settings'):
                    point = snapshot['points'][destination]
                    measure('open-' + destination, destination, lambda point=point: tap_point(point))
                    point = snapshot['points']['chat']
                    measure('return-' + destination, 'chat', lambda point=point: tap_point(point))
                # Native return reveals chrome; collapse then expand through real input.
                first, last = snapshot['points']['swipeFrom'], snapshot['points']['swipeTo']
                measure('collapse', 'collapsed', lambda: adb('shell', 'input', 'swipe', *map(str, [*first, *last]), '320'))
                point = snapshot['points']['compact'];measure('expand', 'expanded', lambda: tap_point(point))
                point = snapshot['points']['settings'];measure('theme-settings', 'settings', lambda: tap_point(point))
                tap_point(label_point('白天与黑夜'))
                for theme, label in [('dark', '始终黑夜'), ('light', '始终白天')]:
                    point = label_point(label)
                    measure('theme-' + theme, theme, lambda point=point: tap_point(point))
                tap_point(label_point('完成'))
                point = snapshot['points']['chat'];measure('theme-return', 'chat', lambda: tap_point(point))
                assert snapshot['page']['theme'] == 'light', 'Website theme did not return to light'
                send('arm', 'warm-resume', 'resume');events('armed', 'warm-resume')
                adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
                warm = adb('shell', 'am', 'start', '-W', '--activity-single-top', '-n', COMPONENT)
                (directory / 'warm-am-start.txt').write_text(warm)
                row['actions'].append(events('measurement', 'warm-resume', seconds=20))
                snapshot = events('snapshot', 'warm-resume');preserve(snapshot)
                row['warmAmStartMs'] = {k: int(v) for k, v in re.findall(r'^(ThisTime|TotalTime|WaitTime):\s*(\d+)', warm, re.M)}
                send('finish', 'final');row['frames'] = events('finished');row['memoryFinal'] = memory_sample()
                (directory / 'final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
                row['status'] = 'passed'
            finally:
                stop.set();sampler.join(timeout=40)
                assert not sampler.is_alive(), 'CPU observer did not stop'
                (directory / 'process-samples.json').write_text(json.dumps(samples, indent=2) + '\n')
                row['cpu'] = cpu_summary(samples, hz)
                persist()
        installed_after = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://' + PACKAGE + '.evidence/build-identity'))
        verify_installed(installed_after, expected)
        assert len([r for r in loopback.TRACE if r['kind'] == 'http']) == args.repetitions, 'A benchmark action reloaded the document'
        assert all(r['host'] == '127.0.0.1' and r['port'] == 8765 for r in loopback.TRACE if r['kind'] == 'socks' and r['accepted'])
        names = sorted({action['name'] for row in report['iterations'] for action in row['actions']})
        report['responseToDrawMs'] = {name: summary([action['responseToDrawMs'] for row in report['iterations'] for action in row['actions'] if action['name'] == name]) for name in names}
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed';report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        (args.out / 'loopback-trace.json').write_text(json.dumps(loopback.TRACE, indent=2) + '\n')
        persist()
        for server in servers:
            server.shutdown();server.server_close()
    print(json.dumps({'status': report['status'], 'label': args.label, 'sourceCommit': args.source,
                      'repetitions': len(report['iterations']), 'responseToDrawMs': report.get('responseToDrawMs')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
