#!/usr/bin/env python3
"""Operate actual Android source dialogs once per action; verify the detached candidate and library."""
import argparse
import hashlib
import json
import pathlib
import re
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
import sys

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--adb", required=True)
PARSER.add_argument("--serial", default="emulator-5554")
PARSER.add_argument("--expected-apk-sha", default="")
ARGS = PARSER.parse_args()
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from network_ui_route_contract import visible_inactive_route, reveal_modal_action, clipboard_overlay_present
OUT = ROOT / "work/gecko-integration"
OUT.mkdir(parents=True, exist_ok=True)
PACKAGE = "local.pocketchat.test"
ACTIVITY = PACKAGE + "/local.pocketchat.NetworkSourcesUiIntegrationActivity"
UI_CHECKS = []
RUNNER_REPORT = None
ACTION_TRACE = []
CURRENT_COMMAND = "starting"


def adb(*args, binary=False, timeout=35):
    return subprocess.check_output([ARGS.adb, "-s", ARGS.serial, *args], text=not binary, timeout=timeout)


def app_json(name):
    endpoint = {"network-source-ui-state.json": "network-source-ui-state", "network-source-ui-results.json": "network-source-ui"}[name]
    raw = adb("exec-out", "content", "read", "--uri", "content://" + PACKAGE + ".evidence/" + endpoint)
    return json.loads(raw)


def wait_for(read, predicate, description, seconds=65):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            last = read()
        except (subprocess.CalledProcessError, json.JSONDecodeError, ET.ParseError):
            last = None
        if last is not None and predicate(last):
            return last
        try:
            result = app_json("network-source-ui-results.json")
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            result = None
        if result is not None and result.get("status") == "failed":
            raise AssertionError(result)
        time.sleep(.3)
    raise TimeoutError(description + ": " + str(last))


def state():
    return app_json("network-source-ui-state.json")


def command(value):
    global CURRENT_COMMAND
    CURRENT_COMMAND = value
    adb("shell", "am", "start", "-W", "--activity-single-top", "-n", ACTIVITY, "--es", "command", value)
    return wait_for(state, lambda item: item.get("stage") == value, "Activity command " + value, seconds=15)


def xml():
    adb("shell", "uiautomator", "dump", "/sdcard/pocket-source-ui.xml")
    raw = adb("exec-out", "cat", "/sdcard/pocket-source-ui.xml")
    (OUT / "network-source-ui-latest.xml").write_text(raw)
    return ET.fromstring(raw)


def record_action(action, **evidence):
    ACTION_TRACE.append({"sequence": len(ACTION_TRACE) + 1, "command": CURRENT_COMMAND,
                         "action": action, "monotonicSeconds": time.monotonic(),
                         "uiXml": (OUT / "network-source-ui-latest.xml").read_text(), **evidence})
    (OUT / "network-source-ui-action-trace.json").write_text(
        json.dumps(ACTION_TRACE, ensure_ascii=False, indent=2) + "\n")


def bounds(node):
    values = [int(x) for x in re.findall(r"\d+", node.attrib.get("bounds", ""))]
    if len(values) != 4 or values[2] <= values[0] or values[3] <= values[1]:
        raise AssertionError("Invalid visible bounds: " + str(node.attrib))
    return values


def matching(tree, text=None, desc=None, part=None, kind=None):
    return [node for node in tree.iter("node") if
            (text is None or node.attrib.get("text") == text) and
            (desc is None or node.attrib.get("content-desc") == desc) and
            (part is None or part in node.attrib.get("text", "")) and
            (kind is None or kind in node.attrib.get("class", ""))]


def node(text=None, desc=None, part=None, kind=None, index=0):
    tree = wait_for(xml, lambda tree: len(matching(tree, text, desc, part, kind)) > index,
                    "Visible node " + str((text, desc, part, kind, index)), seconds=20)
    return matching(tree, text, desc, part, kind)[index]


def tap(text=None, desc=None, part=None, kind=None, index=0):
    chosen = node(text, desc, part, kind, index)
    left, top, right, bottom = bounds(chosen)
    record_action("tap", selector={"text": text, "description": desc, "part": part,
                                   "kind": kind, "index": index}, node=chosen.attrib,
                  x=(left + right) // 2, y=(top + bottom) // 2)
    adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))


