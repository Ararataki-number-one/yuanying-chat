"""Exact historical inputs for one UI suite job resource envelope.

Actual workflow execution and raw-workflow controls retain the current bytes.
Only an entire reviewed image may restore the earlier comparison input; no
action deadline, workload, reader, sample or acceptance result is adapted.
"""
import copy
import functools
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = '.github/workflows/browser-2_1-acceptance.yml'
BASE_COMMIT = '89729eb2c079d40237ecd466c7444da934206d98'
BASE_TREE = '583db08f6595ddc8e5a387e5cc035de1e70cb690'
PREVIOUS_BYTES = 92783
PREVIOUS_SHA256 = 'e077be03328741ac49c8043d17af707287c8fff664c0486eb91dbeff6ce0f0e8'
CURRENT_BYTES = 92820
CURRENT_SHA256 = '6d61140b1f654c38b9a9b7cb030c4e4481aa521ca1a662a45abc79f80563e381'
MAX_BYTES = 256 * 1024
EXPRESSION = "${{ matrix.phase == 'ui' && 60 || 40 }}"
DELTAS = (('android/ui-job-container-budget', 50532,
           b'  android:\n    needs: build\n    runs-on: ubuntu-24.04\n    timeout-minutes: 40\n',
           b"  android:\n    needs: build\n    runs-on: ubuntu-24.04\n    timeout-minutes: ${{ matrix.phase == 'ui' && 60 || 40 }}\n"),)

