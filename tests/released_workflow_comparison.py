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
MAVEN_DOWNLOADS = {
    'Verify independent subscription catalogues and candidate snapshots': (
        ('org/json/json/20240303/json-20240303.jar', 'work/gecko-integration/catalog-json.jar',
         '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed'),
        ('org/yaml/snakeyaml/2.3/snakeyaml-2.3.jar', 'work/gecko-integration/sharing-yaml.jar',
         '63a76fe66b652360bd4c2c107e6f0258daa7d4bb492008ba8c26fcd230ff9146'),
        ('com/vaadin/external/google/android-json/0.0.20131108.vaadin1/android-json-0.0.20131108.vaadin1.jar',
         'work/gecko-integration/sharing-android-json.jar',
         'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'),
    ),
    'Verify versioned environment models and authoritative intents': (
        ('org/json/json/20250517/json-20250517.jar', 'work/profile-host/json.jar',
         '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796'),
    ),
}


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


@lru_cache(maxsize=1)
def _reviewed_maven_comparisons():
    workflow = yaml.safe_load(historical_bytes('.github/workflows/gecko-integration.yml'))
    curl = 'curl -fsSL --retry 2 --retry-max-time 15 --connect-timeout 8 --max-time 25'
    primary = 'https://repo.maven.apache.org/maven2/'
    mirror = 'https://maven-central.storage-download.googleapis.com/maven2/'
    pairs = {}
    for name, downloads in MAVEN_DOWNLOADS.items():
        selected = [step for step in workflow['jobs']['build']['steps'] if step.get('name') == name]
        assert len(selected) == 1, 'One original Maven dependency step is required'
        previous = selected[0]
        script = previous['run']
        for coordinate, output, digest in downloads:
            command = f'curl -fsSL --retry 3 {primary}{coordinate} -o {output}\n'
            checksum = f"echo '{digest}  {output}' | sha256sum -c -\n"
            assert script.count(command + checksum) == 1, 'Original Maven command and checksum must be adjacent'
            fallback = (f'{curl} \\\n  {primary}{coordinate} -o {output} ||\n'
                        f'  {curl} \\\n    {mirror}{coordinate} -o {output}\n')
            script = script.replace(command + checksum, fallback + checksum, 1)
        pairs[name] = (_encoded(dict(previous, run=script)), previous)
    return pairs


def released_toolchain_step(step):
    """Compare one actual parsed step only after its full reviewed value matches."""
    if type(step) is not dict:
        return step
    name = step.get('name')
    if name in MAVEN_DOWNLOADS:
        pairs = (_reviewed_maven_comparisons()[name],)
    elif name in {name for _, name in STEPS}:
        pairs = _reviewed_comparisons()[0]
    else:
        return step
    try:
        encoded = _encoded(step)
    except (TypeError, ValueError) as error:
        raise AssertionError('Actual reviewed workflow step is not canonical') from error
    for current, previous in pairs:
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
