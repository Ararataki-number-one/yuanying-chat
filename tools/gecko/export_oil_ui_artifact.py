#!/usr/bin/env python3
"""Read-only byte-preserving export of one fixed, already captured UI artifact."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = 'Ararataki-number-one/yuanying-chat'
RUN = 40229064741
ATTEMPT = 1
ARTIFACT = 12612339188
SOURCE = '2fde13cb715d61909ad093909969989c8bf63f4b'
TREE = '774a2d7be83450dc373bd1f6472b8cc0a1a6c469'
APP_TREE = 'fca71b457960c5f2491bb95ccc43341a787a2dfc'
ARCHIVE_BYTES = 131761222
ARCHIVE_SHA256 = '28fd3ff748b6fc66317eb63b07fe284358a4be6819904293a9cbe8b0f7976ab0'
APK = 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
PART_LIMIT = 18 * 1024 * 1024
PART_COUNT = 4
MAX_ENTRIES = 512


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Authenticated API requests never follow redirects.
        return None


def archive_response(opener):
    try:
        return opener.open(api_request(f'/repos/{REPOSITORY}/actions/artifacts/{ARTIFACT}/zip'), timeout=180)
    except urllib.error.HTTPError as response:
        if response.code != 302:
            raise
        location = response.headers.get('Location', '')
        response.close()
        target = urllib.parse.urlsplit(location)
        require(target.scheme == 'https' and target.hostname
                and (target.hostname.endswith('.blob.core.windows.net')
                     or target.hostname.endswith('.githubusercontent.com'))
                and target.username is None and target.password is None,
                'Unexpected GitHub artifact redirect')
        # A completely new request has no Authorization, cookies or original headers.
        # The signed blob location is deliberately not logged or written to provenance.
        request = urllib.request.Request(location, headers={'User-Agent': 'PocketChat-ui-artifact-export'})
        return urllib.request.build_opener(NoRedirect()).open(request, timeout=180)


def api_request(path):
    require(path.startswith('/repos/' + REPOSITORY + '/'), 'Unexpected API resource')
    return urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'PocketChat-fixed-ui-artifact-export'})


def api_json(opener, path, destination):
    with opener.open(api_request(path), timeout=120) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    require(len(raw) <= 2 * 1024 * 1024, 'Oversized API response')
    destination.write_bytes(raw)
    return json.loads(raw)


def validate_metadata(run, artifact, commit):
    require(run.get('id') == RUN and run.get('run_attempt') == ATTEMPT
            and run.get('head_sha') == SOURCE and run.get('head_branch') == 'ui/oil-detail-round-1'
            and run.get('path') == '.github/workflows/oil-ui-detail.yml'
            and run.get('workflow_id') == 396350162 and run.get('event') == 'push'
            and run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('repository', {}).get('full_name') == REPOSITORY,
            'Original capture run identity/status differs')
    require(artifact.get('id') == ARTIFACT and artifact.get('name') == f'oil-ui-{RUN}-{ATTEMPT}'
            and artifact.get('size_in_bytes') == ARCHIVE_BYTES and artifact.get('expired') is False
            and artifact.get('digest') == 'sha256:' + ARCHIVE_SHA256,
            'Original artifact identity/digest differs')
    origin = artifact.get('workflow_run', {})
    require(origin.get('id') == RUN and origin.get('head_sha') == SOURCE
            and origin.get('repository_id') == 1401080063
            and origin.get('head_repository_id') == 1401080063,
            'Artifact is not from the fixed original source/run')
    require(commit.get('sha') == SOURCE and commit.get('tree', {}).get('sha') == TREE,
            'Original commit/tree differs')


def allowed_member(name):
    """Exactly the original workflow's non-secret upload roster, plus its one APK."""
    if name == APK:
        return True
    if re.fullmatch(r'work/oil-ui/[A-Za-z0-9_.-]+\.(?:json|log|txt)', name):
        return True
    if re.fullmatch(r'work/oil-ui/build-identity/[A-Za-z0-9_.-]+\.json', name):
        return True
    if re.fullmatch(r'work/oil-ui/round-1/[A-Za-z0-9_.-]+\.(?:json|png|xml)', name):
        return True
    if name == 'work/gecko-integration/emulator-bootstrap-results.json':
        return True
    if name in {'work/native-caret-sdk/' + s for s in (
            'sdk-build-receipt.json', 'derived-sdk-verification.json',
            'derived-sdk-compilation.json', 'resolved-artifacts.json')}:
        return True
    return re.fullmatch(r'work/native-caret-sdk/compile/[A-Za-z0-9_.-]+-javac\.log', name) is not None


