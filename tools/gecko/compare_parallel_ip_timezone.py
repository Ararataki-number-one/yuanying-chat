#!/usr/bin/env python3
"""Compare PocketChat's default Gecko IP time zone on one disposable emulator."""

import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from threading import Event, Lock, Thread
import time
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree
from zoneinfo import TZPATH

from parallel_ip_timezone_relay import handle_external_connect, preflight
from run_parallel_coexistence import (Device, Fixture, Handler, PARALLEL, apk_digest,
                                      find_control, gecko_failure_state, parallel_ui_nodes,
                                      preferences, require)


BASE_SHA = '8561e56364383440bdcfea9b7e3538ca47117d1e95b651842a4cde8dc30ae711'
CHROMIUM_SHA = '6ed70a9b49edc10bd758048be09562455a8a8d21b92b434b669c9b5ad72f42ea'
ZONE = r'[A-Za-z][A-Za-z0-9+_-]*(?:/[A-Za-z0-9+_-]+)*'
UI_ERRORS = (OSError, RuntimeError, subprocess.SubprocessError, ElementTree.ParseError)


class Phase:
    """Handler state stays attached to its accepted connection through phase changes."""

    def __init__(self, server, allow_geo):
        self.authority = server.authority
        self.nonce = secrets.token_hex(14)
        self.url = f'{server.origin}/gecko/{self.nonce}'
        self.path = urlsplit(self.url).path
        self.heading = 'PocketChat-gecko-' + self.nonce
        self.allow_geo = allow_geo
        self.document = Event()
        self.javascript = Event()
        self.zone = ''
        self._lock = Lock()
        self._counts = Counter()

    def record(self, key):
        with self._lock:
            self._counts[key] += 1

    def counts(self):
        with self._lock:
            return dict(self._counts)


class ComparisonHandler(Handler):
    def do_CONNECT(self):
        if self.path == self.server.authority:
            super().do_CONNECT()
        else:
            handle_external_connect(self, self.server.allow_geo)

    def do_GET(self):
        phase = self.server
        address = urlsplit(self.path)
        if self.headers.get('Host') != phase.authority or address.netloc not in ('', phase.authority):
            phase.record('rejectedRequests')
            self.answer(403)
            return
        if address.path == phase.path and not address.query:
            page = f"""<!doctype html><meta charset="utf-8"><title>{phase.heading}</title><h1>{phase.heading}</h1>
<script>requestAnimationFrame(() => requestAnimationFrame(() => {{
  const h = document.querySelector('h1');
  const visible = document.visibilityState === 'visible' && h.getBoundingClientRect().width > 0 && h.textContent === document.title;
  const params = new URLSearchParams({{visible: String(visible), title: document.title, build: navigator.productSub,
    gecko: String(/Gecko\\/157[.]0 Firefox\\/157[.]0/.test(navigator.userAgent)), zone: Intl.DateTimeFormat().resolvedOptions().timeZone}});
  fetch('{phase.path}/proof?' + params);
}}));</script>"""
            phase.document.set()
            self.answer(200, page.encode())
            return
        if address.path == phase.path + '/proof':
            fields = parse_qs(address.query, max_num_fields=8)
            zone = fields.get('zone', [''])[0]
            if (len(zone) <= 80 and re.fullmatch(ZONE, zone)
                    and fields == dict(visible=['true'], title=[phase.heading], build=['20100101'],
                                       gecko=['true'], zone=[zone])):
                phase.zone = zone
                phase.javascript.set()
                self.answer(200)
                return
        self.answer(404)


class ComparisonFixture(Fixture):
    def __init__(self):
        super().__init__(secrets.token_hex(10))
        self.active = Phase(self, False)

    def finish_request(self, request, client_address):
        ComparisonHandler(request, client_address, self.active)

    def handle_error(self, request, client_address):
        # Avoid recording exception text, socket endpoints or request bodies.
        pass


@contextmanager
def proxy_fixture(device):
    with ComparisonFixture() as fixture:
        remote = f'tcp:{fixture.server_port}'
        device.call('reverse', '--no-rebind', remote, remote)
        thread = Thread(target=fixture.serve_forever, daemon=True)
        thread.start()
        try:
            yield fixture
        finally:
            fixture.shutdown()
            thread.join(timeout=5)
            device.call('reverse', '--remove', remote, check=False)


