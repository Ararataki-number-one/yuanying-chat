"""Finite workflow input inverse before the unchanged historical test oracle.

Only the exact S10 workflow or its one reviewed diagnostic insertion is accepted.
No command, workload, timeout, matrix or original predicate is filtered out.
"""
import functools
import hashlib

PREVIOUS_SHA256 = 'f158d6cc9409912559519759c8b883468990eb531ddbca1dbc5c8517d10a1218'
CURRENT_SHA256 = '61f948af1adbb5ace54c40cce8b2fff0a3884da6ce128eecf397792845337599'
BEFORE = b'''        python3 -c "$ANDROID_CAPACITY_PREFLIGHT" guest '${{ matrix.phase }}'
'''
STEP = b'''    - name: Record bounded native setup endpoint diagnostics
      if: always()
      shell: bash
      env:
        POCKET_NATIVE_SETUP_PHASE: ${{ matrix.phase }}
        POCKET_NATIVE_SETUP_BOOT_OUTCOME: ${{ steps.android_boot.outcome }}
      run: python3 tests/gecko/print_native_setup11_diagnostic.py
'''
AFTER = b'    - name: Verify network performance and compact chrome\n'


def restore_previous_workflow(raw):
    if type(raw) is not bytes:
        raise AssertionError('Native setup diagnostic workflow must be exact bytes')
    digest = hashlib.sha256(raw).hexdigest()
    if digest == PREVIOUS_SHA256:
        return raw
    if digest != CURRENT_SHA256:
        raise AssertionError('Unreviewed native setup diagnostic workflow bytes')
    context = BEFORE + STEP + AFTER
    if raw.count(context) != 1 or raw.count(STEP) != 1:
        raise AssertionError('Native setup diagnostic insertion context differs')
    previous = raw.replace(context, BEFORE + AFTER, 1)
    if (hashlib.sha256(previous).hexdigest() != PREVIOUS_SHA256
            or previous.count(BEFORE + AFTER) != 1
            or previous.replace(BEFORE + AFTER, context, 1) != raw):
        raise AssertionError('Native setup diagnostic complete inverse differs')
    return previous


def wrap_history_inverse(original):
    @functools.wraps(original)
    def exact_diagnostic_input(case, source):
        if type(source) is not str:
            raise AssertionError('Historical workflow input must remain text')
        return original(case, restore_previous_workflow(source.encode()).decode())
    return exact_diagnostic_input


def wrap_bytes_inverse(original):
    """Keep a historical test's generator input exact without altering its tool."""
    @functools.wraps(original)
    def exact_diagnostic_input(raw):
        return original(restore_previous_workflow(raw))
    return exact_diagnostic_input


# Source13 adds only a diagnostic after the unchanged editing command. Keep
# the complete Source10/11 input port above unchanged and feed it exact11 bytes.
EDITING13_SHA256 = '22f507ecac58d307a237b666460e74c4bd47804c56e9bdd8f3cfed64efcb1578'
EDITING13_BEFORE = b"      if: ${{ matrix.phase == 'editing' }}\n"
EDITING13_STEP = b'''    - name: Record bounded editing transport diagnostics
      if: ${{ always() && matrix.phase == 'editing' }}
      shell: bash
      env:
        POCKET_EDITING_TRANSPORT_PHASE: ${{ matrix.phase }}
        POCKET_EDITING_TRANSPORT_OUTCOME: ${{ steps.editing.outcome }}
      run: python3 tests/gecko/print_editing_transport13_diagnostic.py --adb "$(command -v adb)" --serial emulator-5554
'''
EDITING13_AFTER = b'    - name: Verify network sharing and explicit import UI\n'


def restore_setup11_workflow(raw):
    """Undo only the exact13 insertion; unknown complete workflow bytes fail."""
    if type(raw) is not bytes:
        raise AssertionError('Editing transport diagnostic workflow must be exact bytes')
    digest = hashlib.sha256(raw).hexdigest()
    if digest in (PREVIOUS_SHA256, CURRENT_SHA256):
        return raw
    if digest != EDITING13_SHA256:
        raise AssertionError('Unreviewed editing transport diagnostic workflow bytes')
    context = EDITING13_BEFORE + EDITING13_STEP + EDITING13_AFTER
    if raw.count(context) != 1 or raw.count(EDITING13_STEP) != 1:
        raise AssertionError('Editing transport diagnostic insertion context differs')
    previous = raw.replace(context, EDITING13_BEFORE + EDITING13_AFTER, 1)
    if (hashlib.sha256(previous).hexdigest() != CURRENT_SHA256
            or previous.count(EDITING13_BEFORE + EDITING13_AFTER) != 1
            or previous.replace(EDITING13_BEFORE + EDITING13_AFTER, context, 1) != raw):
        raise AssertionError('Editing transport diagnostic complete inverse differs')
    return previous


def _editing13_input_inverse(original):
    @functools.wraps(original)
    def exact_editing13_input(raw):
        return original(restore_setup11_workflow(raw))
    return exact_editing13_input


restore_previous_workflow = _editing13_input_inverse(restore_previous_workflow)


class Setup11WorkflowInput:
    """One ordinary file's exact historical11 read view for retained oracles.

    The real13 frontend and new controls read the actual Path directly. This
    object wraps only the old test module's fixed WORKFLOW.read_bytes call.
    """
    def __init__(self, path):
        self.path = path

    def read_bytes(self):
        if any(p.is_symlink() for p in (self.path, *self.path.parents)) or not self.path.is_file():
            raise AssertionError('Ordinary setup11 workflow input required')
        if self.path.stat().st_size > 128 * 1024:
            raise AssertionError('Setup11 historical workflow input exceeds bound')
        raw = self.path.read_bytes()
        if len(raw) > 128 * 1024:
            raise AssertionError('Setup11 historical workflow input grew outside bound')
        return restore_setup11_workflow(raw)