def checked_members(archive):
    entries = archive.infolist()
    require(0 < len(entries) <= MAX_ENTRIES, 'Unexpected ZIP entry count')
    seen = set()
    result = []
    for entry in entries:
        name = entry.filename
        require(name not in seen, 'Duplicate ZIP path')
        seen.add(name)
        path = PurePosixPath(name)
        require(name and len(name) <= 240 and not path.is_absolute()
                and '\\' not in name and '\x00' not in name
                and all(p not in ('', '.', '..') for p in name.split('/'))
                and str(path) == name and not entry.is_dir(), 'Unsafe/non-file ZIP path')
        mode = entry.external_attr >> 16
        require(stat.S_IFMT(mode) in (0, stat.S_IFREG), 'Non-regular ZIP member')
        require(not entry.flag_bits & 1 and allowed_member(name), 'Unexpected/encrypted ZIP member')
        require(entry.file_size <= (256 * 1024 * 1024 if name == APK else PART_LIMIT),
                'Oversized ZIP member')
        result.append(entry)
    require(APK in seen, 'Original APK member missing')
    require(sum(e.file_size for e in result if e.filename != APK) <= PART_COUNT * PART_LIMIT,
            'Non-APK diagnostics exceed fixed small-part capacity')
    return sorted(result, key=lambda e: e.filename)


def stream_entry(archive, entry, target=None):
    h = hashlib.sha256()
    size = 0
    with archive.open(entry) as source:
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') if target is not None else open(os.devnull, 'wb') as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                require(size <= entry.file_size, 'ZIP member expanded beyond declared size')
                h.update(chunk)
                if target is not None:
                    output.write(chunk)
    require(size == entry.file_size, 'ZIP member length differs')
    return {'bytes': size, 'sha256': h.hexdigest()}


