#!/usr/bin/env python3
"""Reproduce one source-compiled Gecko input class; never modify Mozilla caches."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from sdk_identity_contract import (DERIVED_MANIFEST, EDITABLE_ENTRY, ROOT,
    digest, file_digest, identity_from_receipt, selected_manifest, strict_json)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def delta(official_path, derived_path, manifest):
    assert file_digest(official_path) == manifest['sdkInputAarSha256']
    assert derived_path.stat().st_size == manifest['sdkAarBytes']
    assert file_digest(derived_path) == manifest['sdkAarSha256']
    with zipfile.ZipFile(official_path) as base, zipfile.ZipFile(derived_path) as current:
        assert len(base.namelist()) == len(set(base.namelist()))
        assert len(current.namelist()) == len(set(current.namelist()))
        assert set(base.namelist()) == set(current.namelist())
        aar_rows = []
        for name in base.namelist():
            left, right = base.read(name), current.read(name)
            aar_rows.append(dict(path=name, upstreamSha256=digest(left), derivedSha256=digest(right), changed=left != right))
        assert [r['path'] for r in aar_rows if r['changed']] == ['classes.jar']
        jar = current.read('classes.jar')
        assert digest(jar) == manifest['sdkClassesJarSha256']
        with zipfile.ZipFile(io.BytesIO(base.read('classes.jar'))) as a, zipfile.ZipFile(io.BytesIO(jar)) as b:
            assert len(a.namelist()) == len(set(a.namelist()))
            assert len(b.namelist()) == len(set(b.namelist()))
            assert set(a.namelist()) == set(b.namelist())
            rows = []
            for name in a.namelist():
                left, right = a.read(name), b.read(name)
                rows.append(dict(path=name, upstreamSha256=digest(left), derivedSha256=digest(right), changed=left != right))
            assert [r['path'] for r in rows if r['changed']] == [EDITABLE_ENTRY]
            assert digest(b.read(EDITABLE_ENTRY)) == manifest['sdkGeckoEditableClassSha256']
    return dict(actualArchiveComparison=True, changedClassEntries=[EDITABLE_ENTRY],
                allOtherClassEntriesUnchanged=True, allNativeAndResourceEntriesUnchanged=True,
                sdkInputAarSha256=manifest['sdkInputAarSha256'], sdkAarSha256=manifest['sdkAarSha256'],
                unchangedClassEntries=len(rows) - 1, unchangedAarEntries=len(aar_rows) - 1,
                sdkClassPayload=rows, aarPayload=aar_rows)


def main():
    p = argparse.ArgumentParser()
    for name in ('aar', 'pom', 'sources', 'android-jar', 'annotations-jar', 'kotlin-jar'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--javac', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--run-id', required=True)
    p.add_argument('--run-attempt', required=True)
    p.add_argument('--resolved-artifacts', type=Path)
    a = p.parse_args()
    git = lambda *words: subprocess.check_output(['git', *words], cwd=ROOT, text=True).strip()
    source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    assert not git('status', '--porcelain'), 'Clean committed build recipe required'
    assert re.fullmatch('[1-9][0-9]*', a.run_id) and re.fullmatch('[1-9][0-9]*', a.run_attempt)
    manifest, manifest_sha = selected_manifest(source)
    official = strict_json((ROOT / 'third-party/sdk/geckoview-157.0.1-official.json').read_bytes())
    for name, path in [('aar', a.aar), ('pom', a.pom), ('sources', a.sources)]:
        assert path.stat().st_size == official[name]['bytes']
        assert file_digest(path) == official[name]['sha256']
    assert file_digest(a.annotations_jar) == 'ddd072ddbb553178e205517ce777b2f05aa9e412982d9ecb4eedc74f1212f697'
    a.out.mkdir(parents=True, exist_ok=True)
    derived = a.out / 'geckoview-caret.aar'
    receipt_path = a.out / 'sdk-build-receipt.json'
    if a.resolved_artifacts is None:
        assert not derived.exists() and not receipt_path.exists(), 'Preserve prior SDK build evidence'
        work = a.out / 'compile'
        work.mkdir()
        with zipfile.ZipFile(a.aar) as z:
            official_classes = z.read('classes.jar')
        assert digest(official_classes) == official['classesJarSha256']
        (work / 'official-classes.jar').write_bytes(official_classes)
        with zipfile.ZipFile(a.sources) as z:
            original_source = z.read('org/mozilla/geckoview/GeckoEditable.java')
        assert digest(original_source) == official['geckoEditableSourceSha256']
        original_file = work / 'original/GeckoEditable.java'
        original_file.parent.mkdir()
        original_file.write_bytes(original_source)
        candidate_file = ROOT / 'third-party/gecko/GeckoEditable.java'
        assert file_digest(candidate_file) == manifest['candidateEditableSourceSha256']
        patched = work / 'patch-check/GeckoEditable.java'
        patched.parent.mkdir()
        patched.write_bytes(original_source)
        subprocess.run(['patch', '--batch', '--fuzz=0', str(patched), str(ROOT / manifest['sourcePatch']['path'])], check=True)
        assert patched.read_bytes() == candidate_file.read_bytes(), 'Source patch does not produce the compiled source'
        version = subprocess.check_output([str(a.javac), '-version'], stderr=subprocess.STDOUT, text=True).strip()
        assert re.fullmatch(r'javac 17\.[0-9.]+', version), 'Pinned Java 17 compiler required'
        classpath = [a.android_jar, work / 'official-classes.jar', a.annotations_jar, a.kotlin_jar]
        inputs = {str(path): file_digest(path) for path in classpath}
        compiled = {}
        for label, src in [('original', original_file), ('candidate', candidate_file)]:
            classes = work / label / 'classes'
            classes.mkdir(parents=True, exist_ok=True)
            arguments = ['-encoding', 'UTF-8', '-source', '17', '-target', '17', '-cp',
                         ':'.join(map(str, classpath)), '-d', str(classes), str(src)]
            with (work / (label + '-javac.log')).open('wb') as log:
                subprocess.run([str(a.javac), '-J-XX:ActiveProcessorCount=2', *arguments],
                               stdout=log, stderr=subprocess.STDOUT, check=True)
            compiled[label] = sorted(str(x.relative_to(classes)) for x in classes.rglob('*.class'))
        assert compiled['original'] == compiled['candidate']
        assert {str(path): file_digest(path) for path in classpath} == inputs
        replacement = (work / 'candidate/classes' / EDITABLE_ENTRY).read_bytes()
        assert digest(replacement) == manifest['sdkGeckoEditableClassSha256']
        javap = a.javac.parent / 'javap'
        for name in compiled['original']:
            if name == EDITABLE_ENTRY:
                continue
            clazz = name.removesuffix('.class').replace('/', '.')
            disassembly = []
            for label in ('original', 'candidate'):
                raw = subprocess.check_output([str(javap), '-c', '-s', '-p', '-constants', '-classpath',
                    str(work / label / 'classes'), clazz], text=True)
                (work / label / (name.rsplit('/', 1)[-1] + '.javap')).write_text(raw)
                disassembly.append(re.sub(r'#\d+', '#POOL', raw))
            assert disassembly[0] == disassembly[1], 'Unreviewed sibling method change: ' + name
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(official_classes)) as base, zipfile.ZipFile(buffer, 'w') as output:
            assert len(base.namelist()) == len(set(base.namelist()))
            expected_names = {name for name in base.namelist() if name.startswith('org/mozilla/geckoview/GeckoEditable') and name.endswith('.class')}
            assert expected_names == set(compiled['original'])
            for info in base.infolist():
                output.writestr(info, replacement if info.filename == EDITABLE_ENTRY else base.read(info.filename))
        derived_classes = buffer.getvalue()
        assert digest(derived_classes) == manifest['sdkClassesJarSha256']
        with zipfile.ZipFile(a.aar) as base, zipfile.ZipFile(derived, 'w') as output:
            for info in base.infolist():
                output.writestr(info, derived_classes if info.filename == 'classes.jar' else base.read(info.filename))
        archive_delta = delta(a.aar, derived, manifest)
        write(a.out / 'derived-sdk-archive-comparison.json', archive_delta)
        group, artifact, version_name = manifest['sdkRuntimeCoordinate'].split(':')
        maven = a.out / 'maven' / group.replace('.', '/') / artifact / version_name
        maven.mkdir(parents=True)
        # Only this generated local coordinate can resolve the reviewed derived SDK.
        # Every dependency and license entry is inherited from the pinned official POM.
        ns = 'http://maven.apache.org/POM/4.0.0'
        ET.register_namespace('', ns)
        project = ET.Element('{' + ns + '}project')
        for tag, value in [('modelVersion', '4.0.0'), ('groupId', group), ('artifactId', artifact),
                           ('version', version_name), ('packaging', 'aar')]:
            ET.SubElement(project, '{' + ns + '}' + tag).text = value
        original_pom = ET.parse(a.pom).getroot()
        for tag in ('licenses', 'dependencies', 'dependencyManagement'):
            element = original_pom.find('{' + ns + '}' + tag)
            if element is not None:
                project.append(copy.deepcopy(element))
        ET.ElementTree(project).write(maven / (artifact + '-' + version_name + '.pom'), encoding='utf-8', xml_declaration=True)
        # A hard link preserves bytes and avoids a second large SDK cache file.
        import os
        os.link(derived, maven / (artifact + '-' + version_name + '.aar'))
        receipt = dict(manifest, sourceCommit=source, sourceTree=tree,
                       runId=a.run_id, runAttempt=a.run_attempt, sdkManifestSha256=manifest_sha)
        write(receipt_path, receipt)
        raw = receipt_path.read_bytes()
        identity = identity_from_receipt(raw, manifest, manifest_sha, source, tree)
        write(a.out / 'assets/pocketchat-sdk-build.json', identity)
        (a.out / 'assets/pocketchat-sdk-build-receipt.json').write_bytes(raw)
        write(a.out / 'derived-sdk-compilation.json', dict(sourceCommit=source, sourceTree=tree,
            runId=a.run_id, runAttempt=a.run_attempt, compiler=version, classpathSha256=inputs,
            compiledClassNames=compiled, officialSiblingsRetained=True,
            normalizedSiblingMethodSemanticsEqual=True, candidateSourceSha256=file_digest(candidate_file),
            actualAndroidExecution=False, releaseAcceptance=False))
    else:
        archive_delta = delta(a.aar, derived, manifest)
        raw = receipt_path.read_bytes()
        identity = identity_from_receipt(raw, manifest, manifest_sha, source, tree)
        assert identity['runId'] == a.run_id and identity['runAttempt'] == a.run_attempt, 'Saved SDK receipt belongs to another build invocation'
        resolved = json.loads(a.resolved_artifacts.read_text())
        assert isinstance(resolved, list) and resolved
        assert {'releaseCompileClasspath', 'integrationCompileClasspath'} <= {x['configuration'] for x in resolved}
        for item in resolved:
            path = Path(item['path'])
            assert item['coordinate'] == manifest['sdkRuntimeCoordinate']
            assert path.stat().st_size == item['bytes'] == manifest['sdkAarBytes']
            assert file_digest(path) == item['sha256'] == manifest['sdkAarSha256']
        write(a.out / 'derived-sdk-verification.json', dict(identity, status='passed',
            gradleResolvedAarVerified=True, resolvedArtifacts=resolved, archiveDelta=archive_delta,
            actualAndroidExecution=False, releaseAcceptance=False))
    assert git('rev-parse', 'HEAD') == source and not git('status', '--porcelain')
    print(json.dumps(dict(sourceCommit=source, sourceTree=tree, sdkAarSha256=manifest['sdkAarSha256'],
        sdkRuntimeCoordinate=manifest['sdkRuntimeCoordinate'], gradleResolvedAarVerified=a.resolved_artifacts is not None,
        actualAndroidExecution=False, releaseAcceptance=False)))


if __name__ == '__main__':
    main()
