"""UI-only acceptance of the unchanged diagnostics APK on a fresh official AVD.

The caller owns APK installation, launcher startup and a network namespace with
only loopback. No test Activity, run-as, private preferences, account, certificate
installation, system trust changes or AI submission is used here. The caller must
start the deny-by-default synthetic proxy before invoking exercise(). All records
are fixed markers; hierarchy contents, input values and evidence are not logged.
"""
import json
import re
import time
import uuid
import xml.etree.ElementTree as ET

PACKAGE = "local.pocketchat.aidiagnostics"
ENVIRONMENT = "AI-synthetic"
PAGE_URL = "https://gecko-failure.test/"
GATEWAY_URL = "https://gateway-failure.test/v1/diagnose"
SYNTHETIC_TOKEN = "local-synthetic-token-0000000000000001"


class UiBlocked(RuntimeError):
    """Only fixed diagnostics, never observed UI text or command output."""


def _bounds(node):
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if not match:
        raise UiBlocked("missing-control-bounds")
    x1, y1, x2, y2 = map(int, match.groups())
    if x2 <= x1 or y2 <= y1:
        raise UiBlocked("empty-control-bounds")
    return x1, y1, x2, y2


def _nodes(tree, *, text=None, desc=None, cls=None, prefix=None):
    return [node for node in tree.iter("node")
            if node.get("package") == PACKAGE
            and node.get("visible-to-user") != "false"
            and node.get("enabled") != "false"
            and (text is None or node.get("text") == text)
            and (desc is None or node.get("content-desc") == desc)
            and (cls is None or node.get("class") == cls)
            and (prefix is None or node.get("content-desc", "").startswith(prefix))]


def _target(tree, selector, *, actionable=False):
    found = _nodes(tree, **selector)
    if actionable:
        parents = {child: node for node in tree.iter() for child in node}
        targets = []
        for node in found:
            while node is not None and node.get("clickable") != "true":
                node = parents.get(node)
            if node is not None and node.get("package") == PACKAGE and node not in targets:
                targets.append(node)
        found = targets
    if len(found) > 1:
        raise UiBlocked("ambiguous-control")
    return found[0] if found else None


