"""Run the production Gecko window-selection methods on explicit JVM boundaries.

The SDK sessions, Activity host and navigation observer are controlled doubles.
These checks prove ownership and callback ordering, not Android/Gecko execution.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT/'app/src/main/java/local/pocketchat'
TEMPLATE = ROOT/'tests/gecko-window-selection-host/SelectionHost.java.in'


def member(source, signature):
    """Extract the complete, unmodified Java member, ignoring braces in comments."""
    if source.count(signature) != 1:
        raise ValueError('Expected one production member: '+signature)
    start = source.index(signature)
    index = source.index('{', start)
    depth = 0
    quote = None
    escaped = line = block = False
    while index < len(source):
        char, pair = source[index], source[index:index+2]
        if line:
            if char == '\n':
                line = False
        elif block:
            if pair == '*/':
                block = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif pair == '//':
            line = True
            index += 1
        elif pair == '/*':
            block = True
            index += 1
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[start:index+1]
        index += 1
    raise ValueError('Unclosed production member: '+signature)


class GeckoWindowSelectionTests(unittest.TestCase):
    def test_actual_window_selection_ownership_reentry_and_retained_documents(self):
        java_home = os.environ.get('JAVA_HOME')
        java = Path(os.environ.get('PROFILE_JAVA') or (str(Path(java_home)/'bin/java') if java_home else '')
                    or shutil.which('java') or '')
        javac = java.with_name('javac')
        self.assertTrue(java.is_file() and javac.is_file(), 'A complete JDK with javac is required')
        web_path = PRODUCTION/'GeckoWebView.java'
        address_path = PRODUCTION/'GeckoAddressUi.java'
        bridge_path = PRODUCTION/'BrowserBridgeRequests.java'
        inputs = (web_path, address_path, bridge_path, TEMPLATE, Path(__file__).resolve())
        before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
        browser, address = web_path.read_text(), address_path.read_text()
        signatures = (
            '  private boolean navigationCurrent(',
            '  private boolean activationCurrent(',
            '  static final class BrowserWindow {',
            '  private boolean browserWindowOpen(',
            '  List<BrowserWindow> browserWindows()',
            '  private boolean browserWindowOwned(',
            '  boolean selectBrowserWindow(',
            '  private void activate(',
        )
        methods = '\n\n'.join(member(browser, signature) for signature in signatures)
        host = TEMPLATE.read_text().replace('/* ACTUAL_WEB_MEMBERS */', methods).replace(
            '/* ACTUAL_HOST_AVAILABILITY */', member(address, '  static boolean available('))
        with tempfile.TemporaryDirectory(prefix='gecko-window-selection-') as directory:
            work = Path(directory)
            source = work/'SelectionHost.java'
            source.write_text(host)
            compiled = subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', str(work),
                str(bridge_path), str(source)], capture_output=True, text=True, timeout=45)
            self.assertEqual(compiled.returncode, 0, compiled.stdout+compiled.stderr)
            executed = subprocess.run([str(java), '-cp', str(work), 'local.pocketchat.SelectionHost'],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(executed.returncode, 0, executed.stdout+executed.stderr)
            report = json.loads(executed.stdout)
            self.assertEqual(report['status'], 'passed')
            self.assertGreaterEqual(report['checks'], 70)
            self.assertFalse(report['actualAndroidExecution'])
            self.assertFalse(report['actualGeckoExecution'])
        self.assertEqual(before, {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
                         'Production and host inputs changed during actual method execution')
        report.update(sourceSha256=before, actualProductionMethodExecution=True,
            scope='Verbatim Gecko window ownership/list/selection/activation and Activity availability methods, '
                  'plus the complete production BrowserBridgeRequests class. Explicit JVM session, surface, '
                  'host, navigation and client boundary doubles; no Android rendering, SDK session or network acceptance.')
        output = os.environ.get('GECKO_WINDOW_SELECTION_REPORT')
        if output:
            Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
