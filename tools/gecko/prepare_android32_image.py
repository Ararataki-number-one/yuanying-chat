#!/usr/bin/env python3
"""Install the pinned official API 32 image for real CPU glass fallback acceptance.

This verifies complete archive bytes and CRCs; setup alone runs no Android workload.
The established API 35 installer and pin stay independent and unchanged.
"""
import argparse
import json
from pathlib import Path
import tempfile

from prepare_android_image import digest, download, extract

PIN = Path(__file__).with_name('android-32-system-image.json')
PACKAGE = Path(__file__).with_name('android-32-google-apis-x86_64-package.xml')


def clean_target(target):
    """Require an unused ordinary SDK path before writing a staged package."""
    target = Path(target)
    for parent in (target, *target.parents):
        if parent.is_symlink():
            raise ValueError('System image target must not contain symlinks')
        if parent.exists() and not parent.is_dir():
            raise ValueError('System image target must use ordinary directories')
    if target.exists():
        raise FileExistsError('System image target must be provisioned in a clean SDK: ' + str(target))
    return target


def install(archive, target, package_xml, archive_source_revision, source_properties_sha256):
    target = clean_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-image-', dir=target.parent) as stage:
        image = extract(archive, Path(stage), 'x86_64')
        source_properties = image / 'source.properties'
        if digest(source_properties, 'sha256') != source_properties_sha256:
            raise ValueError('Extracted source.properties differs from the pinned official archive bytes')
        props = dict(line.split('=', 1) for line in source_properties.read_text().splitlines() if '=' in line)
        # The official r08 catalog package contains Pkg.Revision=4. Pin both
        # identities independently; package.xml registers catalog revision 8.
        expected = {'Pkg.Revision': str(archive_source_revision), 'AndroidVersion.ApiLevel': '32',
                    'SystemImage.TagId': 'google_apis', 'SystemImage.Abi': 'x86_64'}
        if any(props.get(key) != value for key, value in expected.items()):
            raise ValueError('Extracted image differs from the pinned Google API 32 x86_64 revision')
        for name in ('system.img', 'ramdisk.img', 'kernel-ranchu'):
            path = image / name
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Incomplete image: ' + name)
        (image / 'package.xml').write_bytes(package_xml.read_bytes())
        clean_target(target)
        image.rename(target)
    return props


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root', required=True, type=Path)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    pin = json.loads(PIN.read_text())
    if pin['package'] != 'system-images;android-32;google_apis;x86_64':
        raise ValueError('Unexpected API 32 system image package')
    target = args.sdk_root / 'system-images/android-32/google_apis/x86_64'
    clean_target(target)
    args.cache.mkdir(parents=True, exist_ok=True)
    archive = args.cache / 'image-api32-verified.zip'
    attempts = download(pin, archive)
    props = install(archive, target, PACKAGE, pin['archiveSourceRevision'], pin['sourcePropertiesSha256'])
    report = dict(status='passed', downloadAttempts=attempts, setupOnly=True,
                  actualAndroidExecution=False, workloadExecuted=False, package=pin['package'],
                  catalogRevision=pin['revision'], archiveSourceRevision=pin['archiveSourceRevision'],
                  sourcePropertiesSha256=digest(target / 'source.properties', 'sha256'), url=pin['url'], bytes=archive.stat().st_size,
                  sha1=digest(archive, 'sha1'), sha256=digest(archive, 'sha256'),
                  packageXmlSha256=digest(PACKAGE, 'sha256'), properties=props)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    archive.unlink()
    print(json.dumps({key: report[key] for key in ('status', 'setupOnly', 'catalogRevision', 'archiveSourceRevision', 'sourcePropertiesSha256', 'bytes', 'sha1', 'sha256')}), flush=True)


if __name__ == '__main__':
    main()
