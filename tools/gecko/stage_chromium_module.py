#!/usr/bin/env python3
"""Stage an exact PocketChat Chromium split set without accessing signing secrets."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tempfile
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from caret_build_identity import dex_definitions, digest
from release_channel_contract import SIGNER, release_tag, require


PACKAGE = 'local.pocketchat'
PREFIX = b'PocketChat Chromium module manifest 1\n'
ABIS = {'arm64-v8a': 'arm64_v8a', 'x86_64': 'x86_64'}
BASE_MIN_SDK = 26
MODULE_MIN_SDK = 29
DELIVERY = 'local.pocketchat.CHROMIUM_DELIVERY'
MAX_BYTES = 512 * 1024 * 1024
MAX_SPLITS = 64
CONFIG_NAME = re.compile(r'chromium\.config\.[A-Za-z0-9_]{1,60}')
ABI_CONFIGS = {'arm64_v8a', 'x86_64', 'armeabi', 'armeabi_v7a', 'x86', 'riscv64', 'mips', 'mips64'}
DEX_NAME = re.compile(r'classes(?:[2-9]|[1-9][0-9]+)?\.dex')
ENGINE_CLASSES = ('Lcom/cefrium/', 'Lorg/chromium/base/', 'Lorg/chromium/content/',
                  'Lorg/chromium/content_public/', 'Lorg/chromium/net/',
                  'Llocal/pocketchat/CefriumSetupProvider;')
# The Cefrium permission bridge links these classes, which AGP shares from the base APK.
ACTIVITY_RESULT_CLASSES = frozenset({
    'Landroidx/activity/result/ActivityResultCallback;',
    'Landroidx/activity/result/ActivityResultLauncher;',
    'Landroidx/activity/result/ActivityResultRegistry;',
    'Landroidx/activity/result/ActivityResultRegistryOwner;',
    'Landroidx/activity/result/contract/ActivityResultContract;',
    'Landroidx/activity/result/contract/ActivityResultContracts;',
    'Landroidx/activity/result/contract/ActivityResultContracts$RequestMultiplePermissions;',
})
PEM_CERT = re.compile(rb'-----BEGIN CERTIFICATE-----\r?\n.*?-----END CERTIFICATE-----', re.S)
# Cefrium 0.21.0 Libre binaries and resources from the verified SDK artifacts.
ENGINE_SHA = {
    'arm64-v8a': 'f7ff35036b7207a9d341fb8156b2d80782027ee7ce9ae21cf7ff6400bb2a84a2',
    'x86_64': 'beb97208d3f68ca809ec2e8cb7e65b6253a5d6389b62b7cc3f23f84a11ee56ed',
}
ASSET_SHA = {
    'assets/chrome_100_percent.pak+com.cefrium+': '2ebdeb0ae15644fb57c607af77a08b8d0be62684981fc2c79dc20df2e62e53d9',
    'assets/chrome_200_percent.pak+com.cefrium+': '1d4557116277dbe0925c0d5814f47290f4d9e627f929fa2ca4f4b4630342d507',
    'assets/icudtl.dat+com.cefrium+': '278e1e022a8b9370de99e2bff2bb8d61bfaaaa54122ec782cf6ccd9ac463f0d4',
    'assets/resources.pak+com.cefrium+': 'a03710473465334ab972003d049b5400d378482bc48d9df4b240392e6cb10fec',
    'assets/stored-locales/en-US.pak+com.cefrium+': 'a07f05300ca3294f70b4cc620b1c6f8cdfca545e1dc5d20ec291b7ed82e0ea23',
}


def apk_command(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def attributes(xmltree):
    """Read the main manifest sections and direct application metadata from aapt2."""
    sections = {}
    metadata = []
    elements = []
    for line in xmltree.splitlines():
        content = line.lstrip()
        indent = len(line) - len(content)
        if content.startswith('E: '):
            element = content.split()[1]
            while elements and indent <= elements[-1][0]:
                elements.pop()
            parent = elements[-1][1] if elements else None
            values = {}
            if (element == 'manifest' and parent is None) or (
                    parent == 'manifest' and element in ('uses-sdk', 'application')):
                require(element not in sections, f'Duplicate APK manifest element: {element}')
                sections[element] = values
            elif parent == 'application' and element == 'meta-data':
                metadata.append(values)
            elements.append((indent, element, values))
        elif elements and indent == elements[-1][0] + 2 and content.startswith('A: '):
            values = elements[-1][2]
            name, value = content[3:].split('=', 1)
            name = name.partition('(')[0].split(':')[-1]
            require(name not in values, f'Duplicate APK manifest attribute: {name}')
            # Preserve typed boolean metadata: a string value "true" must not authorize delivery.
            if value.startswith('"'):
                values[name] = value.split('"', 2)[1] if name != 'value' else value.split(' ', 1)[0]
            else:
                values[name] = value
    return sections, metadata


def apk_signer(apksigner, apk, min_sdk, expected_signer):
    report = apk_command(apksigner, 'verify', '--verbose', '--print-certs-pem',
                         '--min-sdk-version', str(min_sdk), apk)
    require(b'Number of signers: 1' in report.splitlines(), f'Expected one verified signer: {apk.name}')
    certificates = {item + b'\n' for item in PEM_CERT.findall(report)}
    require(len(certificates) == 1, f'Inconsistent APK signing certificates: {apk.name}')
    cert = certificates.pop()
    cert_digest = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.decode('ascii'))).hexdigest()
    require(cert_digest == expected_signer, f'APK lacks the original PocketChat signer: {apk.name}')
    return cert


def manifest_role(aapt2, apk, version, version_code, abi):
    xml = apk_command(aapt2, 'dump', 'xmltree', '--file', 'AndroidManifest.xml', apk).decode('utf-8')
    sections, metadata = attributes(xml)
    root, sdk, app = (sections.get(name, {}) for name in ('manifest', 'uses-sdk', 'application'))
    require(root.get('package') == PACKAGE and root.get('versionCode') == str(version_code)
            and root.get('versionCodeMajor', '0') == '0', f'Unexpected APK package or version code: {apk.name}')
    require(app and app.get('debuggable', 'false') == 'false', f'Unexpected APK application/debug mode: {apk.name}')
    role = root.get('split', '')
    require(role == '' or role == 'chromium' or CONFIG_NAME.fullmatch(role), f'Invalid APK split name: {role}')
    require(root.get('versionName', version if CONFIG_NAME.fullmatch(role) else None) == version,
            f'Unexpected APK version name: {apk.name}')
    minimum = sdk.get('minSdkVersion', '')
    require(minimum.isascii() and minimum.isdecimal(), f'Missing numeric minimum SDK: {apk.name}')
    if not role:
        require(int(minimum) == BASE_MIN_SDK and not root.get('requiredSplitTypes')
                and root.get('isFeatureSplit', 'false') == 'false' and not root.get('configForSplit')
                and app.get('isSplitRequired', 'false') == 'false', 'Gecko base must install alone on Android 8')
        require(app.get('extractNativeLibs', 'true') == 'true', 'Chromium installation requires extracted native libraries')
        capability = [entry.get('value') for entry in metadata if entry.get('name') == DELIVERY]
        require(capability == ['true'], 'Gecko base does not advertise on-demand Chromium delivery')
        require(not re.search(r'com[.]cefrium[.]|org[.]chromium[.](?:base|content|content_public|net)[.]'
                              r'|local[.]pocketchat[.]CefriumSetupProvider', xml),
                'Chromium component declared in the Gecko base APK')
    elif role == 'chromium':
        require(BASE_MIN_SDK <= int(minimum) <= MODULE_MIN_SDK and root.get('isFeatureSplit') == 'true'
                and not root.get('configForSplit'), 'Unexpected Chromium feature manifest')
    else:
        config = role.removeprefix('chromium.config.')
        require(BASE_MIN_SDK <= int(minimum) <= MODULE_MIN_SDK and root.get('configForSplit') == 'chromium'
                and app.get('hasCode') == 'false' and root.get('isFeatureSplit', 'false') == 'false'
                and (config not in ABI_CONFIGS or config == ABIS[abi]), f'Unexpected Chromium configuration: {role}')
    return role, set(filter(None, root.get('requiredSplitTypes', '').split(','))), set(filter(None, root.get('splitTypes', '').split(',')))


def digest_asset(archive, member):
    with archive.open(member) as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_payload(apk, role, abi):
    with ZipFile(apk) as archive:
        names = set(archive.namelist())
        require('AndroidManifest.xml' in names and len(names) == len(archive.infolist()),
                f'Invalid APK manifest or duplicate members: {apk.name}')
        require(not any(name.endswith(('.p12', '.jks')) for name in names), f'Unexpected key file in {apk.name}')
        native = {name for name in names if re.fullmatch(r'lib/[^/]+/[^/]+\.so', name)}
        require(all(name.startswith(f'lib/{abi}/') for name in native), f'Unexpected APK native ABI: {apk.name}')
        definitions = set()
        for name in sorted(names):
            if DEX_NAME.fullmatch(name):
                definitions.update(dex_definitions(archive.read(name)))
        engine = f'lib/{abi}/libcef.so'
        if not role:
            require(definitions and f'lib/{abi}/libxul.so' in native and f'lib/{abi}/libmozglue.so' in native,
                    'Gecko code and both native libraries must be in the base APK')
            require(not any(Path(name).name == 'libcef.so' or '+com.cefrium+' in name for name in names)
                    and not any(name.startswith(ENGINE_CLASSES) for name in definitions),
                    'Chromium native library, assets or code found in the Gecko base APK')
            require(ACTIVITY_RESULT_CLASSES <= definitions, 'Gecko base lacks the shared AndroidX Activity Result API')
        elif role == 'chromium':
            require('Lcom/cefrium/Cefrium;' in definitions, 'Chromium feature must provide Cefrium classes')
            require(ACTIVITY_RESULT_CLASSES.isdisjoint(definitions),
                    'Chromium feature duplicates the shared AndroidX Activity Result API')
            for member, expected in ASSET_SHA.items():
                require(member in names and archive.getinfo(member).compress_type == ZIP_STORED
                        and digest_asset(archive, member) == expected, f'Cefrium asset missing, compressed or changed: {member}')
        elif role == 'chromium.config.' + ABIS[abi]:
            require(not definitions and engine in native, 'Chromium ABI configuration lacks the native engine')
        else:
            require(not native and not definitions, f'Unexpected native or Java code in APK configuration: {role}')
        if engine in native:
            require(digest_asset(archive, engine) == ENGINE_SHA[abi], 'Unexpected Chromium native engine bytes')
        return engine in native


def read_set(args, apk_directory, publishable_base):
    apks = sorted(apk_directory.glob('*.apk'))
    require(2 <= len(apks) <= MAX_SPLITS + 1, 'Expected one base APK and a bounded Chromium split set')
    base_hash = digest(publishable_base)
    roles = {}
    split_types = set()
    feature_needs = set()
    certificate = None
    engine_roles = []
    for apk in apks:
        role, required, supplies = manifest_role(args.aapt2, apk, args.version, args.version_code, args.abi)
        require(role not in roles, f'Duplicate APK role: {role or "base"}')
        min_sdk = MODULE_MIN_SDK if role else BASE_MIN_SDK
        cert = apk_signer(args.apksigner, apk, min_sdk, SIGNER)
        if check_payload(apk, role, args.abi):
            engine_roles.append(role)
        byte_hash = digest(apk)
        roles[role] = (apk, {'name': role, 'bytes': apk.stat().st_size, 'sha256': byte_hash})
        if not role:
            require(byte_hash == base_hash, 'Extracted base differs from the exact APK to be published')
            certificate = cert
        elif role == 'chromium':
            feature_needs = required
        else:
            split_types.update(supplies)
    require({'', 'chromium'} <= roles.keys(), 'Required APK split(s) missing')
    require(len(engine_roles) == 1, 'Expected exactly one Chromium native engine split')
    require(feature_needs <= split_types, 'Required Chromium configuration type(s) missing')
    splits = [roles[role][1] for role in sorted(roles) if role]
    require(all(item['bytes'] > 0 for item in splits) and sum(item['bytes'] for item in splits) <= MAX_BYTES,
            'Chromium split download exceeds the installer size limit')
    tag_fields = {'version': args.version, 'channel': 'stable'}
    if args.candidate is not None:
        tag_fields.update(channel='candidate', candidateNumber=args.candidate)
    manifest = {'schema': 1, 'package': PACKAGE, 'tag': release_tag(tag_fields), 'version': args.version,
                'versionCode': args.version_code, 'abi': args.abi, 'minSdk': MODULE_MIN_SDK,
                'baseSha256': base_hash, 'signerSha256': SIGNER, 'nativeSplit': engine_roles[0], 'splits': splits}
    return (json.dumps(manifest, ensure_ascii=True, indent=2) + '\n').encode('ascii'), roles, certificate


def verify_detached(openssl, directory, raw, signature, certificate):
    require(0 < signature.stat().st_size <= 8192, 'Invalid detached signature size')
    original_cert = directory / 'cert.pem'
    original_cert.write_bytes(certificate)
    algorithm = apk_command(openssl, 'x509', '-in', original_cert, '-text', '-noout')
    require(re.search(rb'^\s*Public Key Algorithm: (?:rsaEncryption|id-ecPublicKey)\s*$', algorithm, re.M),
            'Original APK signing key is neither RSA nor ECDSA')
    public_key = directory / 'public.pem'
    public_key.write_bytes(apk_command(openssl, 'x509', '-in', original_cert, '-pubkey', '-noout'))
    payload = directory / 'manifest.payload'
    payload.write_bytes(PREFIX + raw)
    try:
        apk_command(openssl, 'dgst', '-sha256', '-verify', public_key, '-signature', signature, payload)
    except subprocess.CalledProcessError as failure:
        raise ValueError('Detached signature does not match the manifest and original APK signing certificate') from failure


def run(args):
    require(0 < args.version_code <= 2_100_000_000, 'Invalid PocketChat version code')
    require(not args.output.exists(), 'Output directory already exists')
    require(args.base_apk.is_file() and args.split_set.is_dir(), 'Missing base APK or split-set directory')
    require(args.output.parent.is_dir(), 'Output parent directory does not exist')
    with tempfile.TemporaryDirectory(prefix='.chromium-release-', dir=args.output.parent) as tmp:
        private = Path(tmp)
        inputs = private / 'apks'
        inputs.mkdir()
        apks = list(args.split_set.glob('*.apk'))
        require(2 <= len(apks) <= MAX_SPLITS + 1 and sum(path.stat().st_size for path in apks) <= 2 * MAX_BYTES,
                'Invalid extracted APK set count or total size')
        for path in apks:
            require(path.is_file() and not path.is_symlink(), f'Invalid split APK input: {path.name}')
            shutil.copyfile(path, inputs / path.name)
        raw, roles, cert = read_set(args, inputs, args.base_apk)
        names = f'PocketChat-{args.version}-chromium-{args.abi}'
        result = private / 'result'
        result.mkdir()
        (result / (names + '.json')).write_bytes(raw)
        if args.signature is None:
            (result / 'manifest.payload').write_bytes(PREFIX + raw)
        else:
            require(args.manifest.is_file() and args.manifest.stat().st_size == len(raw) and args.manifest.read_bytes() == raw,
                    'Supplied signed manifest does not match these exact APKs')
            require(args.signature.is_file() and 0 < args.signature.stat().st_size <= 8192,
                    'Missing or invalid detached signature')
            staged_signature = result / (names + '.sig')
            shutil.copyfile(args.signature, staged_signature)
            verify_detached(args.openssl, private, raw, staged_signature, cert)
            for role, (apk, _) in roles.items():
                if role:
                    filename = f'{names}--{role}.apk'
                else:
                    arch = 'arm64' if args.abi == 'arm64-v8a' else args.abi
                    filename = f'PocketChat-{args.version}-gecko-{arch}.apk'
                apk.rename(result / filename)
        require(not args.output.exists(), 'Output directory already exists')
        result.rename(args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-apk', type=Path, required=True, help='Exact original-signed base APK to distribute')
    parser.add_argument('--split-set', type=Path, required=True, help='Extracted base and Chromium split APKs from one signed bundle')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--version', required=True)
    parser.add_argument('--version-code', type=int, required=True)
    parser.add_argument('--abi', choices=ABIS, required=True)
    parser.add_argument('--candidate', type=int)
    parser.add_argument('--apksigner', default='apksigner')
    parser.add_argument('--aapt2', default='aapt2')
    parser.add_argument('--openssl', default='openssl')
    parser.add_argument('--manifest', type=Path, help='Exact JSON from preparation, required with --signature')
    parser.add_argument('--signature', type=Path, help='Raw signature of manifest.payload from authorized signer')
    args = parser.parse_args()
    if (args.manifest is None) != (args.signature is None):
        parser.error('Use both --manifest and --signature to stage the signed files, or neither to prepare the payload.')
    try:
        run(args)
    except (ValueError, OSError, BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