def field_focus_state(tree, description):
    # Android can show spelling suggestions after focusing an existing name.
    # This framework popup becomes the accessible window, hiding the EditText.
    if any(item.attrib.get("resource-id") == "android:id/suggestionWindowContainer"
           for item in tree.iter("node")):
        return "spelling-popup"
    fields = matching(tree, desc=description, kind="EditText")
    return "focused" if len(fields) == 1 and fields[0].attrib.get("focused") == "true" else "waiting"


def fill(description, value):
    chosen = node(desc=description, kind="EditText")
    left, top, right, bottom = bounds(chosen)
    record_action("focus-field", description=description, node=chosen.attrib,
                  x=(left + right) // 2, y=(top + bottom) // 2)
    adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
    focused = wait_for(xml, lambda tree: field_focus_state(tree, description) != "waiting",
                       "Actual focused field " + description, seconds=15)
    if field_focus_state(focused, description) == "spelling-popup":
        record_action("dismiss-spelling-popup", description=description)
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        focused = wait_for(xml, lambda tree: field_focus_state(tree, description) == "focused",
                           "Actual field focus after spelling popup " + description, seconds=15)
    old = matching(focused, desc=description, kind="EditText")[0].attrib.get("text", "")
    if old:
        adb("shell", "input", "keyevent", "123")
        adb("shell", "input", "keyevent", *("67" for _ in old))
    # Only synthetic ASCII values are accepted; quoting prevents shell interpretation of URLs.
    assert value.isascii() and "%" not in value
    adb("shell", "input", "text", shlex.quote(value))
    tree = xml()
    actual = matching(tree, desc=description, kind="EditText")
    record_action("field-value", description=description, expected=value,
                  nodes=[item.attrib for item in actual])
    assert len(actual) == 1 and actual[0].attrib.get("text") == value, (
        "Actual Android field did not receive the one input operation", description,
        value, [item.attrib for item in actual])


def reveal_field(description, title):
    tree = xml()
    for attempt in range(4):
        found = matching(tree, desc=description, kind="EditText")
        if len(found) == 1:
            bounds(found[0])
            return
        assert not found and len(matching(tree, desc=title)) == 1, (description, title)
        containers = [item for item in tree.iter("node")
                      if item.attrib.get("class") == "android.widget.ScrollView"
                      and item.attrib.get("package") == PACKAGE
                      and item.attrib.get("scrollable") == "true"]
        assert len(containers) == 1, ("Expected the actual modal scroll body", title)
        container = containers[0]
        left, top, right, bottom = bounds(container)
        before = [item.attrib for item in matching(container, kind="EditText")]
        x = (left + right) // 2
        start_y, end_y = top + (bottom - top) * 4 // 5, top + (bottom - top) // 5
        assert left < x < right and top < end_y < start_y < bottom
        command = ["shell", "input", "swipe", str(x), str(start_y), str(x), str(end_y), "600"]
        record_action("reveal-field-scroll", description=description, title=title,
                      attempt=attempt + 1, container=container.attrib, beforeFields=before,
                      command=command)
        adb(*command)
        tree = xml()
        after = [item.attrib for item in matching(tree, kind="EditText")]
        before_geometry = [(item.get("content-desc"), item.get("text"), item.get("bounds")) for item in before]
        after_geometry = [(item.get("content-desc"), item.get("text"), item.get("bounds")) for item in after]
        record_action("revealed-field-scroll-state", description=description, afterFields=after,
                      actualVisibleFieldsMoved=before_geometry != after_geometry)
        assert before_geometry != after_geometry, "Actual modal scroll did not move its visible fields"
    found = matching(tree, desc=description, kind="EditText")
    if len(found) == 1:
        bounds(found[0])
        return
    raise AssertionError("Actual modal scroll did not reveal field: " + description)


def reveal_action(text, title):
    wait_for(xml, lambda tree: len(matching(tree, desc=title)) == 1,
             "Actual modal before revealing " + text, seconds=20)
    reveal_modal_action(xml,
                        lambda x1, y1, x2, y2: adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "600"),
                        title, text, PACKAGE,
                        record=lambda **evidence: record_action("reveal-modal-action-scroll", **evidence))


