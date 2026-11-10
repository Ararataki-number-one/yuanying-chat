"""Finite cellular preparation inputs for unchanged historical source oracles.

Only the complete reviewed workflow may reverse its eight preparation CLI
replacements and one mandatory host-control step. Execution, installed bytes,
workloads, readers, budgets and raw current-workflow checks never use an inverse.
The five source ports below reverse only their exact added input wiring; old
predicates, old source hashes and all historical fixtures remain unchanged.
"""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = '.github/workflows/browser-2_1-acceptance.yml'
BASE_COMMIT = 'b55eee51d143170b46a5363aa5c6e120f07b982c'
BASE_TREE = 'cbb6692ea39577f5a15930a3953746027082972f'
PREVIOUS_BYTES = 92383
PREVIOUS_SHA256 = '2629831d0afd9176b0ce4d92a4c03117b66a3f20c4912885b4c31b391160f83e'
CURRENT_BYTES = 92783
CURRENT_SHA256 = 'e077be03328741ac49c8043d17af707287c8fff664c0486eb91dbeff6ce0f0e8'
MAX_BYTES = 131072

# (owner, exact after-image byte offset, predecessor bytes, reviewed bytes).
# Offsets and the complete-file SHA reject moved or duplicated commands.
DELTAS = (('build/strict-cellular-host-controls',
  7217,
  b'',
  b'    - name: Verify strict cellular emulator preparation controls\n      shell: bash\n      run: |\n    '
  b'    set -euo pipefail\n        python3 tests/gecko_cellular_bootstrap_test.py\n        python3 tests/p'
  b'rofile_cellular_workflow_source_compatibility_test.py\n'),
 ('chrome-diagnostic/native',
  46838,
  b'python3 tools/gecko/prepare_native_adb.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase native'),
 ('chrome-diagnostic/normal',
  47117,
  b'python3 tools/gecko/prepare_emulator.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase normal'),
 ('android/native',
  53783,
  b'python3 tools/gecko/prepare_native_adb.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase native'),
 ('android/normal',
  54062,
  b'python3 tools/gecko/prepare_emulator.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase normal'),
 ('editing-samples/native',
  69280,
  b'python3 tools/gecko/prepare_native_adb.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase native'),
 ('editing-samples/normal',
  69559,
  b'python3 tools/gecko/prepare_emulator.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase normal'),
 ('browser/normal',
  83431,
  b'python3 tools/gecko/prepare_emulator.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase normal'),
 ('tls/normal',
  90848,
  b'python3 tools/gecko/prepare_emulator.py',
  b'python3 tools/gecko/prepare_cellular_adb.py --phase normal'))

