"""Read-only byte identity checks for the compatibility prototype; no signing/runtime claims."""
import hashlib
import io
import json
import pathlib
import re
import struct
import zipfile
import zlib

OBSERVER_PREFIXES = ('Lorg/mozilla/geckoview/PocketGeckoEditableTrace',
                     'Lorg/mozilla/geckoview/PocketGeckoInputTrace',
                     'Lorg/mozilla/geckoview/PocketInputWriterTrace')
EDITABLE = 'Lorg/mozilla/geckoview/GeckoEditable;'
FIXTURE = 'Llocal/pocketchat/GeckoCaretCompatibilityIntegrationActivity;'
CARET_HELPER = 'Llocal/pocketchat/CaretCompatibilityBuildIdentity;'
CONTROLLED_IME = 'Llocal/pocketchat/ControlledCaretInputMethodService;'
CONTROLLED_IME_XML = 'res/xml/caret_controlled_input_method.xml'
IDENTITY_ASSET = 'assets/caret-build-identity.json'
OBSERVER_ASSET = 'assets/caret-document-observer.js'


def require(value, message):
    if not value:
        raise ValueError(message)


def strict_json(raw):
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate JSON field: ' + key)
            value[key] = item
        return value
    def reject_constant(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def digest(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_sdk_receipt(path, aar, root, official_aar):
    # Consume the SAME exact generated SDK receipt embedded in the production APK.
    # The shared contract verifies the selected Git source manifest, patch and recipe.
    import subprocess
    import sys
    sys.path.insert(0, str(pathlib.Path(root) / 'tools/gecko'))
    import sdk_identity_contract as sdk_contract
    raw = pathlib.Path(path).read_bytes()
    receipt = strict_json(raw)
    source, tree = receipt.get('sourceCommit'), receipt.get('sourceTree')
    def reader(selected_source, name):
        return subprocess.check_output(['git', 'show', selected_source + ':' + name],
                                       cwd=root, stderr=subprocess.PIPE)
    manifest, manifest_sha = sdk_contract.selected_manifest(source, reader)
    receipt = sdk_contract.validate_receipt(raw, manifest, manifest_sha, source, tree)
    sdk_contract.verify_derived_artifacts(official_aar, aar, manifest)
    return receipt


def embedded_identity(sdk_receipt, sdk_receipt_path):
    for key in ('sourceCommit', 'runId', 'runAttempt'):
        require(isinstance(sdk_receipt.get(key), str), 'Missing SDK execution identity: ' + key)
    require(re.fullmatch('[0-9a-f]{40}', sdk_receipt['sourceCommit']) is not None, 'Invalid source identity')
    require(sdk_receipt['runId'].isdigit() and sdk_receipt['runAttempt'].isdigit(), 'Invalid run identity')
    return dict(schema=1, sourceCommit=sdk_receipt['sourceCommit'], runId=sdk_receipt['runId'],
                runAttempt=sdk_receipt['runAttempt'], sdkReceiptSha256=digest(sdk_receipt_path),
                sdkAarSha256=sdk_receipt['sdkAarSha256'], sdkClassJarSha256=sdk_receipt['sdkClassesJarSha256'],
                sdkEditableClassSha256=sdk_receipt['sdkGeckoEditableClassSha256'], sdkManifestSha256=sdk_receipt['sdkManifestSha256'], normalMode=True,
                sdkObserverIncluded=False)


def u32(data, offset):
    require(0 <= offset <= len(data) - 4, 'DEX integer outside file')
    return struct.unpack_from('<I', data, offset)[0]


def dex_definitions(data):
    # Definitions, not string/type references. Includes original DEX checksum validation.
    require(data[:8] in [b'dex\n' + version + b'\0' for version in (b'035', b'037', b'038', b'039', b'040')],
            'Unsupported DEX version')
    require(len(data) >= 112 and u32(data, 32) == len(data) and u32(data, 36) == 112
            and u32(data, 40) == 0x12345678, 'Invalid DEX header')
    require(data[12:32] == hashlib.sha1(data[32:]).digest()
            and u32(data, 8) == zlib.adler32(data[12:]) & 0xffffffff, 'DEX checksum mismatch')
    strings, strings_at = u32(data, 56), u32(data, 60)
    types, types_at = u32(data, 64), u32(data, 68)
    classes, classes_at = u32(data, 96), u32(data, 100)
    for count, at, width in ((strings, strings_at, 4), (types, types_at, 4), (classes, classes_at, 32)):
        require(count <= len(data) // width and (count == 0 or at >= 112)
                and 0 <= at <= len(data) and count * width <= len(data) - at, 'Invalid DEX table bounds')
    result = set()
    for i in range(classes):
        type_index = u32(data, classes_at + i * 32)
        require(type_index < types, 'DEX type index outside table')
        string_index = u32(data, types_at + type_index * 4)
        require(string_index < strings, 'DEX string index outside table')
        offset = u32(data, strings_at + string_index * 4)
        length, shift = 0, 0
        for _ in range(5):
            require(offset < len(data), 'Truncated DEX string')
            byte = data[offset]; offset += 1
            length |= (byte & 127) << shift
            if byte < 128:
                break
            shift += 7
        else:
            raise ValueError('Oversized DEX string length')
        end = data.find(b'\0', offset)
        require(end >= offset, 'Unterminated DEX string')
        descriptor = data[offset:end].replace(b'\xc0\x80', b'\0').decode('utf-8', 'surrogatepass')
        require(len(descriptor.encode('utf-16-le', 'surrogatepass')) // 2 == length
                and descriptor.startswith('L') and descriptor.endswith(';')
                and descriptor not in result, 'Invalid/duplicate DEX class definition')
        result.add(descriptor)
    return result


def audit_apk(path, package='local.pocketchat.test', component='local.pocketchat.GeckoCaretCompatibilityIntegrationActivity', require_fixture=True):
    definitions, records = set(), []
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate APK members')
        names = sorted(name for name in archive.namelist()
                       if re.fullmatch(r'classes(?:[2-9]|[1-9][0-9]+)?\.dex', name))
        require(names, 'APK has no standard DEX definitions')
        for name in names:
            data = archive.read(name)
            current = dex_definitions(data)
            require(not (current & definitions), 'Duplicate class definition across DEX files')
            definitions.update(current)
            records.append(dict(entry=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                classDefinitions=sorted(current), classDefinitionCount=len(current)))
        if require_fixture:
            raw = archive.read(IDENTITY_ASSET)
            identity = strict_json(raw)
            require(OBSERVER_ASSET in archive.namelist(), 'Integration APK passive observation asset missing')
            observer_raw = archive.read(OBSERVER_ASSET)
        else:
            require(IDENTITY_ASSET not in archive.namelist(), 'Release APK includes caret fixture identity asset')
            require(OBSERVER_ASSET not in archive.namelist(), 'Release APK includes passive caret fixture observation asset')
            require(CONTROLLED_IME_XML not in archive.namelist(), 'Release APK includes controlled test IME resource')
            observer_raw = None
            raw, identity = None, None
    bad = sorted(item for item in definitions if item.startswith(OBSERVER_PREFIXES))
    require(not bad, 'Installed APK contains SDK diagnostic observer definitions: ' + repr(bad))
    require(EDITABLE in definitions, 'APK lacks SDK editable definition')
    require((FIXTURE in definitions) is require_fixture and (CARET_HELPER in definitions) is require_fixture,
            'APK fixture/helper definition presence differs from variant')
    require(require_fixture or CONTROLLED_IME not in definitions, 'Release APK includes controlled test IME definition')
    return dict(schema=1, apkSha256=digest(path), package=package, component=component,
                definitionCount=len(definitions), dex=records, observerDefinitions=bad,
                editableDefinitionCount=1, fixtureDefinitionCount=int(FIXTURE in definitions), caretHelperDefinitionCount=int(CARET_HELPER in definitions),
                controlledImeDefinitionCount=int(CONTROLLED_IME in definitions),
                embeddedIdentityAssetSha256=hashlib.sha256(raw).hexdigest() if raw is not None else None, embeddedBuildIdentity=identity,
                sdkManifestSha256=identity.get('sdkManifestSha256') if identity is not None else None,
                observerScriptSha256=hashlib.sha256(observer_raw).hexdigest() if observer_raw is not None else None)
