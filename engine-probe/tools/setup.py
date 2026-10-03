#!/usr/bin/env python3
"""Prepare pinned Linux SDK tools in ignored work/ without replacing production tools."""
import hashlib, json, pathlib, shutil, urllib.request, zipfile

repo = pathlib.Path(__file__).resolve().parents[2]
out = repo / 'work/gecko-sdk-validation'
out.mkdir(parents=True, exist_ok=True)
artifacts = [
    ('https://dl.google.com/android/repository/platform-37.1_r01.zip',
     'cadf0a541847820ea3d8ffc5c192562a18376cf9ba510bf9659c772f9a442184', 'sdk/platforms/android-37.1'),
    ('https://dl.google.com/android/repository/build-tools_r37_linux.zip',
     '01af179347cbcd9c208b7f8171f7b21f6dd1d2f85bcd15e88caa51d5d7b86060', 'sdk/build-tools/37.0.0'),
    ('https://services.gradle.org/distributions/gradle-9.8.0-bin.zip',
     'bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c', 'gradle/gradle-9.8.0'),
    ('https://maven.mozilla.org/maven2/org/mozilla/geckoview/geckoview/157.0.20260924084938/geckoview-157.0.20260924084938.aar',
     '25de06a6204382c08e405adc36da7373098bdc230d6d768f17a6fe971f0dece0', None),
]
receipts = []
for url, digest, installed in artifacts:
    archive = out / url.rsplit('/', 1)[1]
    if not archive.exists():
        temporary = archive.with_suffix(archive.suffix + '.part')
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as target:
            shutil.copyfileobj(response, target)
        temporary.replace(archive)
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError('Archive checksum mismatch: ' + archive.name)
    if installed and not (out / installed).exists():
        with zipfile.ZipFile(archive) as z:
            temp = out / (archive.stem + '-unpacked')
            temp.mkdir(exist_ok=True)
            z.extractall(temp)
            for entry in z.infolist():
                if entry.external_attr >> 16:
                    (temp / entry.filename).chmod(entry.external_attr >> 16)
            prefixes = {entry.filename.split('/')[0] for entry in z.infolist()}
            if len(prefixes) != 1:
                raise RuntimeError('Unexpected archive layout')
            destination = out / installed
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp / prefixes.pop()), destination)
    receipts.append({'url': url, 'sha256': actual, 'bytes': archive.stat().st_size, 'verified': True})
adb = out / 'sdk/platform-tools'
existing_adb = repo / 'work/cloud-setup/adb/platform-tools'
if not adb.exists() and existing_adb.exists():
    adb.symlink_to(existing_adb, target_is_directory=True)
(out / 'setup-receipts.json').write_text(json.dumps(receipts, indent=2) + '\n')
print('Pinned GeckoView / Android 37.1 / Gradle 9.8.0 verified in', out)
