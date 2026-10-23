#!/usr/bin/env python3
"""Execute required phase-two host checks and retain source-bound evidence."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from network_sources_contract import SETTINGS_HOST_MINIMUMS, SETTINGS_JSON_SHA256, SETTINGS_PARSER_SUITES, verify_settings_ui_host

ROOT = Path(__file__).resolve().parents[2]
HOSTS = {'receipt': 'tests/network-application-host/run.py',
         'provider': 'tests/network-application-host/provider.py',
         'retry': 'tests/network-apply-host/run.py',
         'ui': 'tests/network-settings-ui-host/run.py'}


def bind_host_report(value, kind, source, implementation, digest):
    """Bind an already-successful actual child report; never repair its outcome."""
    assert value['actualAndroidExecution'] is False
    assert value.get('sourceCommit', source) == source
    assert not value.get('diagnosticOnly', False)
    assert not value.get('sourceDirty', False) and not value.get('dirty', False)
    if kind == 'ui':
        # This existing runner's schema has two result objects, no status field.
        assert value.get('status', 'passed') == 'passed'
        verify_settings_ui_host(value['results'])
    else:
        assert value['status'] == 'passed'
        assert value['passed'] == len(value['checks']) >= SETTINGS_HOST_MINIMUMS[kind]
        assert all(row['pass'] is True for row in value['checks'])
        assert len({row['name'] for row in value['checks']}) == len(value['checks'])
    return dict(value, status='passed', sourceCommit=source, ciSourceDirty=False,
                ciHost={'jsonImplementation': implementation, 'jsonJarSha256': digest})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--json-desktop', type=Path, required=True)
    parser.add_argument('--json-android', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, default=ROOT / 'work/gecko-integration')
    args = parser.parse_args()
    out = args.output_directory.resolve(); out.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True))
    assert not dirty, 'CI settings evidence requires clean committed source'
    success = True
    for implementation, jar in (('desktop', args.json_desktop), ('android', args.json_android)):
        jar = jar.resolve()
        digest = hashlib.sha256(jar.read_bytes()).hexdigest()
        assert digest == SETTINGS_JSON_SHA256[implementation], 'Pinned JSON implementation differs'
        for kind, script in HOSTS.items():
            prefix = 'network-settings-' + kind + '-' + implementation
            path = out / (prefix + '-host-results.json')
            command = [sys.executable, str(ROOT / script), '--java-home', str(args.java_home.resolve()),
                       '--json-jar', str(jar), '--output', str(path)]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            (out / (prefix + '-stdout.txt')).write_text(result.stdout)
            (out / (prefix + '-stderr.txt')).write_text(result.stderr)
            if result.returncode:
                value = {'status': 'failed', 'exitCode': result.returncode, 'sourceCommit': source,
                         'actualAndroidExecution': False, 'ciSourceDirty': dirty,
                         'ciHost': {'jsonImplementation': implementation, 'jsonJarSha256': digest}}
                success = False
            else:
                value = json.loads(path.read_text())
                value = bind_host_report(value, kind, source, implementation, digest)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    suites = {}
    for name, minimum in SETTINGS_PARSER_SUITES.items():
        path = ROOT / 'tests' / name
        spec = importlib.util.spec_from_file_location('required_' + path.stem, path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
        (out / ('network-settings-' + path.stem + '-stdout.txt')).write_text(stream.getvalue())
        passed = result.wasSuccessful() and result.testsRun >= minimum and not result.skipped
        success &= passed
        suites[name] = dict(testsRun=result.testsRun, successful=passed, failures=len(result.failures),
                            errors=len(result.errors), skipped=len(result.skipped),
                            sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report = dict(status='passed' if all(row['successful'] for row in suites.values()) else 'failed',
                  sourceCommit=source, ciSourceDirty=dirty, actualAndroidExecution=False, suites=suites,
                  scope='Executed parser controls using synthetic evidence; not Android execution or performance data.')
    (out / 'network-settings-parser-negative-results.json').write_text(json.dumps(report, indent=2) + '\n')
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    assert success, 'A required settings host/parser check failed; original evidence retained'


if __name__ == '__main__':
    main()