# BEGIN_EXACT_SOURCE_PORTS
SOURCE_PORTS = {'tests/cellular_workflow_source_compatibility.py': {'previousBytes': 18600,
                                                     'previousSha256': '5b30698c2cc47e9856f75c9f515585a3ad9a46050b5d9fb6c67351945e56cda6',
                                                     'reviewedBytes': 19107,
                                                     'reviewedSha256': '9ea0646243693eef2c59b4310309ab38b5e6c9827a1a7072ec24b5744e058dc0',
                                                     'deltas': (('tests/cellular_workflow_source_compatibility.py:204',
                                                                 15351,
                                                                 b'',
                                                                 b'    raw = _ui_job_budget.historical_work'
                                                                 b'flow_input(raw, path)\n'),
                                                                ('tests/cellular_workflow_source_compatibility.py:254',
                                                                 17574,
                                                                 b'',
                                                                 b'    raw = _ui_job_budget.workflow_read_i'
                                                                 b'nput(path)\n'),
                                                                ('tests/cellular_workflow_source_compatibility.py:256',
                                                                 17716,
                                                                 b'            and path.stat().st_size == C'
                                                                 b"URRENT_BYTES), 'Ordinary exact current w"
                                                                 b"orkflow required'\n    raw = path.read_by"
                                                                 b'tes()\n',
                                                                 b'            and len(raw) == CURRENT_BYTE'
                                                                 b"S), 'Ordinary exact current workflow req"
                                                                 b"uired'\n"),
                                                                ('tests/cellular_workflow_source_compatibility.py:287',
                                                                 18674,
                                                                 b'',
                                                                 b'\n\n# A single reviewed UI job envelope ma'
                                                                 b'y feed these unchanged historical pins.\n'
                                                                 b'import importlib.util as _ui_job_budget_'
                                                                 b'import\n_ui_job_budget_spec = _ui_job_bud'
                                                                 b"get_import.spec_from_file_location('sele"
                                                                 b"cted_ui_job_budget_source_input', Path(_"
                                                                 b"_file__).with_name('ui_job_budget_source"
                                                                 b"_compatibility.py'))\n_ui_job_budget = _u"
                                                                 b'i_job_budget_import.module_from_spec(_ui'
                                                                 b'_job_budget_spec)\n_ui_job_budget_spec.lo'
                                                                 b'ader.exec_module(_ui_job_budget)\n'))},
 'tests/profile_cellular_workflow_source_compatibility_test.py': {'previousBytes': 13629,
                                                                  'previousSha256': '4f62dabfe27e263d20d7b51f63022b54d3740435b60a49afdc71d49db293a01a',
                                                                  'reviewedBytes': 13818,
                                                                  'reviewedSha256': '03186279c7e39900fb20ad0da243d92b2eb8f25cb3cc178aa82f2c00cbb2d2e9',
                                                                  'deltas': (('tests/profile_cellular_workflow_source_compatibility_test.py:14',
                                                                              376,
                                                                              b'',
                                                                              b'import ui_job_budget_source_'
                                                                              b'compatibility as ui_job_budg'
                                                                              b'et\n'),
                                                                             ('tests/profile_cellular_workflow_source_compatibility_test.py:49',
                                                                              1708,
                                                                              b'        return (ROOT / cellu'
                                                                              b'lar.PATH).read_bytes()\n',
                                                                              b'        return ui_job_budget'
                                                                              b'.historical_workflow_input(('
                                                                              b'ROOT / cellular.PATH).read_b'
                                                                              b'ytes(), cellular.PATH)\n'),
                                                                             ('tests/profile_cellular_workflow_source_compatibility_test.py:205',
                                                                              11706,
                                                                              b'        self.assertEqual(cls'
                                                                              b'.new, yaml.safe_load(raw))\n',
                                                                              b'        self.assertEqual(ui_'
                                                                              b'job_budget.historical_yaml_i'
                                                                              b'nput(cls.new), yaml.safe_loa'
                                                                              b'd(raw))\n'),
                                                                             ('tests/profile_cellular_workflow_source_compatibility_test.py:208',
                                                                              12024,
                                                                              b'        self.assertEqual(cls'
                                                                              b'.new, yaml.safe_load(raw))\n',
                                                                              b'        self.assertEqual(ui_'
                                                                              b'job_budget.historical_yaml_i'
                                                                              b'nput(cls.new), yaml.safe_loa'
                                                                              b'd(raw))\n'))},
 'tests/browser_acceptance_workflow_test.py': {'previousBytes': 7771,
                                               'previousSha256': '31e23b6ea823bfc5d79132e0eec22f927d54c2c1ce3ab982fe672f6d926cb5d0',
                                               'reviewedBytes': 7910,
                                               'reviewedSha256': 'd33fcea3bd599bf116e180a8bd2aff3fcbdd544a99f983ecc4076ad070261c66',
                                               'deltas': (('tests/browser_acceptance_workflow_test.py:13',
                                                           327,
                                                           b'',
                                                           b'from ui_job_budget_source_compatibility import h'
                                                           b'istorical_job_field_input as ui_job_budget_field'
                                                           b'_input\n'),
                                                          ('tests/browser_acceptance_workflow_test.py:40',
                                                           1784,
                                                           b'                        self.assertEqual(current'
                                                           b"[key],value+['browser','tls'] if name=='verify' "
                                                           b"and key=='needs' else value)\n",
                                                           b'                        self.assertEqual(ui_job_'
                                                           b'budget_field_input(name,key,current[key]),value+'
                                                           b"['browser','tls'] if name=='verify' and key=='ne"
                                                           b"eds' else value)\n"))},
 'tests/browser_ip_timezone_publish_gate_test.py': {'previousBytes': 13131,
                                                    'previousSha256': '5a09c0f219fe3392051cb8167e298767c452b3335680b1203e53e4366f9514ed',
                                                    'reviewedBytes': 13274,
                                                    'reviewedSha256': '01615f9651000795b42213289f74c4f5002ad891bf394bfb9feed24eda5e2e04',
                                                    'deltas': (('tests/browser_ip_timezone_publish_gate_test.py:16',
                                                                399,
                                                                b'',
                                                                b'from ui_job_budget_source_compatibility '
                                                                b'import historical_job_field_input as ui_'
                                                                b'job_budget_field_input\n'),
                                                               ('tests/browser_ip_timezone_publish_gate_test.py:160',
                                                                10468,
                                                                b'                    self.assertEqual(cur'
                                                                b"rent['jobs'][name].get(field), expected,"
                                                                b' (name, field))\n',
                                                                b'                    self.assertEqual(ui_'
                                                                b'job_budget_field_input(name, field, curr'
                                                                b"ent['jobs'][name].get(field)), expected,"
                                                                b' (name, field))\n'))},
 'tests/final_browser_source_compatibility.py': {'previousBytes': 17069,
                                                 'previousSha256': '496d31b89d756d63476ecc53f5f652625ad6fdf516eff02575c380f6cf1ba5d0',
                                                 'reviewedBytes': 17318,
                                                 'reviewedSha256': '48f045aacf673d4a90eadc17ae44055bbca843594cb0d3f8bd80d326124cf19a',
                                                 'deltas': (('tests/final_browser_source_compatibility.py:262',
                                                             17069,
                                                             b'',
                                                             b'\n\n# Only the whole reviewed UI job metadata '
                                                             b'test reaches the older build guard.\nfrom ui_'
                                                             b'job_budget_source_compatibility import wrap_'
                                                             b'build_budget_input as _ui_job_budget_build_i'
                                                             b'nput\nbuild_budget_input = _ui_job_budget_bui'
                                                             b'ld_input(build_budget_input)\n'),)},
 'tests/workspace_runner_source_compatibility.py': {'previousBytes': 24754,
                                                    'previousSha256': '295f3672ca903056348379baa7f8fa6d88e76257f431a96f04fac9e861ab74fc',
                                                    'reviewedBytes': 25052,
                                                    'reviewedSha256': 'ea6ea4364a59fba80c95e7c034adb5ab11ec2eff910f6e2ec815963f74ca0807',
                                                    'deltas': (('tests/workspace_runner_source_compatibility.py:261',
                                                                24754,
                                                                b'',
                                                                b'\n\n# Exact UI job metadata inputs precede'
                                                                b' the unchanged workspace source guards.\n'
                                                                b'from ui_job_budget_source_compatibility '
                                                                b'import wrap_source_input as _ui_job_budg'
                                                                b'et_source_input\nsource_input = _ui_job_b'
                                                                b'udget_source_input(source_input)\nhistori'
                                                                b'cal_input = _ui_job_budget_source_input('
                                                                b'historical_input)\n'),)},
 'tests/profile_final_browser_source_compatibility_test.py': {'previousBytes': 89714,
                                                              'previousSha256': '30d7ddd93d3f86188050cbc04eefc2faa39014a87bebc9a3e1dfbea191b6ce61',
                                                              'reviewedBytes': 89931,
                                                              'reviewedSha256': '4179285fb49e92d1e3cc3ab561021620fd642d29ec7f38064380183905f9837a',
                                                              'deltas': (('tests/profile_final_browser_source_compatibility_test.py:26',
                                                                          848,
                                                                          b'',
                                                                          b'from ui_job_budget_source_compat'
                                                                          b'ibility import historical_source'
                                                                          b'_input as ui_job_budget_source_i'
                                                                          b'nput\n'),
                                                                         ('tests/profile_final_browser_source_compatibility_test.py:1118',
                                                                          75898,
                                                                          b"        ip_raw = (ROOT/'tests/br"
                                                                          b'owser_ip_timezone_publish_gate_t'
                                                                          b"est.py').read_bytes()\n",
                                                                          b'        ip_raw = ui_job_budget_s'
                                                                          b"ource_input((ROOT/'tests/browser"
                                                                          b'_ip_timezone_publish_gate_test.p'
                                                                          b"y').read_bytes(), 'tests/browser"
                                                                          b'_ip_timezone_publish_gate_test.p'
                                                                          b"y')\n"),
                                                                         ('tests/profile_final_browser_source_compatibility_test.py:1204',
                                                                          83098,
                                                                          b'        current = (ROOT/relative'
                                                                          b').read_bytes()\n',
                                                                          b'        current = ui_job_budget_'
                                                                          b'source_input((ROOT/relative).rea'
                                                                          b'd_bytes(), relative)\n'))},
 'tests/profile_gradle_workflow_test_source_compatibility_test.py': {'previousBytes': 6893,
                                                                     'previousSha256': '5563bda90d57ad303973dbaaabc571bf9bd007d0656a94e3babe57a8b65591ba',
                                                                     'reviewedBytes': 7123,
                                                                     'reviewedSha256': '6eff4f1c2b22871ff6712f69d79103bf95c380f9b818757ea8898cb334831b6c',
                                                                     'deltas': (('tests/profile_gradle_workflow_test_source_compatibility_test.py:12',
                                                                                 378,
                                                                                 b'',
                                                                                 b'from ui_job_budget_sourc'
                                                                                 b'e_compatibility import h'
                                                                                 b'istorical_source_input a'
                                                                                 b's ui_job_budget_source_i'
                                                                                 b'nput\n'),
                                                                                ('tests/profile_gradle_workflow_test_source_compatibility_test.py:67',
                                                                                 3631,
                                                                                 b'        raw = (ROOT / fi'
                                                                                 b'nal.BUILD_BUDGET_PATH).r'
                                                                                 b'ead_bytes()\n',
                                                                                 b'        raw = ui_job_bud'
                                                                                 b'get_source_input((ROOT /'
                                                                                 b' final.BUILD_BUDGET_PATH'
                                                                                 b').read_bytes(), final.BU'
                                                                                 b'ILD_BUDGET_PATH)\n'),
                                                                                ('tests/profile_gradle_workflow_test_source_compatibility_test.py:84',
                                                                                 4876,
                                                                                 b'        self.assertEqual'
                                                                                 b'(before, (ROOT / inputs.'
                                                                                 b'FINAL).read_bytes())\n',
                                                                                 b'        self.assertEqual'
                                                                                 b'(before, ui_job_budget_s'
                                                                                 b'ource_input((ROOT / inpu'
                                                                                 b'ts.FINAL).read_bytes(), '
                                                                                 b'inputs.FINAL))\n'),
                                                                                ('tests/profile_gradle_workflow_test_source_compatibility_test.py:107',
                                                                                 6512,
                                                                                 b'            self.assertE'
                                                                                 b'qual(bodies((ROOT / path'
                                                                                 b').read_bytes()), bodies('
                                                                                 b"git('show', value['baseC"
                                                                                 b"ommit'] + ':' + path)))\n",
                                                                                 b'            self.assertE'
                                                                                 b'qual(bodies(ui_job_budge'
                                                                                 b't_source_input((ROOT / p'
                                                                                 b'ath).read_bytes(), path)'
                                                                                 b"), bodies(git('show', va"
                                                                                 b"lue['baseCommit'] + ':' "
                                                                                 b'+ path)))\n'))},
 'tests/profile_workspace_runner_source_compatibility_test.py': {'previousBytes': 10082,
                                                                 'previousSha256': '1ca7835f527028893428180f75ed6ca1e65965785ce31a601cabe1139b8cf7d9',
                                                                 'reviewedBytes': 10335,
                                                                 'reviewedSha256': '04b0e992735319551a41d876d05b0e67e1c1eae9550160d96719bbb33900ec8d',
                                                                 'deltas': (('tests/profile_workspace_runner_source_compatibility_test.py:11',
                                                                             260,
                                                                             b'',
                                                                             b'from ui_job_budget_source_co'
                                                                             b'mpatibility import historica'
                                                                             b'l_source_input as ui_job_bud'
                                                                             b'get_source_input\n'),
                                                                            ('tests/profile_workspace_runner_source_compatibility_test.py:35',
                                                                             1469,
                                                                             b'                current = (R'
                                                                             b'OOT/relative).read_bytes()\n',
                                                                             b'                current = ui'
                                                                             b'_job_budget_source_input((RO'
                                                                             b'OT/relative).read_bytes(), r'
                                                                             b'elative)\n'),
                                                                            ('tests/profile_workspace_runner_source_compatibility_test.py:70',
                                                                             4245,
                                                                             b'            current = (ROOT/'
                                                                             b'relative).read_bytes()\n',
                                                                             b'            current = ui_job'
                                                                             b'_budget_source_input((ROOT/r'
                                                                             b'elative).read_bytes(), relat'
                                                                             b'ive)\n'),
                                                                            ('tests/profile_workspace_runner_source_compatibility_test.py:77',
                                                                             4754,
                                                                             b'            current = (ROOT/'
                                                                             b'relative).read_bytes()\n',
                                                                             b'            current = ui_job'
                                                                             b'_budget_source_input((ROOT/r'
                                                                             b'elative).read_bytes(), relat'
                                                                             b'ive)\n'),
                                                                            ('tests/profile_workspace_runner_source_compatibility_test.py:87',
                                                                             5456,
                                                                             b'            current = (ROOT/'
                                                                             b'relative).read_bytes()\n',
                                                                             b'            current = ui_job'
                                                                             b'_budget_source_input((ROOT/r'
                                                                             b'elative).read_bytes(), relat'
                                                                             b'ive)\n'))}}
