#!/usr/bin/env python3
"""Check a privately signed PocketChat parallel-install APK pair."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import ssl
import subprocess
from zipfile import BadZipFile

from caret_build_identity import digest
from release_channel_contract import SIGNER, require
from stage_chromium_module import (ABIS, BASE_MIN_SDK, DELIVERY, MODULE_MIN_SDK,
                                   PEM_CERT, apk_command, attributes, check_payload)


PACKAGE = 'local.pocketchat.parallel'
SETUP = 'local.pocketchat.CefriumSetupProvider'
BROWSER = 'local.pocketchat.CefriumBrowserActivity'
GECKO_PRELOAD = 'org.mozilla.gecko.process.ZygotePreload'
COMPONENTS = {'activity', 'activity-alias', 'provider', 'receiver', 'service'}


def application_components(xmltree):
    """Read direct application components from Android 37 aapt2 xmltree output."""
    application_indent = None
    component_indent = None
    components = []
    for line in xmltree.splitlines():
        content = line.lstrip()
        indent = len(line) - len(content)
        if content.startswith('E: '):
            element = content.split()[1]
            if application_indent is None:
                if element == 'application':
                    application_indent = indent
                continue
            if indent <= application_indent:
                break
            if indent <= application_indent + 4:
                component_indent = None
                if element in COMPONENTS:
                    component_indent = indent
                    components.append((element, {}))
        elif component_indent is not None and indent == component_indent + 2 and content.startswith('A: '):
            key, value = content[3:].split('=', 1)
            key = key.partition('(')[0].split(':')[-1]
            fields = components[-1][1]
            require(key not in fields, f'Duplicate component attribute: {key}')
            fields[key] = value.split('"', 2)[1] if value.startswith('"') else value
    return components


def check_manifest(xmltree, apk, role):
    sections, metadata = attributes(xmltree)
    root, sdk, app = (sections.get(name, {}) for name in ('manifest', 'uses-sdk', 'application'))
    require(root.get('package') == PACKAGE and not root.get('sharedUserId'),
            f'Expected independent application ID {PACKAGE}: {apk.name}')
    require(root.get('split', '') == role and root.get('isFeatureSplit', 'false') == str(bool(role)).lower()
            and not root.get('configForSplit') and not root.get('requiredSplitTypes')
            and app.get('isSplitRequired', 'false') == 'false', f'Unexpected split requirements: {apk.name}')
    version = root.get('versionName', '')
    code = root.get('versionCode', '')
    minimum = sdk.get('minSdkVersion', '')
    require(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) and re.fullmatch(r'[1-9][0-9]*', code)
            and root.get('versionCodeMajor', '0') == '0', f'Invalid APK version: {apk.name}')
    require(re.fullmatch(r'[0-9]+', minimum) and BASE_MIN_SDK <= int(minimum) <= MODULE_MIN_SDK,
            f'Unexpected minimum Android API: {apk.name}')
    require(app.get('debuggable', 'false') == 'false' and app.get('process', PACKAGE) == PACKAGE
            and app.get('extractNativeLibs') == 'true', f'Unexpected application configuration: {apk.name}')

    components = application_components(xmltree)
    authorities = set()
    by_name = {}
    for kind, fields in [('application', app), *components]:
        name = fields.get('name', '')
        require(not name.rsplit('.', 1)[-1].startswith('AppUpdate'), f'Official updater declaration in {apk.name}: {name}')
        if kind != 'application':
            require(name and name not in by_name, f'Duplicate or unnamed component in {apk.name}: {name}')
            by_name[name] = fields
        affinity = fields.get('taskAffinity', '')
        require(not affinity or affinity == PACKAGE or affinity.startswith(PACKAGE + '.'),
                f'Unscoped task affinity in {apk.name}: {affinity}')
        process = fields.get('process', PACKAGE)
        require(process == PACKAGE or process.startswith(':'), f'Unscoped process in {apk.name}: {process}')
        if kind == 'provider':
            for authority in fields.get('authorities', '').split(';'):
                require(authority.startswith(PACKAGE + '.') and authority not in authorities,
                        f'Unscoped or duplicate provider authority in {apk.name}: {authority}')
                require(authority != PACKAGE + '.app-updates', f'Official update provider authority in {apk.name}')
                authorities.add(authority)

    if not role:
        flags = [entry.get('value') for entry in metadata if entry.get('name') == DELIVERY]
        require(int(minimum) == BASE_MIN_SDK and app.get('allowBackup') == 'false'
                and app.get('zygotePreloadName') == GECKO_PRELOAD and flags == ['true'],
                'Gecko base must retain its Android minimum, data isolation, preload and Chromium delivery flag')
        require(by_name.get('local.pocketchat.BrandLaunchActivity', {}).get('taskAffinity') == PACKAGE + '.windows',
                'Parallel launcher must have its own task affinity')
        require({PACKAGE + suffix for suffix in ('.saved-downloads', '.lifecycle0', '.network-ui0')} <= authorities,
                'Expected the parallel base providers for saved files and per-environment lifecycle and network state')
        require(not any(name.startswith(('com.cefrium.', 'org.chromium.')) or name in (SETUP, BROWSER) for name in by_name),
                'Chromium component declared in the Gecko base')
    else:
        require(authorities == {PACKAGE + '.cefrium-setup'} and by_name.get(SETUP, {}).get('authorities') in authorities
                and not app.get('zygotePreloadName') and not app.get('zygotePreloadNativeLib'),
                'Expected the split-scoped Cefrium setup provider and the Java renderer path')
        for name in (SETUP, BROWSER):
            fields = by_name.get(name, {})
            require(fields.get('exported') == 'false' and fields.get('process', PACKAGE) == PACKAGE,
                    f'Cefrium must start privately in the application process: {name}')
        renderers = [fields for name, fields in by_name.items() if name.startswith('com.cefrium.ChildServices$Sandboxed')]
        require(renderers and all(fields.get('isolatedProcess') == 'true' and fields.get('exported') == 'false'
                                  and fields.get('useAppZygote', 'false') == 'false' for fields in renderers),
                'Expected private isolated Chromium renderer services outside the Gecko app zygote')
    return (version, int(code)), authorities


def signer_digest(apksigner, apk):
    report = apk_command(apksigner, 'verify', '--verbose', '--print-certs-pem',
                         '--min-sdk-version', str(BASE_MIN_SDK), apk)
    certificates = set(PEM_CERT.findall(report))
    require(b'Number of signers: 1' in report.splitlines() and len(certificates) == 1,
            f'Expected one consistent, verified signer: {apk.name}')
    certificate = ssl.PEM_cert_to_DER_cert(certificates.pop().decode('ascii'))
    result = hashlib.sha256(certificate).hexdigest()
    require(result != SIGNER, f'Parallel APK must never use the official signing certificate: {apk.name}')
    return result


def run(args):
    apks = {}
    versions, signers, authorities = set(), set(), set()
    pair = ((args.base, ''), (args.feature, 'chromium'))
    for apk, role in pair:
        require(apk.name not in apks and apk.is_file(), f'Expected a distinct APK file: {apk}')
        require(apk.resolve() != args.output.resolve(), f'Output would overwrite {apk}')
        xmltree = apk_command(args.aapt2, 'dump', 'xmltree', '--file', 'AndroidManifest.xml', apk).decode('utf-8')
        version, apk_authorities = check_manifest(xmltree, apk, role)
        require(authorities.isdisjoint(apk_authorities), 'Duplicate provider authority across the APK pair')
        authorities.update(apk_authorities)
        versions.add(version)
        signers.add(signer_digest(args.apksigner, apk))
        require(check_payload(apk, role, args.abi) == bool(role), f'Unexpected native Chromium placement: {apk.name}')
        apks[apk.name] = {'split': role, 'bytes': apk.stat().st_size, 'sha256': digest(apk)}
    require(len(versions) == 1 and len(signers) == 1, 'Base and Chromium APKs must share the same version and signer')
    version, code = versions.pop()
    return {'schema': 1, 'status': 'passed', 'scope': 'static-apk-pair', 'package': PACKAGE,
            'version': version, 'versionCode': code, 'abi': args.abi, 'signerSha256': signers.pop(), 'apks': apks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--feature', type=Path, required=True)
    parser.add_argument('--abi', choices=ABIS, required=True)
    parser.add_argument('--aapt2', default='aapt2')
    parser.add_argument('--apksigner', default='apksigner')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        args.output.write_text(json.dumps(run(args), indent=2) + '\n', encoding='utf-8')
    except subprocess.CalledProcessError as failure:
        parser.exit(1, f'{failure}: {failure.stderr.decode(errors="replace").strip()}\n')
    except (OSError, ValueError, BadZipFile) as failure:
        parser.exit(1, f'{failure}\n')


if __name__ == '__main__':
    main()
