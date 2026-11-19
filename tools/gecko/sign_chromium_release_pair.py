#!/usr/bin/env python3
"""Sign and verify a reviewed same-AAB release pair in the private signing environment."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import chromium_release_publication as publication
import stage_chromium_module as staging
from release_channel_contract import require


ROOT = Path(__file__).resolve().parents[2]


def sign_pair(args):
    require(args.keystore.is_file() and all(os.environ.get(name) for name in ('POCKET_STORE_PASSWORD', 'POCKET_KEY_PASSWORD')),
            'Open the authorized original APK signing environment first')
    require(not args.output.exists() and args.output.parent.is_dir(), 'Provide a new private signing output directory')
    require(publication.git('rev-parse', 'HEAD') == args.source and not publication.git('status', '--porcelain'),
            'Sign the exact clean release candidate checkout')
    build = publication.read_json(args.build)
    release = {'sourceCommit': args.source, 'version': build['version'], 'versionCode': build['versionCode'],
               'buildRunId': build['runId'], 'buildRunAttempt': build['runAttempt'],
               'unsignedSha256': build['apks']['base-master.apk']['sha256']}
    publication.validate_build(build, release, args.build_commit)
    publication.runtime_summary(args.runtime, release, build)
    publication.verify_hosted_acceptance(release, authenticate=False)
    args.output = args.output.resolve()
    with tempfile.TemporaryDirectory(prefix='.original-chromium-pair-', dir=args.output.parent) as folder:
        workspace = Path(folder)
        unsigned = workspace / 'unsigned'
        unsigned.mkdir()
        for filename in publication.APK_SET:
            artifact = args.unsigned / filename
            checked = unsigned / filename
            shutil.copyfile(artifact, checked)
            expected = {key: value for key, value in build['apks'][filename].items() if key != 'contentsSha256'}
            require(publication.identity(checked) == expected, f'CI unsigned APK changed: {filename}')
            require(publication.apk_contents(checked) == build['apks'][filename]['contentsSha256'], 'Wrong APK content')
            publication.assert_unsigned(args.tools / 'apksigner', checked)
        signed = workspace / 'signed'
        signed.mkdir()
        apk_name = f"PocketChat-{release['version']}-gecko-arm64.apk"
        base = signed / apk_name
        subprocess.run([sys.executable, str(ROOT / 'tools/sign-apk.py'), str(unsigned / 'base-master.apk'),
                        '--key', str(args.keystore.resolve()), '--tools', str(args.tools.resolve()),
                        '--java', str(args.java), '--output', str(base)], check=True, cwd=ROOT)
        feature = signed / 'chromium-master.apk'
        aligned = workspace / 'chromium-aligned.apk'
        subprocess.run([str(args.tools / 'zipalign'), '-f', '-P', '16', '4',
                        str(unsigned / 'chromium-master.apk'), str(aligned)], check=True)
        subprocess.run([str(args.java), '-jar', str(args.tools / 'lib/apksigner.jar'), 'sign', '--alignment-preserved', 'true',
                        '--ks', str(args.keystore), '--ks-key-alias', 'local', '--ks-pass', 'env:POCKET_STORE_PASSWORD',
                        '--key-pass', 'env:POCKET_KEY_PASSWORD', '--out', str(feature), str(aligned)], check=True)
        args_for_stage = SimpleNamespace(base_apk=base, split_set=signed, output=workspace / 'payload',
                                        version=release['version'], version_code=release['versionCode'],
                                        abi=publication.ABI, candidate=None, aapt2=args.tools / 'aapt2',
                                        apksigner=args.tools / 'apksigner', openssl='openssl',
                                        signature=None, manifest=None)
        staging.run(args_for_stage)
        artifact, metadata, signature_name = publication.public_names(release)
        args_for_stage.manifest = args_for_stage.output / metadata
        payload = args_for_stage.output / 'manifest.payload'
        args_for_stage.signature = workspace / signature_name
        subprocess.run([str(args.java), str(Path(__file__).with_name('OriginalChromiumManifestSigning.java')),
                        str(args.keystore), str(payload), str(args_for_stage.signature)], check=True)
        args_for_stage.output = workspace / 'release'
        staging.run(args_for_stage)
        release['sha256'] = staging.digest(base)
        publication.verify_signed_files(release, build, args_for_stage.output / apk_name, args_for_stage.output, args.tools)
        shutil.copyfile(signed / 'gecko-apk-verification.json', args_for_stage.output / 'gecko-apk-verification.json')
        args_for_stage.output.rename(args.output)
    print(json.dumps({'directory': str(args.output), 'base': apk_name, 'module': artifact,
                      'sourceCommit': args.source, 'signed': True, 'published': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('keystore', 'java', 'tools', 'build', 'unsigned', 'runtime', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--build-commit', required=True)
    sign_pair(parser.parse_args())


if __name__ == '__main__':
    main()