# Exact source read ports, with complete before/after images. These are not
# execution inputs or substitutes for any old predicate.
SOURCE_PORTS = {'tests/gradle_transport_source_compatibility.py': {'previousBytes': 4169,
                                                    'previousSha256': 'c2441890bd30cd1125118e9ff7e20960aadb41620d290ddace93ffb09a23ac30',
                                                    'reviewedBytes': 4879,
                                                    'reviewedSha256': '5df5db81e05487312585a9ee9af78085d705b3c829fa293c5d0dbddda455f1ea',
                                                    'deltas': (('tests/gradle_transport_source_compatibility.py:82',
                                                                4169,
                                                                b'',
                                                                b'\n\n# Only exact reviewed preparation inpu'
                                                                b'ts are reversed for historical oracles.\n'
                                                                b'# Current execution and current YAML che'
                                                                b'cks keep the complete actual workflow.\ni'
                                                                b'mport importlib.util as _cellular_import'
                                                                b'\n_cellular_spec = _cellular_import.spec_'
                                                                b"from_file_location('selected_cellular_wo"
                                                                b"rkflow_source_input', Path(__file__).wit"
                                                                b"h_name('cellular_workflow_source_compati"
                                                                b"bility.py'))\n_cellular_input = _cellular"
                                                                b'_import.module_from_spec(_cellular_spec)'
                                                                b'\n_cellular_spec.loader.exec_module(_cell'
                                                                b'ular_input)\nsource_input = _cellular_inp'
                                                                b'ut.wrap_bytes(source_input)\ncanonical_hi'
                                                                b'story_input = _cellular_input.wrap_workf'
                                                                b'low(canonical_history_input)\nhistorical_'
                                                                b'toolchain_step = _cellular_input.wrap_st'
                                                                b'ep(historical_toolchain_step)\n'),)},
 'tests/profile_gradle_transport_source_compatibility_test.py': {'previousBytes': 7645,
                                                                 'previousSha256': 'b10f1118c9abc58b654624ae3c88375d5d5d54e9dd48443bb775b3ea4a1252e1',
                                                                 'reviewedBytes': 7867,
                                                                 'reviewedSha256': '15d545e70c01259b8afa80587707df9c34cab036a98d7ce532a8792079e48cc3',
                                                                 'deltas': (('tests/profile_gradle_transport_source_compatibility_test.py:15',
                                                                             532,
                                                                             b'',
                                                                             b'from cellular_workflow_sourc'
                                                                             b'e_compatibility import histo'
                                                                             b'rical_input as cellular_work'
                                                                             b'flow_source_input\n'),
                                                                            ('tests/profile_gradle_transport_source_compatibility_test.py:30',
                                                                             1524,
                                                                             b'',
                                                                             b'            raw = cellular_w'
                                                                             b'orkflow_source_input(raw, pa'
                                                                             b'th)\n'),
                                                                            ('tests/profile_gradle_transport_source_compatibility_test.py:46',
                                                                             2751,
                                                                             b'',
                                                                             b'            raw = cellular_w'
                                                                             b'orkflow_source_input(raw, pa'
                                                                             b'th)\n'))},
 'tests/profile_environment_workspace_workflow_source_compatibility_test.py': {'previousBytes': 15505,
                                                                               'previousSha256': '86cea5903cc471ccd8e9e2cced19f6bb857c24d7061a7585571219e6e6826c47',
                                                                               'reviewedBytes': 15648,
                                                                               'reviewedSha256': '822c9334b5699e725cb4ec2a5fd4bbc8e0dd2f3db7b0213139affeb86f8a5f16',
                                                                               'deltas': (('tests/profile_environment_workspace_workflow_source_compatibility_test.py:14',
                                                                                           376,
                                                                                           b'',
                                                                                           b'from cellular_wo'
                                                                                           b'rkflow_source_co'
                                                                                           b'mpatibility impo'
                                                                                           b'rt source_port_i'
                                                                                           b'nput as cellular'
                                                                                           b'_source_port_inp'
                                                                                           b'ut\n'),
                                                                                          ('tests/profile_environment_workspace_workflow_source_compatibility_test.py:216',
                                                                                           13780,
                                                                                           b'        source ='
                                                                                           b' (ROOT / path).r'
                                                                                           b'ead_text()\n',
                                                                                           b'        source ='
                                                                                           b' cellular_source'
                                                                                           b'_port_input((ROO'
                                                                                           b'T / path).read_b'
                                                                                           b'ytes(), path).de'
                                                                                           b'code()\n'))},
 'tests/native_timezone_probe_test.py': {'previousBytes': 28339,
                                         'previousSha256': '84a00beace7cd5fff27311fee1d417deb83c639cc3f505f66099cbfa67cc04d9',
                                         'reviewedBytes': 28483,
                                         'reviewedSha256': '0ccb3b65fcff511489ebad1cb84021651088c95428070e4e13d003122059260e',
                                         'deltas': (('tests/native_timezone_probe_test.py:19',
                                                     377,
                                                     b'',
                                                     b'from cellular_workflow_source_compatibility import h'
                                                     b'istorical_workflow_text as cellular_workflow_history'
                                                     b'_input\n'),
                                                    ('tests/native_timezone_probe_test.py:216',
                                                     15070,
                                                     b"        original=yaml.safe_load((ROOT/'.github/workf"
                                                     b"lows/browser-2_1-acceptance.yml').read_text())\n",
                                                     b'        original=yaml.safe_load(cellular_workflow_hi'
                                                     b"story_input((ROOT/'.github/workflows/browser-2_1-acc"
                                                     b"eptance.yml').read_text()))\n"))},
 'tests/gecko_cpu_acceptance_test.py': {'previousBytes': 46552,
                                        'previousSha256': '74c373fcbd99d4588303203601617855225e644328044319a9102f50d89754df',
                                        'reviewedBytes': 46696,
                                        'reviewedSha256': '20e2f3b9a77589bfeff39070d8a7c18ce6ee665188b8c246eed041d2ca993a28',
                                        'deltas': (('tests/gecko_cpu_acceptance_test.py:21',
                                                    405,
                                                    b'',
                                                    b'from cellular_workflow_source_compatibility import h'
                                                    b'istorical_workflow_text as cellular_workflow_history'
                                                    b'_input\n'),
                                                   ('tests/gecko_cpu_acceptance_test.py:376',
                                                    34214,
                                                    b"        original=yaml.safe_load((ROOT/'.github/workf"
                                                    b"lows/browser-2_1-acceptance.yml').read_text())\n",
                                                    b'        original=yaml.safe_load(cellular_workflow_hi'
                                                    b"story_input((ROOT/'.github/workflows/browser-2_1-acc"
                                                    b"eptance.yml').read_text()))\n"))}}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _inverse(raw, size, digest, previous_size, previous_digest, deltas):
    assert type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'Complete bounded source bytes required'
    assert (len(raw), sha(raw)) == (size, digest), 'Unknown complete cellular source after-image'
    right = len(raw)
    for owner, offset, before, after in reversed(deltas):
        assert type(owner) is str and owner and type(offset) is int and offset >= 0
        assert type(before) is bytes and type(after) is bytes and 0 < len(after) <= 32768
        assert len(before) <= 32768 and offset + len(after) <= right, 'Overlapping cellular source contexts'
        assert raw[offset:offset + len(after)] == after, 'Missing, changed or moved exact cellular context'
        raw = raw[:offset] + before + raw[offset + len(after):]
        right = offset
    assert (len(raw), sha(raw)) == (previous_size, previous_digest), 'Entire original source did not restore'
    return raw