def parse_status(nodes):
    summaries = {node.get('text', '').strip() for node in nodes
                 if node.get('text', '').strip().startswith('已保存：') and '当前：' in node.get('text', '')}
    if len(summaries) != 1:
        return None
    current = summaries.pop()
    observed = re.search(r'当前出口观测：[^\s·]+\s*·\s*(' + ZONE + r')（ipwho[.]is）', current)
    status = {
        'defaultIpSelected': bool(re.match(r'已保存：跟随当前出口 IP\s*当前：', current)),
        'nativeReadback': '当前：当前会话原生设置已回读' in current,
        'ipMatched': observed is not None,
        'standardizedProtectionPriority': '强化保护原生统一时区优先' in current,
        'unmatched': 'IP 时区未匹配' in current,
        'issue': next((label for phrase, label in (
            ('当前浏览器出口尚未确认', 'route-unconfirmed'), ('查询超时', 'lookup-timeout'),
            ('查询失败', 'lookup-failed'), ('查询不可用', 'lookup-unavailable'),
            ('响应无效', 'lookup-invalid'), ('原生时区准备未完成', 'native-timeout'),
            ('原生时区设置未被', 'native-readback-failed'), ('原生时区确认未保存', 'native-save-failed'),
        ) if phrase in current), 'none-or-unclassified'),
    }
    # Keep the observed IANA name only in memory. The status text includes the egress IP.
    return status, observed[1] if observed else ''


def same_zone(left, right):
    if not left or not right:
        return None
    utc_names = {'Etc/UTC', 'UTC', 'Etc/GMT', 'GMT'}
    if left == right or {left, right} <= utc_names:
        return True
    for directory in TZPATH:
        a, b = Path(directory) / left, Path(directory) / right
        if a.is_file() and b.is_file():
            return os.path.samefile(a, b)
    return None


