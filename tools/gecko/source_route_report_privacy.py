"""Public derivatives for incidental SDK URLs in the controlled route report.

The original runner, provider report and route decisions are unchanged. Only
non-fixture routes[*].url display values may lose supported service keys under
the existing policy. Original hashes describe provenance, not raw authenticity.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

_spec = importlib.util.spec_from_file_location('source_route_publication_guard', Path(__file__).with_name('caret_ime_guard.py'))
_guard = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _guard
_spec.loader.exec_module(_guard)
REPORT = 'network-source-route-results.json'
MARKER = 'diagnosticUrlPrivacy'
CONTROLLED_ORIGIN = 'https://127.0.0.1:9879/'


def require(value, reason):
    if not value:
        raise ValueError('Source route publication privacy: ' + reason)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('Source route publication privacy: nonfinite JSON')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    require(isinstance(value, dict), 'report object required')
    return value


def validate_marker(report):
    marker = report[MARKER]
    require(isinstance(marker, dict) and set(marker) == {
        'schema', 'kind', 'policy', 'sourceReport', 'captures',
        'onlyDiagnosticUrlValuesChanged', 'originalHashIsProvenanceOnly'}, 'marker shape')
    require(type(marker['schema']) is int and marker['schema'] == 1 and marker['kind'] == 'incidental-sdk-route-url-derivatives'
            and marker['policy'] == _guard.PRIVACY_POLICY
            and marker['onlyDiagnosticUrlValuesChanged'] is True
            and marker['originalHashIsProvenanceOnly'] is True, 'marker scope')
    source = marker['sourceReport']
    require(isinstance(source, dict) and set(source) == {'bytes', 'sha256'}
            and type(source['bytes']) is int and 0 < source['bytes'] <= _guard.PRIVACY_MAX_BYTES
            and isinstance(source['sha256'], str) and len(source['sha256']) == 64
            and all(c in '0123456789abcdef' for c in source['sha256']), 'original report reference')
    captures = marker['captures']
    require(isinstance(captures, list) and 0 < len(captures) <= _guard.PRIVACY_MAX_REPLACEMENTS, 'capture count')
    rows = report.get('routes')
    require(isinstance(rows, list), 'route list required')
    seen = set()
    for capture in captures:
        require(isinstance(capture, dict) and set(capture) == {'routeIndex', 'capturePrivacy'}, 'capture shape')
        index = capture['routeIndex']
        require(type(index) is int and 0 <= index < len(rows) and index not in seen, 'route index')
        seen.add(index)
        require(isinstance(rows[index], dict), 'route object required')
        url = rows[index].get('url')
        require(isinstance(url, str) and not url.startswith(CONTROLLED_ORIGIN), 'fixture URL cannot be projected')
        require(_guard.verify_capture_privacy(capture['capturePrivacy'], url)
                and capture['capturePrivacy'].get('changed') is True, 'URL derivative marker')


def public_report_bytes(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= _guard.PRIVACY_MAX_BYTES, 'bounded report bytes required')
    text = raw.decode('utf-8', errors='strict')
    findings = _guard.service_api_key_findings(text)
    if not findings:
        if ('"' + MARKER + '"') in text:
            value = strict_json(raw)
            if MARKER in value:
                validate_marker(value)
        _guard.assert_public_diagnostic_text(Path(REPORT), raw)
        return raw
    original = strict_json(raw)
    require(MARKER not in original, 'already marked report still contains a supported key')
    report = copy.deepcopy(original)
    rows = report.get('routes', [])
    require(isinstance(rows, list), 'route list required')
    captures = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        url = row.get('url')
        if not isinstance(url, str) or url.startswith(CONTROLLED_ORIGIN):
            continue
        derivative, privacy = _guard.redact_service_api_keys(url)
        require(_guard.verify_capture_privacy(privacy, derivative), 'invalid URL derivative')
        if privacy['changed']:
            row['url'] = derivative
            captures.append(dict(routeIndex=index, capturePrivacy=privacy))
    require(captures, 'supported key is outside allowed diagnostic URL fields')
    report[MARKER] = dict(schema=1, kind='incidental-sdk-route-url-derivatives',
                         policy=_guard.PRIVACY_POLICY,
                         sourceReport=dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
                         captures=captures, onlyDiagnosticUrlValuesChanged=True,
                         originalHashIsProvenanceOnly=True)
    validate_marker(report)
    # Explicitly prove every acceptance value and non-URL diagnostic unchanged.
    restored = copy.deepcopy(report)
    del restored[MARKER]
    for capture in captures:
        index = capture['routeIndex']
        restored['routes'][index]['url'] = original['routes'][index]['url']
    require(restored == original, 'non-URL report value changed')
    result = (json.dumps(report, indent=2) + '\n').encode('utf-8')
    # Keys in credentials, checks, fixture URLs or other fields still fail closed.
    _guard.assert_public_diagnostic_text(Path(REPORT), result)
    return result


def read_report(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= _guard.PRIVACY_MAX_BYTES, 'ordinary bounded report required')
        raw = stream.read(_guard.PRIVACY_MAX_BYTES + 1)
    require(len(raw) == info.st_size, 'report changed while reading')
    return raw


def prepare_stage(directory):
    """Transform the staged copy only; leave the runner's original OUT untouched."""
    path = Path(directory) / REPORT
    if not path.exists() and not path.is_symlink():
        return
    original = read_report(path)
    derivative = public_report_bytes(original)
    if derivative == original:
        return
    fd, temporary = tempfile.mkstemp(prefix='.source-route-public-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(derivative)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
