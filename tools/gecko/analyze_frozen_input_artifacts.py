#!/usr/bin/env python3
"""Read-only posthoc analysis of three explicitly frozen original CI artifacts."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile

SOURCE = {
    'sourceCommit': '596bfb1f7ad6f03548cdac5ce1932cd999cdd637',
    'sourceTree': '7cf5f75e541f57a3f336f8ab332a463cfe131e61',
    'runId': '40720430995', 'runAttempt': '1',
}
BRANCH = 'diagnostic/gecko-input-scheduler-20261028'
HELPER_SHA = '785b72beae8f1bd5a24c36e2bc7d5769c078fc83fb54d36d3d3faa812000b7b3'
PROCESSOR_URL = 'https://github.com/google/perfetto/releases/download/v54.0/linux-amd64.zip'
PROCESSOR_SHA = '2066ad35f7f56baf622f88506ded9cc07e2bc569417e7cd22e057126c06da382'
FLAGS = dict(diagnosticOnly=True, applicationAcceptance=False, releaseAcceptance=False,
             physicalPhoneAcceptance=False, protectionEffectivenessAcceptance=False,
             uniqueCauseEstablished=False)
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_FILES = 5000
MAX_JSON = 4 * 1024 * 1024
MAX_LOG = 256 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def file_identity(path):
    need(path.is_file() and not path.is_symlink(), 'Ordinary original file required')
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def dump(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def read_json(path, limit=MAX_JSON):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit,
         'Bounded ordinary JSON file required')
    return json.loads(path.read_text(encoding='utf-8'))


def safe_name(name):
    need(isinstance(name, str) and 0 < len(name) <= 240 and
         re.fullmatch(r'[A-Za-z0-9_./-]+', name), 'Unsafe archive path characters')
    path = PurePosixPath(name)
    need(not path.is_absolute() and '..' not in path.parts and str(path) == name,
         'Noncanonical or escaping archive path')
    return path


def copy_bounded(source, target, maximum, expected=None):
    size = 0
    with target.open('xb') as output:
        while True:
            block = source.read(min(1024 * 1024, maximum - size + 1))
            if not block:
                break
            size += len(block)
            need(size <= maximum, 'Expanded file exceeds extraction bound')
            output.write(block)
    need(expected is None or size == expected, 'Extracted byte count differs')


def safe_zip(archive, destination):
    need(archive.stat().st_size <= MAX_ARCHIVE, 'ZIP exceeds archive bound')
    need(not destination.exists() and not destination.is_symlink(), 'Fresh ZIP destination required')
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        need(0 < len(members) <= MAX_FILES, 'ZIP entry count exceeds bound')
        names, total = set(), 0
        for member in members:
            name = member.filename[:-1] if member.is_dir() else member.filename
            safe_name(name)
            need(name not in names, 'Duplicate ZIP path')
            names.add(name)
            mode = stat.S_IFMT(member.external_attr >> 16)
            need(mode in ((0, stat.S_IFDIR) if member.is_dir() else (0, stat.S_IFREG)),
                 'ZIP contains a special file or symlink')
            need(not member.flag_bits & 1 and 0 <= member.file_size <= MAX_ARCHIVE,
                 'Encrypted or oversized ZIP member')
            total += member.file_size
            need(total <= MAX_TOTAL, 'ZIP expanded total exceeds bound')
        destination.mkdir()
        for member in members:
            target = destination / member.filename
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as stream:
                    copy_bounded(stream, target, member.file_size, member.file_size)
    return names


def same_source(value):
    need(all(value.get(key) == expected for key, expected in SOURCE.items()),
         'Original source/tree/run/attempt binding differs')


def extract_phase(archive, destination, raw_tar):
    need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size <= MAX_ARCHIVE,
         'Bounded ordinary original phase archive required')
    need(not destination.exists() and not destination.is_symlink(), 'Fresh phase destination required')
    # Bound the gzip expansion before tarfile sees any extended headers or paths.
    with gzip.open(archive, 'rb') as stream:
        copy_bounded(stream, raw_tar, MAX_TOTAL + 16 * 1024 * 1024)
    with tarfile.open(raw_tar, 'r:') as source:
        members, total = {}, 0
        for member in source:
            name = str(safe_name(member.name))
            need(member.isfile() and name not in members, 'Nonregular or duplicate phase archive member')
            need(0 <= member.size <= MAX_ARCHIVE, 'Oversized phase member')
            total += member.size
            need(len(members) < MAX_FILES + 1 and total <= MAX_TOTAL, 'Phase extraction exceeds bound')
            members[name] = member
        need('_ci_bundle.json' in members and members['_ci_bundle.json'].size <= MAX_JSON,
             'Bounded original bundle manifest missing')
        with source.extractfile(members['_ci_bundle.json']) as stream:
            manifest = json.loads(stream.read(MAX_JSON + 1))
        same_source(manifest)
        need(type(manifest.get('schema')) is int and manifest['schema'] == 1 and
             manifest.get('kind') == 'phase' and manifest.get('phase') == 'editing',
             'Unexpected original bundle kind or phase')
        rows = manifest.get('files')
        need(isinstance(rows, list) and 0 < len(rows) <= MAX_FILES, 'Invalid original file manifest')
        expected = {}
        for row in rows:
            name = str(safe_name(row['path']))
            need(name.startswith('work/gecko-integration/') and name not in expected,
                 'Unexpected or duplicate original evidence path')
            need(type(row.get('bytes')) is int and 0 <= row['bytes'] <= MAX_ARCHIVE and
                 re.fullmatch('[0-9a-f]{64}', str(row.get('sha256'))), 'Invalid original file identity')
            expected[name] = row
        need(set(members) == {'_ci_bundle.json'} | set(expected), 'Archive and manifest file sets differ')
        # Check every declared size and digest before creating the extraction tree.
        for name, row in expected.items():
            member = members[name]
            need(member.size == row['bytes'], 'Original phase file size differs')
            h = hashlib.sha256()
            with source.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
            need(h.hexdigest() == row['sha256'], 'Original phase file SHA differs')
        destination.mkdir()
        for name, member in members.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as stream:
                copy_bounded(stream, target, member.size, member.size)
    return manifest


def bindings_for(path, sample):
    value = read_json(path)
    same_source(value)
    need(type(value.get('schema')) is int and value['schema'] == 1 and value.get('headBranch') == BRANCH and
         value.get('status') == 'frozen-final-original-artifact-metadata', 'Final frozen bindings required; no fallback')
    need(all(value.get(key) is flag for key, flag in FLAGS.items()), 'Every binding diagnostic flag must be explicit and Boolean')
    rows = value.get('artifacts')
    need(isinstance(rows, list) and len(rows) == 3 and {x.get('sample') for x in rows} == {'1', '2', '3'},
         'Exactly the three fixed original artifact bindings required')
    ids = set()
    for row in rows:
        need(row.get('name') == 'scheduler-diagnostic-40720430995-1-editing-' + row['sample'],
             'Unexpected original artifact name')
        need(type(row.get('artifactId')) is int and row['artifactId'] > 0 and row['artifactId'] not in ids,
             'Actual distinct original artifact IDs required')
        ids.add(row['artifactId'])
        need(all(type(row.get(key)) is int and 0 < row[key] <= MAX_ARCHIVE
                 for key in ('apiSizeInBytes', 'zipBytes')), 'Exact bounded artifact sizes required')
        need(re.fullmatch('[0-9a-f]{64}', str(row.get('zipSha256'))), 'Actual original artifact ZIP SHA required')
    return next(row for row in rows if row['sample'] == sample)


def gh_api(route, target, maximum):
    with target.open('xb') as output, target.with_suffix(target.suffix + '.stderr.log').open('xb') as errors:
        result = subprocess.run(['gh', 'api', route], stdout=output, stderr=errors, timeout=180, check=False)
    need(result.returncode == 0, 'GitHub API read failed; original response files retained')
    need(target.stat().st_size <= maximum, 'GitHub API response exceeds bound')


def download_original(repository, binding, out):
    need(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'Actual GitHub repository required')
    prefix = 'repos/' + repository + '/actions/'
    run_path = out / 'original-run-attempt.json'
    gh_api(prefix + 'runs/40720430995/attempts/1', run_path, MAX_JSON)
    run = read_json(run_path)
    need(str(run.get('id')) == SOURCE['runId'] and str(run.get('run_attempt')) == SOURCE['runAttempt'] and
         run.get('head_sha') == SOURCE['sourceCommit'] and run.get('head_branch') == BRANCH and
         run.get('status') == 'completed', 'Original run attempt identity or final status differs')
    metadata_path = out / 'original-artifact-metadata.json'
    route = prefix + 'artifacts/' + str(binding['artifactId'])
    gh_api(route, metadata_path, MAX_JSON)
    metadata = read_json(metadata_path)
    workflow_run = metadata.get('workflow_run', {})
    need(metadata.get('id') == binding['artifactId'] and metadata.get('name') == binding['name'] and
         metadata.get('size_in_bytes') == binding['apiSizeInBytes'] and metadata.get('expired') is False and
         metadata.get('digest') == 'sha256:' + binding['zipSha256'] and
         str(workflow_run.get('id')) == SOURCE['runId'] and workflow_run.get('head_sha') == SOURCE['sourceCommit'] and
         workflow_run.get('head_branch') == BRANCH, 'Original artifact metadata binding differs')
    archive = out / 'original-artifact.zip'
    gh_api(route + '/zip', archive, MAX_ARCHIVE)
    need(file_identity(archive) == dict(bytes=binding['zipBytes'], sha256=binding['zipSha256']),
         'Original artifact ZIP bytes or SHA differs')
    return archive


def install_processor(out):
    archive = out / 'official-perfetto-v54-linux-amd64.zip'
    result = subprocess.run(['curl', '-fsSL', '--connect-timeout', '15', '--max-time', '120',
                             '--max-filesize', str(128 * 1024 * 1024), PROCESSOR_URL, '-o', str(archive)],
                            timeout=135, check=False)
    need(result.returncode == 0 and sha(archive) == PROCESSOR_SHA, 'Pinned official Perfetto archive differs')
    target = out / 'trace_processor_shell'
    with zipfile.ZipFile(archive) as source:
        members = [x for x in source.infolist() if PurePosixPath(x.filename).name == 'trace_processor_shell']
        need(len(members) == 1 and not members[0].is_dir() and 0 < members[0].file_size <= 64 * 1024 * 1024 and
             stat.S_IFMT(members[0].external_attr >> 16) in (0, stat.S_IFREG), 'Unexpected pinned processor member')
        with source.open(members[0]) as stream:
            copy_bounded(stream, target, members[0].file_size, members[0].file_size)
    target.chmod(0o700)
    return target


def validate_config(original, run):
    name = str(safe_name(run.get('configFile')))
    need(PurePosixPath(name).name == name and name == 'perfetto-config.pbtxt' and
         run.get('configSource') == 'stdin', 'Original stdin config binding required')
    need(type(run.get('configBytes')) is int and 0 < run['configBytes'] <= 65536 and
         re.fullmatch('[0-9a-f]{64}', str(run.get('configSha256'))), 'Bounded original config identity required')
    need(file_identity(original / name) == dict(bytes=run['configBytes'], sha256=run['configSha256']),
         'Original stdin config bytes or SHA differs')


def trace_closure(processor, trace, out):
    """Keep optional posthoc closure observations; missing closure never blocks analysis."""
    out.mkdir()
    queries = {
        'closure-metadata': "SELECT * FROM metadata WHERE name IN ('tracing_started_ns','tracing_disabled_ns','all_data_source_flushed_ns','unique_session_name','trace_time_clock_id') ORDER BY name LIMIT 501",
        'closure-stats': "SELECT * FROM stats WHERE lower(name) LIKE '%flush%' ORDER BY name,idx LIMIT 501",
    }
    records = []
    for name, sql in queries.items():
        sql_path, csv_path, err_path = (out / (name + suffix) for suffix in ('.sql', '.stdout.csv', '.stderr.log'))
        sql_path.write_text(sql + '\n')
        record = dict(name=name, status='unavailable', rows=[], **FLAGS)
        try:
            with csv_path.open('xb') as stdout, err_path.open('xb') as stderr:
                result = subprocess.run([str(processor), '--full-sort', '-q', str(sql_path), str(trace)],
                                        stdout=stdout, stderr=stderr, timeout=180, check=False)
            record['returnCode'] = result.returncode
            need(result.returncode == 0 and csv_path.stat().st_size <= MAX_JSON, 'Closure query unavailable or exceeds bound')
            with csv_path.open(encoding='utf-8', newline='') as stream:
                reader = csv.DictReader(stream)
                need(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'Invalid closure CSV header')
                rows = list(reader)
            need(len(rows) <= 501 and all(None not in row and all(v is not None for v in row.values()) for row in rows),
                 'Closure CSV shape or count differs')
            record.update(status='queried', totalRows=len(rows), rowLimitReached=len(rows) == 501,
                          rows=[{k: v[:1024] for k, v in row.items()} for row in rows[:64]])
        except Exception as error:
            record.update(errorType=type(error).__name__, error=str(error)[:1024])
        for key, path in (('sql', sql_path), ('csv', csv_path), ('stderr', err_path)):
            if path.is_file(): record[key] = dict(file=path.name, **file_identity(path))
        records.append(record)
    closure = dict(status='optional-diagnostic-closure-observations', queries=records,
                   closureCompletenessIndependentlyEstablished=False,
                   scope='Raw metadata and flush counters only; missing closure is allowed and no successful final flush is inferred.', **FLAGS)
    dump(out / 'closure.json', closure)
    return closure


def validate_originals(original, phase, sample):
    run = read_json(original / 'diagnostic-run.json')
    scope = read_json(original / 'diagnostic-scope.json')
    same_source(run)
    same_source(scope)
    need(run.get('sample') == sample and scope.get('sample') == sample and
         run.get('diagnosticOnly') is True and scope.get('diagnosticOnly') is True and
         run.get('applicationAcceptance') is False and scope.get('applicationAcceptance') is False and
         scope.get('releaseAcceptance') is False and run.get('physicalPhoneAcceptance') is False and
         run.get('workloadInvocationCount') == 1, 'Original capture scope or sample differs')
    validate_config(original, run)
    trace = original / 'android.perfetto-trace'
    need(file_identity(trace) == dict(bytes=run.get('traceBytes'), sha256=run.get('traceSha256')),
         'Original trace and diagnostic record do not match')
    performance = phase / 'work/gecko-integration/gecko-performance-results.json'
    report = read_json(performance)
    need(report.get('sourceCommit') == SOURCE['sourceCommit'], 'Original performance source differs')
    rows = report.get('nativeInputDriver', {}).get('receipts')
    need(isinstance(rows, list) and 0 < len(rows) <= 64, 'All original native-input receipt references required')
    receipts, seen = [], set()
    for row in rows:
        name = str(safe_name(row['file']))
        need(PurePosixPath(name).name == name and name.startswith('native-input-') and name.endswith('.json') and
             name not in seen, 'Unsafe or duplicate original native receipt reference')
        seen.add(name)
        path = performance.parent / name
        need(path.stat().st_size <= 2 * 1024 * 1024 and sha(path) == row.get('sha256'),
             'Original referenced native receipt hash differs')
        receipt = read_json(path)
        same_source(receipt.get('buildIdentity', {}))
        need(receipt.get('sourceCommit') == SOURCE['sourceCommit'] and receipt.get('sourceTree') == SOURCE['sourceTree'],
             'Original native receipt source differs')
        receipts.append(path)
    return run, trace, receipts


def log_projection(report, out, sample):
    def bound(value, depth=0):
        if depth > 9:
            return '[nested rows omitted from bounded log; full analysis retained]'
        if isinstance(value, dict):
            return {key: bound(item, depth + 1) for key, item in list(value.items())[:96] if key != 'rows'}
        if isinstance(value, list):
            return [bound(item, depth + 1) for item in value[:24]]
        if isinstance(value, str):
            return value[:2048]
        return value
    value = bound(report)
    value.update(FLAGS)
    value['artifactBindingVerified'] = True
    value['logProjection'] = dict(bounded=True, maxBytes=MAX_LOG, totalWindows=len(report['windows']),
                                 shownWindows=len(value['windows']), fullFile='correlation/analysis.json')
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    while len(raw.encode('utf-8')) > MAX_LOG and value['windows']:
        value['windows'] = value['windows'][:len(value['windows']) // 2]
        value['logProjection']['shownWindows'] = len(value['windows'])
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    need(len(raw.encode('utf-8')) <= MAX_LOG, 'Derived analysis log exceeds bound; full file retained')
    dump(out / 'analysis-for-log.json', value)
    print('BEGIN_INPUT_ANALYSIS_JSON sample=' + sample, flush=True)
    print(raw, flush=True)
    print('END_INPUT_ANALYSIS_JSON sample=' + sample, flush=True)


def analyze(args):
    out = args.out.resolve()
    need(not out.exists() and not out.is_symlink(), 'Fresh data-analysis output required')
    out.mkdir(parents=True)
    scope = dict(schema=1, status='failed', scope='Posthoc read-only diagnostic data analysis; no Android execution or qualification',
                 sample=args.sample, originalSource=SOURCE, actualAndroidExecution=False, newQualification=False,
                 analysisExecution={key: os.environ.get(key) for key in
                                    ('GITHUB_REPOSITORY', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')}, **FLAGS)
    try:
        provenance = out / 'analysis-provenance'
        provenance.mkdir()
        for path in (args.bindings.resolve(), Path(__file__).resolve(),
                     Path(__file__).with_name('correlate_input_trace.py').resolve(),
                     Path(__file__).resolve().parents[2] / '.github/workflows/gecko-input-analysis.yml'):
            shutil.copyfile(path, provenance / path.name)
        helper = Path(__file__).with_name('correlate_input_trace.py').resolve()
        need(sha(helper) == HELPER_SHA, 'Unchanged reviewed correlation helper required')
        binding = bindings_for(args.bindings, args.sample)
        archive = download_original(os.environ.get('GITHUB_REPOSITORY', ''), binding, out)
        original = out / 'original-artifact-files'
        safe_zip(archive, original)
        phase = out / 'original-phase-files'
        manifest = extract_phase(original / 'original-phase.tar.gz', phase, out / 'original-phase.tar')
        run, trace, receipts = validate_originals(original, phase, args.sample)
        dump(out / 'verified-original-binding.json', dict(schema=1, sample=args.sample, artifact=binding,
             originalSource=SOURCE, originalManifest=file_identity(phase / '_ci_bundle.json'),
             originalTrace=file_identity(trace), originalStdinConfig=file_identity(original / run['configFile']), originalPerformance=file_identity(phase / 'work/gecko-integration/gecko-performance-results.json'),
             originalReceipts=[dict(file=path.name, **file_identity(path)) for path in receipts],
             originalCaptureStatus=run.get('status'), originalPhaseBuildIndexSha256=manifest.get('buildIndexSha256'), **FLAGS))
        processor = install_processor(out)
        closure = trace_closure(processor, trace, out / 'posthoc-trace-closure')
        scope['posthocTraceClosure'] = closure
        command = [sys.executable, str(helper), '--processor', str(processor), '--trace', str(trace),
                   '--out', str(out / 'correlation')]
        for path in receipts:
            command.extend(['--receipt', str(path)])
        with (out / 'correlation.stdout.log').open('xb') as stdout, (out / 'correlation.stderr.log').open('xb') as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=2100, check=False)
        need(result.returncode == 0, 'Original-data correlation failed; all raw inputs and outputs retained')
        report = read_json(out / 'correlation/analysis.json', MAX_TOTAL)
        need(all(report.get(key) == expected for key, expected in FLAGS.items()) and
             report.get('originalInputsUnchanged') is True, 'Derived diagnostic scope or input preservation differs')
        need(file_identity(archive) == dict(bytes=binding['zipBytes'], sha256=binding['zipSha256']),
             'Original artifact ZIP changed during analysis')
        report['posthocTraceClosure'] = closure
        log_projection(report, out, args.sample)
        scope.update(status='completed-diagnostic-data-analysis', artifactBindingVerified=True,
                     receiptCount=len(receipts), qualityPartial=report['quality']['partial'])
    except Exception as error:
        scope.update(errorType=type(error).__name__, error=str(error)[:2048])
        raise
    finally:
        dump(out / 'analysis-scope.json', scope)
        print('INPUT_ANALYSIS_SCOPE ' + json.dumps(scope, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bindings', type=Path, required=True)
    parser.add_argument('--sample', choices=('1', '2', '3'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    analyze(parser.parse_args())


if __name__ == '__main__':
    main()
