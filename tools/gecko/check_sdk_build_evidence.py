"""Keep immutable Mozilla input checks separate from the shipped derived SDK."""
import hashlib
import json
from pathlib import Path
import subprocess
try:
    from .sdk_identity_contract import (SDK_COORDINATE, SDK_RUNTIME_COORDINATE,
        SDK_AAR_SHA256, SDK_CLASSES_SHA256, EDITABLE_ENTRY, SDK_RECEIPT_FILE,
        selected_manifest, verify_sdk_identity, strict_json, source_bytes)
except ImportError:
    from sdk_identity_contract import (SDK_COORDINATE, SDK_RUNTIME_COORDINATE,
        SDK_AAR_SHA256, SDK_CLASSES_SHA256, EDITABLE_ENTRY, SDK_RECEIPT_FILE,
        selected_manifest, verify_sdk_identity, strict_json, source_bytes)


def verify_sdk_build_evidence(directory,source,reader=source_bytes):
    directory=Path(directory)
    sdk=strict_json((directory/'official-sdk-verification.json').read_bytes())
    receipt_raw=(directory/'official-sdk-input.json').read_bytes();receipt=strict_json(receipt_raw)
    assert sdk['status']=='passed' and sdk['sourceCommit']==source
    assert sdk['coordinate']==receipt['coordinate']==SDK_COORDINATE
    assert sdk['firefoxVersion']==receipt['firefoxVersion']=='157.0.1'
    assert sdk['receiptSha256']==hashlib.sha256(receipt_raw).hexdigest()
    assert sdk['aarSha256']==receipt['aar']['sha256']==SDK_AAR_SHA256
    assert sdk['classesJarSha256']==receipt['classesJarSha256']==SDK_CLASSES_SHA256
    assert sdk['actualAndroidExecution'] is False
    assert sdk['sdkAarModified'] is False and sdk['sdkClassTransformApplied'] is False
    try:
        manifest,manifest_sha=selected_manifest(source,reader)
    except subprocess.CalledProcessError:
        # Historical selected sources did not have a derived receipt. All their
        # previous resolved-official-AAR checks remain mandatory.
        assert sdk['gradleResolvedAarVerified'] is True
        assert sdk['resolvedArtifacts'] and all(row['sha256']==SDK_AAR_SHA256 and row['bytes']==receipt['aar']['bytes'] for row in sdk['resolvedArtifacts'])
        return None
    assert sdk['gradleResolvedAarVerified'] is False,'Upstream input verification must not claim the derived dependency is an unmodified official AAR'
    staged_manifest=(directory/'derived-sdk-input.json').read_bytes()
    assert hashlib.sha256(staged_manifest).hexdigest()==manifest_sha,'Staged derived input differs from selected source'
    raw=(directory/SDK_RECEIPT_FILE).read_bytes()
    device=strict_json((directory/'device-results.json').read_bytes())
    assert device['status']=='passed' and device['sourceCommit']==source and device['actualAndroidExecution'] is True
    installed=device['eventTransport']['buildIdentity']
    identity=verify_sdk_identity(installed,source=source,tree=installed['sourceTree'],receipt_raw=raw,reader=reader)
    actual=strict_json((directory/'derived-sdk-verification.json').read_bytes())
    assert actual['status']=='passed' and actual['sourceCommit']==source and actual['sourceTree']==identity['sourceTree']
    assert actual['runId']==identity['runId'] and actual['runAttempt']==identity['runAttempt']
    assert actual['actualAndroidExecution'] is False and actual['releaseAcceptance'] is False
    assert actual['gradleResolvedAarVerified'] is True
    for key in ('sdkBuildKind','sdkRuntimeCoordinate','sdkAarSha256','sdkClassesJarSha256','sdkGeckoEditableClassSha256','sdkManifestSha256','sdkBuildReceiptSha256'):
        assert actual[key]==identity[key],'Derived SDK verifier differs from installed build: '+key
    resolved=actual['resolvedArtifacts'];assert isinstance(resolved,list) and resolved
    assert all(row['coordinate']==SDK_RUNTIME_COORDINATE and row['sha256']==manifest['sdkAarSha256'] and type(row['bytes']) is int and row['bytes']==manifest['sdkAarBytes'] for row in resolved)
    assert {'releaseCompileClasspath','integrationCompileClasspath'} <= {row['configuration'] for row in resolved},'Both compile variants must resolve the exact derived input'
    delta=actual['archiveDelta']
    assert delta['actualArchiveComparison'] is True and delta['changedClassEntries']==[EDITABLE_ENTRY]
    assert delta['allOtherClassEntriesUnchanged'] is True and delta['allNativeAndResourceEntriesUnchanged'] is True
    assert delta['sdkInputAarSha256']==SDK_AAR_SHA256 and delta['sdkAarSha256']==manifest['sdkAarSha256']
    assert type(delta['unchangedClassEntries']) is int and delta['unchangedClassEntries']>0
    assert type(delta['unchangedAarEntries']) is int and delta['unchangedAarEntries']>0
    return dict(identity,scope='Source-bound build/input provenance; derived Java input class, unchanged native/resources/other classes. No physical phone or input repair acceptance.')
