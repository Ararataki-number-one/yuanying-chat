#!/usr/bin/env python3
"""Install the exact official emulator already used by Chromium delivery probes."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.dom import minidom
from zipfile import ZipFile

from prepare_android_image import EMULATOR_PACKAGE, digest, download, install_emulator

PIN = {
    "package": "emulator",
    "revision": "37.2.13",
    "buildId": "16740729",
    "url": "https://dl.google.com/android/repository/emulator-linux_x64-16740729.zip",
    "bytes": 349658551,
    "sha1": "f41f9e31eb5ca64926603c03265c50bbc0ff4172",
    "sha256": "cbc7c3cfb83220b8a0f9c513fdab557712e74d339ec19ddffa43f23350ae9bdd",
}


def registration_xml():
    with minidom.parse(str(EMULATOR_PACKAGE)) as document:
        package, = document.getElementsByTagName("localPackage")
        if package.getAttribute("path") != PIN["package"]:
            raise ValueError("Incorrect emulator package registration template")
        revision, = package.getElementsByTagName("revision")
        for field, value in zip(("major", "minor", "micro"), PIN["revision"].split(".")):
            component, = revision.getElementsByTagName(field)
            component.firstChild.data = value
        return document.toxml(encoding="utf-8")


def provision(sdk_root, cache, report):
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "chromium-emulator-verified.zip"
    attempts = download(PIN, archive)
    with ZipFile(archive) as source:
        properties = dict(line.split("=", 1) for line in
                          source.read("emulator/source.properties").decode().splitlines() if "=" in line)
    if properties.get("Pkg.BuildId") != PIN["buildId"]:
        raise ValueError("Incorrect emulator build ID in official archive")
    with TemporaryDirectory(prefix="chromium-emulator-package-", dir=cache) as temporary:
        package = Path(temporary) / "package.xml"
        package.write_bytes(registration_xml())
        properties = install_emulator(archive, sdk_root / "emulator", package, PIN["revision"])
        receipt = {
            **PIN,
            "sha256": digest(archive, "sha256"),
            "packageXmlSha256": digest(package, "sha256"),
            "properties": properties,
            "downloadAttempts": attempts,
            "setupOnly": True,
            "actualAndroidExecution": False,
            "status": "passed",
        }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(receipt, indent=2) + "\n")
    archive.unlink()
    print(json.dumps(receipt), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    provision(args.sdk_root, args.cache, args.report)


if __name__ == "__main__":
    main()