def source_input(raw, path):
    assert type(path) is str and path == PATH, 'Exact owned cellular workflow path required'
    assert len(DELTAS) == 9, 'Only eight preparation calls and one host step are owned'
    return _inverse(raw, CURRENT_BYTES, CURRENT_SHA256, PREVIOUS_BYTES, PREVIOUS_SHA256, DELTAS)


def historical_input(raw, path):
    """Recognize only the complete after-image; all else faces its old oracle."""
    raw = _ui_job_budget.historical_workflow_input(raw, path)
    if (type(raw) is bytes and type(path) is str and path == PATH
            and len(raw) == CURRENT_BYTES and sha(raw) == CURRENT_SHA256):
        return source_input(raw, path)
    return raw


def historical_workflow_text(source):
    assert type(source) is str, 'Complete workflow text required'
    raw = source.encode()
    restored = historical_input(raw, PATH)
    return restored.decode() if restored is not raw else source


def source_port_input(raw, path):
    assert type(path) is str and path in SOURCE_PORTS, 'Exact owned cellular source read port required'
    row = SOURCE_PORTS[path]
    return _inverse(raw, row['reviewedBytes'], row['reviewedSha256'],
                    row['previousBytes'], row['previousSha256'], row['deltas'])


def _encoded_step(step):
    return json.dumps(step, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


@functools.lru_cache(maxsize=1)
def _step_pairs(raw):
    # The caller checks actual current whole bytes before this parse cache.
    import yaml
    before = yaml.safe_load(source_input(raw, PATH))
    after = yaml.safe_load(raw)
    pairs = []
    for owner in ('chrome-diagnostic', 'android', 'editing-samples', 'browser', 'tls'):
        selected = [step for step in after['jobs'][owner]['steps']
                    if 'python3 tools/gecko/prepare_cellular_adb.py' in step.get('run', '')]
        assert len(selected) == 1, 'One exact preparation step per original job required'
        current = selected[0]
        previous = [step for step in before['jobs'][owner]['steps'] if step.get('name') == current['name']]
        assert len(previous) == 1, 'One original preparation step required'
        pairs.append((_encoded_step(current), previous[0]))
    return tuple(pairs)


def historical_step_input(step):
    """One old comparison LHS; actual parsed workflow dictionaries stay raw."""
    if (type(step) is not dict or step.get('name') not in (
            'Boot Android for focused diagnostics', 'Boot Android for native acceptance',
            'Boot a fresh real Android emulator with its actual WebView provider')):
        return step
    path = ROOT / PATH
    raw = _ui_job_budget.workflow_read_input(path)
    assert (path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
            and len(raw) == CURRENT_BYTES), 'Ordinary exact current workflow required'
    assert (len(raw), sha(raw)) == (CURRENT_BYTES, CURRENT_SHA256), 'Actual cellular workflow is unreviewed'
    try:
        encoded = _encoded_step(step)
    except (TypeError, ValueError):
        return step
    for current, previous in _step_pairs(raw):
        if encoded == current:
            return copy.deepcopy(previous)
    return step


def wrap_bytes(original):
    @functools.wraps(original)
    def previous_source(raw, path):
        return original(historical_input(raw, path), path)
    return previous_source


def wrap_workflow(original):
    @functools.wraps(original)
    def previous_workflow(raw):
        return original(historical_input(raw, PATH))
    return previous_workflow


def wrap_step(original):
    @functools.wraps(original)
    def previous_step(step):
        return original(historical_step_input(step))
    return previous_step


# A single reviewed UI job envelope may feed these unchanged historical pins.
import importlib.util as _ui_job_budget_import
_ui_job_budget_spec = _ui_job_budget_import.spec_from_file_location('selected_ui_job_budget_source_input', Path(__file__).with_name('ui_job_budget_source_compatibility.py'))
_ui_job_budget = _ui_job_budget_import.module_from_spec(_ui_job_budget_spec)
_ui_job_budget_spec.loader.exec_module(_ui_job_budget)