def wait_clipboard_overlay():
    # Android's clipboard preview can consume a tap in the lower left even
    # when uiautomator exposes the underlying app button. Observe its actual
    # WindowManager lifetime; never repeat a missed app action or disable it.
    observations = []
    first = None
    def read():
        nonlocal first
        raw = adb("shell", "dumpsys", "window", "windows")
        present = clipboard_overlay_present(raw, PACKAGE)
        if first is None:
            first = raw
        observations.append({"monotonicSeconds": time.monotonic(), "overlayPresent": present,
                             "sha256": hashlib.sha256(raw.encode()).hexdigest()})
        (OUT / "network-source-ui-clipboard-windows.json").write_text(json.dumps(
            {"firstWindowDump": first, "lastWindowDump": raw, "observations": observations},
            ensure_ascii=False, indent=2) + "\n")
        return present
    wait_for(read, lambda present: not present, "Actual system clipboard overlay closed before one app tap", seconds=30)
    record_action("wait-system-clipboard-overlay", evidence="network-source-ui-clipboard-windows.json",
                  observations=observations)


def assert_fields(expected):
    tree = xml()
    values = {description: [item.attrib for item in matching(tree, desc=description, kind="EditText")]
              for description in expected}
    record_action("save-fields", expected=expected, actual=values)
    assert all(len(values[description]) == 1 and values[description][0].get("text") == value
               for description, value in expected.items()), ("Actual fields changed before save", values)


def check(name, condition):
    UI_CHECKS.append({"name": name, "pass": bool(condition)})
    assert condition, name


def screen(name):
    (OUT / name).write_bytes(adb("exec-out", "screencap", "-p", binary=True))


def centered(title):
    tree = xml()
    heading = matching(tree, desc=title)
    assert len(heading) == 1, title
    parents = {child: parent for parent in tree.iter() for child in parent}
    current = heading[0]
    screen_size = adb("shell", "wm", "size")
    width, height = map(int, re.findall(r"(\d+)x(\d+)", screen_size)[-1])
    found = None
    while current in parents:
        current = parents[current]
        if "bounds" not in current.attrib:
            continue
        rect = bounds(current)
        if width * .6 <= rect[2] - rect[0] < width * .98 and rect[3] - rect[1] > 180:
            found = rect
    check(title + " has a centered phone-width modal surface", found is not None and
          abs((found[0] + found[2]) / 2 - width / 2) < width * .08 and
          abs((found[1] + found[3]) / 2 - height / 2) < height * .13)


def wait_source(role, name, predicate=lambda row: True, seconds=65):
    array = "entries" if role == "entry" else "exits"
    return wait_for(state, lambda item: any(row.get("name") == name and predicate(row)
                                           for row in item[array]), "Source state " + role + "/" + name, seconds)


def add(role, name):
    command("entry-tab" if role == "entry" else "exit-tab")
    tap(text="＋ 添加", index=0)
    centered("添加" + ("入口" if role == "entry" else "出口") + "订阅")
    fill("订阅名称", name)
    fill("订阅地址", "https://127.0.0.1:9/" + name.lower())
    assert_fields({"订阅名称": name, "订阅地址": "https://127.0.0.1:9/" + name.lower()})
    tap(text="保存订阅")
    wait_source(role, name)
    # Publication continues after the user closes the progress dialog.
    tap(desc="关闭读取" + ("入口" if role == "entry" else "出口") + "节点")
    command("assert-" + role + "-added")


def edit_source(role):
    command("open-" + role + "-edit")
    centered("编辑" + ("入口" if role == "entry" else "出口") + "订阅")
    name = "EntryEdited" if role == "entry" else "ExitEdited"
    fill("订阅名称", name)
    fill("订阅地址", "https://127.0.0.1:9/edited-" + role)
    assert_fields({"订阅名称": name, "订阅地址": "https://127.0.0.1:9/edited-" + role})
    tap(text="保存订阅")
    wait_source(role, name)
    tap(desc="关闭读取" + ("入口" if role == "entry" else "出口") + "节点")
    command("assert-" + role + "-edited")


