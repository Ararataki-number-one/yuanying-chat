#!/usr/bin/env python3
"""Derive an isolated trace workflow from frozen, unchanged CI job sections.

This generator never starts CI. The generated graph is diagnostic-only and has
no publisher, production ref update, acceptance collector or release job.
"""
import argparse
import copy
import hashlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '.github/workflows/gecko-integration.yml'
TARGET = ROOT / '.github/workflows/gecko-input-scheduler-diagnostic.yml'
BASE_SOURCE = 'fb67b081895bd37639d0a909155f607100d5cecb'
BASE_SHA256 = '2326576f077e3e00cb495890111ad7d8c2e1a045f200adafbcc794992b33dab9'
PREFIX = 'scheduler-diagnostic-'
BRANCH = 'diagnostic/gecko-input-scheduler-20261028'
PUSH_PATHS = ['.github/workflows/gecko-input-scheduler-diagnostic.yml',
              'tools/gecko/trace_input_scheduler.py',
              'tools/gecko/generate_input_scheduler_diagnostic_workflow.py',
              'tests/gecko_scheduler_diagnostic_workflow_test.py',
              'tests/gecko_scheduler_trace_input_test.py']
PERFETTO_URL = 'https://github.com/google/perfetto/releases/download/v54.0/linux-amd64.zip'
PERFETTO_SHA256 = '2066ad35f7f56baf622f88506ded9cc07e2bc569417e7cd22e057126c06da382'
UPLOAD = 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
DOWNLOAD = 'actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0'


class LiteralDumper(yaml.SafeDumper):
    pass


def literal_string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value,
                                   style='|' if '\n' in value else None)


LiteralDumper.add_representer(str, literal_string)


def marker_script(path, kind):
    return """python3 - <<'PYCODE'
import json,os,pathlib,subprocess
root=pathlib.Path.cwd()
identity={'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'sourceTree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
          'runId':os.environ['GITHUB_RUN_ID'],'runAttempt':os.environ['GITHUB_RUN_ATTEMPT']}
assert identity['sourceCommit']==os.environ['GITHUB_SHA']
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
record=dict(schema=1,diagnosticOnly=True,applicationAcceptance=False,releaseAcceptance=False,
            kind=%r,baseSourceCommit=%r,originalWorkflowSha256=%r,**identity)
record.update(sample=os.environ.get('DIAGNOSTIC_SAMPLE'),
              bootStepOutcome=os.environ.get('DIAGNOSTIC_BOOT_OUTCOME'),
              traceRunnerStepOutcome=os.environ.get('DIAGNOSTIC_RUNNER_OUTCOME'),
              analysisStepOutcome=os.environ.get('DIAGNOSTIC_ANALYSIS_OUTCOME'),
              scope='Original fixed workloads with bounded external scheduler/input-service tracing. '
                    'Trace overhead means these artifacts never qualify an application or release.')
path=pathlib.Path(%r);path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(record,sort_keys=True,indent=2)+'\\n')
PYCODE
""" % (kind, BASE_SOURCE, BASE_SHA256, path)


def namespace_artifacts(step):
    step = copy.deepcopy(step)
    if step.get('uses') in (UPLOAD, DOWNLOAD):
        original = step['with']['name']
        assert not original.startswith(PREFIX)
        step['with']['name'] = PREFIX + original
    # The diagnostic workflow only needs repository reads. Tests retain their
    # original source and commands; no checkout credentials remain available.
    if step.get('uses', '').startswith('actions/checkout@'):
        step.setdefault('with', {})['persist-credentials'] = False
        # Retention fix -> corrected capture -> first diagnostic -> frozen source.
        step['with']['fetch-depth'] = 4
    return step