class _Ui:
    def __init__(self, adb):
        self.adb = adb
        self.deadline = time.monotonic() + 420
        self.remote = "/sdcard/ai-diagnostic-ui-" + uuid.uuid4().hex + ".xml"

    def call(self, *args, timeout=15):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise UiBlocked("overall-ui-deadline")
        # Caller may retain command metadata, but must not log returned XML.
        try:
            return self.adb(*args, timeout=min(timeout, remaining))
        except Exception:
            raise UiBlocked("adb-ui-command-failed") from None

    def tree(self):
        # Remove only our own generated previous dump. A failed dump can never
        # be satisfied by stale hierarchy bytes from another screen.
        self.call("shell", "rm", "-f", self.remote)
        result = self.call("shell", "uiautomator", "dump", self.remote, timeout=18)
        if "ERROR:" in result or "dumped to: " + self.remote not in result:
            return None
        raw = self.call("shell", "cat", self.remote)
        if len(raw) > 1000000:
            raise UiBlocked("hierarchy-too-large")
        try:
            tree = ET.fromstring(raw)
        except ET.ParseError:
            raise UiBlocked("invalid-hierarchy") from None
        if tree.tag != "hierarchy":
            raise UiBlocked("invalid-hierarchy-root")
        return tree

    def wait(self, predicate, *, timeout=45):
        end = min(self.deadline, time.monotonic() + timeout)
        while time.monotonic() < end:
            tree = self.tree()
            if tree is not None:
                value = predicate(tree)
                if value is not None and value is not False:
                    return tree, value
            time.sleep(.15)
        raise UiBlocked("expected-ui-state-not-observed")

    def seen(self, text, *, timeout=45):
        return self.wait(lambda tree: _target(tree, {"text": text}), timeout=timeout)[0]

    def tap(self, *, hold=False, scroll=False, **selector):
        # Scroll only a currently observed native ScrollView, never the website.
        for attempt in range(5 if scroll else 1):
            try:
                tree, node = self.wait(lambda tree: _target(tree, selector, actionable=True),
                                       timeout=8 if scroll else 45)
                break
            except UiBlocked as error:
                if not scroll or str(error) != "expected-ui-state-not-observed" or attempt == 4:
                    raise
                tree = self.tree()
                scrollers = [] if tree is None else [node for node in _nodes(tree)
                    if node.get("class") == "android.widget.ScrollView"
                    and node.get("scrollable") == "true"]
                if len(scrollers) != 1:
                    raise UiBlocked("native-scroll-target-unavailable")
                x1, y1, x2, y2 = _bounds(scrollers[0])
                x, start, end = (x1 + x2) // 2, y1 + (y2-y1)*3//4, y1 + (y2-y1)//4
                self.call("shell", "input", "touchscreen", "swipe", str(x), str(start), str(x), str(end), "300")
        x1, y1, x2, y2 = _bounds(node)
        x, y = (x1+x2)//2, (y1+y2)//2
        if hold:
            if node.get("long-clickable") != "true":
                raise UiBlocked("long-click-not-exposed")
            self.call("shell", "input", "touchscreen", "swipe", str(x), str(y), str(x), str(y), "900")
        else:
            self.call("shell", "input", "tap", str(x), str(y))

    def fill(self, description, value, *, password=False):
        if not re.fullmatch(r"[A-Za-z0-9:/._~-]{1,256}", value):
            raise UiBlocked("non-synthetic-input")
        selector = {"desc": description, "cls": "android.widget.EditText"}
        tree, node = self.wait(lambda tree: _target(tree, selector))
        old_length = len(node.get("text", ""))
        if old_length > 256:
            raise UiBlocked("unexpected-field-size")
        self.tap(**selector)
        # MOVE_END collapses select-all; bounded native DEL events replace the
        # field without clipboard access, IME plugins or shell metacharacters.
        self.call("shell", "input", "keyevent", "KEYCODE_MOVE_END", *(["KEYCODE_DEL"] * old_length))
        self.call("shell", "input", "text", value)
        if not password:
            self.wait(lambda tree: any(node.get("text") == value for node in _nodes(tree, **selector)))

    def hide_keyboard(self):
        shown = r"(?:mInputShown|mIsInputViewShown|isInputViewShown)=true\b"
        if re.search(shown, self.call("shell", "dumpsys", "input_method")):
            self.call("shell", "input", "keyevent", "KEYCODE_BACK")

    def check_tab(self, label):
        def item(tree):
            node = _target(tree, {"text": label})
            return node if node is not None and node.get("checkable") == "true" else None

        _, node = self.wait(item)
        if node.get("checked") != "true":
            x1, y1, x2, y2 = _bounds(node)
            self.call("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
            self.wait(lambda tree: any(n.get("checkable") == "true" and n.get("checked") == "true"
                                      for n in _nodes(tree, text=label)))

    def close(self):
        try:
            self.adb("shell", "rm", "-f", self.remote, timeout=5)
        except Exception:
            pass



def _timezone_summary(tree):
    """Only read the fixed native status, never serialize its other contents."""
    status = [node.get("text", "") for node in _nodes(tree, cls="android.widget.TextView")
              if node.get("text", "").startswith("已保存：跟随系统时区\n当前：")]
    if len(status) > 1:
        raise UiBlocked("ambiguous-timezone-status")
    return bool(status), bool(status and "当前会话原生设置已回读" in status[0])


def _system_timezone_preflight(ui, record):
    """Use the product editor on the fresh synthetic environment only.

    Default IP timezone needs a remote IP lookup, which the closed proxy rejects.
    Explicit system mode removes that lookup dependency while retaining the
    product's native setting readback, route, TLS and protection gates.
    """
    environment = "当前环境：" + ENVIRONMENT + "，点按切换环境"
    ui.wait(lambda tree: _target(tree, {"desc": environment}))
    ui.tap(desc="浏览器菜单", cls="android.widget.Button")
    ui.tap(text="编辑当前环境", cls="android.widget.Button", scroll=True)
    ui.seen("编辑 · " + ENVIRONMENT)
    ui.tap(text="浏览器", cls="android.widget.Button")
    ui.tap(text="环境模板与生效状态", cls="android.widget.Button", scroll=True)
    ui.seen("环境模板")
    ui.tap(text="此环境的独立时区", cls="android.widget.Button", scroll=True)
    ui.seen("此环境的独立时区")
    selector = {"desc": "此环境时区模式", "cls": "android.widget.Spinner"}
    ui.wait(lambda tree: _target(tree, selector))
    record("timezone_editor_opened", "passed")
    ui.tap(**selector)

    # Android Spinner list rows can report clickable=false. Require the entire
    # exact four-option native list, then tap only the observed system-mode row.
    options = ("跟随当前出口 IP（默认）", "跟随系统时区", "UTC", "指定 IANA 时区")
    def system_option(tree):
        if not all(_nodes(tree, text=label) for label in options):
            return None
        node = _target(tree, {"text": "跟随系统时区"})
        return node if node is not None and node.get("class") in (
            "android.widget.TextView", "android.widget.CheckedTextView") else None
    _, option = ui.wait(system_option)
    x1, y1, x2, y2 = _bounds(option)
    ui.call("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
    ui.wait(lambda tree: any(_nodes(node, text="跟随系统时区")
                             for node in _nodes(tree, **selector)))
    record("timezone_system_selected", "passed")
    ui.tap(text="应用并重新加载", cls="android.widget.Button")
    tree = ui.seen("应用当前环境时区？")
    if not any(node.get("text", "").startswith("保存为“跟随系统时区”后将重新加载当前网页")
               for node in _nodes(tree, cls="android.widget.TextView")):
        raise UiBlocked("timezone-confirmation-mode-mismatch")
    # This flow has just created the named empty environment; no user document,
    # account, unsaved text or file operation has ever been introduced into it.
    choices = [label for label in ("已保存输入，应用", "应用并重新加载")
               if _nodes(tree, text=label, cls="android.widget.Button")]
    if len(choices) != 1:
        raise UiBlocked("timezone-confirmation-control-unavailable")
    ui.tap(text=choices[0], cls="android.widget.Button")
    record("timezone_apply_confirmed", "passed")
    ui.wait(lambda tree: _timezone_summary(tree)[0], timeout=45)
    record("timezone_system_saved", "passed", "explicit-product-setting-only")
    ui.wait(lambda tree: _timezone_summary(tree)[1], timeout=45)
    record("timezone_native_readback", "passed", "native-setting-readback-not-page-or-worker-proof")
    ui.tap(desc="关闭此环境的独立时区", cls="android.widget.Button")
    ui.seen("环境模板")
    ui.tap(desc="关闭环境模板", cls="android.widget.Button")
    ui.seen("编辑 · " + ENVIRONMENT)
    ui.tap(text="取消", cls="android.widget.Button")
    ui.wait(lambda tree: _target(tree, {"desc": "网页工具", "cls": "android.widget.Button"}))
    ui.wait(lambda tree: _target(tree, {"desc": environment}))
    record("timezone_preflight", "passed")


def _preview(tree, *, configured=False):
    """Read only the explicit native preview TextView, validate, then discard."""
    candidates = [node.get("text", "") for node in _nodes(tree, cls="android.widget.TextView")
                  if "\n本地证据\n" in node.get("text", "")
                  or "\n将发送的证据\n" in node.get("text", "")]
    if len(candidates) != 1:
        raise UiBlocked("preview-text-unavailable")
    content = candidates[0]
    start = content.find("\n{")
    if start < 0:
        raise UiBlocked("preview-json-unavailable")
    try:
        value = json.loads(content[start+1:])
    except (ValueError, TypeError):
        raise UiBlocked("preview-json-invalid") from None
    expected = {"version", "provider", "evidence"} if configured else {"evidence"}
    if type(value) is not dict or set(value) != expected:
        raise UiBlocked("preview-envelope-not-whitelisted")
    if configured and (type(value["version"]) is not int or value["version"] != 1 or value["provider"] != "openai"):
        raise UiBlocked("preview-provider-mismatch")
    evidence = value["evidence"]
    if type(evidence) is not list or len(evidence) != 1:
        raise UiBlocked("preview-selection-mismatch")
    entry = evidence[0]
    if type(entry) is not dict or set(entry) != {
            "schema", "engine", "tabEvidenceId", "scope", "navigationAttribution", "events"}:
        raise UiBlocked("preview-fields-not-whitelisted")
    if (type(entry["schema"]) is not int or entry["schema"] != 1 or entry["engine"] != "GECKO"
            or entry["scope"] != "TAB_CALLBACK_OBSERVATIONS"
            or entry["navigationAttribution"] != "UNKNOWN"
            or type(entry["tabEvidenceId"]) is not str
            or not re.fullmatch(r"T[1-9][0-9]{0,9}", entry["tabEvidenceId"])):
        raise UiBlocked("preview-attribution-invalid")
    events = entry["events"]
    if type(events) is not list or not 1 <= len(events) <= 16:
        raise UiBlocked("native-events-unavailable")
    identifiers = set()
    kinds = {"LOAD_START", "LOCATION_CHANGED", "LOAD_ERROR", "PAGE_STOP_SUCCESS", "PAGE_STOP_FAILURE", "CONTENT_CRASH", "CONTENT_KILL"}
    signals = {"UNKNOWN", "DNS_FAILURE", "TIMEOUT", "CERTIFICATE_REJECTED", "TLS_FAILURE", "CONTENT_CRASH", "CONTENT_KILL"}
    for event in events:
        if type(event) is not dict or set(event) != {"id", "kind", "signal", "code", "category", "elapsedMs"}:
            raise UiBlocked("event-fields-not-whitelisted")
        if (type(event["id"]) is not str or not re.fullmatch(r"E[1-9][0-9]{0,18}", event["id"])
                or event["id"] in identifiers or type(event["kind"]) is not str
                or type(event["signal"]) is not str or event["kind"] not in kinds or event["signal"] not in signals
                or type(event["elapsedMs"]) is not int or not 0 <= event["elapsedMs"] <= 3600000):
            raise UiBlocked("event-values-not-whitelisted")
        identifiers.add(event["id"])
        code, category = event["code"], event["category"]
        if (code is None) != (category is None) or (code is not None and
                (type(code) is not int or type(category) is not int or not 0 <= code <= 2147483647 or not 0 <= category <= 2147483647)):
            raise UiBlocked("native-error-code-invalid")
    # Retain only anonymous validated evidence in memory for equality checks.
    return evidence


def exercise(adb, record, fixture):
    """Operate the already launched fresh APK; return fixed summary flags.

    adb(*args, timeout=seconds) returns CR-free text. record(name, status,
    detail=None) receives fixed markers only. fixture exposes url/proxy_host/
    proxy_port attributes matching the isolated synthetic topology. Optional
    gateway_url must be the fixed synthetic URL; its presence requests opening
    and cancelling the confirmation dialog. This function NEVER presses send.
    """
    if (getattr(fixture, "url", None) != PAGE_URL
            or getattr(fixture, "proxy_host", None) != "10.0.2.2"
            or type(getattr(fixture, "proxy_port", None)) is not int
            or fixture.proxy_port != 37891
            or getattr(fixture, "gateway_url", GATEWAY_URL) != GATEWAY_URL):
        raise UiBlocked("unexpected-fixture-topology")
    ui = _Ui(adb)
    stage = "android_ui"
    checkpoint = "first_launch"
    confirmation = False
    try:
        ui.tap(text="立即进入", cls="android.widget.Button", scroll=True)
        ui.tap(desc="浏览器菜单", cls="android.widget.Button")
        ui.tap(text="管理全部环境", cls="android.widget.Button")
        ui.tap(desc="新建环境", cls="android.widget.Button")
        ui.seen("创建环境")
        ui.fill("环境名称", ENVIRONMENT)
        ui.tap(text="下一步", cls="android.widget.Button")
        ui.tap(text="自己配置网络", cls="android.widget.RadioButton")
        ui.tap(text="下一步", cls="android.widget.Button")
        ui.tap(text="创建并打开", cls="android.widget.Button")
        more = {"desc": ENVIRONMENT + "的更多网络操作", "cls": "android.widget.Button"}
        checkpoint = "environment_created"
        ui.wait(lambda tree: _target(tree, more, actionable=True), timeout=60)
        record("synthetic_environment", "passed")

        # The creation wizard already opened this environment's network page.
        # The isolated deny-all proxy prevents any default startup URL access.
        checkpoint = "environment_network_menu"
        ui.tap(**more)
        checkpoint = "network_mode_menu"
        ui.tap(text="网络方式", cls="android.widget.Button")
        ui.tap(desc="应用专用代理")
        checkpoint = "proxy_editor"
        ui.fill("代理地址", "http://10.0.2.2:37891")
        ui.hide_keyboard()
        ui.tap(text="保存并应用", cls="android.widget.Button")
        checkpoint = "proxy_save_or_apply_decision"
        immediate = "立即切换，可能中断当前任务"
        deferred = "任务结束后自动应用"
        tree, state = ui.wait(lambda tree: (
            "apply" if _nodes(tree, text="选择应用时间")
                and _nodes(tree, text=immediate, cls="android.widget.Button")
                and _nodes(tree, text=deferred, cls="android.widget.Button") else
            "receipt" if _nodes(tree, text="本次保存结果") else
            "invalid" if _nodes(tree, text="填写有效的 HTTP / SOCKS 代理地址") else None),
            timeout=75)
        if state == "invalid":
            raise UiBlocked("synthetic-proxy-address-rejected")
        if state == "apply":
            # Only the freshly created, isolated synthetic environment exists
            # in this flow, with zero existing tasks and no personal accounts.
            ui.tap(text=immediate, cls="android.widget.Button")
            record("synthetic_proxy_apply_confirmed", "passed")
            checkpoint = "proxy_save_receipt"
            tree = ui.seen("本次保存结果", timeout=75)
        if not any(node.get("text", "").startswith(("已应用", "已保存"))
                   for node in _nodes(tree, cls="android.widget.TextView")):
            raise UiBlocked("proxy-save-not-confirmed")
        ui.tap(text="关闭", cls="android.widget.Button")
        record("synthetic_proxy_saved", "passed", "native-form-save-only-route-needs-fixture-receipt")
        # This is the native workspace of the new environment. Its dock
        # switches that same Activity to Gecko without reopening a profile.
        checkpoint = "open_same_environment_browser_dock"
        ui.tap(desc="浏览器", text="浏览器", cls="android.widget.Button")
        checkpoint = "gecko_toolbar"
        ui.wait(lambda tree: _target(tree, {"desc": "网页工具", "cls": "android.widget.Button"}), timeout=60)
        record("gecko_browser_workspace", "passed")
        stage = "timezone_preflight"
        checkpoint = "apply_system_timezone_through_product_ui"
        _system_timezone_preflight(ui, record)
        stage = "android_ui"
        checkpoint = "issue_synthetic_gecko_navigation"
        ui.tap(prefix="当前网址 ", cls="android.widget.Button")
        ui.seen("打开网址")
        ui.fill("网址或搜索", PAGE_URL)
        ui.hide_keyboard()
        ui.tap(text="前往", cls="android.widget.Button")
        checkpoint = "observed_synthetic_address_bar"
        ui.wait(lambda tree: _target(tree, {"prefix": "当前网址 " + PAGE_URL,
                                            "cls": "android.widget.Button"}))
        record("synthetic_address_navigation", "passed")
        checkpoint = "open_ai_from_long_press"
        ui.tap(desc="网页工具", cls="android.widget.Button", hold=True)
        ui.seen("AI 助手 · 浏览器诊断")
        record("android_ui", "passed")

        stage = "redacted_preview"
        # A callback arriving while selecting invalidates the frozen evidence.
        # Reacquire from this same tab at most three times, never accept stale UI.
        proof = None
        for attempt in range(3):
            checkpoint = "tap_choose_tab_evidence"
            ui.tap(text="选择标签页证据", cls="android.widget.Button")
            checkpoint = "await_tab_picker_or_empty_notice"
            tree, state = ui.wait(lambda tree: (
                "selection" if _nodes(tree, text="选择标签页证据（最多 3 个）") else
                "empty" if _nodes(tree, text="当前环境没有可以归属到标签页的原生错误记录。") else None))
            if state == "empty":
                if attempt < 2:
                    time.sleep(3)
                    continue
                raise UiBlocked("no-native-tab-snapshot")
            labels = [node.get("text") for node in _nodes(tree)
                      if re.fullmatch(r"标签页 [1-9][0-9]*", node.get("text", ""))
                      and node.get("checkable") == "true"]
            if len(labels) != 1:
                raise UiBlocked("unexpected-tab-count")
            checkpoint = "toggle_one_native_tab"
            ui.check_tab(labels[0])
            checkpoint = "apply_native_tab_selection"
            ui.tap(text="选入", cls="android.widget.Button")
            checkpoint = "read_the_native_evidence_preview"
            ui.tap(text="预览证据", cls="android.widget.Button")
            tree, state = ui.wait(lambda tree: (
                "preview" if _nodes(tree, text="查看本地诊断证据") else
                "stale" if _nodes(tree, text="标签页发生变化，请重新选择证据。") else None))
            if state == "stale":
                continue
            proof = _preview(tree)
            break
        if proof is None:
            raise UiBlocked("no-stable-native-evidence")
        certificates = [event for event in proof[0]["events"] if event["kind"] == "LOAD_ERROR"
                        and event["signal"] == "CERTIFICATE_REJECTED" and event["code"] is not None]
        native_error = None
        if certificates:
            certificate = certificates[-1]
            native_error = {"code": certificate["code"], "category": certificate["category"],
                            "signal": "CERTIFICATE_REJECTED", "navigationAttribution": "UNKNOWN"}
            record("gecko_certificate_error", "passed", native_error)
        else:
            record("gecko_certificate_error", "unverified", "valid-preview-without-native-certificate-signal")
        checkpoint = "inspect_redacted_local_preview"
        if _nodes(tree, text="确认新请求并发送") or _nodes(tree, text="沿用编号发送"):
            raise UiBlocked("unconfigured-preview-exposed-send")
        record("redacted_preview", "passed", "anonymous-native-fields-only")
        ui.tap(text="关闭", cls="android.widget.Button")
        ui.seen("AI 助手 · 浏览器诊断")

        stage = "confirmation_cancel"
        checkpoint = "configure_synthetic_gateway"
        if hasattr(fixture, "gateway_url"):
            ui.tap(text="配置 AI 网关", cls="android.widget.Button")
            ui.seen("选择 AI 供应商")
            ui.tap(text="继续", cls="android.widget.Button")
            ui.seen("GPT 网关")
            ui.fill("已授权的 HTTPS 网关", GATEWAY_URL)
            ui.fill("本窗口访问令牌", SYNTHETIC_TOKEN, password=True)
            ui.hide_keyboard()
            ui.tap(text="使用", cls="android.widget.Button")
            checkpoint = "confirm_and_close_without_sending"
            ui.tap(text="预览证据", cls="android.widget.Button")
            tree, state = ui.wait(lambda tree: (
                "confirmation" if _nodes(tree, text="确认发送脱敏证据") else
                "route-blocked" if _nodes(tree, text="查看本地诊断证据") else
                "stale" if _nodes(tree, text="标签页发生变化，请重新选择证据。") else None))
            if state == "confirmation":
                if _preview(tree, configured=True) != proof:
                    raise UiBlocked("confirmation-evidence-changed")
                if len(_nodes(tree, text="确认新请求并发送", cls="android.widget.Button")) != 1:
                    raise UiBlocked("confirmation-button-unavailable")
                # Deliberately close; never invoke the actual sending control.
                ui.tap(text="关闭", cls="android.widget.Button")
                ui.seen("AI 助手 · 浏览器诊断")
                confirmation = True
                record("confirmation_cancel", "passed", "confirmation-opened-and-closed-without-send")
            else:
                if state == "route-blocked":
                    ui.tap(text="关闭", cls="android.widget.Button")
                record("confirmation_cancel", "unverified", "protected-route-or-evidence-not-current")
        else:
            record("confirmation_cancel", "unverified", "local-preview-only")
        stage = "assistant_closed"
        checkpoint = "return_to_gecko"
        ui.tap(text="关闭", cls="android.widget.Button")
        ui.wait(lambda tree: _target(tree, {"desc": "网页工具", "cls": "android.widget.Button"}))
        record("assistant_closed", "passed")
        return {"nativeCertificateError": native_error is not None, "redactedPreview": True,
                "confirmationCancelled": confirmation, "submitted": False,
                "nativeError": native_error}
    except UiBlocked as error:
        record(stage, "failed", {"checkpoint": checkpoint, "reason": str(error)})
        raise
    except Exception:
        record(stage, "failed", {"checkpoint": checkpoint, "reason": "unexpected-ui-driver-failure"})
        raise UiBlocked("unexpected-ui-driver-failure") from None
    finally:
        ui.close()
