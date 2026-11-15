"""Finite old comparison values bound to the real 2.1.4 release.

The caller still parses the actual current workflow. Only an exact reviewed
step or the one reviewed Android timeout may use its former comparison value;
unrelated current fields and newly added release checks stay current.
"""
import copy
from functools import lru_cache
import json

import yaml

import cellular_workflow_source_compatibility as cellular
import gradle_transport_source_compatibility as transport
from historical_source_inputs import historical_bytes
import ui_job_budget_source_compatibility as budget


STEPS = (
    ('build', 'Prepare locked toolchain'),
    ('chrome-diagnostic', 'Boot Android for focused diagnostics'),
    ('android', 'Boot Android for native acceptance'),
    ('editing-samples', 'Boot Android for native acceptance'),
    ('browser', 'Boot a fresh real Android emulator with its actual WebView provider'),
    ('tls', 'Boot a fresh real Android emulator with its actual WebView provider'),
)


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


@lru_cache(maxsize=1)
def _reviewed_comparisons():
    # The unchanged whole-source inverses independently check every historical
    # intermediate. No current YAML, unknown hash or additional inverse enters
    # this mapping, and the returned predecessor is never an execution input.
    raw = historical_bytes(budget.PATH)
    before = transport.source_input(
        cellular.source_input(budget.source_input(raw, budget.PATH), budget.PATH), budget.PATH)
    reviewed, previous = yaml.safe_load(raw), yaml.safe_load(before)
    pairs = []
    for owner, name in STEPS:
        current = [step for step in reviewed['jobs'][owner]['steps'] if step.get('name') == name]
        old = [step for step in previous['jobs'][owner]['steps'] if step.get('name') == name]
        assert len(current) == len(old) == 1, 'One exact reviewed workflow step is required'
        assert current[0] != old[0], 'A released comparison must have a proved predecessor'
        pairs.append((_encoded(current[0]), old[0]))
    timeout = reviewed['jobs']['android']['timeout-minutes']
    old_timeout = previous['jobs']['android']['timeout-minutes']
    assert type(timeout) is str and timeout == budget.EXPRESSION
    assert type(old_timeout) is int and old_timeout == 40
    return tuple(pairs), timeout, old_timeout


def released_toolchain_step(step):
    """Compare one actual parsed step only after its full reviewed value matches."""
    if type(step) is not dict or step.get('name') not in {name for _, name in STEPS}:
        return step
    try:
        encoded = _encoded(step)
    except (TypeError, ValueError) as error:
        raise AssertionError('Actual reviewed workflow step is not canonical') from error
    for current, previous in _reviewed_comparisons()[0]:
        if encoded == current:
            return copy.deepcopy(previous)
    raise AssertionError('Actual reviewed workflow step differs from its released value')


def released_job_field_input(job, field, value):
    """Keep every current field raw except the exact reviewed Android timeout."""
    if job != 'android' or field != 'timeout-minutes':
        return value
    _, reviewed, previous = _reviewed_comparisons()
    assert type(value) is str and value == reviewed, 'Actual Android timeout differs from its reviewed value'
    return previous
