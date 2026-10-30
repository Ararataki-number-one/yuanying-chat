"""Production clipboard projection and exact copy entrypoints with bounded payloads.

JVM collaborators are explicit doubles; no real clipboard, Android lifecycle,
network attack, ChatGPT document, or phone protection acceptance is executed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / 'app/src/main/java/local/pocketchat'
PINS = {'desktop': '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796',
        'android-json': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}


def member(source, needle):
    start = source.index(needle)
    cursor, depth, quote, line, block = source.index('{', start), 0, None, False, False
    while cursor < len(source):
        c, pair = source[cursor], source[cursor:cursor + 2]
        if line:
            if c == '\n':
                line = False
        elif block:
            if pair == '*/':
                block = False
                cursor += 1
        elif quote:
            if c == '\\':
                cursor += 2
                continue
            if c == quote:
                quote = None
        elif pair == '//':
            line = True
            cursor += 1
        elif pair == '/*':
            block = True
            cursor += 1
        elif c in ('"', "'"):
            quote = c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return source[start:cursor + 1]
        cursor += 1
    raise AssertionError('Incomplete actual production member: ' + needle)


def entry_source(root=ROOT, fixed=True):
    source = (root / 'app/src/main/java/local/pocketchat/EnvironmentAudit.java').read_text()
    request = (root / 'app/src/main/java/local/pocketchat/RequestIdentityAuditSession.java').read_text()
    template = (ROOT / 'tests/audit-diagnostic-export-host/CopyEntrypoints.java.in').read_text()
    methods = {
        '__ADDRESS__': member(source, 'static String address('),
        '__SUMMARY__': member(source, 'String summary(boolean redact)'),
        '__DEEP_COPY__': member(source, 'String deepRecordCopy('),
        '__SAFE_COPY__': member(source, 'String safeCopy('),
        '__REQUEST_SUMMARY__': member(request, 'String summary(boolean redact)'),
        '__DIAGNOSTIC_COPY__': member(source, 'String diagnosticCopy(') if fixed else '',
        '__COMPARISON_DIAGNOSTIC_COPY__': member(source, 'String comparisonDiagnosticCopy(') if fixed else '',
    }
    for marker, code in methods.items():
        if template.count(marker) != 1:
            raise AssertionError('Copy host must include every actual member exactly once')
        template = template.replace(marker, code)
    return template, methods


def execute(java, jar, main, rendered=None, fixed=True):
    with tempfile.TemporaryDirectory(prefix='audit-diagnostic-export-host-') as temp:
        sources = [PROD / name for name in ('J.java', 'AuditReport.java', 'AuditDiagnosticExport.java')]
        if rendered is None:
            sources += [ROOT / 'tests/audit-diagnostic-export-host/AuditDiagnosticExportHost.java']
            # AuditReport's only application dependency in this host is the IP classifier.
            stub = Path(temp) / 'BrowserNetworkGuard.java'
            stub.write_text('package local.pocketchat; final class BrowserNetworkGuard {static boolean localHost(String v){return v.startsWith("127.")||v.equals("::1");}}')
            sources += [stub]
        else:
            source = Path(temp) / 'CopyEntrypoints.java'
            source.write_text(rendered)
            sources += [source]
            if not fixed:
                sources.remove(PROD / 'AuditDiagnosticExport.java')
        compile_run = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                                      '-encoding', 'UTF-8', '-cp', str(jar), '-d', temp, *map(str, sources)],
                                     capture_output=True, text=True, timeout=40)
        if compile_run.returncode:
            raise AssertionError(compile_run.stdout + compile_run.stderr)
        args = [str(fixed).lower()] if rendered is not None else []
        run = subprocess.run([java, '-cp', temp + os.pathsep + str(jar), 'local.pocketchat.' + main, *args],
                             capture_output=True, text=True, timeout=20)
    return dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                compileStdout=compile_run.stdout, compileStderr=compile_run.stderr)


class AuditDiagnosticExportTest(unittest.TestCase):
    def dependencies(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK with jdk.compiler required')
        jars = {'desktop': Path(os.environ.get('PROFILE_JSON_JAR', ROOT / 'work/profile-host/json.jar')),
                'android-json': Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT / 'work/profile-host/android-json.jar'))}
        for runtime, jar in jars.items():
            self.assertTrue(jar.is_file(), 'Pinned JSON dependency required')
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), PINS[runtime])
        return java, jars

    def test_strict_bounded_projection_omits_unknown_and_known_text_fields(self):
        java, jars = self.dependencies()
        runs = []
        for runtime, jar in jars.items():
            observed = execute(java, jar, 'AuditDiagnosticExportHost')
            self.assertEqual(observed['returncode'], 0, observed['stdout'] + observed['stderr'])
            report = json.loads(observed['stdout'])
            self.assertEqual(report['status'], 'passed')
            self.assertGreaterEqual(report['passed'], 100)
            self.assertIs(report['actualClipboardExecution'], False)
            self.assertIs(report['protectionEffectivenessAcceptance'], False)
            runs.append(dict(runtime=runtime, report=report, **observed))
        out = ROOT / 'work/diagnostic45/projection-host-results.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        inputs = [PROD / n for n in ('J.java', 'AuditReport.java', 'AuditDiagnosticExport.java')]
        inputs += [ROOT / 'tests/audit-diagnostic-export-host/AuditDiagnosticExportHost.java', Path(__file__)]
        out.write_text(json.dumps(dict(status='passed', runs=runs, actualAndroidExecution=False, actualClipboardExecution=False,
                                      sourceSha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}), indent=2) + '\n')

    def test_actual_copy_entrypoints_use_projection_without_changing_local_records(self):
        java, jars = self.dependencies()
        rendered, methods = entry_source()
        runs = []
        for runtime, jar in jars.items():
            observed = execute(java, jar, 'CopyEntrypoints', rendered)
            self.assertEqual(observed['returncode'], 0, observed['stdout'] + observed['stderr'])
            self.assertIn('TOTAL 6\n', observed['stdout'])
            self.assertIn('"deepContainsControlledSecret":false', observed['stdout'])
            self.assertIn('"briefContainsControlledSecret":false', observed['stdout'])
            runs.append(dict(runtime=runtime, **observed))
        out = ROOT / 'work/diagnostic45/copy-entrypoint-host-results.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dict(status='passed', runs=runs, actualAndroidExecution=False, actualClipboardExecution=False,
                                      productionMembersSha256={k: hashlib.sha256(v.encode()).hexdigest() for k, v in methods.items()}), indent=2) + '\n')

    def test_self_check_clipboard_bindings_do_not_use_raw_local_comparison(self):
        audit_ui = (PROD / 'EnvironmentAuditUi.java').read_text()
        pair_ui = (PROD / 'FingerprintComparisonUi.java').read_text()
        copied = re.findall(r'ClipData\.newPlainText\("[^"\n]*",audit\.([A-Za-z]+)\(\)\)', audit_ui + pair_ui)
        self.assertEqual(sorted(copied), ['comparisonDiagnosticCopy', 'deepRecordCopy', 'safeCopy'])
        self.assertIn('raw.setText(audit.comparisonCopy())', pair_ui)
        for value in ('复制脱敏深检诊断', '复制脱敏简要结果'):
            self.assertIn(value, audit_ui)
        self.assertIn('复制脱敏双报告诊断', pair_ui)
        self.assertIn('原始文字和地址留在本机查看', audit_ui)


if __name__ == '__main__':
    unittest.main()
