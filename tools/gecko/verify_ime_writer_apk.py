#!/usr/bin/env python3
"""Verify a tainted integration APK and its unchanged official native bytes."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['apk', 'receipt', 'output']:
        parser.add_argument('--' + name, required=True, type=pathlib.Path)
    args = parser.parse_args()
    receipt_bytes = args.receipt.read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt['diagnosticOnly'] is not True or receipt['releaseAcceptance'] is not False:
        raise ValueError('Diagnostic receipt required')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if source != receipt['sourceCommit']:
        raise ValueError('Diagnostic APK verification source changed')
    native = {}
    with zipfile.ZipFile(args.apk) as apk:
        stamp = json.loads(apk.read('assets/pocketchat-integration-build.json'))
        if stamp['sourceCommit'] != source or stamp['dirtySource'] is not False or stamp.get('sdkInputWriterDiagnosticsEnabled') is not True or stamp.get('diagnosticOnly') is not True or stamp.get('releaseAcceptance') is not False or stamp['diagnosticSdkAarSha256'] != receipt['diagnosticAarSha256'] or stamp['sdkInputWriterTransformReceiptSha256'] != sha(receipt_bytes):
            raise ValueError('APK diagnostic source stamp rejected')
        for sdk_name, expected in receipt['nativeArchiveSha256'].items():
            apk_name = 'lib/' + sdk_name.removeprefix('jni/')
            if apk_name in apk.namelist():
                actual = sha(apk.read(apk_name))
                if actual != expected:
                    raise ValueError('Official native SDK bytes changed: ' + apk_name)
                native[apk_name] = actual
        if not any(name.endswith('/libxul.so') for name in native):
            raise ValueError('Official SDK native ABI unavailable')
        dex = b''.join(apk.read(name) for name in apk.namelist() if name.startswith('classes') and name.endswith('.dex'))
        if any(marker not in dex for marker in [b'PocketSDKIME', b'outboundReplace actionId=', b'nativeAck actionId=', b'nativeSelectionAccepted start=']):
            raise ValueError('Log-only SDK instrumentation is absent from APK DEX')
    value = dict(schema=1, sourceCommit=source, diagnosticOnly=True, releaseAcceptance=False,
                 sdkInputWriterDiagnosticsEnabled=True, apkSha256=sha(args.apk.read_bytes()),
                 apkBytes=args.apk.stat().st_size, transformReceiptSha256=sha(receipt_bytes),
                 diagnosticAarSha256=receipt['diagnosticAarSha256'], officialNativeBytesIdentical=True,
                 nativeArchiveSha256=native, diagnosticMarkersPresent=True, buildIdentity=stamp,
                 scope='Tainted integration APK only; no production APK or release acceptance.')
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