# END_EXACT_SOURCE_PORTS


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _inverse(raw, size, digest, previous_size, previous_digest, deltas):
    assert type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'Complete bounded UI budget source required'
    assert (len(raw), sha(raw)) == (size, digest), 'Unknown complete UI budget after-image'
    right = len(raw)
    for owner, offset, before, after in reversed(deltas):
        assert type(owner) is str and owner and type(offset) is int and offset >= 0
        assert type(before) is bytes and type(after) is bytes and 0 < len(after) <= 32768
        assert len(before) <= 32768 and offset + len(after) <= right, 'Overlapping UI budget contexts'
        assert raw[offset:offset + len(after)] == after, 'Missing, moved or changed UI budget context'
        raw = raw[:offset] + before + raw[offset + len(after):]
        right = offset
    assert (len(raw), sha(raw)) == (previous_size, previous_digest), 'Entire UI budget predecessor did not restore'
    return raw


def source_input(raw, path):
    assert type(path) is str and path == PATH, 'Exact owned UI budget workflow path required'
    assert len(DELTAS) == 1, 'Only the android UI job resource envelope is owned'
    return _inverse(raw, CURRENT_BYTES, CURRENT_SHA256, PREVIOUS_BYTES, PREVIOUS_SHA256, DELTAS)


def historical_workflow_input(raw, path):
    if (type(raw) is bytes and type(path) is str and path == PATH
            and len(raw) == CURRENT_BYTES and sha(raw) == CURRENT_SHA256):
        return source_input(raw, path)
    return raw


