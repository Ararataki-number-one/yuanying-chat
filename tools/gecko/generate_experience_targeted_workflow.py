#!/usr/bin/env python3
"""Derive one diagnostic build and four original fresh-device workflows.

This generator never starts CI. Compiled bundles and original assertions remain
unchanged; every result from this graph is explicitly ineligible for release.
"""
import argparse
import ast
import copy
import hashlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '.github/workflows/gecko-integration.yml'
TARGET = ROOT / '.github/workflows/gecko-experience-targeted.yml'
BASE_SOURCE = '0ac8f6373a1398c9802bc7184084a3191ae2ae53'
BASE_SHA256 = '10e35f9884e6eac2ea2fc2e0e6d6f6d5d14c55dc7e776cd0128019c75ab3f2f5'
BRANCH = 'diagnostic/gecko-experience-targeted-20261029'
PREFIX = 'experience-targeted-'
READ = {'contents': 'read', 'actions': 'read'}
UPLOAD = 'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02'
DOWNLOAD = 'actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0'
PUBLISH = 'python3 tools/gecko/publish_ci.py\n'
UI_LINE = 'if ! python3 tests/gecko/run_ui_visuals.py --adb "$(command -v adb)" --serial emulator-5554; then\n'
UI_DIAGNOSTIC_LINE = UI_LINE.replace('if ! python3 ', 'if ! GITHUB_ACTIONS=false python3 ')
FILES_LINE = 'if ! python3 tests/gecko/run_device.py --adb "$(command -v adb)" --serial emulator-5554; then\n'
FILES_DIAGNOSTIC_LINE = FILES_LINE.replace('; then', ' --reading-zoom-trace; then')
PUSH_PATHS = ['.github/workflows/gecko-experience-targeted.yml',
              'tools/gecko/generate_experience_targeted_workflow.py',
              'tests/gecko_experience_targeted_workflow_test.py']
STEP_IDS = {
    'Compile release and native regression package': 'diagnostic_compile',
    'Seal one source/run-bound build for every Android phase': 'diagnostic_seal',
    'Verify network performance and compact chrome': 'diagnostic_ui',
    'Verify network sharing and explicit import UI': 'diagnostic_sharing',
    'Verify system and manual appearance without recreation': 'diagnostic_appearance',
    'Verify webpage appearance receipts through the actual Gecko bridge': 'diagnostic_web_appearance',
    'Verify production environments and file transfers': 'diagnostic_files',
}

class LiteralDumper(yaml.SafeDumper):
    pass

def literal(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value,
        style='|' if '\n' in value else None)

LiteralDumper.add_representer(str, literal)

def base():
    raw = BASE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASE_SHA256, 'Review a changed main workflow before deriving diagnostics'
    return yaml.safe_load(raw)

def verify_ui_checkpoint_only():
    """The one env override disables only the runner's existing publisher arm."""
    source = (ROOT / 'tests/gecko/run_ui_visuals.py').read_text()
    assert source.count('GITHUB_ACTIONS') == 1
    module = ast.parse(source)
    checkpoint = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'checkpoint')
    guards = [n for n in ast.walk(checkpoint) if isinstance(n, ast.If) and 'GITHUB_ACTIONS' in ast.unparse(n.test)]
    assert len(guards) == 1
    guard = guards[0]
    assert ast.unparse(guard.test) == "os.environ.get('GITHUB_ACTIONS') == 'true'" and not guard.orelse
    assert len(guard.body) == 2
    assert isinstance(guard.body[0], ast.Assign) and isinstance(guard.body[0].value, ast.Call)
    assert ast.unparse(guard.body[0].value.func) == 'subprocess.run'
    assert ast.literal_eval(guard.body[0].value.args[0].elts[1].args[0].right) == 'tools/gecko/publish_ci.py'
    assert isinstance(guard.body[1], ast.Expr) and ast.unparse(guard.body[1].value.func) == 'print'

def reading_interface_ready(source):
    calls = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_argument'
             and any(isinstance(a, ast.Constant) and a.value == '--reading-zoom-trace' for a in n.args)]
    assert len(calls) == 1, 'Reading agent must provide the opt-in trace interface before a source freeze'
    kwargs = {n.arg: n.value for n in calls[0].keywords}
    assert isinstance(kwargs.get('action'), ast.Constant) and kwargs['action'].value == 'store_true'
    assert 'default' not in kwargs or (isinstance(kwargs['default'], ast.Constant) and kwargs['default'].value is False)

