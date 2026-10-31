#!/usr/bin/env python3
"""Check the unchanged historical diagnostic graph using a finite input port.

The original83 generator still rejects a changed main workflow by design. This
tests-only frontend supports --check; it never writes or triggers a workflow and
never contributes formal14 or phone qualification.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from native_setup11_workflow_contract import restore_previous_workflow, wrap_bytes_inverse

GENERATOR = ROOT / 'tools/gecko/generate_experience_targeted_workflow.py'
GENERATOR_SHA256 = '1274bafdf4b9557b60800618ec90ea3f63a312405d321693e406c58c5f630f00'
MAIN_WORKFLOW = ROOT / '.github/workflows/gecko-integration.yml'
MAX_WORKFLOW_BYTES = 128 * 1024


def read_workflow(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise AssertionError('Ordinary historical workflow input required')
    if path.stat().st_size > MAX_WORKFLOW_BYTES:
        raise AssertionError('Historical workflow input exceeds bound')
    raw = path.read_bytes()
    if len(raw) > MAX_WORKFLOW_BYTES:
        raise AssertionError('Historical workflow input grew outside bound')
    restore_previous_workflow(raw)
    return path, raw


def load_generator(workflow_input=MAIN_WORKFLOW):
    path, _ = read_workflow(workflow_input)
    raw = GENERATOR.read_bytes()
    if hashlib.sha256(raw).hexdigest() != GENERATOR_SHA256:
        raise AssertionError('Original approved83 historical generator differs')
    spec = importlib.util.spec_from_file_location('source11_unchanged_historical_generator', GENERATOR)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    # This explicit frontend changes input preparation only. The original
    # base/derive/render definitions, fixed historical source and graph remain.
    original.BASE = path
    original.reviewed_base_bytes = wrap_bytes_inverse(original.reviewed_base_bytes)
    return original


def check(workflow_input=MAIN_WORKFLOW):
    path, raw = read_workflow(workflow_input)
    original = load_generator(path)
    base = original.base()
    graph = original.derive()
    rendered = original.render().encode()
    if rendered != original.TARGET.read_bytes():
        raise AssertionError('Unchanged historical diagnostic graph differs')
    original.reading_interface_ready((ROOT / 'tests/gecko/run_device.py').read_text())
    return dict(schema=1, status='checked-historical-diagnostic-graph-only', diagnosticOnly=True,
                originalGeneratorSha256=GENERATOR_SHA256,
                mainInputSha256=hashlib.sha256(raw).hexdigest(),
                historicalBaseSource=original.BASE_SOURCE, historicalBaseSha256=original.BASE_SHA256,
                originalBaseJobs=sorted(base['jobs']), diagnosticJobs=sorted(graph['jobs']),
                renderedSha256=hashlib.sha256(rendered).hexdigest(),
                workflowWritten=False, ciTriggered=False, formalFourteenQualification=False,
                applicationAcceptance=False, physicalPhoneAcceptance=False,
                originalCliSupportsChangedMain=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True)
    parser.add_argument('--workflow-input', type=Path, default=MAIN_WORKFLOW)
    args = parser.parse_args()
    print(json.dumps(check(args.workflow_input), sort_keys=True))


if __name__ == '__main__':
    main()