def workflow_read_input(path):
    """Read one ordinary bounded file before restoring its historical bytes."""
    assert (isinstance(path, Path) and path.is_file() and not path.is_symlink()
            and path.resolve() == path.absolute()
            and path.stat().st_size in (PREVIOUS_BYTES, CURRENT_BYTES)), 'Ordinary exact UI budget workflow required'
    raw = historical_workflow_input(path.read_bytes(), PATH)
    assert (len(raw), sha(raw)) == (PREVIOUS_BYTES, PREVIOUS_SHA256), 'Unreviewed actual UI budget workflow'
    return raw


def _actual_workflow():
    path = ROOT / PATH
    assert (path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
            and path.stat().st_size == CURRENT_BYTES), 'Ordinary actual UI budget after-image required'
    raw = path.read_bytes()
    source_input(raw, PATH)
    return raw


def historical_yaml_input(value):
    """One historical comparison LHS; never mutate the raw parsed workflow."""
    import yaml
    raw = _actual_workflow()
    encode = lambda item: json.dumps(item, sort_keys=True, separators=(',', ':'), allow_nan=False)
    assert type(value) is dict and encode(value) == encode(yaml.safe_load(raw)), 'Exact actual workflow object required'
    return yaml.safe_load(source_input(raw, PATH))


