"""Copy only verified, bounded JSON from the production IP-timezone workload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gecko.sdk_identity_contract import source_bytes, strict_json

SUMMARY = 'gecko-ip-timezone-results.json'
RAW_DIRECTORY = 'gecko-ip-timezone-evidence'
RAW_FILES = (
    'default-socks.json', 'route-switch-http.json', 'https-proxy.json',
    'cancel-late.json', 'manual-system.json', 'manual-iana.json',
    'rfp-priority.json', 'manual-rfp-denied.json', 'bootstrap-isolation.json',
    'redirect-rejected.json', 'invalid-geo-rejected.json',
    'route-receipts.json', 'setup-scope.json',
)
MAX_SUMMARY_BYTES = 4 * 1024 * 1024
MAX_RAW_BYTES = 262144
IP_RELEASE_TOOLS = (
    'tools/browser/ip_timezone_publication.py',
)
IP_SOURCE_ONLY_TOOLS = (
    'tools/browser/check_gecko_ip_timezone_evidence.py',
    'tools/browser/run_gecko_ip_timezone_integration.py',
    'tools/browser/ip_timezone_fixture_server.py',
    'tools/browser/fingerprint_fixture_server.py',
    'tools/browser/newworker_fixture_server.py',
)


def require(value, message):
    if not value:
        raise ValueError('IP timezone publication: ' + message)


def read_regular(path, limit):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit,
                'bounded regular JSON required: ' + path.name)
        data = stream.read(limit + 1)
        require(len(data) == info.st_size, 'JSON changed while reading: ' + path.name)
    return data


def read_json(path, limit):
    data = read_regular(path, limit)
    require(type(strict_json(data)) is dict, 'JSON object required: ' + path.name)
    return data


def capture(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), 'real evidence directory required')
    raw = directory / RAW_DIRECTORY
    require(raw.is_dir() and not raw.is_symlink(), 'real raw-evidence directory required')
    require({entry.name for entry in raw.iterdir()} == set(RAW_FILES),
            'exact thirteen raw JSON files required')
    values = {SUMMARY: read_json(directory / SUMMARY, MAX_SUMMARY_BYTES)}
    for name in RAW_FILES:
        values[RAW_DIRECTORY + '/' + name] = read_json(raw / name, MAX_RAW_BYTES)
    return values


def verify(directory, source, expected, reader):
    from browser.check_gecko_ip_timezone_evidence import verify_gecko_ip_timezone_evidence
    return verify_gecko_ip_timezone_evidence(directory, source, expected, reader=reader)


def copy_gecko_ip_timezone_evidence(directory, destination, source, expected,
                                  required_regression=None, reader=source_bytes):
    require(type(source) is str and re.fullmatch('[0-9a-f]{40}', source),
            'exact source commit required')
    require(type(expected) is dict and expected.get('sourceCommit') == source,
            'original installed-APK reference required')
    captured = capture(directory)
    checked = verify(directory, source, expected, reader)
    require(type(checked) is dict and checked, 'selected-source regression receipt required')
    if required_regression is not None:
        require(checked == required_regression, 'verified regression changed before publication')
    require(capture(directory) == captured, 'evidence changed during verification')
    destination = Path(destination)
    require(destination.is_dir() and not destination.is_symlink(), 'real destination directory required')
    require(not (destination / SUMMARY).exists() and not (destination / SUMMARY).is_symlink(),
            'summary destination already exists')
    raw_destination = destination / RAW_DIRECTORY
    require(not raw_destination.exists() and not raw_destination.is_symlink(),
            'raw destination already exists')
    destination_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    raw_fd = None
    try:
        os.mkdir(RAW_DIRECTORY, dir_fd=destination_fd)
        raw_fd = os.open(RAW_DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=destination_fd)
        # Fixed names and directory descriptors retain the verified output
        # directory even if another local process replaces a path meanwhile.
        for relative, data in captured.items():
            parent_fd = destination_fd if relative == SUMMARY else raw_fd
            name = SUMMARY if relative == SUMMARY else Path(relative).name
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            with os.fdopen(os.open(name, flags, 0o644, dir_fd=parent_fd), 'wb') as stream:
                stream.write(data)
    finally:
        if raw_fd is not None:
            os.close(raw_fd)
        os.close(destination_fd)
    require(capture(destination) == captured, 'staged evidence changed or output path was replaced')
    return dict(regression=checked, files=list(captured),
                sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in captured.items()})


def copy_gecko_ip_timezone_tools(root, destination, source, reader=source_bytes):
    root, destination = Path(root), Path(destination)
    values = {}
    for relative in IP_RELEASE_TOOLS + IP_SOURCE_ONLY_TOOLS:
        data = read_regular(root / relative, 2 * 1024 * 1024)
        require(b'\0' not in data, 'regular Python source required: ' + relative)
        data.decode('utf-8')
        if relative in IP_SOURCE_ONLY_TOOLS:
            require(data == reader(source, relative), 'tested source-only dependency changed: ' + relative)
        values[relative] = data
    parent = destination / 'tools/browser'
    require(destination.is_dir() and not destination.is_symlink()
            and (destination / 'tools').is_dir() and not (destination / 'tools').is_symlink()
            and parent.is_dir() and not parent.is_symlink(), 'real staged tool directories required')
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for relative, data in values.items():
            target = destination / relative
            if target.exists() or target.is_symlink():
                require(read_regular(target, 2 * 1024 * 1024) == data,
                        'staged source dependency already differs: ' + relative)
                continue
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            with os.fdopen(os.open(Path(relative).name, flags, 0o644, dir_fd=descriptor), 'wb') as stream:
                stream.write(data)
    finally:
        os.close(descriptor)
    require(destination.is_dir() and not destination.is_symlink()
            and (destination / 'tools').is_dir() and not (destination / 'tools').is_symlink()
            and parent.is_dir() and not parent.is_symlink(), 'staged tool directory was replaced')
    for relative, data in values.items():
        require(read_regular(destination / relative, 2 * 1024 * 1024) == data,
                'staged source dependency changed: ' + relative)
    return list(values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--source', required=True)
    parser.add_argument('--device-reference', required=True, type=Path)
    args = parser.parse_args()
    reference = strict_json(read_json(args.device_reference, 4 * 1024 * 1024))
    require(reference.get('status') == 'passed' and reference.get('sourceCommit') == args.source
            and reference.get('actualAndroidExecution') is True,
            'successful original device reference required')
    expected = reference['eventTransport']['buildIdentity']
    copied = copy_gecko_ip_timezone_evidence(args.directory, args.destination, args.source, expected)
    print(json.dumps(dict(status='passed', sourceCommit=args.source, files=len(copied['files']))))


if __name__ == '__main__':
    main()
