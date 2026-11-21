#!/usr/bin/env python3
"""Exercise two independently installed PocketChat packages on a fresh API 33 AVD."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import file_digest, sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import shlex
import sqlite3
import subprocess
import tempfile
from threading import Event, Lock, Thread
import time
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree


OFFICIAL = "local.pocketchat"
PARALLEL = "local.pocketchat.parallel"
CATALOG = "databases/environment-catalog.db"
ORIGIN_PORT = 8765
SHARED_AUTHORITIES = {"saved-downloads", "network-shares"} | {
    f"{family}{slot}" for family in ("lifecycle", "network-ui") for slot in range(8)
}
CHECKS = ("packageIdentity", "providerIsolation", "officialDataIntegrity",
          "parallelGecko", "parallelNativeChromium", "portableBackup")
GECKO_VISIBLE_STATES = {
    "runtimeInitFailure": "新内核未能启动",
    "sdkOrAddonFailure": "浏览器初始化失败",
    "startupWindowFailure": "浏览器启动窗口未能",
    "browserWindowFailure": "浏览器窗口未能启动",
    "cpuPreparationFailure": "CPU 冷启动配置未能安全准备",
    "cpuAcknowledgementFailure": "原生 CPU 配置未确认",
    "tlsPreparationFailure": "TLS 冷启动配置未能安全准备",
    "tlsAcknowledgementFailure": "原生 TLS 协议尚未确认",
    "protectionAcknowledgementFailure": "当前浏览器保护尚未就绪",
    "requestIdentityFailure": "浏览器请求身份保护未能安装",
    "routeNotReady": "线路正在更新",
    "noConfiguredNetwork": "请先配置手机独立网络",
    "networkOffline": "当前离线",
    "unexpectedVpnRequired": "手机 VPN 未连接",
    "websiteFailure": "网页暂时无法打开",
    "websiteConnectionFailure": "连接失败",
    "browserStartupPending": "正在打开浏览器",
    "pageCheckPending": "正在核对网页",
    "ipTimezoneNotMatched": "IP 时区未匹配",
    "ipTimezoneLookupFailure": "IP 时区查询失败",
    "ipTimezoneLookupTimeout": "IP 时区查询超时",
    "timezoneAdmissionPending": "当前原生时区尚未确认",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def apk_digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


class Device:
    def __init__(self, adb, serial):
        self.command = [adb, "-s", serial]
        self.serial = serial

    def call(self, *args, payload=None, timeout=15, check=True):
        result = subprocess.run(self.command + [str(part) for part in args], input=payload,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if check and result.returncode:
            output = (result.stderr or result.stdout).decode(errors="replace").strip()
            raise RuntimeError(f"adb {args[0]} failed ({result.returncode}): {output[-600:]}")
        return result

    def shell(self, *args):
        return self.call("shell", shlex.join(str(arg) for arg in args)).stdout.decode().strip()

    def prepare(self):
        require(re.fullmatch(r"emulator-[0-9]+", self.serial), "Only an explicit emulator is permitted")
        require(self.shell("getprop", "ro.kernel.qemu") == "1", "This target is not an Android emulator")
        require(self.shell("getprop", "ro.build.version.sdk") == "33", "Expected the fresh API 33 AVD")
        require(self.shell("getprop", "ro.product.cpu.abi") == "x86_64", "Expected x86_64 emulator ABI")
        require(self.shell("am", "get-current-user") == "0", "Expected the primary fresh test user")
        installed = set(self.shell("pm", "list", "packages").splitlines())
        require(all("package:" + package not in installed for package in (OFFICIAL, PARALLEL)),
                "PocketChat already exists on this emulator; refusing to operate on existing data")
        if self.shell("id", "-u") != "0" and self.shell("getprop", "ro.debuggable") == "1":
            self.call("root", check=False)
            self.call("wait-for-device", timeout=40)
        require(self.shell("id", "-u") == "0", "The disposable emulator has no root ADB for private-byte checks")

    def install(self, *paths):
        command = "install" if len(paths) == 1 else "install-multiple"
        result = self.call(command, *paths, timeout=120)
        require("Success" in result.stdout.decode(), "Package installer did not confirm success")

    def stop(self, package):
        self.shell("am", "force-stop", package)

    def start(self, package, activity, url=None, *, edit_environment=False):
        arguments = ["am", "start", "-W", "-n", f"{package}/local.pocketchat.{activity}"]
        if url:
            arguments.extend(("-a", "android.intent.action.VIEW", "-d", url))
        if edit_environment:
            arguments.extend(("--ez", "openEnvironmentEditor", "true"))
        result = self.call("shell", shlex.join(arguments), timeout=55).stdout.decode()
        require("Status: ok" in result, f"Android did not start {package}/{activity}: {result[-500:]}")

    def package_info(self, package, version_code):
        result = self.shell("dumpsys", "package", package)
        app_id = re.search(r"^\s*(?:appId|userId)=(\d+)\s*$", result, re.M)
        version = re.search(r"^\s*versionCode=(\d+)\b", result, re.M)
        require(app_id and version and int(version[1]) == version_code, f"Unexpected installed identity for {package}")
        uid = int(app_id[1])
        require(uid >= 10000, f"Non-application UID for {package}")
        root = f"/data/user/0/{package}"
        require(self.shell("stat", "-c", "%u", root) == str(uid), f"Private directory owner differs for {package}")
        paths = self.shell("pm", "path", package).splitlines()
        authorities = {}
        for provider in re.finditer(r"^\s*\[([^\]\r\n]+)\]:\s*\n\s*Provider\{[^\s]+\s+([^/\s]+)/", result, re.M):
            authorities[provider[1]] = provider[2]
        return dict(uid=uid, versionCode=version_code, dataRoot=root, splitCount=len(paths),
                    chromiumSplit=any(path.endswith("/split_chromium.apk") for path in paths), authorities=authorities)

    def write_private(self, package, uid, relative, payload):
        path = f"/data/user/0/{package}/{relative}"
        parent = path.rsplit("/", 1)[0]
        command = (f"umask 077 && mkdir -p {shlex.quote(parent)} && cat > {shlex.quote(path)} && "
                   f"chown {uid}:{uid} {shlex.quote(parent)} {shlex.quote(path)} && "
                   f"chmod 700 {shlex.quote(parent)} && chmod 600 {shlex.quote(path)} && "
                   f"restorecon {shlex.quote(parent)} {shlex.quote(path)}")
        self.call("shell", "-T", command, payload=payload)

    def private_bytes(self, package, relative):
        return self.call("exec-out", "cat", f"/data/user/0/{package}/{relative}").stdout

    def private_exists(self, package, relative):
        return self.call("shell", "test", "-e", f"/data/user/0/{package}/{relative}",
                         check=False).returncode == 0


def preferences(values):
    root = ElementTree.Element("map")
    for name, value in values.items():
        if isinstance(value, bool):
            ElementTree.SubElement(root, "boolean", name=name, value=str(value).lower())
        else:
            ElementTree.SubElement(root, "string", name=name).text = value
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def official_state(device, uid, nonce):
    # Keep the old app stopped after seeding to distinguish unintended writes
    # from the old app's own normal catalog and session maintenance.
    device.start(OFFICIAL, "WindowHomeActivity")
    deadline = time.monotonic() + 20
    while not device.private_exists(OFFICIAL, CATALOG):
        require(time.monotonic() < deadline, "Old app did not create its real environment catalog")
        time.sleep(0.4)
    device.stop(OFFICIAL)
    marker = ("synthetic-old-data-" + nonce).encode()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "sentinel.db"
        with sqlite3.connect(path) as database:
            database.execute("CREATE TABLE fixture_data (value TEXT NOT NULL)")
            database.execute("INSERT INTO fixture_data VALUES (?)", (marker.decode(),))
        sentinels = {
            "shared_prefs/coexistence_fixture.xml": preferences({"fixture": marker.decode()}),
            "databases/coexistence_fixture.db": path.read_bytes(),
            "files/coexistence-fixture.bin": marker + b"\x00\xff",
            "no_backup/coexistence-fixture.bin": marker + b"\xff\x00",
        }
    for name, payload in sentinels.items():
        device.write_private(OFFICIAL, uid, name, payload)
        require(device.private_bytes(OFFICIAL, name) == payload, f"Fixture write did not read back: {name}")
    catalog = device.private_bytes(OFFICIAL, CATALOG)
    require(catalog.startswith(b"SQLite format 3\x00"), "Old app catalog lacks a real SQLite header")
    sentinels[CATALOG] = catalog
    for suffix in ("-wal", "-shm"):
        if device.private_exists(OFFICIAL, CATALOG + suffix):
            sentinels[CATALOG + suffix] = device.private_bytes(OFFICIAL, CATALOG + suffix)
    return sentinels


class Fixture(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, nonce):
        self.host = f"pocketchat-coexist-{nonce}.invalid"
        self.authority = f"{self.host}:{ORIGIN_PORT}"
        self.origin = f"http://{self.authority}"
        self.pages = {name: Event() for name in ("gecko", "chromium")}
        self.proofs = {name: {} for name in self.pages}
        self.received = {name: Event() for name in self.pages}
        self.nonce = nonce
        self.cold_gecko_state = None
        self.gecko_navigation_retried = False
        self.gecko_timezone_ui = []
        self._lock = Lock()
        self._events = Counter()
        super().__init__(("127.0.0.1", 0), Handler)

    def url(self, name):
        return f"{self.origin}/{name}/{self.nonce}"

    def record(self, event):
        with self._lock:
            self._events[event] += 1

    def counts(self):
        with self._lock:
            return dict(self._events)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.server.record("proxyConnections")

    def log_message(self, *_args):
        pass

    def answer(self, code, payload=b""):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_CONNECT(self):
        if self.path != self.server.authority:
            self.server.record("rejectedConnects")
            if self.path == "ipwho.is:443":
                self.server.record("ipTimezoneConnectRejected")
            self.answer(403)
            return
        self.server.record("fixtureConnects")
        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.wfile.flush()
        self.connection.settimeout(12)
        self.handle_one_request()
        self.close_connection = True

    def do_GET(self):
        fixture = self.server
        address = urlsplit(self.path)
        if self.headers.get("Host") != fixture.authority or address.netloc not in ("", fixture.authority):
            fixture.record("rejectedRequests")
            self.answer(403)
            return
        fixture.record("fixtureRequests")
        for engine in fixture.pages:
            page = f"/{engine}/{fixture.nonce}"
            if address.path == page and not address.query:
                heading = f"PocketChat-{engine}-{fixture.nonce}"
                payload = f'''<!doctype html><meta charset=utf-8><title>{heading}</title><h1>{heading}</h1>
<script>requestAnimationFrame(() => requestAnimationFrame(() => {{
const visible = document.visibilityState === 'visible' &&
  document.querySelector('h1').getBoundingClientRect().width > 0 && document.querySelector('h1').textContent === document.title;
fetch('{page}/proof?' + new URLSearchParams({{
  build: navigator.productSub, visible: String(visible), title: document.title, ua: navigator.userAgent
}}));
}}));</script>'''
                fixture.pages[engine].set()
                self.answer(200, payload.encode())
                return
            if address.path == page + "/proof":
                fields = parse_qs(address.query)
                if all(len(fields.get(field, [])) == 1 for field in ("build", "visible", "title", "ua")):
                    fixture.proofs[engine].update({name: fields[name][0] for name in ("build", "visible", "title", "ua")})
                    fixture.received[engine].set()
                    self.answer(200)
                    return
        self.answer(404)


@contextmanager
def local_fixture(device, nonce):
    with Fixture(nonce) as server:
        remote = f"tcp:{server.server_port}"
        device.call("reverse", "--no-rebind", remote, remote)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield server
        finally:
            server.shutdown()
            worker.join(timeout=5)
            device.call("reverse", "--remove", remote, check=False)


def run_engine(device, uid, fixture, engine):
    device.stop(PARALLEL)
    settings = {
        "environmentInitialized": True, "pageMode": True, "networkConfigured": True,
        "networkMode": "external", "requireExternalVpn": False, "autoHistory": False,
        "proxy": f"http://127.0.0.1:{fixture.server_port}", "browserHomeUrl": fixture.url(engine),
        "browserStartScreen": "chromium" if engine == "chromium" else "chatgpt-enhanced",
    }
    device.write_private(PARALLEL, uid, "shared_prefs/chat.xml", preferences(settings))
    device.start(PARALLEL, "MainActivity", fixture.url(engine))
    arrived = fixture.received[engine].wait(60)
    if engine == "gecko" and not arrived and not fixture.pages[engine].is_set():
        cold = gecko_failure_state(device, fixture)
        fixture.cold_gecko_state = cold
        # A general website failure can occur before the optional IP time-zone
        # lookup sends a proxy request. The offline fixture always selects the
        # app's system time zone after observing an unloaded native browser.
        if cold.get("mainActivityResumed") and cold.get("geckoLibraryMapped"):
            select_system_timezone(device, fixture)
            # Retry through the same normal route and require a fresh renderer proof.
            fixture.gecko_navigation_retried = True
            device.start(PARALLEL, "MainActivity", fixture.url(engine))
            arrived = fixture.received[engine].wait(45)
    require(arrived, f"No visible-page JavaScript proof from {engine}")
    proof = fixture.proofs[engine]
    require(fixture.pages[engine].is_set() and proof["visible"] == "true" and
            proof["title"] == f"PocketChat-{engine}-{fixture.nonce}", f"Page proof differs for {engine}")
    expected = "20100101" if engine == "gecko" else "20030107"
    require(proof["build"] == expected, f"Renderer productSub differs for {engine}")
    if engine == "chromium":
        active = device.shell("dumpsys", "activity", "activities")
        require(re.search(r"(?:mResumedActivity|topResumedActivity).*local[.]pocketchat[.]parallel/"
                          r"(?:local[.]pocketchat)?[.]CefriumBrowserActivity\b", active),
                "Rendered page did not belong to the independent Cefrium activity")
        process = device.shell("pidof", PARALLEL).split()
        require(len(process) == 1 and process[0].isdigit(), "Cefrium main process was not uniquely identified")
        maps = device.call("shell", "cat", f"/proc/{process[0]}/maps", check=False)
        require(maps.returncode == 0 and re.search(rb"(?:libcef[.]so|split_chromium[.]apk)(?:[\s!]|$)", maps.stdout),
                "Native split library mapping could not be read from the independent main process")
        proof["nativeSplitMapped"] = True
    proof["receivedPage"] = True
    return proof


def gecko_failure_state(device, fixture):
    evidence = {"proxyCounts": fixture.counts()}
    try:
        activities = device.shell("dumpsys", "activity", "activities")
        evidence["mainActivityResumed"] = any(
            re.search(r"local[.]pocketchat[.]parallel/(?:local[.]pocketchat)?[.]MainActivity\b", line)
            for line in activities.splitlines() if "ResumedActivity" in line)
        processes = device.shell("ps", "-A", "-o", "PID,NAME").splitlines()
        main = []
        for line in processes:
            columns = line.split()
            if len(columns) == 2 and columns[0].isdigit() and columns[1] == PARALLEL:
                main.append(columns[0])
        evidence["mainProcessRunning"] = len(main) == 1
        evidence["geckoChildProcessCount"] = sum(
            bool(re.search(r"\blocal[.]pocketchat[.]parallel:(?:gecko_env\d+_|[^\s]*ChildProcess)", line, re.I))
            for line in processes)
        if len(main) == 1:
            maps = device.call("shell", "cat", f"/proc/{main[0]}/maps", check=False)
            evidence["geckoLibraryMapped"] = (bool(re.search(rb"lib(?:xul|mozglue)[.]so\b", maps.stdout))
                                               if maps.returncode == 0 else None)
            log = device.call("logcat", "-d", "--pid", main[0], "-b", "main", "-t", "700", "-v", "brief",
                              "GeckoRuntime:V", "GeckoSession:V", "GeckoThread:V", "GeckoConsole:V", "AndroidRuntime:V",
                              "*:S", timeout=6, check=False).stdout.decode(errors="replace")
            evidence["nativeLogTags"] = dict(Counter(re.findall(
                r"^[A-Z]/(GeckoRuntime|GeckoSession|GeckoThread|GeckoConsole|AndroidRuntime)\b", log, re.M)))
            evidence["runtimeMarkers"] = [name for name, words in (
                ("zygoteOrChildBindingError", r"(?:bindService|child process|ChildProcess).*(?:failed|fail|denied|exception)"),
                ("extensionError", r"(?:extension|pocketroute).*(?:error|failure|exception)"),
                ("nativeLinkError", r"UnsatisfiedLinkError|dlopen failed"),
                ("sdkManifestReadError", r"pocketchat-sdk-build(?:-receipt)?[.]json"),
                ("applicationFatalException", r"FATAL EXCEPTION")) if re.search(words, log, re.I)]
    except (OSError, RuntimeError, subprocess.SubprocessError):
        evidence["processSnapshotUnavailable"] = True
    try:
        nodes = parallel_ui_nodes(device, fixture.nonce)
        labels = [text for node in nodes for text in (node.get("text", ""), node.get("content-desc", ""))]
        evidence["visibleStates"] = [name for name, phrase in GECKO_VISIBLE_STATES.items()
                                     if any(phrase in value for value in labels)]
        evidence["parallelUiNodeCount"] = len(nodes)
    except (OSError, RuntimeError, subprocess.SubprocessError, ElementTree.ParseError):
        evidence["uiSnapshotUnavailable"] = True
    return evidence


def parallel_ui_nodes(device, nonce):
    path = f"/data/local/tmp/pocketchat-coexist-ui-{nonce}.xml"
    try:
        device.call("shell", "uiautomator", "dump", path, timeout=10)
        raw = device.call("exec-out", "cat", path, timeout=5).stdout
        tree = ElementTree.fromstring(raw)
        return [node for node in tree.iter("node") if node.get("package") == PARALLEL]
    finally:
        try:
            device.call("shell", "rm", "-f", path, timeout=4, check=False)
        except (OSError, subprocess.SubprocessError):
            pass


def find_control(nodes, label, *, contains=False):
    positions = set()
    for node in nodes:
        text = (node.get("text", ""), node.get("content-desc", ""))
        if not (any(label in value for value in text) if contains else label in text):
            continue
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
        if match is None:
            continue
        left, top, right, bottom = map(int, match.groups())
        if right > left and bottom > top and node.get("enabled") != "false":
            positions.add(((left + right) // 2, (top + bottom) // 2))
    require(len(positions) <= 1, f"Ambiguous Android control: {label}")
    return next(iter(positions), None)


def select_system_timezone(device, fixture):
    """Select the environment's real system-zone setting without a network exception."""
    device.start(PARALLEL, "MainActivity", edit_environment=True)
    screen = device.shell("wm", "size")
    sizes = re.findall(r"(?:Physical|Override) size: (\d+)x(\d+)", screen)
    require(sizes, "Android screen dimensions are unavailable")
    width, height = map(int, sizes[-1])

    def observe(label, *, tap=True, scroll=False, contains=False):
        deadline = time.monotonic() + 20
        remaining_scrolls = 3 if scroll else 0
        while time.monotonic() < deadline:
            try:
                nodes = parallel_ui_nodes(device, fixture.nonce)
            except (OSError, RuntimeError, subprocess.SubprocessError, ElementTree.ParseError):
                time.sleep(0.25)
                continue
            position = find_control(nodes, label, contains=contains)
            if position is not None:
                if tap:
                    device.shell("input", "tap", *position)
                fixture.gecko_timezone_ui.append(label)
                return
            if remaining_scrolls and any(node.get("scrollable") == "true" for node in nodes):
                scroller = next(node for node in nodes if node.get("scrollable") == "true")
                region = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", scroller.get("bounds", ""))
                if region:
                    left, top, right, bottom = map(int, region.groups())
                    x = min(width - 1, (left + right) // 2)
                    y = min(height - 1, bottom)
                    if y - top >= 80:
                        device.shell("input", "swipe", x, top + (y - top) * 4 // 5, x, top + (y - top) // 5, 380)
                remaining_scrolls -= 1
            time.sleep(0.25)
        raise RuntimeError(f"Android timezone control did not become visible: {label}")

    observe("浏览器")
    observe("环境模板与生效状态", scroll=True)
    observe("此环境的独立时区", scroll=True)
    observe("此环境时区模式")
    observe("跟随系统时区")
    observe("应用并重新加载")
    observe("已保存输入，应用")
    observe("已保存：跟随系统时区", tap=False, contains=True)
    for _ in range(3):
        device.shell("input", "keyevent", "KEYCODE_BACK")


def run(args, report):
    device = Device(args.adb, args.serial)
    device.prepare()
    report["device"] = dict(api=33, abi="x86_64", rootAdb=True, disposableEmulator=True)
    old_apks = [args.baseline_apk]
    if args.baseline_chromium_apk is not None:
        old_apks.append(args.baseline_chromium_apk)
    device.install(*old_apks)
    old = device.package_info(OFFICIAL, 116)
    nonce = secrets.token_hex(10)
    snapshots = official_state(device, old["uid"], nonce)
    try:
        device.install(args.parallel_base_apk, args.parallel_chromium_apk)
        new = device.package_info(PARALLEL, 117)
        current_old = device.package_info(OFFICIAL, 116)
        require(old["uid"] == current_old["uid"] != new["uid"] and old["dataRoot"] != new["dataRoot"],
                "The two installed applications do not have separate Android identities")
        old_has_split = args.baseline_chromium_apk is not None
        require(old["splitCount"] == current_old["splitCount"] == len(old_apks)
                and old["chromiumSplit"] == current_old["chromiumSplit"] == old_has_split
                and new["splitCount"] == 2 and new["chromiumSplit"],
                "Installed old and independent split inventories differ from the supplied APKs")
        report["checks"]["packageIdentity"] = {"status": "pass", OFFICIAL: current_old, PARALLEL: new}
        before = current_old["authorities"]
        after = new["authorities"]
        require(before == old["authorities"] and before.keys().isdisjoint(after), "Installed provider authorities overlap")
        old_required = SHARED_AUTHORITIES | {"app-updates"}
        if old_has_split:
            old_required.add("cefrium-setup")
        for package, authorities, required in ((OFFICIAL, before, old_required),
                                                (PARALLEL, after, SHARED_AUTHORITIES | {"cefrium-setup"})):
            require(all(authorities.get(f"{package}.{name}") == package for name in required),
                    f"Installed authority owner differs for {package}")
            require(all(owner == package and name.startswith(package + ".") for name, owner in authorities.items()),
                    f"A provider belongs to a different application namespace for {package}")
        require(f"{PARALLEL}.app-updates" not in after, "Parallel provider unexpectedly offers official updates")
        report["checks"]["providerIsolation"] = {"status": "pass", "oldAuthorities": len(before),
                                                   "parallelAuthorities": len(after)}
        with local_fixture(device, nonce) as fixture:
            for engine, check in (("gecko", "parallelGecko"), ("chromium", "parallelNativeChromium")):
                try:
                    proof = run_engine(device, new["uid"], fixture, engine)
                    report["checks"][check] = dict(status="pass", **proof)
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    report["checks"][check] = dict(status="fail", reason=str(error),
                        servedFixtureDocument=fixture.pages[engine].is_set(),
                        pageJavascriptReceipt=fixture.received[engine].is_set())
                    if engine == "gecko":
                        if fixture.cold_gecko_state is None or fixture.gecko_navigation_retried:
                            report["checks"][check]["failureState"] = gecko_failure_state(device, fixture)
                if engine == "gecko" and fixture.cold_gecko_state is not None:
                    report["checks"][check]["coldNavigation"] = fixture.cold_gecko_state
                    report["checks"][check]["normalNavigationRetried"] = fixture.gecko_navigation_retried
                    report["checks"][check]["timeZoneUi"] = fixture.gecko_timezone_ui
    finally:
        current = {name: device.private_bytes(OFFICIAL, name) for name in snapshots
                   if device.private_exists(OFFICIAL, name)}
        unchanged = current == snapshots
        copied = [name for name in snapshots if "coexistence" in name and device.private_exists(PARALLEL, name)]
        report["checks"]["officialDataIntegrity"] = dict(
            status="pass" if unchanged and not copied else "fail", unchanged=unchanged,
            unexpectedCopies=copied,
            before={name: sha256(payload).hexdigest() for name, payload in snapshots.items()},
            after={name: sha256(payload).hexdigest() for name, payload in current.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--baseline-apk", "--official-base", type=Path, required=True)
    parser.add_argument("--baseline-chromium-apk", type=Path)
    parser.add_argument("--parallel-base-apk", "--base", type=Path, required=True)
    parser.add_argument("--parallel-chromium-apk", "--feature", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema": 1, "scope": "Fresh API 33 x86_64 emulator and synthetic data only",
              "checks": {name: {"status": "incomplete", "reason": "Check did not run"} for name in CHECKS}}
    report["checks"]["portableBackup"]["reason"] = "No Android system document export and decryption proof in this fixture"
    try:
        report["inputs"] = {name: apk_digest(getattr(args, name)) for name in
                            ("baseline_apk", "baseline_chromium_apk", "parallel_base_apk", "parallel_chromium_apk")
                            if getattr(args, name) is not None}
        run(args, report)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    required = CHECKS[:-1]
    report["status"] = "pass" if "error" not in report and all(
        report["checks"][key]["status"] == "pass" for key in required) else "fail"
    report["portableBackupGate"] = "incomplete"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Coexistence {report['status']}; portable backup incomplete. Evidence: {args.output}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
