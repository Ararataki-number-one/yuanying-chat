#!/usr/bin/env python3
"""Read-only validation of official SDK inputs and Gradle's resolved AAR."""
import argparse
import hashlib
import io
import json
import pathlib
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECEIPT = ROOT / 'third-party/sdk/geckoview-157.0.1-official.json'


def digest(path, algorithm='sha256'):
    result = hashlib.new(algorithm)
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def class_constants(data):
    """Read ConstantValue fields without executing or rewriting the SDK class."""
    stream = io.BytesIO(data)
    assert stream.read(4) == b'\xca\xfe\xba\xbe'
    stream.read(4)  # minor/major version
    u2 = lambda: struct.unpack('>H', stream.read(2))[0]
    pool = [None] * u2()
    index = 1
    while index < len(pool):
        tag = stream.read(1)[0]
        if tag == 1:
            pool[index] = stream.read(u2()).decode('utf-8')
        elif tag == 3:
            pool[index] = struct.unpack('>i', stream.read(4))[0]
        elif tag == 8:
            pool[index] = ('string', u2())
        else:
            length = {4: 4, 5: 8, 6: 8, 7: 2, 9: 4, 10: 4, 11: 4, 12: 4,
                      15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}[tag]
            stream.read(length)
            if tag in (5, 6):
                index += 1
        index += 1
    stream.read(6)  # access flags, this/super class
    stream.read(2 * u2())  # interfaces
    values = {}
    for _ in range(u2()):
        u2()  # field access flags
        name = pool[u2()]
        u2()  # descriptor
        for _ in range(u2()):
            attribute = pool[u2()]
            content = stream.read(struct.unpack('>I', stream.read(4))[0])
            if attribute == 'ConstantValue':
                value = pool[struct.unpack('>H', content)[0]]
                values[name] = pool[value[1]] if isinstance(value, tuple) else value
    return values


def verify(aar, pom, sources, gradle_cache=None):
    receipt = json.loads(RECEIPT.read_text())
    assert receipt['schema'] == 1 and receipt['releaseChannel'] == 'release'
    assert receipt['sdkAarModified'] is False and receipt['sdkClassTransformApplied'] is False
    coordinate = ':'.join(('org.mozilla.geckoview', 'geckoview', receipt['version']))
    assert receipt['coordinate'] == coordinate
    dependencies = re.findall(r"implementation\s+'(org\.mozilla\.geckoview:[^']+)'", (ROOT / 'app/build.gradle').read_text())
    assert dependencies == [coordinate], 'Actual app dependency does not match the official SDK receipt.'
    for name, file in (('aar', aar), ('pom', pom), ('sources', sources)):
        pin = receipt[name]
        suffix = '-sources.jar' if name == 'sources' else '.' + name
        expected_url = ('https://maven.mozilla.org/maven2/org/mozilla/geckoview/geckoview/'
                        + receipt['version'] + '/geckoview-' + receipt['version'] + suffix)
        assert pin['url'] == expected_url
        if name == 'aar':
            assert pin['officialSha256Url'] == expected_url + '.sha256'
        assert pathlib.Path(file).stat().st_size == pin['bytes'], name + ' byte count changed.'
        assert digest(file) == pin['sha256'], name + ' differs from the pinned official artifact.'
    assert digest(aar, 'sha1') == receipt['aar']['sha1']
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    project = ET.parse(pom).getroot()
    assert ':'.join(project.findtext('m:' + part, namespaces=ns) for part in ('groupId', 'artifactId', 'version')) == coordinate
    assert project.findtext('m:scm/m:tag', namespaces=ns) == receipt['upstreamRevision']
    assert project.findtext('m:scm/m:url', namespaces=ns) == receipt['upstreamSourceUrl']
    with zipfile.ZipFile(aar) as archive:
        classes = archive.read('classes.jar')
        assert hashlib.sha256(classes).hexdigest() == receipt['classesJarSha256']
        with zipfile.ZipFile(io.BytesIO(classes)) as jar:
            assert hashlib.sha256(jar.read('org/mozilla/geckoview/GeckoEditable.class')).hexdigest() == receipt['geckoEditableClassSha256']
            build = class_constants(jar.read('org/mozilla/geckoview/BuildConfig.class'))
            assert build['MOZILLA_OFFICIAL'] == 1 and build['MOZ_UPDATE_CHANNEL'] == receipt['releaseChannel']
            assert build['MOZILLA_VERSION'] == receipt['firefoxVersion'], 'Receipt differs from the actual SDK Firefox version.'
    with zipfile.ZipFile(sources) as archive:
        assert hashlib.sha256(archive.read('org/mozilla/geckoview/GeckoEditable.java')).hexdigest() == receipt['geckoEditableSourceSha256']
    resolved = []
    if gradle_cache is not None:
        directory = pathlib.Path(gradle_cache) / 'caches/modules-2/files-2.1/org.mozilla.geckoview/geckoview' / receipt['version']
        files = sorted(directory.glob('*/geckoview-' + receipt['version'] + '.aar'))
        assert files, 'Gradle did not resolve the pinned official AAR.'
        for file in files:
            assert file.stat().st_size == receipt['aar']['bytes'] and digest(file) == receipt['aar']['sha256'], 'Gradle resolved a modified SDK AAR.'
            resolved.append({'sha256': digest(file), 'bytes': file.stat().st_size})
    return {'status': 'passed', 'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'coordinate': coordinate, 'firefoxVersion': receipt['firefoxVersion'], 'upstreamRevision': receipt['upstreamRevision'],
            'receiptSha256': digest(RECEIPT), 'aarSha256': receipt['aar']['sha256'], 'classesJarSha256': receipt['classesJarSha256'],
            'sdkAarModified': False, 'sdkClassTransformApplied': False, 'gradleResolvedAarVerified': gradle_cache is not None,
            'resolvedArtifacts': resolved, 'actualAndroidExecution': False,
            'scope': 'Official SDK build-input provenance only; no input-correctness or device acceptance claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--aar', required=True, type=pathlib.Path)
    parser.add_argument('--pom', required=True, type=pathlib.Path)
    parser.add_argument('--sources', required=True, type=pathlib.Path)
    parser.add_argument('--gradle-cache', type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.aar, args.pom, args.sources, args.gradle_cache), indent=2))