def delete_source(role):
    command("open-" + role + "-detail")
    reveal_action("删除订阅", ("入口" if role == "entry" else "出口") + "订阅详情")
    tap(text="删除订阅")
    centered("删除" + ("入口" if role == "entry" else "出口") + "订阅")
    expected = "1 个窗口" if role == "entry" else "0 个窗口"
    check(role + " deletion shows the actual referencing-window count", expected in node(part=expected).attrib["text"])
    tap(text="删除订阅")
    key = "entries" if role == "entry" else "exits"
    removed = "EntryEdited" if role == "entry" else "ExitEdited"
    wait_for(state, lambda item: all(row.get("name") != removed for row in item[key]), "Deleted " + role)
    command("assert-" + role + "-deleted")


def main():
    global RUNNER_REPORT
    adb("shell", "am", "force-stop", PACKAGE)
    adb("shell", "pm", "clear", PACKAGE)
    adb("logcat", "-c")
    adb("shell", "am", "start", "-W", "-n", ACTIVITY)
    wait_for(state, lambda item: item.get("ready"), "Native provider seed", seconds=100)
    command("window-tab")
    tree = wait_for(xml, lambda tree: visible_inactive_route(tree, "UI Window"),
                    "Saved-only environment is visibly inactive without inventing a running route", seconds=20)
    record_action("inspect-inactive-window-route", environment="UI Window", actualRouteApplication=False,
                  scope="Saved source configuration and UI layout only; no running core", runningSummary="absent")
    check("Saved-only window card does not claim a running entrance-to-exit route", visible_inactive_route(tree, "UI Window"))
    check("Only the three requested network tabs are visible", all(matching(tree, text=text) for text in ("窗口网络", "入口", "出口")) and not matching(tree, text="订阅"))
    command("open-window-details")
    centered("窗口详情 · UI Window")
    for _ in range(4):
        if matching(xml(), text="查看耗时诊断"):
            break
        size = adb("shell", "wm", "size")
        width, height = map(int, re.findall(r"(\d+)x(\d+)", size)[-1])
        adb("shell", "input", "swipe", str(width // 2), str(height * 7 // 10), str(width // 2), str(height * 4 // 10), "350")
    tap(text="查看耗时诊断")
    centered("耗时诊断 · UI Window")
    tap(text="复制诊断")
    node(text="已复制")
    check("Diagnostic copy confirms inline without leaving the dialog", bool(matching(xml(), desc="耗时诊断 · UI Window")))
    command("assert-diagnostics-copied")
    wait_clipboard_overlay()
    tap(text="返回")
    tap(text="关闭")
    command("entry-tab")
    tap(text="EntrySource")
    centered("入口订阅详情")
    check("Entrance detail exposes its own source address", bool(matching(xml(), text="https://127.0.0.1:9/entry")))
    tap(text="关闭")
    command("exit-tab")
    tap(text="ExitSource")
    centered("出口订阅详情")
    check("Exit detail exposes its separate address", bool(matching(xml(), text="https://127.0.0.1:9/exit")))
    tap(text="查看节点 · 3 个")
    centered("出口节点")
    check("Read-only node list displays real SOCKS aliases and unsupported HTTP", all(matching(xml(), text=text) for text in ("Tokyo", "Tokyo Alias", "Unsupported HTTP")))
    tap(text="关闭")
    tap(text="关闭")

    command("open-editor")
    centered("编辑网络 · UI Window")
    wait_for(xml, lambda tree: any(item.attrib.get("enabled") == "true" for item in matching(tree, text="保存并应用")), "Cached legacy source metadata prepared", seconds=45)
    command("assert-legacy-prepared")
    tap(text="固定出口")
    tap(text="ExitSource")
    centered("选择固定出口节点")
    tap(text="Unsupported HTTP")
    check("Unsupported protocol remains visibly unselectable", bool(matching(xml(), part="当前出口链支持 SOCKS5")))
    tap(text="确定")
    node(part="请选择一个有效的 SOCKS5")
    command("assert-unselected")
    tap(text="Tokyo Alias")
    tap(text="取消")
    command("assert-cancelled-picker")
    tap(text="固定出口")
    tap(text="ExitSource")
    tap(text="Tokyo Alias")
    tap(text="确定")
    node(part="ExitSource · Tokyo Alias")
    command("assert-selected-alias")
    tap(text="取消")
    command("assert-editor-cancelled")

    add("entry", "AddedEntry")
    add("exit", "AddedExit")
    edit_source("entry")
    edit_source("exit")
    for role, name in (("entry", "EntryEdited"), ("exit", "ExitEdited")):
        wait_source(role, name, lambda row: not row["updating"] and bool(row["lastError"]), seconds=90)
        command("assert-" + role + "-failed")
        command("open-" + role + "-detail")
        check(role + " failure is visible in the actual detail dialog", bool(matching(xml(), part="更新失败")))
        tap(text="关闭")

    command("open-manual-detail")
    reveal_action("编辑出口", "出口详情")
    tap(text="编辑出口")
    centered("编辑固定出口")
    fill("出口名称", "ManualEdited")
    reveal_field("端口", "编辑固定出口")
    fill("端口", "19121")
    tap(text="保存出口")
    wait_for(state, lambda item: item["manual"].get("port") == 19121, "Edited manual exit")
    command("assert-manual-edited")
    delete_source("entry")
    delete_source("exit")
    command("open-manual-detail")
    reveal_action("删除出口", "出口详情")
    tap(text="删除出口")
    centered("删除固定出口")
    check("Manual deletion includes its referencing window", "1 个窗口" in node(part="1 个窗口").attrib["text"])
    tap(text="删除出口")
    wait_for(state, lambda item: not item["manual"], "Deleted manual exit")
    command("assert-manual-deleted")
    adb("shell", "am", "start", "-W", "--activity-single-top", "-n", ACTIVITY, "--es", "command", "finish")
    report = wait_for(lambda: app_json("network-source-ui-results.json"), lambda item: item.get("status") in ("passed", "failed"), "UI result", seconds=20)
    report["sourceCommit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    path = adb("shell", "pm", "path", PACKAGE).strip().removeprefix("package:")
    process = subprocess.Popen([ARGS.adb, "-s", ARGS.serial, "exec-out", "cat", path], stdout=subprocess.PIPE)
    digest = hashlib.sha256()
    while True:
        chunk = process.stdout.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    assert process.wait(timeout=35) == 0, "Could not read the actual installed APK"
    report["installedApkSha256"] = digest.hexdigest()
    report["installedPackage"] = PACKAGE
    report["touchUiChecks"] = UI_CHECKS
    report["touchUiCheckCount"] = len(UI_CHECKS)
    RUNNER_REPORT = report
    report["actualAdbTouchExecution"] = True
    (OUT / "network-source-ui-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    assert report["status"] == "passed" and report["checkCount"] == len(report["checks"]) == 85
    assert len(UI_CHECKS) == 27 and all(item["pass"] for item in report["checks"] + UI_CHECKS)
    assert report["actualAndroidExecution"] and report["actualNativeExecution"] and report["actualKeystoreEncryption"] and not report["actualRouteApplication"]
    if ARGS.expected_apk_sha:
        assert report["installedApkSha256"] == ARGS.expected_apk_sha, "Installed integration APK differs from the build receipt"
    screen("network-source-ui-screen.png")
    print(json.dumps({"status": "passed", "androidChecks": report["checkCount"], "touchUiChecks": len(UI_CHECKS)}, ensure_ascii=False))


try:
    main()
except BaseException as failure:
    (OUT / "network-source-ui-failure-log.txt").write_text(adb("logcat", "-d"))
    screen("network-source-ui-screen.png")
    try:
        report = RUNNER_REPORT if RUNNER_REPORT is not None else app_json("network-source-ui-results.json")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        try:
            partial = state()
            (OUT / "network-source-ui-failure-state.json").write_text(json.dumps(partial, ensure_ascii=False, indent=2) + "\n")
            report = {"checks": partial.get("checks", []), "checkCount": partial.get("checkCount", 0),
                      "stage": partial.get("stage"), "partialAndroidEvidence": True}
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            report = {"checks": [], "checkCount": 0}
    try:
        xml()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ET.ParseError):
        pass
    report["androidStatus"] = report.get("status", "no-result")
    report["status"] = "failed"
    report["runnerFailure"] = type(failure).__name__ + ": " + str(failure)
    report["touchUiChecks"] = UI_CHECKS
    report["touchUiCheckCount"] = len(UI_CHECKS)
    (OUT / "network-source-ui-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    raise
