#!/usr/bin/env python3
"""Propose reproducible SDK hashes for review; never install or qualify an APK."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ENTRY = 'org/mozilla/geckoview/GeckoEditable.class'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('aar', 'sources', 'android-jar', 'annotations-jar', 'kotlin-jar', 'javac', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    assert not git('status', '--porcelain'), 'Candidate compiler requires committed source'
    official = json.loads((ROOT / 'third-party/sdk/geckoview-157.0.1-official.json').read_text())
    for name, path in (('aar', a.aar), ('sources', a.sources)):
        assert path.stat().st_size == official[name]['bytes']
        assert digest(path.read_bytes()) == official[name]['sha256']
    assert digest(a.annotations_jar.read_bytes()) == 'ddd072ddbb553178e205517ce777b2f05aa9e412982d9ecb4eedc74f1212f697'
    assert re.fullmatch(r'javac 17\.[0-9.]+', subprocess.check_output([str(a.javac), '-version'], stderr=subprocess.STDOUT, text=True).strip())
    a.out.mkdir(parents=True)
    with zipfile.ZipFile(a.sources) as archive:
        original_source = archive.read('org/mozilla/geckoview/GeckoEditable.java')
    assert digest(original_source) == official['geckoEditableSourceSha256']
    original = a.out / 'original/GeckoEditable.java'
    original.parent.mkdir()
    original.write_bytes(original_source)
    candidate = ROOT / 'third-party/gecko/GeckoEditable.java'
    patched = a.out / 'patched.java'
    patched.write_bytes(original_source)
    patch = ROOT / 'third-party/gecko/GeckoEditable-native-caret.patch'
    subprocess.run(['patch', '--batch', '--fuzz=0', str(patched), str(patch)], check=True)
    assert patched.read_bytes() == candidate.read_bytes()
    with zipfile.ZipFile(a.aar) as archive:
        base_classes = archive.read('classes.jar')
    assert digest(base_classes) == official['classesJarSha256']
    classes_jar = a.out / 'official-classes.jar'
    classes_jar.write_bytes(base_classes)
    cp = ':'.join(map(str, (a.android_jar, classes_jar, a.annotations_jar, a.kotlin_jar)))
    outputs = {}
    for label, source in (('original', original), ('candidate', candidate)):
        output = a.out / label / 'classes'
        output.mkdir(parents=True)
        with (a.out / (label + '-javac.log')).open('wb') as log:
            subprocess.run([str(a.javac), '-J-XX:ActiveProcessorCount=2', '-encoding', 'UTF-8', '-source', '17', '-target', '17',
                            '-cp', cp, '-d', str(output), str(source)], stdout=log, stderr=subprocess.STDOUT, check=True)
        outputs[label] = sorted(str(x.relative_to(output)) for x in output.rglob('*.class'))
    assert outputs['original'] == outputs['candidate'], 'Unexpected sibling class set'
    for name in outputs['original']:
        if name == ENTRY:
            continue
        clazz = name.removesuffix('.class').replace('/', '.')
        disassembly = [subprocess.check_output([str(a.javac.parent / 'javap'), '-c', '-s', '-p', '-constants',
                        '-classpath', str(a.out / label / 'classes'), clazz], text=True) for label in ('original', 'candidate')]
        assert re.sub(r'#\d+', '#POOL', disassembly[0]) == re.sub(r'#\d+', '#POOL', disassembly[1]), name
    replacement = (a.out / 'candidate/classes' / ENTRY).read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_classes)) as archive, zipfile.ZipFile(buffer, 'w') as output:
        for info in archive.infolist():
            output.writestr(info, replacement if info.filename == ENTRY else archive.read(info.filename))
    derived_classes = buffer.getvalue()
    derived = a.out / 'candidate.aar'
    with zipfile.ZipFile(a.aar) as archive, zipfile.ZipFile(derived, 'w') as output:
        for info in archive.infolist():
            output.writestr(info, derived_classes if info.filename == 'classes.jar' else archive.read(info.filename))
    with zipfile.ZipFile(a.aar) as base, zipfile.ZipFile(derived) as current:
        assert base.namelist() == current.namelist()
        assert [n for n in base.namelist() if base.read(n) != current.read(n)] == ['classes.jar']
    with zipfile.ZipFile(io.BytesIO(base_classes)) as base, zipfile.ZipFile(io.BytesIO(derived_classes)) as current:
        assert base.namelist() == current.namelist()
        assert [n for n in base.namelist() if base.read(n) != current.read(n)] == [ENTRY]
    proposal = json.loads((ROOT / 'third-party/sdk/geckoview-157.0.1-editable-selection.json').read_text())
    proposal.update(sdkRuntimeCoordinate='local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket3',
                    sdkAarSha256=digest(derived.read_bytes()), sdkAarBytes=derived.stat().st_size,
                    sdkClassesJarSha256=digest(derived_classes), sdkGeckoEditableClassSha256=digest(replacement),
                    candidateEditableSourceSha256=digest(candidate.read_bytes()),
                    sourcePatch=dict(path=str(patch.relative_to(ROOT)), bytes=patch.stat().st_size, sha256=digest(patch.read_bytes())))
    public = a.out / 'proposal'
    public.mkdir()
    (public / 'proposed-sdk-manifest.json').write_text(json.dumps(proposal, indent=2) + '\n')
    (public / 'GeckoEditable.class').write_bytes(replacement)
    (public / 'compile-receipt.json').write_text(json.dumps(dict(sourceCommit=git('rev-parse', 'HEAD'),
        sourceTree=git('rev-parse', 'HEAD^{tree}'), actualArchiveComparison=True, unchangedSiblings=len(outputs['original'])-1,
        changedClassEntries=[ENTRY], allOtherClassEntriesUnchanged=True, allNativeAndResourceEntriesUnchanged=True,
        actualAndroidExecution=False, releaseAcceptance=False,
        scope='Candidate compilation and exact archive delta only; never APK or input acceptance.'), indent=2) + '\n')
    print(json.dumps(dict(candidateCompiled=True, proposedManifest=str(public / 'proposed-sdk-manifest.json'), releaseAcceptance=False)))


if __name__ == '__main__':
    main()