def generated():
    raw = BASE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASE_SHA256, 'Review a changed base workflow before regenerating'
    source = yaml.safe_load(raw)
    build = copy.deepcopy(source['jobs']['build'])
    original = copy.deepcopy(source['jobs']['editing-samples'])
    removed = [s for s in build['steps'] if s.get('run') == 'python3 tools/gecko/publish_ci.py']
    assert len(removed) == 1 and removed[0]['name'] == 'Publish unsigned build for local original signing'
    build['steps'] = [namespace_artifacts(s) for s in build['steps'] if s not in removed]
    build['name'] = 'Diagnostic build (no application acceptance)'
    seal = next(i for i, s in enumerate(build['steps']) if s.get('name') == 'Seal one source/run-bound build for every Android phase')
    build['steps'].insert(seal, {'name': 'Declare this compiled bundle diagnostic only',
                               'run': marker_script('work/ci-build/diagnostic-build-scope.json', 'scheduler-trace-build')})
    transfer = next(s for s in build['steps'] if s.get('name') == 'Transfer exact compiled APKs and SDK inputs')
    transfer['with']['path'] = 'work/ci-build/bundle.tar.gz\nwork/ci-build/diagnostic-build-scope.json\n'
    transfer['with']['retention-days'] = 3

    samples = copy.deepcopy(original)
    samples['name'] = 'Diagnostic editing (${{ matrix.sample }})'
    samples['strategy']['matrix']['sample'] = ['1', '2', '3']
    assert samples['strategy']['fail-fast'] is False
    original_step = next(s for s in original['steps'] if s.get('name') == 'Run one original workload on this independent Android device')
    original_run = original_step['run']
    assert original_run.count('python3 tools/gecko/run_caret_editing_phase.py ') == 1
    assert "POCKETCHAT_ORIGINAL_EDITING" not in original_run
    keep = []
    for step in original['steps']:
        if step.get('name') == 'Preserve and verify this sample without replay' or step.get('with', {}).get('path') == 'work/key-order-sample/':
            continue
        step = namespace_artifacts(step)
        if step.get('name') == 'Boot Android for native acceptance':
            step['id'] = 'android_boot'
        if step.get('name') == original_step['name']:
            step['id'] = 'trace_workload'
            step['name'] = 'Trace one unchanged original workload, once'
            step['run'] = ("mkdir -p work/input-scheduler-diagnostic\n"
                           "cat > work/input-scheduler-diagnostic/original-editing.sh <<'POCKETCHAT_ORIGINAL_EDITING'\n"
                           + original_run + "POCKETCHAT_ORIGINAL_EDITING\n"
                           "python3 tools/gecko/trace_input_scheduler.py run --sample '${{ matrix.sample }}' "
                           "--out work/input-scheduler-diagnostic "
                           "--command-file work/input-scheduler-diagnostic/original-editing.sh\n")
        keep.append(step)
    samples['steps'] = keep
    samples['steps'].extend([
        {'name': 'Analyze bounded trace after the original workload has ended',
         'id': 'trace_analysis', 'if': 'always()', 'shell': 'bash',
         'run': """set -euo pipefail
mkdir -p work/input-scheduler-tools
curl -fsSL --connect-timeout 15 --max-time 120 %s -o work/input-scheduler-tools/linux-amd64.zip
echo '%s  work/input-scheduler-tools/linux-amd64.zip' | sha256sum -c -
python3 - <<'PYCODE'
import pathlib,stat,zipfile
archive=pathlib.Path('work/input-scheduler-tools/linux-amd64.zip')
target=pathlib.Path('work/input-scheduler-tools/trace_processor_shell')
with zipfile.ZipFile(archive) as source:
    members=[m for m in source.infolist() if pathlib.PurePosixPath(m.filename).name=='trace_processor_shell']
    assert len(members)==1 and 0<members[0].file_size<=64*1024*1024
    mode=(members[0].external_attr>>16)&0o170000
    assert not members[0].is_dir() and mode in (0,stat.S_IFREG)
    with source.open(members[0]) as src,target.open('xb') as dst:
        import shutil
        shutil.copyfileobj(src,dst,1024*1024)
target.chmod(0o700)
PYCODE
python3 tools/gecko/trace_input_scheduler.py analyze --sample '${{ matrix.sample }}' --out work/input-scheduler-diagnostic --trace-processor work/input-scheduler-tools/trace_processor_shell
""" % (PERFETTO_URL, PERFETTO_SHA256)},
        {'name': 'Seal original phase bytes without an acceptance collector', 'if': 'always()',
         'run': 'python3 tools/gecko/ci_bundle.py pack --kind phase --phase editing --bundle work/input-scheduler-diagnostic/original-phase.tar.gz'},
        {'name': 'Declare diagnostic scope regardless of workload outcome', 'if': 'always()',
         'env': {'DIAGNOSTIC_SAMPLE': '${{ matrix.sample }}',
                 'DIAGNOSTIC_BOOT_OUTCOME': '${{ steps.android_boot.outcome }}',
                 'DIAGNOSTIC_RUNNER_OUTCOME': '${{ steps.trace_workload.outcome }}',
                 'DIAGNOSTIC_ANALYSIS_OUTCOME': '${{ steps.trace_analysis.outcome }}'},
         'run': marker_script('work/input-scheduler-diagnostic/diagnostic-scope.json', 'scheduler-traced-original-editing')},
        {'name': 'Preserve diagnostic trace and unchanged phase evidence', 'if': 'always()', 'uses': UPLOAD,
         'with': {'name': PREFIX + '${{ github.run_id }}-${{ github.run_attempt }}-editing-${{ matrix.sample }}',
                  'path': 'work/input-scheduler-diagnostic/', 'if-no-files-found': 'error',
                  'retention-days': 5, 'compression-level': 6}},
    ])
    workflow = {
        'name': 'Diagnostic only: Android input scheduler and services',
        'on': {'push': {'branches': [BRANCH], 'paths': PUSH_PATHS}, 'workflow_dispatch': None},
        'permissions': {'contents': 'read', 'actions': 'read'},
        'concurrency': {'group': 'input-scheduler-diagnostic-${{ github.ref }}', 'cancel-in-progress': False},
        'env': copy.deepcopy(source['env']),
        'jobs': {'build': build, 'editing-trace': samples},
    }
    return workflow


def render():
    return ('# Generated diagnostic-only workflow; do not edit by hand.\n'
            '# Original workload oracles and native gesture protocol are unchanged.\n'
            '# These artifacts never authorize application acceptance or a release.\n'
            + yaml.dump(generated(), Dumper=LiteralDumper, sort_keys=False,
                        allow_unicode=True, width=100000))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = render()
    if args.check:
        assert TARGET.read_text() == content, 'Generated diagnostic workflow differs'
    else:
        TARGET.write_text(content)
    print('Diagnostic workflow verified' if args.check else 'Diagnostic workflow generated; not triggered')


if __name__ == '__main__':
    main()
