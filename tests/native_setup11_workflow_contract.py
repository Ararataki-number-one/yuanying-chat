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
