"""One exact user-authorized 2.0.3 release, with known failures disclosed.

This is not regression acceptance and cannot authorize a later release.
Application bytes, SDK provenance, original signature and public hashes remain
mandatory. Normal releases continue using their existing qualification gates.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import zipfile

SOURCE = '7d04c0f64a30c3862797a73f41733666e11700f6'
ARTIFACT = '449718fd9aef93e8dfa90cc8359d1d521d163281'
FAILURE = 'ad673c921405679ec80eab8c8d1a85434a795ba7'
FAILURE_SOURCE = '0e35bc9b346c8042150c3a8275b94e5bce2e8ea9'
UNSIGNED = '904bdfff66de2a798ef8c3940e7e2af7557399819a313fa743404b0bad0e9c28'
SIGNER = 'f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
EXCEPTION = 'user-authorized-2.0.3-known-input-issue'
ISSUES = ['rapid-caret-input-ordering', 'final-profile-template-resource-suites-incomplete',
          'physical-phone-not-tested']
RAW = 'https://raw.githubusercontent.com/Ararataki-number-one/yuanying-chat/'
IDENTITY = ('sourceCommit', 'version', 'versionCode', 'sha256', 'bytes', 'signerSha256')


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_record(m, record):
    expected = dict(version='2.0.3', versionCode=56, sourceCommit=SOURCE,
                    unsignedSha256=UNSIGNED, signerSha256=SIGNER, package='local.pocketchat',
                    filename='PocketChat-2.0.3-gecko-arm64.apk', channel='stable',
                    releaseException=EXCEPTION, nativeRegression='incomplete-with-known-issue',
                    physicalArmPhone='not-tested', knownIssues=ISSUES, buildArtifactCommit=ARTIFACT)
    for key, value in expected.items():
        require(type(m.get(key)) is type(value) and m.get(key) == value, 'Invalid release field: '+key)
    require(type(m.get('bytes')) is int and m['bytes'] > 0, 'Missing APK size')
    require(re.fullmatch('[0-9a-f]{64}', m.get('sha256', '')), 'Missing APK hash')
    require(not any(key in m for key in ('manualAcceptance', 'manualAcceptanceArtifact',
            'controlledCaretCompatibilityRegression')), 'Cannot claim missing acceptance')
    fields = set(IDENTITY) | {'schema', 'kind', 'requestedBy', 'userRequest',
                             'disclosedIssues', 'recordedAt', 'physicalPhoneAcceptance'}
    require(set(record) == fields, 'Unexpected authorization fields')
    require(record['schema'] == 1 and record['kind'] == EXCEPTION, 'Wrong authorization kind')
    require(record['requestedBy'] == 'user' and record['userRequest'] == '发布', 'Explicit request required')
    require(record['disclosedIssues'] == ISSUES, 'Known limitations must be recorded')
    require(record['physicalPhoneAcceptance'] == 'not-reported', 'No physical acceptance reported')
    require(datetime.datetime.fromisoformat(record['recordedAt'].replace('Z', '+00:00')).utcoffset()
            is not None, 'Recording time needs timezone')
    for key in IDENTITY:
        require(type(record[key]) is type(m[key]) and record[key] == m[key], 'Wrong APK: '+key)
    return record


def verify_authorization(m, root):
    root = Path(root)
    reference = m['releaseAuthorizationArtifact']
    require(reference['file'] == 'release-authorization.json', 'Wrong authorization file')
    raw = (root / reference['file']).read_bytes()
    require(len(raw) == reference['bytes'] and digest(raw) == reference['sha256'], 'Authorization hash mismatch')
    return verify_record(m, json.loads(raw))


def verify_release(root):
    root = Path(root)
    m = json.loads((root/'release-manifest.json').read_text())
    verify_authorization(m, root)
    notes = (root/'RELEASE.md').read_text()
    require(all(text in notes for text in ('光标', '未完成', '真机')), 'Release notes must disclose limitations')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root)
    def fetch(commit):
        require(re.fullmatch('[0-9a-f]{40}', commit), 'Invalid commit')
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', '--filter=blob:none',
                        'origin', commit], cwd=root, check=True)
    tools = m['releaseToolsCommit']
    for commit in (SOURCE, tools, FAILURE_SOURCE):
        fetch(commit)
    allowed = {'.github/workflows/gecko-integration.yml', '.github/workflows/profile-upgrade-checks.yml',
               '.github/workflows/publish-gecko-release.yml', 'docs/RELEASE-v2.0.3.md',
               'docs/VALIDATION-v2.0.3.md', 'tools/publish-update-feed.py',
               'tools/gecko/release_203_authorization.py', 'tools/gecko/release_203_authorization_test.py'}
    for commit in (tools, FAILURE_SOURCE):
        changed = set(git('diff', '--name-only', SOURCE, commit).decode().splitlines())
        require(changed <= allowed, 'Application/build/test bytes changed since selected APK')
    parents = [line.split()[1] for line in git('cat-file', '-p', 'HEAD').decode().split('\n\n', 1)[0].splitlines()
               if line.startswith('parent ')]
    require(parents[0] == SOURCE and tools in parents, 'Publication source parents differ')
    for name in ['.github/workflows/publish-gecko-release.yml', 'tools/publish-update-feed.py',
                 *[str(p.relative_to(root)) for p in (root/'tools/gecko').glob('*.py')]]:
        require((root/name).read_bytes() == git('show', tools+':'+name), 'Release tool changed: '+name)
    def remote(commit, name):
        with urllib.request.urlopen(RAW+commit+'/'+name, timeout=120) as response:
            return response.read()
    failure = remote(FAILURE, 'gecko-caret-compat-results.json')
    require((root/'known-caret-failure.json').read_bytes() == failure, 'Original input failure must be retained')
    require(json.loads(failure)['status'] == 'failed', 'Failure must not be relabeled passed')
    build = json.loads(remote(ARTIFACT, 'manifest.json'))
    require(build['sourceCommit'] == SOURCE and build['versionCode'] == 56, 'Wrong build')
    artifact, = build['artifacts']
    require(artifact['abi'] == 'arm64-v8a' and artifact['sha256'] == UNSIGNED, 'Wrong unsigned input')
    # Bind every included diagnostic to its immutable build, including SDK receipts.
    for path in (root/'evidence').iterdir():
        require(path.is_file() and path.read_bytes() == remote(ARTIFACT, path.name), 'Evidence changed: '+path.name)
    with tempfile.TemporaryDirectory(prefix='release-203-') as directory:
        unsigned = Path(directory)/'unsigned.apk'
        with unsigned.open('wb') as output:
            for part in artifact['chunks']:
                raw = remote(ARTIFACT, part['file'])
                require(len(raw) == part['bytes'] and digest(raw) == part['sha256'], 'Build chunk mismatch')
                output.write(raw)
        require(unsigned.stat().st_size == artifact['bytes'] and digest(unsigned.read_bytes()) == UNSIGNED,
                'Unsigned APK mismatch')
        apk = root/m['filename']
        with apk.open('wb') as output:
            for index, part in enumerate(m['parts']):
                require(part['file'] == m['filename']+f'.part{index:02d}', 'Invalid APK part')
                raw = (root/part['file']).read_bytes()
                require(len(raw) == part['bytes'] and digest(raw) == part['sha256'], 'Signed chunk mismatch')
                output.write(raw)
        require(apk.stat().st_size == m['bytes'] and digest(apk.read_bytes()) == m['sha256'], 'Signed APK mismatch')
        def contents(archive):
            require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate APK entries')
            return {n: digest(archive.read(n)) for n in archive.namelist()
                    if not re.fullmatch(r'META-INF/(?:MANIFEST.MF|[^/]+\.(?:SF|RSA|DSA|EC))', n)}
        with zipfile.ZipFile(unsigned) as original, zipfile.ZipFile(apk) as signed:
            require(contents(original) == contents(signed), 'Signing changed application bytes')
            from tools.gecko.sdk_identity_contract import sdk_from_apk, SDK_FIELDS
            from tools.gecko.check_sdk_build_evidence import verify_sdk_build_evidence
            sdk = verify_sdk_build_evidence(root/'evidence', SOURCE)
            shipped = sdk_from_apk(signed, SOURCE, git('rev-parse', SOURCE+'^{tree}').decode().strip())
            for key in (*SDK_FIELDS, 'sourceCommit', 'sourceTree', 'runId', 'runAttempt'):
                require(shipped[key] == sdk[key], 'Shipped SDK mismatch: '+key)
        android = Path(os.environ['POCKET_ANDROID_TOOLS']) if 'POCKET_ANDROID_TOOLS' in os.environ else sorted(
            Path(os.environ['ANDROID_HOME']).glob('build-tools/*/apksigner'))[-1].parent
        cert = subprocess.check_output([str(android/'apksigner'), 'verify', '--print-certs', str(apk)], text=True)
        require(set(re.findall(r'certificate SHA-256 digest: ([0-9a-f]{64})', cert)) == {SIGNER}, 'Wrong signer')
        info = subprocess.check_output([str(android/'aapt2'), 'dump', 'badging', str(apk)], text=True)
        require("package: name='local.pocketchat' versionCode='56' versionName='2.0.3'" in info
                and 'application-debuggable' not in info, 'Wrong production package')
    print('Exact 2.0.3 APK integrity verified. Publication authorized; regression remains incomplete with a known input issue.')