def historical_job_field_input(job, field, value):
    """Restore only the reviewed android job timeout for an older assertion."""
    if job == 'android' and field == 'timeout-minutes' and type(value) is str and value == EXPRESSION:
        _actual_workflow()
        return 40
    return value


def source_port_input(raw, path):
    assert type(path) is str and path in SOURCE_PORTS, 'Exact owned UI budget source port required'
    row = SOURCE_PORTS[path]
    return _inverse(raw, row['reviewedBytes'], row['reviewedSha256'],
                    row['previousBytes'], row['previousSha256'], row['deltas'])


def historical_source_input(raw, path):
    if type(raw) is bytes and type(path) is str and path in SOURCE_PORTS:
        row = SOURCE_PORTS[path]
        if (len(raw), sha(raw)) == (row['reviewedBytes'], row['reviewedSha256']):
            return source_port_input(raw, path)
    return raw


def wrap_source_input(original):
    @functools.wraps(original)
    def prior(raw, path):
        return original(historical_source_input(raw, path), path)
    return prior


def wrap_build_budget_input(original):
    """Keep the original one-test path boundary of the older build adapter."""
    @functools.wraps(original)
    def prior(raw, path):
        if type(path) is str and path == 'tests/browser_acceptance_workflow_test.py':
            raw = historical_source_input(raw, path)
        return original(raw, path)
    return prior
