"""Two exact historical source ports for the explicit Chrome v2 dispatcher.

The Android workload and current v2 negative controls never use this module.
The existing first-tap/HOME guard keeps its original fixtures, whole-file pins,
assertions and test methods. Only the reviewed append and its UI read port are
reversed here; unknown whole inputs fail before any old inverse is applied.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = 'tests/gecko/run_chrome_collapse.py'
GUARD = 'tests/profile_chrome_home_resume_test.py'
HEADER = 'tools/gecko/chrome_header_readiness.py'
UI = 'tests/gecko/run_ui_visuals.py'
LEGACY = {
    RUNNER: ((15834, '630b6ac6be99f47316f4d6a49bf646ed43f5d064309b03588e09a01bb423fe67'),
             (15545, 'c2b30b11c52fbca41abfd2df289dcc1f5221194222edb1b6e5170ef0f5a36ac5')),
    GUARD: ((17378, '9388860ff1fea7bfd1f4531a7d01de07700a25e79b21f464680881ec30d10a78'),
            (17207, '2b43c68398b9a926ea44de10fe4a1d11d649f1684dec7282e4f43c36946ac9c9')),
    HEADER: ((19503, '77590576542e0e5faeb88beaab59ae6950361dee88cb6c974260f611a92b26be'),
             (16475, '68bf1296e88147ced5e7908df57b88cfaf211575366f02e0a5022be144fcc65a')),
}
CURRENT = {
    RUNNER: (16350, 'edaa810f470717a45092cce966d451506d2817f9a41def33d62a1d83ed200acf'),
    GUARD: (17471, 'b3b9a6aa3f929bc04a629238c56d02c169450dd50a2110bba04c5b08df958676'),
}
APPEND = b'''

def run_versioned(adb,adb_bytes,source,trace,out,focus,*,navigation_contract):
    """Require an explicit protocol; the historical v1 workload stays intact."""
    if type(navigation_contract) is not int or navigation_contract not in (1,2):
        raise ValueError('Explicit supported Chrome navigation contract required')
    if navigation_contract==1:
        return run(adb,adb_bytes,source,trace,out,focus)
    from run_chrome_collapse_v2 import run_v2
    return run_v2(adb,adb_bytes,source,trace,out,focus)
'''
APPEND_SHA256 = 'b4d612962af421950fe0b80422c9e540cd48b3f457b12d93b2dee200073626de'
PORT_IMPORT = b'from chrome_navigation_v2_source_compatibility import historical_ui_path\n'
OLD_SHARED = b"SHARED=ROOT/'tests/gecko/run_ui_visuals.py'\n"
NEW_SHARED = b"SHARED=historical_ui_path(ROOT/'tests/gecko/run_ui_visuals.py')\n"


def reject():
    raise ValueError('Unreviewed header readiness change')


def pin(raw):
    return len(raw), hashlib.sha256(raw).hexdigest()


def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in LEGACY:
        reject()
    actual = pin(raw)
    if actual in LEGACY[relative]:
        return raw
    if actual != CURRENT.get(relative):
        reject()
    if relative == RUNNER:
        if pin(APPEND) != (516, APPEND_SHA256) or not raw.endswith(APPEND) or raw.count(APPEND) != 1:
            reject()
        restored = raw[:-len(APPEND)]
    elif relative == GUARD:
        if raw.count(PORT_IMPORT) != 1 or raw.count(NEW_SHARED) != 1 or OLD_SHARED in raw:
            reject()
        restored = raw.replace(PORT_IMPORT, b'', 1).replace(NEW_SHARED, OLD_SHARED, 1)
    else:
        reject()
    if pin(restored) != LEGACY[relative][0]:
        reject()
    return restored


class _HistoricalUiPath:
    """A local read port, not a global Path patch or runtime code substitution."""
    def __init__(self, path):
        if not isinstance(path, Path) or path != ROOT/UI or path.is_symlink():
            reject()
        self.path = path

    def read_text(self):
        from ui_workspace_v2_source_compatibility import historical_input
        return historical_input(self.path.read_bytes(), UI).decode('utf-8', 'strict')


def historical_ui_path(path):
    return _HistoricalUiPath(path)
