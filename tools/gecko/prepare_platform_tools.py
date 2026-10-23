#!/usr/bin/env python3
"""Pin the complete official host platform-tools before Android is started.

Setup does not execute or retry an application workload or an installed APK read.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

from prepare_android_image import digest, extract

PIN = Path(__file__).with_name('android-platform-tools.json')


def verified(path, pin):
    return path.is_file() and path.stat().st_size == pin['bytes'] and digest(path, 'sha256') == pin['sha256']


def install(archive, target, revision):
    """Validate all ZIP CRCs and package identity before replacing SDK tools."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-platform-tools-', dir=target.parent) as stage:
        tools = extract(archive, Path(stage), 'platform-tools')
        props = dict(line.split('=', 1) for line in (tools / 'source.properties').read_text().splitlines() if '=' in line)
        if props.get('Pkg.Revision') != revision or props.get('Pkg.UserSrc') != 'false':
            raise ValueError('Platform-tools package identity differs')
        for name in ('adb', 'fastboot'):
            binary = tools / name
            if not binary.is_file() or not binary.stat().st_size or not binary.stat().st_mode & 0o100:
                raise ValueError('Missing executable platform tool: ' + name)
        backup = Path(stage) / 'previous'
        if target.exists():
            props_file = target / 'source.properties'
            previous = dict(line.split('=', 1) for line in props_file.read_text().splitlines() if '=' in line) if props_file.is_file() else {}
            if (not re.fullmatch(r'\d+\.\d+\.\d+', previous.get('Pkg.Revision', ''))
                    or previous.get('Pkg.UserSrc') != 'false' or not (target / 'adb').is_file()
                    or not (target / 'fastboot').is_file()):
                raise ValueError('Refusing to replace a non-SDK directory')
            target.rename(backup)
        try:
            tools.rename(target)
        except BaseException:
            if backup.exists():
                backup.rename(target)
            raise
    return props


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root', required=True, type=Path)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    pin = json.loads(PIN.read_text())
    args.cache.mkdir(parents=True, exist_ok=True)
    archive = args.cache / 'platform-tools-verified.zip'
    if not verified(archive, pin):
        partial = archive.with_suffix('.partial')
        try:
            request = urllib.request.Request(pin['url'], headers={'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open('wb') as output:
                length = response.headers.get('Content-Length')
                if length is not None and int(length) != pin['bytes']:
                    raise ValueError('Wrong platform-tools response length')
                count = 0
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > pin['bytes']:
                        raise ValueError('Oversized platform-tools archive')
                    output.write(block)
            if not verified(partial, pin):
                raise ValueError('Platform-tools archive differs from locked size/SHA256')
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    target = args.sdk_root / 'platform-tools'
    ambient = target / 'adb'
    ambient_sha = digest(ambient, 'sha256') if ambient.is_file() else None
    # This runs only during setup, before any emulator or app is started. Replace
    # the entire package so the emulator and clients cannot select mixed versions.
    if ambient.is_file():
        subprocess.run([str(ambient), 'kill-server'], check=True, timeout=15)
    props = install(archive, target, pin['revision'])
    version = subprocess.check_output([str(target / 'adb'), 'version'], text=True, timeout=10)
    if '\nVersion ' + pin['revision'] + '-' not in version:
        raise ValueError('Installed adb binary does not match pinned package')
    report = dict(status='passed', setupOnly=True, applicationAcceptance=False,
                  actualAndroidExecution=False, workloadExecuted=False, package=pin['package'],
                  revision=pin['revision'], url=pin['url'], bytes=archive.stat().st_size,
                  sha256=digest(archive, 'sha256'), ambientAdbSha256=ambient_sha,
                  installedAdbSha256=digest(target / 'adb', 'sha256'), actualVersion=version, properties=props)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    archive.unlink()
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
