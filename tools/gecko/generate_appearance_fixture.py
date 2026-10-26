#!/usr/bin/env python3
"""Stage the integration variant's narrowly scoped Gecko appearance overlay.

The release source stays unchanged. This is a controlled synthetic CSS fixture,
not evidence that the official ChatGPT website has passed a device test.
"""
import argparse
import hashlib
import json
from pathlib import Path


SOURCE = Path("app/src/main/assets/gecko/appearance.js")
ASSETS = Path("work/appearance-fixture/assets")
OVERLAY = ASSETS / "gecko/appearance.js"
RECEIPT = ASSETS / "pocketchat-appearance-fixture.json"
GUARD = b"location.origin !== 'https://chatgpt.com' || window.top !== window"
FIXTURE_GUARD = (
    b"(location.origin !== 'https://chatgpt.com' && "
    b"!(location.origin === 'http://127.0.0.1:8765' && "
    b"location.pathname.startsWith('/appearance-sync/'))) || window.top !== window"
)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def expected(repo):
    source = (repo / SOURCE).read_bytes()
    if source.count(GUARD) != 1:
        raise ValueError("Expected exactly one unchanged production appearance origin guard")
    overlay = source.replace(GUARD, FIXTURE_GUARD, 1)
    if overlay.count(FIXTURE_GUARD) != 1 or overlay.replace(FIXTURE_GUARD, GUARD, 1) != source:
        raise ValueError("The integration overlay must differ only at the origin guard")
    receipt = {
        "schema": 1,
        "integrationOnly": True,
        "scope": "Controlled synthetic loopback CSS fixture; not the official ChatGPT website",
        "sourcePath": SOURCE.as_posix(),
        "sourceSha256": sha256(source),
        "sourceBytes": len(source),
        "overlayPath": OVERLAY.as_posix(),
        "overlaySha256": sha256(overlay),
        "overlayBytes": len(overlay),
        "generatorPath": "tools/gecko/generate_appearance_fixture.py",
        "generatorSha256": sha256(Path(__file__).read_bytes()),
        "transform": {
            "kind": "one-exact-origin-guard-replacement",
            "count": 1,
            "before": GUARD.decode("ascii"),
            "after": FIXTURE_GUARD.decode("ascii"),
            "remainingBytesIdentical": True,
            "additionalOrigin": "http://127.0.0.1:8765",
            "additionalPathPrefix": "/appearance-sync/",
            "topFrameRequired": True,
        },
    }
    return overlay, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"), receipt


def stage(repo, verify=False):
    repo = Path(repo).resolve()
    overlay, receipt_bytes, receipt = expected(repo)
    outputs = ((repo / OVERLAY, overlay), (repo / RECEIPT, receipt_bytes))
    if verify:
        for path, content in outputs:
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError("Stale or missing appearance fixture asset: " + str(path))
    else:
        for path, content in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Repository root (defaults to this script's checkout)")
    parser.add_argument("--verify", action="store_true", help="Check staged bytes without writing")
    args = parser.parse_args()
    receipt = stage(args.root, args.verify)
    print(json.dumps({"status": "verified" if args.verify else "staged",
                      "sourceSha256": receipt["sourceSha256"],
                      "overlaySha256": receipt["overlaySha256"],
                      "receiptPath": RECEIPT.as_posix()}, sort_keys=True))


if __name__ == "__main__":
    main()