class Settings:
    def __init__(self, device, nonce):
        self.device = device
        self.nonce = nonce

    def nodes(self):
        try:
            return parallel_ui_nodes(self.device, self.nonce)
        except UI_ERRORS:
            return []

    def control(self, *labels, scroll=False, tap=True):
        deadline = time.monotonic() + 24
        moves = 0
        while time.monotonic() < deadline:
            nodes = self.nodes()
            for label in labels:
                position = find_control(nodes, label)
                if position:
                    if tap:
                        self.device.shell('input', 'tap', *position)
                    return True
            if scroll and moves < 5:
                for node in nodes:
                    bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
                    if node.get('scrollable') == 'true' and bounds:
                        x1, y1, x2, y2 = map(int, bounds.groups())
                        if y2 - y1 >= 100:
                            x = (x1 + x2) // 2
                            self.device.shell('input', 'swipe', x, y1 + (y2-y1)*4//5, x, y1 + (y2-y1)//5, 380)
                            moves += 1
                            break
            time.sleep(.3)
        return False

    def open(self):
        self.device.start(PARALLEL, 'MainActivity', edit_environment=True)
        for label, scroll in [('浏览器', False), ('环境模板与生效状态', True), ('此环境的独立时区', True)]:
            if not self.control(label, scroll=scroll):
                return False
        return True

    def summary(self):
        until = time.monotonic() + 15
        while time.monotonic() < until:
            result = parse_status(self.nodes())
            if result and (result[0]['defaultIpSelected'] or result[0]['nativeReadback']):
                return result
            time.sleep(.4)
        return None

    def retry_default(self):
        if not self.control('重试当前出口 IP 查询', scroll=True):
            return False
        if not self.control('应用当前环境时区？', tap=False):
            return False
        if not self.control('已保存输入，应用', '应用并重新加载'):
            return False
        # Confirm async save actually reached its success callback before closing.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if any('配置已保存，正在等待当前会话的原生确认' in n.get('text', '') for n in self.nodes()):
                break
            time.sleep(.25)
        else:
            return False
        for _ in range(3):
            self.device.shell('input', 'keyevent', 'KEYCODE_BACK')
        return True


def observation(device, phase):
    state = gecko_failure_state(device, phase)
    return {'document': phase.document.is_set(), 'visibleGeckoJavascript': phase.javascript.is_set(),
            'geckoMapped': state.get('geckoLibraryMapped'), 'activityResumed': state.get('mainActivityResumed'),
            'visibleStates': state.get('visibleStates', []), 'proxyCounts': phase.counts()}


def run_arm(device, fixture, expected_uid, allow_geo, arm):
    require(device.shell('pm', 'clear', '--user', '0', PARALLEL) == 'Success', 'app-clear')
    require(device.package_info(PARALLEL, 117)['uid'] == expected_uid, 'identity-after-reset')
    phase = Phase(fixture, allow_geo)
    fixture.active = phase
    values = {'environmentInitialized': True, 'pageMode': True, 'networkConfigured': True,
              'networkMode': 'external', 'requireExternalVpn': False, 'autoHistory': False,
              'proxy': f'http://127.0.0.1:{fixture.server_port}', 'browserHomeUrl': phase.url,
              'browserStartScreen': 'chatgpt-enhanced', 'url': phase.url, 'geckoBrowserUrl': phase.url}
    device.write_private(PARALLEL, expected_uid, 'shared_prefs/chat.xml', preferences(values))
    ui = Settings(device, phase.nonce)
    arm['resetConfirmed'] = True
    arm['sameDefaultRetry'] = False
    try:
        device.start(PARALLEL, 'MainActivity', phase.url)
        phase.javascript.wait(60)
        arm['cold'] = observation(device, phase)
        arm['final'] = dict(arm['cold'])
        if not ui.open() or not (summary := ui.summary()):
            arm['uiIssue'] = 'initial-summary-unavailable'
            return
        initial, zone = summary
        arm['cold']['settings'] = initial
        arm['final']['settings'] = initial
        arm['pageMatchesUiZone'] = same_zone(phase.zone, zone)
        if arm['cold']['visibleGeckoJavascript'] or not initial['defaultIpSelected'] or initial['standardizedProtectionPriority']:
            return
        if not ui.retry_default():
            arm['uiIssue'] = 'default-retry-unconfirmed'
            return
        arm['sameDefaultRetry'] = True
        device.start(PARALLEL, 'MainActivity', phase.url)
        phase.javascript.wait(45)
        arm['final'] = observation(device, phase)
        if not ui.open() or not (summary := ui.summary()):
            arm['uiIssue'] = 'retry-summary-unavailable'
            return
        final, zone = summary
        arm['final']['settings'] = final
        arm['pageMatchesUiZone'] = same_zone(phase.zone, zone)
    finally:
        device.stop(PARALLEL)
        arm['proxyTotals'] = phase.counts()


def classify(report):
    if report['servicePreflight'].get('status') != 'passed':
        return 'inconclusive', 'geo-service-unavailable'
    denied, allowed = report['arms']['denied'], report['arms']['allowed']
    a, b = denied.get('final', {}), allowed.get('final', {})
    if any('uiIssue' in arm or not arm.get('resetConfirmed') or not result.get('settings', {}).get('defaultIpSelected')
           or result['settings'].get('standardizedProtectionPriority')
           for arm, result in ((denied, a), (allowed, b))):
        return 'inconclusive', 'default-mode-or-ui-unconfirmed'
    if not all(x.get('geckoMapped') and x.get('activityResumed') for x in (a, b)):
        return 'inconclusive', 'native-foreground-gecko-unconfirmed'
    if not a['proxyCounts'].get('geoDenied'):
        return 'inconclusive', 'no-denied-default-lookup-observed'
    if a['document'] or a['visibleGeckoJavascript'] or a['settings']['ipMatched']:
        return 'fail', 'offline-default-was-not-blocked'
    if not a['settings']['unmatched']:
        return 'inconclusive', 'offline-default-state-unconfirmed'
    if not b['proxyCounts'].get('geoOpened'):
        return 'inconclusive', 'no-app-upstream-connection'
    if not b['settings']['ipMatched'] or not b['settings']['nativeReadback']:
        return 'inconclusive', 'allowed-service-app-observation-unconfirmed'
    if not b['document'] or not b['visibleGeckoJavascript']:
        return 'fail', 'confirmed-default-did-not-render'
    if allowed['pageMatchesUiZone'] is False:
        return 'fail', 'page-and-native-timezones-differ'
    if allowed['pageMatchesUiZone'] is not True:
        return 'inconclusive', 'timezone-equivalence-unconfirmed'
    return 'pass', 'default-loaded-after-ui-retry' if allowed['sameDefaultRetry'] else 'default-loaded-on-first-navigation'


def run(args, report):
    report['stage'] = 'verify-apks'
    require(apk_digest(args.parallel_base_apk) == BASE_SHA and apk_digest(args.parallel_chromium_apk) == CHROMIUM_SHA,
            'unexpected-inputs')
    report['stage'] = 'prepare-emulator'
    device = Device(args.adb, args.serial)
    device.prepare()
    report['stage'] = 'install-known-test-pair'
    device.install(args.parallel_base_apk, args.parallel_chromium_apk)
    info = device.package_info(PARALLEL, 117)
    require(info['splitCount'] == 2 and info['chromiumSplit'], 'installed-splits')
    with proxy_fixture(device) as fixture:
        # Preflight has its own immutable counter scope and cannot prove an app request.
        fixture.active = Phase(fixture, True)
        report['stage'] = 'preflight'
        report['servicePreflight'] = preflight(fixture.server_port)
        if report['servicePreflight']['status'] != 'passed':
            report['reason'] = 'geo-service-unavailable'
            return
        for name in ('denied', 'allowed'):
            report['stage'] = name
            arm = report['arms'][name] = {}
            run_arm(device, fixture, info['uid'], name == 'allowed', arm)
        report['stage'] = 'compare'
        report['status'], report['reason'] = classify(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--parallel-base-apk', type=Path, required=True)
    parser.add_argument('--parallel-chromium-apk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'schema': 1, 'scope': 'test-signed x86_64 Gecko only; fresh Android 13 emulator; fixed proxy allowlist only; whole-device egress unverified',
              'sourceRun': '44867757446', 'baseSha256': BASE_SHA, 'featureSha256': CHROMIUM_SHA,
              'status': 'inconclusive', 'reason': 'setup-or-device-error', 'arms': {}}
    try:
        run(args, report)
    except (OSError, RuntimeError, subprocess.SubprocessError, ElementTree.ParseError, ValueError) as error:
        # Some tool failures can include a real endpoint or an entire UI node. Emit only their type.
        report['errorClass'] = type(error).__name__
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Default IP timezone: {report['status']} ({report['reason']})")
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