def bind_original_reports(archive, members):
    def raw(name):
        require(name in members, 'Required original file missing: ' + name)
        return archive.read(name)
    build = json.loads(raw('work/oil-ui/build-identity/capture-results.json'))
    capture = json.loads(raw('work/oil-ui/round-1/capture-results.json'))
    invocation = json.loads(raw('work/oil-ui/invocation.json'))
    require(invocation.get('sourceCommit') == SOURCE and invocation.get('sourceTree') == TREE
            and invocation.get('runId') == str(RUN) and invocation.get('runAttempt') == str(ATTEMPT),
            'Original invocation binding differs')
    require(build.get('mode') == 'verify-build' and build.get('status') == 'build-verified'
            and capture.get('mode') == 'capture' and capture.get('status') == 'captured'
            and capture.get('actualAndroidExecution') is True,
            'Original build/capture report was incomplete')
    identity = capture['buildIdentity']
    require(canonical(identity) == canonical(build['buildIdentity']), 'Original build/capture identities differ')
    apk = members[APK]
    require(identity.get('sourceCommit') == SOURCE and identity.get('sourceTree') == TREE
            and identity.get('dirtySource') is False and identity.get('package') == 'local.pocketchat.test'
            and identity.get('apkSha256') == apk['sha256'] and identity.get('apkBytes') == apk['bytes']
            and capture.get('installedApk', {}).get('sha256') == apk['sha256'],
            'Original APK stream/build/installed identity differs')
    sdkraw = raw('work/native-caret-sdk/sdk-build-receipt.json')
    sdk = json.loads(sdkraw)
    require(digest(sdkraw) == identity.get('sdkReceiptSha256') and sdk.get('sourceCommit') == SOURCE
            and sdk.get('runId') == str(RUN) and sdk.get('runAttempt') == str(ATTEMPT),
            'Original SDK receipt source/run/byte identity differs')
    screens = capture.get('screenshots')
    planned = capture.get('plannedScreens')
    require(isinstance(screens, list) and len(screens) == 40 and isinstance(planned, list)
            and len(planned) == 40 and build.get('plannedScreens') == planned,
            'Original 40-scene roster is incomplete')
    refs = set()
    for index, (screen, plan) in enumerate(zip(screens, planned), 1):
        require(screen.get('index') == index and screen.get('scene') == plan.get('scene')
                and screen.get('themeRequested') == plan.get('theme')
                and all(screen.get(k) == plan.get(k) for k in ('widthDp', 'heightDp', 'fontScale')),
                'Original scene identity differs')
        for field, suffix in [('image', '.png'), ('xml', '.xml')]:
            leaf = screen.get(field)
            require(isinstance(leaf, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', leaf)
                    and leaf.endswith(suffix), 'Unsafe original scene reference')
            path = 'work/oil-ui/round-1/' + leaf
            require(path not in refs and path in members
                    and members[path]['sha256'] == screen.get(field + 'Sha256'),
                    'Original screenshot/hierarchy hash differs or duplicates')
            refs.add(path)
    actual_visuals = {p for p in members if p.endswith(('.png', '.xml'))}
    require(refs == actual_visuals, 'Unreferenced or missing original visual member')
    return {'originalApk': apk, 'originalInstalledApk': capture['installedApk'],
            'originalSdkReceiptSha256': digest(sdkraw), 'originalScreens': 40,
            'originalBuildAndCaptureBound': True, 'originalVisualBytesBound': True,
            'apkSignatureReverifiedByExporter': False,
            'scope': 'Transport cross-check only; original capture/build reports remain unmodified. No new Android execution or release acceptance.'}


def export_archive(archive_path, out):
    # Hash the entire original ZIP before any derived output; this is not an APK extraction.
    h = hashlib.sha256()
    size = 0
    with archive_path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(chunk)
            h.update(chunk)
    require(size == ARCHIVE_BYTES and h.hexdigest() == ARCHIVE_SHA256, 'Original ZIP bytes/digest differ')
    records, parts = {}, [0] * PART_COUNT
    with zipfile.ZipFile(archive_path) as archive:
        entries = checked_members(archive)
        # First pass verifies every member CRC and streams the APK hash without writing APK bytes.
        for entry in entries:
            records[entry.filename] = dict(stream_entry(archive, entry), originalZipPath=entry.filename,
                                          originalCrc32=f'{entry.CRC:08x}')
        binding = bind_original_reports(archive, records)
        # Only after full archive and source/report validation, copy allowed original bytes.
        for entry in entries:
            if entry.filename == APK:
                records[entry.filename]['exported'] = False
                records[entry.filename]['reason'] = 'Original full APK remains in the fixed GitHub artifact; streamed for hash only.'
                continue
            candidates = [i for i, used in enumerate(parts) if used + entry.file_size <= PART_LIMIT]
            require(candidates, 'Cannot fit fixed diagnostic parts')
            i = candidates[0]
            part = f'part-{i + 1:02d}'
            copied = stream_entry(archive, entry, out / part / entry.filename)
            require(copied['bytes'] == records[entry.filename]['bytes']
                    and copied['sha256'] == records[entry.filename]['sha256'], 'Export copy bytes differ')
            parts[i] += entry.file_size
            records[entry.filename].update(exported=True, part=part)
    return {'archiveBytesVerified': True, 'allMemberCrcVerified': True,
            'allMemberSha256Recorded': True, 'originalReportBinding': binding,
            'members': records, 'parts': [dict(name=f'part-{i + 1:02d}', uncompressedBytes=n)
                                         for i, n in enumerate(parts) if n]}


def main():
    out = Path('work/oil-ui-artifact-export')
    out.mkdir(parents=True, exist_ok=False)
    provenance = out / 'provenance'
    provenance.mkdir()
    result = {'schema': 1, 'status': 'started', 'transportOnly': True,
              'originalCaptureSource': SOURCE, 'originalCaptureTree': TREE, 'originalAppTree': APP_TREE,
              'originalRun': RUN, 'originalAttempt': ATTEMPT, 'originalArtifactId': ARTIFACT,
              'originalArtifactBytes': ARCHIVE_BYTES, 'originalArtifactSha256': ARCHIVE_SHA256,
              'originalArtifactRetainedAtGitHub': True, 'newAndroidExecution': False,
              'releaseAcceptance': False, 'signingExecuted': False, 'publicationExecuted': False}
    try:
        require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY
                and os.environ.get('GITHUB_EVENT_NAME') == 'push'
                and os.environ.get('GITHUB_REF_NAME', '').startswith('debug/oil-ui-export-'),
                'Unexpected export repository/event/branch')
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        require(head == os.environ['GITHUB_SHA'] and head != SOURCE
                and not subprocess.check_output(['git', 'status', '--porcelain'], text=True),
                'Exporter checkout identity is dirty or differs')
        result['exporterIdentity'] = dict(sourceCommit=head,
            sourceTree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
            runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ['GITHUB_RUN_ATTEMPT'],
            helperSha256=digest(Path(__file__).read_bytes()),
            workflowSha256=digest(Path('.github/workflows/oil-ui-artifact-export.yml').read_bytes()))
        opener = urllib.request.build_opener(NoRedirect())
        run = api_json(opener, f'/repos/{REPOSITORY}/actions/runs/{RUN}/attempts/{ATTEMPT}', provenance/'original-run.json')
        artifact = api_json(opener, f'/repos/{REPOSITORY}/actions/artifacts/{ARTIFACT}', provenance/'original-artifact.json')
        commit = api_json(opener, f'/repos/{REPOSITORY}/git/commits/{SOURCE}', provenance/'original-commit.json')
        validate_metadata(run, artifact, commit)
        archive = Path(os.environ['RUNNER_TEMP']) / f'oil-ui-original-{ARTIFACT}.zip'
        total = 0
        with archive_response(opener) as response:
            with archive.open('xb') as target:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    require(total <= ARCHIVE_BYTES, 'Download exceeds fixed original ZIP size')
                    target.write(chunk)
        result.update(export_archive(archive, out))
        result['status'] = 'exported-original-bytes'
    except Exception as error:
        result.update(status='failed-closed', errorType=type(error).__name__, error=str(error))
        raise
    finally:
        write(provenance/'export-provenance.json', result)


if __name__ == '__main__':
    main()
