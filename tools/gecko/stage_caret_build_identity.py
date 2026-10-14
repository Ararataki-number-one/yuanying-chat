#!/usr/bin/env python3
"""Stage immutable SDK/source/run identity before compiling both normal APKs."""
import argparse
import json
import pathlib
from caret_build_identity import digest, embedded_identity, validate_sdk_receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk-receipt', type=pathlib.Path, required=True)
    parser.add_argument('--sdk-aar', type=pathlib.Path, required=True)
    parser.add_argument('--official-sdk-aar', type=pathlib.Path, required=True)
    parser.add_argument('--root', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    receipt = validate_sdk_receipt(args.sdk_receipt, args.sdk_aar, args.root, args.official_sdk_aar)
    identity = embedded_identity(receipt, args.sdk_receipt)
    if args.output.exists():
        raise ValueError('Refusing to overwrite an existing identity asset')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(identity, indent=2) + '\n')
    print(json.dumps({'status': 'staged', 'sourceCommit': identity['sourceCommit'], 'output': str(args.output),
                      'embeddedIdentityAssetSha256': digest(args.output), 'runtimeAcceptanceIncluded': False}))


if __name__ == '__main__':
    main()