def scope_steps(job):
    phase = '${{ matrix.phase }}' if job == 'android' else ('${{ matrix.scenario }}' if job == 'chrome-diagnostic' else 'build')
    outcomes = {'JOB_STATUS': '${{ job.status }}'}
    if job == 'build':
        outcomes.update(COMPILE_OUTCOME='${{ steps.diagnostic_compile.outcome }}', SEAL_OUTCOME='${{ steps.diagnostic_seal.outcome }}')
    elif job == 'android':
        outcomes.update(BOOT_OUTCOME='${{ steps.android_boot.outcome }}',
            UI_OUTCOME='${{ steps.diagnostic_ui.outcome }}', SHARING_OUTCOME='${{ steps.diagnostic_sharing.outcome }}',
            APPEARANCE_OUTCOME='${{ steps.diagnostic_appearance.outcome }}', WEB_APPEARANCE_OUTCOME='${{ steps.diagnostic_web_appearance.outcome }}',
            FILES_OUTCOME='${{ steps.diagnostic_files.outcome }}')
    else:
        outcomes.update(BOOT_OUTCOME='${{ steps.android_boot.outcome }}', ORIGINAL_RUNNER_OUTCOME='${{ steps.focused.outcome }}')
    script = """python3 - <<'TARGETED_SCOPE'
import hashlib,json,os,pathlib,re,subprocess
root=pathlib.Path.cwd()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
assert source==os.environ['GITHUB_SHA'] and re.fullmatch('[0-9a-f]{40}',tree)
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
assert os.environ['GITHUB_REF']==%r
assert os.environ['GITHUB_RUN_ID'].isdigit() and os.environ['GITHUB_RUN_ATTEMPT']=='1'
phase=os.environ['TARGETED_PHASE'];assert phase in %r
record=dict(schema=1,diagnosticOnly=True,applicationAcceptance=False,releaseAcceptance=False,
    protectionEffectivenessAcceptance=False,physicalPhoneAcceptance=False,qualification=False,
    sourceCommit=source,sourceTree=tree,runId=os.environ['GITHUB_RUN_ID'],runAttempt=os.environ['GITHUB_RUN_ATTEMPT'],
    job=%r,phase=phase,referenceWorkflowSource=%r,referenceWorkflowSha256=%r,
    derivedWorkflowSha256=hashlib.sha256((root/'.github/workflows/gecko-experience-targeted.yml').read_bytes()).hexdigest(),
    maximumOriginalWorkloadInvocations=1,readingZoomTraceRequested=(%r=='android' and phase=='files'),
    uiCheckpointPublisherSuppressedOnly=True,originalStepOutcomes={k:os.environ.get(k) for k in %r},
    scope='Targeted controlled-fixture diagnosis only. Workflow success does not establish all four VM outcomes or release acceptance; a separate complete formal cohort remains required.')
path=root/'work/experience-targeted'/(%r+'-'+phase+'-scope.json');path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(record,sort_keys=True,indent=2)+'\\n')
print(json.dumps(record,sort_keys=True))
TARGETED_SCOPE
""" % ('refs/heads/'+BRANCH, ('ui','files') if job=='android' else (('cold','after-reload') if job=='chrome-diagnostic' else ('build',)),
         job, BASE_SOURCE, BASE_SHA256, job, tuple(outcomes), job)
    marker = {'name': 'Declare diagnostic-only scope and original outcomes', 'if': 'always()',
              'env': {'TARGETED_PHASE': phase, **outcomes}, 'run': script}
    upload = {'name': 'Preserve diagnostic-only scope marker', 'if': 'always()', 'uses': UPLOAD,
              'with': {'name': PREFIX+'scope-${{ github.run_id }}-${{ github.run_attempt }}-'+job+'-'+phase,
                       'path': 'work/experience-targeted/'+job+'-'+phase+'-scope.json',
                       'if-no-files-found': 'error', 'retention-days': 7, 'compression-level': 6}}
    return [marker, upload]

def derive():
    original = base(); verify_ui_checkpoint_only()
    jobs = {}
    removed = 0
    for key in ('build','android','chrome-diagnostic'):
        job = copy.deepcopy(original['jobs'][key]); steps=[]
        for step in job['steps']:
            step=copy.deepcopy(step)
            if step.get('run') == PUBLISH.rstrip('\n'):
                assert key == 'build' and step.get('name') == 'Publish unsigned build for local original signing'
                removed += 1; continue
            if 'run' in step:
                run=step['run']; removed += run.splitlines(keepends=True).count(PUBLISH)
                run=''.join(line for line in run.splitlines(keepends=True) if line != PUBLISH)
                if step.get('name') == 'Verify network performance and compact chrome':
                    assert run.count(UI_LINE)==1
                    run=run.replace(UI_LINE,UI_DIAGNOSTIC_LINE)
                if step.get('name') == 'Verify production environments and file transfers':
                    assert run.count(FILES_LINE)==1
                    run=run.replace(FILES_LINE,FILES_DIAGNOSTIC_LINE)
                assert 'publish_ci.py' not in run
                step['run']=run
            if step.get('uses') in (UPLOAD,DOWNLOAD):
                assert not step['with']['name'].startswith(PREFIX)
                step['with']['name']=PREFIX+step['with']['name']
            if step.get('uses','').startswith('actions/checkout@'):
                step.setdefault('with',{})['persist-credentials']=False
            if step.get('name') in STEP_IDS:
                assert 'id' not in step
                step['id']=STEP_IDS[step['name']]
            steps.append(step)
        job['steps']=steps+scope_steps(key)
        job['permissions']=dict(READ)
        job['if']="github.ref == 'refs/heads/"+BRANCH+"' && github.run_attempt == 1"
        job['name']={'build':'Diagnostic experience build (no release acceptance)',
            'android':'Diagnostic experience (${{ matrix.phase }})',
            'chrome-diagnostic':'Diagnostic experience Chrome (${{ matrix.scenario }})'}[key]
        if key=='android':job['strategy']['matrix']['phase']=['ui','files']
        jobs[key]=job
    assert removed==6
    return {'name':'Diagnostic only: original UI, files and Chrome experience',
        'on':{'push':{'branches':[BRANCH],'paths':PUSH_PATHS}},
        'permissions':dict(READ),'concurrency':{'group':'gecko-experience-targeted-${{ github.ref }}','cancel-in-progress':False},
        'env':copy.deepcopy(original['env']),'jobs':jobs}

def render():
    return yaml.dump(derive(),Dumper=LiteralDumper,sort_keys=False,width=120,allow_unicode=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true')
    a=p.parse_args();text=render()
    if a.write:TARGET.write_text(text)
    else:
        assert TARGET.read_text()==text,'Regenerate targeted graph before freezing source'
        reading_interface_ready((ROOT/'tests/gecko/run_device.py').read_text())
    print('Derived diagnostic graph only; no CI trigger or release qualification.')

if __name__=='__main__':
    main()
