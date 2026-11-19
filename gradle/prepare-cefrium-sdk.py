#!/usr/bin/env python3
"""Stage the exact verified Cefrium SDK artifacts for an opt-in split build."""

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = 'https://maven.cefrium.com/'
NOTICE = PurePosixPath('notice/licenses/cefrium-sdk-0.21.0-NOTICE.txt')
NOTICE_URL = 'https://codeberg.org/cefrium/cef-android/releases/download/v0.21.0/' + NOTICE.name


def digest(path: Path) -> str:
    with path.open('rb') as data:
        return hashlib.file_digest(data, 'sha256').hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=ROOT / 'work/chromium-sdk/maven')
    parser.add_argument('--gradle-cache', type=Path, help='Use verified local files without network')
    args = parser.parse_args()

    for line in (ROOT / 'gradle/cefrium-0.21.0.sha256').read_text().splitlines():
        expected, filename = line.split(maxsplit=1)
        relative = PurePosixPath(filename)
        target = args.repository / relative
        if target.is_file() and digest(target) == expected:
            continue

        # Maven labels the plugin AAR, but the publisher serves JVM plugin bytes as a JAR.
        source = relative
        if relative.name.startswith('cefrium-gradle-plugin-') and relative.suffix == '.aar':
            source = relative.with_suffix('.jar')

        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as staging:
            staged = Path(staging) / target.name
            if args.gradle_cache:
                if relative == NOTICE:
                    raise ValueError(f'Stage the verified notice from {NOTICE_URL} at {target}')
                cached_module = args.gradle_cache / 'com.cefrium' / source.parts[2] / source.parts[3]
                cached = next((file for file in cached_module.glob(f'*/{source.name}')
                               if digest(file) == expected), None)
                if cached is None:
                    raise ValueError(f'No verified cached file for {filename}')
                shutil.copyfile(cached, staged)
            else:
                url = NOTICE_URL if relative == NOTICE else REPOSITORY + source.as_posix()
                print(f'Retrieving pinned Cefrium input {relative}', flush=True)
                request = Request(url, headers={'User-Agent': 'PocketChat build dependency verifier/1'})
                with urlopen(request, timeout=120) as response, staged.open('wb') as output:
                    shutil.copyfileobj(response, output)

            if digest(staged) != expected:
                raise ValueError(f'SHA-256 mismatch: {filename}')
            staged.replace(target)
    print(f'Cefrium SDK verified: {args.repository}')


if __name__ == '__main__':
    main()
