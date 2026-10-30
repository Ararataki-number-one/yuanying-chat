"""Exact production invalidation/cancellation methods with explicit JVM doubles.

The host counts cancellation and retained-activity decisions, not real Android
scheduling, native network bytes, physical memory savings, or Gecko API calls.
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
PINNED_JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')


def method(source, name):
    match = re.search(r'(?m)^  (?:[A-Za-z][A-Za-z0-9_<>?.\[\]]*\s+)+' + re.escape(name) + r'\([^\n]*?\)\s*\{', source)
    if not match:
        raise AssertionError('Missing actual production method: ' + name)
    depth, quote, cursor = 1, None, match.end()
    while cursor < len(source):
        c = source[cursor]
        if quote:
            if c == '\\':
                cursor += 2
                continue
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            quote = c
        elif source.startswith('//', cursor):
            end = source.find('\n', cursor)
            cursor = len(source) if end < 0 else end
            continue
        elif source.startswith('/*', cursor):
            end = source.find('*/', cursor + 2)
            if end < 0:
                raise AssertionError('Unterminated production comment')
            cursor = end + 2
            continue
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if not depth:
                return source[match.start():cursor + 1]
        cursor += 1
    raise AssertionError('Unterminated actual production method')


def execute(root=ROOT, expect_fixed=True):
    java = os.environ.get('PROFILE_JAVA') or (str(PINNED_JAVA) if PINNED_JAVA.is_file() else shutil.which('java'))
    if not java:
        raise RuntimeError('JDK required for actual production audit-retirement host checks')
    paths = {name: root / 'app/src/main/java/local/pocketchat' / (name + '.java')
             for name in ('ChatSession', 'EnvironmentAudit', 'EnvironmentResourcePolicy')}
    source = {name: path.read_text() for name, path in paths.items()}
    template = ROOT / 'tests/resource-retirement-host/AuditRetirementHost.java.in'
    rendered = template.read_text()
    values = {
        '__CURRENT__': method(source['EnvironmentAudit'], 'current'),
        '__CANCEL__': method(source['EnvironmentAudit'], 'cancel'),
        '__CLEANUP__': method(source['EnvironmentAudit'], 'cleanup'),
        '__RETIRE__': method(source['EnvironmentAudit'], 'retirePageCheck') if expect_fixed else '',
        '__BROWSER_ACTIVE__': method(source['ChatSession'], 'browserWorkActive'),
        '__BEGIN_NAVIGATION__': method(source['ChatSession'], 'beginNavigation'),
        '__INVALIDATE_CONNECTION__': method(source['ChatSession'], 'invalidateConnection'),
    }
    for key, value in values.items():
        if rendered.count(key) != 1:
            raise AssertionError('Host template must include each full production method once')
        rendered = rendered.replace(key, value)
    with tempfile.TemporaryDirectory(prefix='resource-retirement40-host-') as temporary:
        temp = Path(temporary)
        target = temp / 'AuditRetirementHost.java'
        target.write_text(rendered)
        compiled = subprocess.run([java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8',
                                   '-encoding', 'UTF-8', '-d', temporary, str(target), str(paths['EnvironmentResourcePolicy'])],
                                  capture_output=True, text=True, timeout=30)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        run = subprocess.run([java, '-cp', temporary, 'local.pocketchat.AuditRetirementHost', str(expect_fixed).lower()],
                             capture_output=True, text=True, timeout=15)
    metrics = [json.loads(line.removeprefix('METRICS ')) for line in run.stdout.splitlines() if line.startswith('METRICS ')]
    counts = re.findall(r'^TOTAL ([0-9]+)$', run.stdout, re.MULTILINE)
    return dict(status='passed' if run.returncode == 0 else 'failed', expectedFixed=expect_fixed,
                actualAndroidExecution=False, actualGeckoExecution=False, actualNativeHttpExecution=False,
                physicalMemoryMeasurement=False, scope='Exact extracted production methods on JVM; explicit fake scheduler and HttpURLConnection',
                returncode=run.returncode, stdout=run.stdout, stderr=run.stderr,
                passed=int(counts[0]) if len(counts) == 1 else None, metrics=metrics[0] if len(metrics) == 1 else None,
                sourceSha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},
                methodSha256={key: hashlib.sha256(value.encode()).hexdigest() for key, value in values.items()},
                templateSha256=hashlib.sha256(template.read_bytes()).hexdigest())


class ResourceAuditRetirementTest(unittest.TestCase):
    def test_document_and_route_invalidation_retire_only_obsolete_page_checks(self):
        report = execute()
        out = ROOT / 'work/resource40/audit-retirement-host.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + '\n')
        self.assertEqual(report['returncode'], 0, report['stdout'] + report['stderr'])
        self.assertEqual(report['passed'], 40)
        self.assertEqual(report['metrics'], dict(invalidatedChecksStillRunning=0, cancelledFutures=2, disconnectedConnections=2, idleActivityHeld=0))
        self.assertFalse(report['physicalMemoryMeasurement'])


if __name__ == '__main__':
    unittest.main()
