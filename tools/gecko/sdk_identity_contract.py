"""Strict selected-source SDK provenance; a report cannot choose its expected SDK.

The immutable Mozilla receipt describes the input. A source-derived SDK uses
one selected-source manifest, a runtime build receipt, and an APK SDK asset.
Official schema-1 integration stamps remain readable for historical 1.7 builds.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SDK_COORDINATE = 'org.mozilla.geckoview:geckoview:157.0.20261005135250'
SDK_RUNTIME_COORDINATE = 'local.pocketchat.sdk:geckoview-caret:157.0.20261005135250-pocket3'
SDK_AAR_SHA256 = '15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268'
SDK_CLASSES_SHA256 = '73b9e0b8a6a1d5842010f2dd06f5a50408981238027b481cef162984d1896c8e'
SDK_EDITABLE_SHA256 = '608461e22cae3ed19572aa43a0dc38d4926d48709bd456c91853935462f5fa54'
DERIVED_EDITABLE_SHA256 = 'e9df13aef0bafcca2c70a8ecba2e3add5b1a13739e41ee6cebc4c97913d57c88'
UPSTREAM_REVISION = '737ec77d798755890b062aab541a90d6c75afd19'
DERIVED_MANIFEST = 'third-party/sdk/geckoview-157.0.1-editable-selection.json'
SDK_ASSET = 'assets/pocketchat-sdk-build.json'
SDK_RECEIPT_ASSET = 'assets/pocketchat-sdk-build-receipt.json'
SDK_RECEIPT_FILE = 'sdk-build-receipt.json'
EDITABLE_ENTRY = 'org/mozilla/geckoview/GeckoEditable.class'
SDK_FIELDS = ('sdkBuildKind', 'sdkCoordinate', 'sdkRuntimeCoordinate',
              'sdkInputCoordinate', 'sdkInputAarSha256', 'sdkAarSha256',
              'sdkClassesJarSha256', 'sdkGeckoEditableClassSha256',
              'sdkManifestSha256', 'sdkBuildReceiptSha256', 'sdkBuildSource')
DERIVED_FLAGS = {'changedClassEntries': [EDITABLE_ENTRY],
                 'allOtherClassEntriesUnchanged': True,
                 'allNativeAndResourceEntriesUnchanged': True,
                 'observerIncluded': False, 'sdkAarModified': True,
                 'sdkClassTransformApplied': True,
                 'patchMethod': 'source-compiled-class-replacement',
                 'asmTransformApplied': False, 'sourceCompileApplied': True,
                 'actualAndroidExecution': False, 'releaseAcceptance': False,
                 'physicalDeviceAcceptance': False}


def require(condition, message):
    if not condition:
        raise ValueError('SDK identity: ' + message)


def sha(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON field: ' + key)
        value[key] = item
    return value


def _constant(value):
    raise ValueError('SDK identity: non-finite JSON constant: ' + value)


def strict_json(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('SDK identity: malformed JSON') from error
    require(isinstance(value, dict), 'JSON object required')
    return value


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def source_bytes(source, path):
    require(sha(source, 40), 'complete selected source commit required')
    return subprocess.check_output(['git', 'show', source + ':' + path], cwd=ROOT, stderr=subprocess.PIPE)


def _record(record, source, reader):
    require(isinstance(record, dict) and set(record) == {'path', 'bytes', 'sha256'}, 'exact source record required')
    path = record.get('path')
    require(isinstance(path, str) and path and str(PurePosixPath(path)) == path
            and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts
            and '\\' not in path and '\x00' not in path, 'unsafe source record path')
    require(type(record.get('bytes')) is int and record['bytes'] > 0 and sha(record.get('sha256')), 'source record pin required')
    raw = reader(source, path)
    require(len(raw) == record['bytes'] and digest(raw) == record['sha256'], 'selected source material differs: ' + path)


def validate_manifest(raw, source, reader=source_bytes):
    value = strict_json(raw)
    require(type(value.get('schema')) is int and value['schema'] == 1, 'derived manifest schema')
    require(value.get('sdkBuildKind') == 'source-derived-java', 'exact derived build kind')
    require(value.get('sdkCoordinate') == value.get('sdkInputCoordinate') == SDK_COORDINATE
            and value.get('sdkRuntimeCoordinate') == SDK_RUNTIME_COORDINATE, 'exact upstream/runtime coordinates')
    require(value.get('sdkInputAarSha256') == SDK_AAR_SHA256
            and value.get('upstreamRevision') == UPSTREAM_REVISION, 'immutable official input provenance')
    require(sha(value.get('sdkAarSha256')) and value['sdkAarSha256'] != SDK_AAR_SHA256
            and sha(value.get('sdkClassesJarSha256')) and value['sdkClassesJarSha256'] != SDK_CLASSES_SHA256
            and value.get('sdkGeckoEditableClassSha256') == DERIVED_EDITABLE_SHA256, 'exact derived artifact pins')
    require(type(value.get('sdkAarBytes')) is int and value['sdkAarBytes'] > 0, 'derived AAR byte count')
    for key, expected in DERIVED_FLAGS.items():
        require(type(value.get(key)) is type(expected) and value[key] == expected, 'derived scope differs: ' + key)
    require(not any(key in value for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt',
                                           'sdkManifestSha256', 'sdkBuildReceiptSha256', 'sdkBuildSource')),
            'static manifest must not contain dynamic or self-referential identity')
    for key in ('sourcePatch', 'sourceRecipe'):
        _record(value.get(key), source, reader)
    require(value['sourcePatch']['path'] != value['sourceRecipe']['path'], 'patch and recipe must be distinct source files')
    return value


def selected_manifest(source, reader=source_bytes):
    raw = reader(source, DERIVED_MANIFEST)
    return validate_manifest(raw, source, reader), digest(raw)


def validate_receipt(raw, manifest, manifest_sha, source, tree):
    require(sha(source, 40) and sha(tree, 40) and sha(manifest_sha), 'selected source/manifest identity')
    receipt = strict_json(raw)
    expected_keys = set(manifest) | {'sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'sdkManifestSha256'}
    require(set(receipt) == expected_keys, 'runtime receipt fields differ from selected manifest schema')
    for key, expected in manifest.items():
        require(_typed_equal(receipt.get(key), expected), 'runtime receipt differs from selected source: ' + key)
    require(receipt.get('sourceCommit') == source and receipt.get('sourceTree') == tree
            and receipt.get('sdkManifestSha256') == manifest_sha, 'runtime receipt source/tree/manifest binding')
    for key in ('runId', 'runAttempt'):
        require(isinstance(receipt.get(key), str) and re.fullmatch('[1-9][0-9]*', receipt[key]), 'positive runtime build identity: ' + key)
    return receipt


def identity_from_receipt(raw, manifest, manifest_sha, source, tree):
    receipt = validate_receipt(raw, manifest, manifest_sha, source, tree)
    fields = {key: manifest[key] for key in SDK_FIELDS if key in manifest}
    fields.update(sdkManifestSha256=manifest_sha, sdkBuildReceiptSha256=digest(raw), sdkBuildSource=source)
    return dict(fields, schema=1, sourceCommit=source, sourceTree=tree,
                runId=receipt['runId'], runAttempt=receipt['runAttempt'])


def verify_sdk_identity(value, source=None, tree=None, receipt_raw=None, reader=source_bytes):
    """Validate selected-source pins; receipt_raw is mandatory at APK/public gates.

    Report/event adapters can omit receipt bytes only after an installed identity
    has been independently verified, and still check selected manifest pins.
    """
    require(isinstance(value, dict), 'build identity object required')
    nested = value.get('sdkBuildIdentity', value)
    require(isinstance(nested, dict), 'embedded SDK build identity object required')
    source = source or value.get('sourceCommit') or nested.get('sourceCommit')
    tree = tree or value.get('sourceTree') or nested.get('sourceTree')
    kind = nested.get('sdkBuildKind', 'official')
    if kind == 'official':
        require(value.get('sdkCoordinate', nested.get('sdkCoordinate')) == SDK_COORDINATE, 'official coordinate')
        for key, expected in {'sdkCoordinate': SDK_COORDINATE, 'sdkRuntimeCoordinate': SDK_COORDINATE,
                              'sdkInputCoordinate': SDK_COORDINATE, 'sdkAarSha256': SDK_AAR_SHA256,
                              'sdkInputAarSha256': SDK_AAR_SHA256, 'sdkClassesJarSha256': SDK_CLASSES_SHA256,
                              'sdkGeckoEditableClassSha256': SDK_EDITABLE_SHA256}.items():
            if key in nested:
                require(nested[key] == expected, 'official SDK field differs: ' + key)
        require(not any(key in nested for key in ('sdkManifestSha256', 'sdkBuildReceiptSha256')),
                'official legacy identity cannot carry a derived receipt')
        # If this selected source ships a derived manifest, official identities
        # cannot downgrade its runtime. Missing historical manifests remain valid.
        if source is not None:
            try:
                reader(source, DERIVED_MANIFEST)
            except (subprocess.CalledProcessError, FileNotFoundError, KeyError):
                pass
            else:
                raise ValueError('SDK identity: selected source requires the derived runtime')
        return nested
    require(kind == 'source-derived-java', 'unknown SDK build kind')
    require(sha(source, 40) and sha(tree, 40), 'derived selected source/tree required')
    manifest, manifest_sha = selected_manifest(source, reader)
    expected = {key: manifest[key] for key in SDK_FIELDS if key in manifest}
    expected.update(sdkManifestSha256=manifest_sha, sdkBuildSource=source)
    require(type(nested.get('schema')) is int and nested['schema'] == 1
            and nested.get('sourceCommit') == source and nested.get('sourceTree') == tree,
            'derived SDK asset source/tree/schema')
    require(set(nested) == set(SDK_FIELDS) | {'schema', 'sourceCommit', 'sourceTree', 'runId', 'runAttempt'},
            'exact derived SDK asset fields required')
    for key, expected_value in expected.items():
        require(nested.get(key) == expected_value, 'derived SDK field differs from selected source: ' + key)
    require(sha(nested.get('sdkBuildReceiptSha256')), 'runtime build receipt hash required')
    for key in ('runId', 'runAttempt'):
        require(isinstance(nested.get(key), str) and re.fullmatch('[1-9][0-9]*', nested[key]), 'SDK asset runtime identity: ' + key)
    if receipt_raw is not None:
        require(nested == identity_from_receipt(receipt_raw, manifest, manifest_sha, source, tree),
                'SDK asset differs from exact runtime build receipt')
    if nested is not value:
        require(value.get('sdkCoordinate') == SDK_COORDINATE, 'outer integration SDK coordinate')
        for key in SDK_FIELDS:
            if key in value:
                require(value[key] == nested[key], 'outer SDK field differs from embedded SDK asset: ' + key)
    return nested


def verify_report_sdk(report, baseline=None, reader=source_bytes):
    identity = report.get('buildIdentity', {})
    source, tree = identity.get('sourceCommit'), identity.get('sourceTree')
    nested = verify_sdk_identity(identity, source, tree, reader=reader)
    if nested.get('sdkBuildKind', 'official') == 'official':
        verify_sdk_identity(report, source, tree, reader=reader)
        require(report.get('sdkCoordinate') == SDK_COORDINATE and report.get('sdkAarSha256') == SDK_AAR_SHA256,
                'historical official report identity')
        expected_engine = 'GeckoView 157.0.1'
        fields = ('sdkCoordinate', 'sdkAarSha256')
    else:
        fields = SDK_FIELDS
        for key in fields:
            require(report.get(key) == nested[key], 'report differs from installed selected SDK: ' + key)
        java = reader(source, 'app/src/main/java/local/pocketchat/GeckoWebView.java').decode('utf-8')
        versions = re.findall(r'static final String VERSION="([^"]+)"', java)
        require(len(versions) == 1, 'exact selected engine label required')
        expected_engine = versions[0]
        require(expected_engine != 'GeckoView 157.0.1', 'derived runtime must have a distinct engine label')
    require(report.get('engineVersion') == expected_engine, 'report engine label differs from selected source')
    if baseline is not None:
        require(isinstance(baseline, dict), 'SDK UA baseline object required')
        for key in fields:
            require(baseline.get(key) == report.get(key), 'UA baseline differs from installed SDK: ' + key)
    return nested


def verify_archive_delta(official_aar, derived_aar):
    """Compare real ZIP members; the sole class exception is the primary class."""
    with ZipFile(official_aar) as old, ZipFile(derived_aar) as new:
        require(len(old.namelist()) == len(set(old.namelist())) and len(new.namelist()) == len(set(new.namelist())),
                'duplicate AAR entries')
        require(set(old.namelist()) == set(new.namelist()) and 'classes.jar' in old.namelist(), 'AAR member set differs')
        for name in old.namelist():
            if name != 'classes.jar':
                with old.open(name) as left, new.open(name) as right:
                    while True:
                        block = left.read(1024 * 1024)
                        require(block == right.read(1024 * 1024), 'native/resource member changed: ' + name)
                        if not block:
                            break
        with ZipFile(io.BytesIO(old.read('classes.jar'))) as oldjar, ZipFile(io.BytesIO(new.read('classes.jar'))) as newjar:
            require(len(oldjar.namelist()) == len(set(oldjar.namelist())) and len(newjar.namelist()) == len(set(newjar.namelist())),
                    'duplicate SDK class entries')
            require(set(oldjar.namelist()) == set(newjar.namelist()), 'SDK class member set differs')
            changed = sorted(name for name in oldjar.namelist() if oldjar.read(name) != newjar.read(name))
            require(changed == [EDITABLE_ENTRY], 'actual changed classes exceed exact primary-class allowlist')
    return changed


def verify_derived_artifacts(official_aar, derived_aar, manifest):
    require(file_digest(official_aar) == SDK_AAR_SHA256, 'actual official input AAR differs')
    require(file_digest(derived_aar) == manifest['sdkAarSha256'] and Path(derived_aar).stat().st_size == manifest['sdkAarBytes'], 'actual derived AAR differs')
    verify_archive_delta(official_aar, derived_aar)
    with ZipFile(derived_aar) as archive:
        classes = archive.read('classes.jar')
        require(digest(classes) == manifest['sdkClassesJarSha256'], 'actual derived classes.jar differs')
        with ZipFile(io.BytesIO(classes)) as jar:
            require(digest(jar.read(EDITABLE_ENTRY)) == manifest['sdkGeckoEditableClassSha256'], 'actual derived primary class differs')


def sdk_from_apk(archive, source, tree, reader=source_bytes):
    names = archive.namelist()
    if SDK_ASSET not in names:
        require(SDK_RECEIPT_ASSET not in names, 'orphaned SDK runtime receipt asset')
        verify_sdk_identity({'sdkCoordinate': SDK_COORDINATE}, source, tree, reader=reader)
        return None
    require(names.count(SDK_ASSET) == 1 and names.count(SDK_RECEIPT_ASSET) == 1, 'exactly one SDK asset and receipt required')
    asset = strict_json(archive.read(SDK_ASSET))
    verify_sdk_identity(asset, source, tree, archive.read(SDK_RECEIPT_ASSET), reader)
    require(asset.get('sdkBuildKind') == 'source-derived-java', 'new SDK asset must identify exact source-derived runtime')
    return asset


def verify_gate_sdk(identity, directory, source, tree, reader=source_bytes):
    nested = identity.get('sdkBuildIdentity', {})
    if nested.get('sdkBuildKind') == 'source-derived-java':
        return verify_sdk_identity(identity, source, tree, (Path(directory) / SDK_RECEIPT_FILE).read_bytes(), reader)
    return verify_sdk_identity(identity, source, tree, reader=reader)
