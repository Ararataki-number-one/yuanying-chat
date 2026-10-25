"""Exact public synthetic R02/N15 evidence selection; importing performs no I/O."""
import re
import shutil

NETWORK_IDENTITY_RAW_DIRS = frozenset(
    'window-network-identity-' + implementation + '-host-results-raw'
    for implementation in ('desktop', 'android'))
NETWORK_IDENTITY_RAW_FILES = frozenset((
    'manifest.json', 'compile.stdout.raw', 'compile.stderr.raw',
    'execute.stdout.raw', 'execute.stderr.raw',
    'device-projection.stdout.raw', 'device-projection.stderr.raw'))
NETWORK_SCOPE_REPORT_FILES = frozenset((
    'network-client-binding-results.json', 'network-client-binding-native-event.raw.json',
    'window-network-identity-desktop-host-results.json',
    'window-network-identity-android-host-results.json'))


def is_binding_stream_name(name):
    """Match the runner's exact positive index formatted with %04d."""
    match = re.fullmatch(r'network-client-binding-adb-([0-9]+)-(stdout|stderr)\.raw\.log', name)
    return bool(match and int(match[1]) > 0 and match[1] == '%04d' % int(match[1]))


def network_scope_relative_paths(out):
    """Declared paths only; optional missing failure evidence stays missing."""
    names = sorted(NETWORK_SCOPE_REPORT_FILES)
    names.extend(directory + '/' + name for directory in sorted(NETWORK_IDENTITY_RAW_DIRS)
                 for name in sorted(NETWORK_IDENTITY_RAW_FILES))
    names.extend(path.name for path in sorted(out.glob('network-client-binding-adb-*.raw.log'))
                 if is_binding_stream_name(path.name))
    return names


def copy_network_scope_evidence(out, stage):
    """Copy only the source-owned R02/N15 reports and original raw streams."""
    for root in (out.absolute(), stage.absolute()):
        assert all(not path.is_symlink() for path in (root, *root.parents)), 'Network evidence ancestor symlink refused'
    names = network_scope_relative_paths(out)
    copied = []
    for name in names:
        path, target = out / name, stage / name
        # A missing optional failure stream is not invented; an existing unsafe
        # path must not be followed, including either owned raw directory.
        assert not path.parent.is_symlink() and not path.is_symlink(), 'Network evidence symlink refused'
        if not path.exists():
            continue
        assert path.is_file() and 0 <= path.stat().st_size <= 1024 ** 3, 'Invalid network evidence file'
        assert not target.parent.is_symlink() and not target.is_symlink(), 'Network evidence destination symlink refused'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(name)
    return copied

