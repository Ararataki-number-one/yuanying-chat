"""Exact historical view of four dashboard-only CI transport additions.

Only the old privacy source oracle uses this view. Actual pack/restore and their
transport controls execute the current source. No Git object or network read is
needed in a shallow CI checkout; both complete byte identities are fixed here.
"""
import hashlib


BEFORE = (14358, '7efcea13daac3874bbf8bf945bca3e213d9b3224020738fe5398582e4ecd3e5a')
AFTER = (15719, '1c232eeb787787895c99e20a8e5f4b36f309b3828fd9e8b14866655d06a4c01f')
OWNER = '62b37a9c52b899ce593a9cec85050d70fb32e56e'
PATH = 'tools/gecko/ci_bundle.py'
HUNKS = (
    ("    'device-event-sequence-current.stderr.log',\n))\n\n# Script and importlib consumers",
     """    'device-event-sequence-current.stderr.log',
))
DASHBOARD_CAPTURE_DIR = OUT / 'ui-visuals' / 'environment-dashboard'
DASHBOARD_CAPTURE_FILES = frozenset(name + suffix for name in (
    'light', 'light-fingerprint', 'home-return', 'warm-list', 'second-environment',
    'workspace-chat', 'large-font', 'large-font-fingerprint', 'landscape',
    'landscape-fingerprint', 'dark', 'dark-fingerprint', 'failure',
) for suffix in ('.png', '.xml'))

# Script and importlib consumers"""),
    ("""    if path.suffix.lower() in ('.jks', '.p12', '.keystore', '.pem'):
        return False
    if path.parent.parent == PurePosixPath(str(OUT)) and path.parent.name in NETWORK_IDENTITY_RAW_DIRS:
""",
     """    if path.suffix.lower() in ('.jks', '.p12', '.keystore', '.pem'):
        return False
    if path.parent == PurePosixPath(str(DASHBOARD_CAPTURE_DIR)):
        return kind == 'phase' and path.name in DASHBOARD_CAPTURE_FILES
    if path.parent.parent == PurePosixPath(str(OUT)) and path.parent.name in NETWORK_IDENTITY_RAW_DIRS:
"""),
    ("""        for directory in ('caret-compat', 'ui-visuals'):
            candidates += [p for p in (root / OUT / directory).glob('*') if p.is_file()]
    files = []
""",
     """        for directory in ('caret-compat', 'ui-visuals'):
            candidates += [p for p in (root / OUT / directory).glob('*') if p.is_file()]
        directory = root / DASHBOARD_CAPTURE_DIR
        if directory.exists() or directory.is_symlink():
            assert directory.is_dir() and all(not path.is_symlink() for path in (
                root, root/'work', root/OUT, directory.parent, directory)), 'CI bundle refuses redirected dashboard evidence directory'
            candidates += [directory / name for name in sorted(DASHBOARD_CAPTURE_FILES)
                           if (directory / name).exists() or (directory / name).is_symlink()]
    files = []
"""),
    ("""            assert allowed(row['path'], kind), 'CI archive path outside the exact input/evidence roots'
            member = archive.getmember(row['path'])
""",
     """            assert allowed(row['path'], kind), 'CI archive path outside the exact input/evidence roots'
            if Path(row['path']).parent == DASHBOARD_CAPTURE_DIR:
                assert all(not path.is_symlink() for path in (
                    root, root/'work', root/OUT, root/DASHBOARD_CAPTURE_DIR.parent,
                    root/DASHBOARD_CAPTURE_DIR)), 'CI restore refuses redirected dashboard evidence directory'
            member = archive.getmember(row['path'])
"""),
)


def pin(raw):
    return len(raw), hashlib.sha256(raw).hexdigest()


def historical_bundle_source(source):
    if type(source) is not str:
        raise AssertionError('Complete CI bundle source text required')
    identity = pin(source.encode('utf-8'))
    if identity == BEFORE:
        return source
    if identity != AFTER:
        raise AssertionError('Unreviewed complete dashboard transport source')
    restored = source
    for original, current in HUNKS:
        if restored.count(current) != 1:
            raise AssertionError('Dashboard transport context missing, repeated or moved')
        restored = restored.replace(current, original, 1)
    if pin(restored.encode('utf-8')) != BEFORE:
        raise AssertionError('Dashboard inverse did not recover the original complete CI source')
    return restored
