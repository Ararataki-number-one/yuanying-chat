"""Actual address-dialog controller against measured Android readback inputs.

The XML files are original S06/API35 artifacts. The JVM widget adapter models
layout events and measured heights; it is not Android rendering or IME proof.
The production source separately compiles against the real Android API jar.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / 'app/src/main/java/local/pocketchat/GeckoAddressUi.java'
FIXTURES = ROOT / 'tests/gecko-address-dialog-host'


def member(source, marker):
    start = source.index(marker)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
        end += 1
    return source[start:end]


class AddressDialogLayoutTest(unittest.TestCase):
    def test_original_api35_ime_resize_proves_input_is_completely_clipped(self):
        before = (FIXTURES / 'api35-landscape-before-ime-resize.xml').read_bytes()
        clipped = (FIXTURES / 'api35-landscape-ime-clipped.xml').read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), '286f81c5ece8ece84e7e0e75b2991bb92ff60a2e2d01c227f7f719efedc71b1e')
        self.assertEqual(hashlib.sha256(clipped).hexdigest(), '73d5592901f025e2be58cab444848e9711b122abf38a1b671fbc180c8f8006ec')
        old = list(ET.fromstring(before).iter('node'))
        rows = list(ET.fromstring(clipped).iter('node'))
        self.assertEqual(sum(n.get('class') == 'android.widget.EditText' for n in old), 1)
        self.assertEqual(sum(n.get('class') == 'android.widget.EditText' for n in rows), 0)
        def height(resource):
            node = next(n for n in rows if n.get('resource-id') == 'android:id/' + resource)
            import re
            x0, y0, x1, y1 = map(int, re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds')).groups())
            return y1 - y0
        self.assertEqual([height(n) for n in ('parentPanel', 'topPanel', 'customPanel', 'buttonPanel')], [381, 142, 71, 168])
        self.assertLess(height('customPanel'), 48 * 3)

    def test_production_controller_short_height_restore_errors_and_cleanup(self):
        source = JAVA.read_text()
        controller = member(source, 'private static final class AddressDialogLayout')
        for prefix in ('android.text.', 'android.graphics.'):
            controller = controller.replace(prefix, '')
        host = (FIXTURES / 'AddressDialogLayoutHost.java').read_text().replace('/* PRODUCTION_CONTROLLER */', controller)
        java_home = os.environ.get('JAVA_HOME', '')
        javac = str(Path(java_home) / 'bin/javac') if java_home and (Path(java_home) / 'bin/javac').is_file() else shutil.which('javac')
        self.assertIsNotNone(javac, 'Set JAVA_HOME or PATH to the installed JDK')
        java = str(Path(javac).with_name('java'))
        with tempfile.TemporaryDirectory(prefix='address-dialog-layout-') as temp:
            path = Path(temp) / 'AddressDialogLayoutHost.java'
            path.write_text(host)
            subprocess.run([javac, '-encoding', 'UTF-8', '-d', temp, str(path)], capture_output=True, text=True, check=True)
            ran = subprocess.run([java, '-cp', temp, 'AddressDialogLayoutHost'], capture_output=True, text=True, check=True)
        result = json.loads(ran.stdout)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['checks'], 43)
        self.assertFalse(result['actualAndroidExecution'])
        self.assertEqual(JAVA.read_text(), source)

    def test_existing_submit_home_ime_and_session_logic_is_not_rewritten(self):
        after = JAVA.read_text()
        retained = json.loads((FIXTURES / 'retained-navigation-handlers.json').read_text())
        self.assertEqual({row['api']: row['measuredHeightPx'] for row in retained['beforeNativeInputObservations']}, {32: 129, 35: 142})
        for row in retained['beforeNativeInputObservations']:
            self.assertEqual(row['bounds'][3] - row['bounds'][1], row['measuredHeightPx'])
            self.assertLess(row['measuredHeightPx'], 144)
        for row in retained['fragments']:
            if 'end' in row:
                start = after.index(row['marker'])
                actual = after[start:after.index(row['end'], start)]
            else:
                actual = member(after, row['marker'])
            self.assertEqual(hashlib.sha256(actual.encode()).hexdigest(), row['sha256'], row['marker'])
        self.assertIn('new TextView(builder.getContext(),null,android.R.attr.windowTitleStyle)', after)
        self.assertLess(after.index('dialog.show();'), after.index('AddressDialogLayout.ensureTouchTarget(input,a.dp(48));'))
        controller = member(after, 'private static final class AddressDialogLayout')
        for forbidden in ('setTextSize(', 'setTextColor(', 'setMinHeight(0)', 'setMinimumHeight(0)',
                          'postDelayed', 'Choreographer', 'Timer', 'inputRow.removeView(input)', 'box.removeView(input)'):
            self.assertNotIn(forbidden, controller)


if __name__ == '__main__':
    unittest.main()
