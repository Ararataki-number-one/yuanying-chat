"""Keep public candidates separate from verified stable app updates."""
import datetime
import re


class ReleaseChannelError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ReleaseChannelError(message)


def release_tag(manifest):
    version = manifest.get('version')
    require(isinstance(version, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version), 'Invalid release version.')
    channel = manifest.get('channel', 'stable')
    require(channel in ('stable', 'candidate'), 'Unknown release channel.')
    number = manifest.get('candidateNumber')
    if channel == 'candidate':
        require(type(number) is int and 1 <= number <= 999, 'Candidates require a positive sequence number.')
        return f'v{version}-candidate{number}-gecko'
    require(number is None, 'A stable release cannot carry a candidate sequence.')
    return f'v{version}-gecko'


def advances_update_channel(manifest):
    release_tag(manifest)
    return manifest.get('channel', 'stable') == 'stable'


def requires_manual_acceptance(manifest):
    release_tag(manifest)
    return advances_update_channel(manifest) and tuple(map(int, manifest['version'].split('.'))) >= (1, 6, 0)


def verify_direct_release(record, identity):
    """Record an explicit publication request without claiming phone acceptance.

    This is a separate, opt-in publication decision. It never satisfies or
    changes the physical-device checklist contract above or below.
    """
    require(isinstance(identity, dict) and identity.get('channel') == 'stable',
            'Direct publication requires an explicit stable release identity.')
    release_tag(identity)
    require(isinstance(record, dict), 'A direct publication authorization is required.')
    identity_fields = ('sourceCommit', 'sha256', 'version', 'versionCode', 'signerSha256', 'bytes')
    required_fields = set(identity_fields) | {
        'schema', 'kind', 'status', 'requestedBy', 'authorizationSource', 'userRequest',
        'requestedChannel', 'scope', 'physicalPhoneAcceptanceStatus', 'recordedAt'}
    require(set(record) == required_fields,
            'Direct publication accepts only authorization fields, never manual acceptance or phone claims.')
    expected = {
        'schema': 1, 'kind': 'user-requested-stable-release', 'status': 'authorized',
        'requestedBy': 'user',
        'requestedChannel': 'stable', 'scope': 'publish-existing-signed-apk-to-stable',
        'physicalPhoneAcceptanceStatus': 'not-reported'}
    require(record['authorizationSource'] in ('current-user-message', 'prior-explicit-user-message-in-current-task'),
            'Publication requires an explicit user instruction in this task, not inferred intent.')
    for key, value in expected.items():
        require(type(record[key]) is type(value) and record[key] == value,
                'Invalid direct publication authorization field: ' + key)
    for key in identity_fields:
        require(type(record[key]) is type(identity.get(key)) and record[key] == identity.get(key),
                'Direct publication authorization belongs to a different ' + key + '.')
    for key, length in (('sourceCommit', 40), ('sha256', 64), ('signerSha256', 64)):
        require(isinstance(record[key], str) and re.fullmatch(r'[0-9a-f]{' + str(length) + r'}', record[key]),
                'Invalid exact APK identity field: ' + key)
    for key in ('versionCode', 'bytes'):
        require(type(record[key]) is int and record[key] > 0, 'Invalid exact APK identity field: ' + key)
    request = record['userRequest']
    require(isinstance(request, str) and request.strip() and len(request) <= 2000,
            'The explicit user publication request is required.')
    # Deliberately accept direct commands, not an inferred instruction from
    # vague continuation, a question, a quoted discussion, or a negation.
    command = re.sub(r'\s+', ' ', request.strip())
    chinese = re.fullmatch(
        r'(?:(?:请|现在|直接|立即|继续|帮我|给我|麻烦)\s*)*'
        r'(?:发布|发行|上线)(?:为)?\s*(?:正式版|正式版本|新版本)(?:吧|即可|就行)?[。.!！]*', command)
    english = re.fullmatch(
        r'(?:please )?(?:publish|release|promote) (?:the )?(?:existing |signed |existing signed )?'
        r'(?:apk |app |release )?(?:(?:to|as) )?(?:a |the )?(?:stable|production)(?: release| version)?[.!]*',
        command, re.IGNORECASE)
    # This exact command follows the explicit stable-release request in the session.
    implement_and_publish = command in ("先做这个，然后发布优化后的下一版本", "继续，然后发布新版本", "做这个然后发布", '做完上面的给我继续优化网络体验我现在的网络延迟还是400多。给我降到200左右。不管你用什么办法，用最高级的，最先进的架构也好，修修补补改进也好。然后再发布你优化后的版本')
    require(chinese is not None or english is not None or implement_and_publish,
            'The authorization must preserve a direct affirmative request to publish the stable release.')
    recorded_at = record['recordedAt']
    require(isinstance(recorded_at, str) and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', recorded_at),
        'Direct publication requires a timezone-qualified ISO 8601 recording time.')
    try:
        parsed = datetime.datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
    except ValueError:
        raise ReleaseChannelError('Invalid direct publication recording time.') from None
    require(parsed.utcoffset() is not None, 'Direct publication recording time requires a timezone.')
    return dict(record, physicalArmPhone='not-tested')


def verify_manual_acceptance(record, identity):
    """Validate a user-reported checklist; never relabel it as automated evidence."""
    require(isinstance(record, dict) and record.get('schema') == 1 and record.get('status') == 'passed', 'A passed physical-device checklist is required.')
    require(record.get('reportedBy') == 'user' and record.get('actualPhysicalPhoneExecution') is True, 'Manual acceptance must identify the user and a physical phone.')
    for key in ('sourceCommit', 'sha256', 'version', 'versionCode'):
        require(record.get(key) == identity.get(key), 'Manual acceptance belongs to a different ' + key + '.')
    require(re.fullmatch(r'[0-9a-f]{40}', record.get('sourceCommit', '')), 'A complete source revision is required.')
    require(re.fullmatch(r'[0-9a-f]{64}', record.get('sha256', '')), 'An exact signed APK hash is required.')
    require(record.get('abi') == 'arm64-v8a', 'An ARM64 phone is required.')
    for key in ('deviceModel', 'androidVersion', 'reportedAt'):
        require(isinstance(record.get(key), str) and 0 < len(record[key].strip()) <= 200, 'Missing manual device field: ' + key)
    required = {'upgrade-data', 'login-session', 'chinese-input', 'attachments', 'downloads',
                'long-reply', 'background-resume', 'environment-isolation', 'fixed-exit', 'independent-subscriptions'}
    if tuple(map(int, identity['version'].split('.'))) >= (1, 7, 0):
        required |= {'template-observations', 'reset-and-slot-reuse'}
    if tuple(map(int, identity['version'].split('.'))) >= (2, 0, 0):
        required |= {'resource-policy', 'sustained-use'}
    checks = record.get('checks')
    require(isinstance(checks, list) and checks, 'A physical-device checklist is required.')
    require(all(isinstance(item, dict) and item.get('pass') is True and isinstance(item.get('name'), str) for item in checks), 'Every reported manual check must pass.')
    names = [item['name'] for item in checks]
    require(len(names) == len(set(names)) and required <= set(names), 'The physical-device checklist is incomplete or duplicated.')
    return {'status': 'passed', 'reportedBy': 'user', 'actualPhysicalPhoneExecution': True,
            'sourceCommit': identity['sourceCommit'], 'sha256': identity['sha256'],
            'version': identity['version'], 'versionCode': identity['versionCode'],
            'abi': record['abi'], 'deviceModel': record['deviceModel'], 'androidVersion': record['androidVersion'],
            'reportedAt': record['reportedAt'], 'checks': len(checks),
            'scope': 'User-reported physical-device acceptance; automated Android and host evidence are separate.'}


# Optional bounded transport of an already signed APK. This never grants release acceptance.
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

CHUNK_BYTES = 60_000_000
MAX_APK_BYTES = 250_000_000
MAX_TAIL_BYTES = 1_048_576
MAX_MANIFEST_BYTES = 262_144
SIGNER = 'f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434'
DESCRIPTOR_KEYS = {'schema','kind','sourceCommit','runId','runAttempt',
                   'unsignedArtifactCommit','buildManifest','prefixBytes','tail'}


class TransportError(ReleaseChannelError):
    pass


def _transport_require(ok, why):
    if not ok:
        raise TransportError(why)


def transport_strict_json(raw):
    _transport_require(isinstance(raw, bytes) and len(raw) <= MAX_MANIFEST_BYTES,
            'JSON input exceeds fixed bound')
    def pairs(items):
        result = {}
        for key, value in items:
            _transport_require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise TransportError('Non-finite JSON number')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise TransportError('Invalid bounded JSON') from error


def read_transport_json_bytes(path):
    try:
        fd = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise TransportError('Cannot open ordinary JSON file') from error
    try:
        info = os.fstat(fd)
        _transport_require(stat.S_ISREG(info.st_mode), 'JSON file is not regular')
        _transport_exact_int(info.st_size, 1, MAX_MANIFEST_BYTES, 'JSON file exceeds fixed bound')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(MAX_MANIFEST_BYTES+1)
            _transport_require(len(raw) == info.st_size, 'JSON file changed while reading')
            return raw
    finally:
        if fd is not None:
            os.close(fd)


def read_transport_json_file(path):
    return transport_strict_json(read_transport_json_bytes(path))


def _transport_exact_int(value, low, high, why):
    _transport_require(type(value) is int and low <= value <= high, why)


def _transport_digest(value, why):
    _transport_require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), why)


def _transport_identity(value, length, why):
    _transport_require(type(value) is str and re.fullmatch(r'[0-9a-f]{'+str(length)+r'}', value), why)


def _transport_positive_decimal(value, why):
    _transport_require(type(value) is str and re.fullmatch(r'[1-9][0-9]{0,19}', value), why)


def _transport_safe_file(value):
    _transport_require(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}', value)
            and value not in ('.','..'), 'Unsafe flat file name')
    return value


def _transport_file_ref(value, *, expected_name, maximum):
    _transport_require(type(value) is dict and set(value) == {'file','bytes','sha256'},
            'Invalid file reference shape')
    _transport_safe_file(value['file'])
    _transport_require(value['file'] == expected_name, 'Unexpected file reference name')
    _transport_exact_int(value['bytes'], 1, maximum, 'Invalid referenced byte count')
    _transport_digest(value['sha256'], 'Invalid referenced SHA256')


def _transport_source_directory(path):
    path = Path(path)
    _transport_require(not path.is_symlink() and path.is_dir(), 'Input directory must be ordinary')
    return path.resolve()


def _transport_regular_stream(root, name, size):
    path = root / _transport_safe_file(name)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise TransportError('Cannot open ordinary referenced file') from error
    try:
        actual = os.fstat(fd)
        _transport_require(stat.S_ISREG(actual.st_mode), 'Referenced file is not regular')
        _transport_require(actual.st_size == size, 'Referenced file byte count differs')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def _transport_read_small(root, ref, maximum):
    _transport_exact_int(ref['bytes'], 1, maximum, 'Small file bound exceeded')
    with _transport_regular_stream(root, ref['file'], ref['bytes']) as stream:
        raw = stream.read(ref['bytes'] + 1)
        _transport_require(len(raw) == ref['bytes'], 'Small file changed while reading')
        _transport_require(not stream.read(1), 'Small file grew while reading')
    _transport_require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Small file SHA256 differs')
    return raw


def _transport_validate_parts(parts, *, total, prefix, why):
    _transport_require(type(parts) is list and len(parts) == (total + CHUNK_BYTES - 1)//CHUNK_BYTES,
            why+' part count differs')
    names = set()
    for number, part in enumerate(parts):
        _transport_require(type(part) is dict and set(part) == {'file','bytes','sha256'}, why+' part shape differs')
        name = _transport_safe_file(part['file'])
        _transport_require(name not in names, why+' duplicate part path')
        names.add(name)
        _transport_require(name == prefix+f'{number:02d}', why+' part path differs')
        expected = min(CHUNK_BYTES, total-number*CHUNK_BYTES)
        _transport_require(type(part['bytes']) is int and part['bytes'] == expected, why+' part byte count differs')
        _transport_digest(part['sha256'], why+' part SHA256 invalid')


def assemble_signed_transport(transport, release, source_dir, output_dir, *, expected_source,
             expected_run, expected_attempt, expected_artifact):
    """Expose a new directory of exact signed parts only after every byte check.

    Only the unsigned APK prefix and a single bounded replacement tail are
    permitted. No seek instructions, executable commands, arbitrary destinations,
    external downloads, key material, or general-purpose patch format exist.
    """
    _transport_identity(expected_source, 40, 'Invalid expected source')
    _transport_identity(expected_artifact, 40, 'Invalid expected immutable artifact')
    _transport_positive_decimal(expected_run, 'Invalid expected run')
    _transport_positive_decimal(expected_attempt, 'Invalid expected attempt')
    _transport_require(type(transport) is dict and set(transport) == DESCRIPTOR_KEYS, 'Invalid transport shape')
    _transport_require(type(transport['schema']) is int and transport['schema'] == 1, 'Invalid transport schema')
    _transport_require(transport['kind'] == 'unsigned-prefix-tail-v1', 'Unsupported transport kind')
    for key, expected in (('sourceCommit',expected_source),('runId',expected_run),
                          ('runAttempt',expected_attempt),('unsignedArtifactCommit',expected_artifact)):
        _transport_require(type(transport[key]) is str and transport[key] == expected, 'Transport identity differs: '+key)
    _transport_file_ref(transport['buildManifest'], expected_name='unsigned-build-manifest.json', maximum=MAX_MANIFEST_BYTES)
    _transport_file_ref(transport['tail'], expected_name='signed-apk-tail.bin', maximum=MAX_TAIL_BYTES)
    root = _transport_source_directory(source_dir)
    build = transport_strict_json(_transport_read_small(root, transport['buildManifest'], MAX_MANIFEST_BYTES))
    _transport_require(type(build) is dict and type(release) is dict, 'Manifest object required')
    for key, expected in (('sourceCommit',expected_source),('runId',expected_run),('runAttempt',expected_attempt)):
        _transport_require(type(build.get(key)) is str and build[key] == expected, 'Build identity differs: '+key)
    for key, expected in (('sourceCommit',expected_source),('buildRunId',expected_run),('buildRunAttempt',expected_attempt)):
        _transport_require(type(release.get(key)) is str and release[key] == expected, 'Release identity differs: '+key)
    version = release.get('version')
    _transport_require(type(version) is str and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version), 'Invalid release version')
    _transport_exact_int(release.get('versionCode'), 1, 2_147_483_647, 'Invalid release version code')
    _transport_require(build.get('version') == version and type(build.get('versionCode')) is int
            and build['versionCode'] == release['versionCode'], 'Build/release versions differ')
    filename = f'PocketChat-{version}-gecko-arm64.apk'
    _transport_require(release.get('filename') == filename and release.get('package') == 'local.pocketchat',
            'Unexpected release APK identity')
    _transport_require(release.get('signerSha256') == SIGNER, 'Unexpected original signer declaration')
    _transport_exact_int(release.get('bytes'), 1, MAX_APK_BYTES, 'Invalid signed APK size')
    _transport_digest(release.get('sha256'), 'Invalid signed APK SHA256')
    _transport_digest(release.get('unsignedSha256'), 'Invalid unsigned APK declaration')
    _transport_require(type(build.get('artifacts')) is list and len(build['artifacts']) == 1, 'Single unsigned artifact required')
    unsigned = build['artifacts'][0]
    _transport_require(type(unsigned) is dict and unsigned.get('abi') == 'arm64-v8a'
            and unsigned.get('signing') == 'unsigned', 'Unexpected unsigned artifact identity')
    _transport_exact_int(unsigned.get('bytes'), 1, MAX_APK_BYTES, 'Invalid unsigned APK size')
    _transport_digest(unsigned.get('sha256'), 'Invalid unsigned full SHA256')
    _transport_require(unsigned['sha256'] == release['unsignedSha256'], 'Unsigned/source receipt SHA256 differs')
    _transport_validate_parts(unsigned.get('chunks'), total=unsigned['bytes'],
                   prefix=f'PocketChat-{version}-arm64-v8a.apk.part', why='Unsigned')
    _transport_validate_parts(release.get('parts'), total=release['bytes'], prefix=filename+'.part', why='Signed')
    all_names = [x['file'] for x in unsigned['chunks']]+[transport['tail']['file'], transport['buildManifest']['file']]
    _transport_require(len(all_names) == len(set(all_names)), 'Duplicate input path')
    prefix = transport['prefixBytes']
    _transport_exact_int(prefix, 1, unsigned['bytes'], 'Invalid prefix range')
    _transport_require(prefix + transport['tail']['bytes'] == release['bytes'], 'Prefix and tail do not match signed size')
    # The tail is read and verified before creating any output.
    tail = _transport_read_small(root, transport['tail'], MAX_TAIL_BYTES)
    destination = Path(output_dir)
    _transport_require(not os.path.lexists(destination), 'Output already exists')
    _transport_require(not destination.parent.is_symlink() and destination.parent.is_dir(), 'Output parent must be ordinary')
    exposed = False
    with tempfile.TemporaryDirectory(prefix='.signed-transport-', dir=destination.parent) as temp:
        stage = Path(temp)
        signed_path = stage / 'signed.tmp'
        full_hash, signed_hash = hashlib.sha256(), hashlib.sha256()
        full_size, copied = 0, 0
        with signed_path.open('xb') as signed:
            for part in unsigned['chunks']:
                part_hash, count = hashlib.sha256(), 0
                with _transport_regular_stream(root, part['file'], part['bytes']) as stream:
                    while raw := stream.read(min(1_048_576, part['bytes']-count+1)):
                        count += len(raw)
                        _transport_require(count <= part['bytes'], 'Unsigned part grew while reading')
                        part_hash.update(raw);full_hash.update(raw);full_size += len(raw)
                        take = min(len(raw), prefix-copied)
                        if take > 0:
                            signed.write(raw[:take]);signed_hash.update(raw[:take]);copied += take
                    _transport_require(count == part['bytes'], 'Unsigned part truncated while reading')
                _transport_require(part_hash.hexdigest() == part['sha256'], 'Unsigned part actual SHA256 differs')
            _transport_require(full_size == unsigned['bytes'] and full_hash.hexdigest() == unsigned['sha256'],
                    'Unsigned full actual SHA256 differs')
            _transport_require(copied == prefix, 'Prefix copy incomplete')
            signed.write(tail);signed_hash.update(tail)
        _transport_require(signed_path.stat().st_size == release['bytes'], 'Signed actual size differs')
        _transport_require(signed_hash.hexdigest() == release['sha256'], 'Signed final actual SHA256 differs')
        parts = stage / 'parts';parts.mkdir()
        produced = []
        with signed_path.open('rb') as signed:
            for part in release['parts']:
                raw = signed.read(part['bytes'])
                _transport_require(len(raw) == part['bytes'] and hashlib.sha256(raw).hexdigest() == part['sha256'],
                        'Signed final part SHA256 differs')
                (parts/part['file']).write_bytes(raw)
                produced.append(dict(part))
            _transport_require(not signed.read(1), 'Unexpected signed suffix')
        receipt = {'schema':1,'status':'passed','scope':'Exact byte transport only; no release or signature acceptance',
                   'sourceCommit':expected_source,'runId':expected_run,'runAttempt':expected_attempt,
                   'unsignedArtifactCommit':expected_artifact,'unsignedBytes':full_size,
                   'unsignedSha256':full_hash.hexdigest(),'prefixBytes':prefix,'tailBytes':len(tail),
                   'signedBytes':release['bytes'],'signedSha256':signed_hash.hexdigest(),
                   'parts':produced,'physicalPhoneAcceptance':False,'releaseAcceptance':False}
        (parts/'transport-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        # mkdir(exist_ok=False) prevents replacing a pre-existing empty directory.
        destination.mkdir(mode=0o700)
        try:
            for path in parts.iterdir():
                path.rename(destination/path.name)
            exposed = True
        finally:
            if not exposed:
                shutil.rmtree(destination)
    return receipt


def signed_transport_artifact_commit(release):
    """Return a validated immutable artifact identity, or the legacy None."""
    _transport_require(type(release) is dict, 'Release manifest object required')
    if 'signedTransportArtifact' not in release:
        return None
    record = release['signedTransportArtifact']
    _transport_require(type(record) is dict and set(record) ==
                       {'file','bytes','sha256','unsignedArtifactCommit'},
                       'Invalid signed transport artifact shape')
    _transport_identity(record['unsignedArtifactCommit'],40,'Invalid transport artifact commit')
    ref = {key:record[key] for key in ('file','bytes','sha256')}
    _transport_file_ref(ref,expected_name='signed-transport.json',maximum=MAX_MANIFEST_BYTES)
    return record['unsignedArtifactCommit']


def verify_unsigned_transport_provenance(release, local_manifest_raw, git_manifest_raw,
                                       git_parents, actual_commit):
    """Verify independently fetched immutable metadata, without network I/O."""
    expected = signed_transport_artifact_commit(release)
    _transport_require(expected is not None and type(actual_commit) is str and actual_commit == expected,
                       'Fetched immutable artifact differs')
    _transport_identity(release.get('sourceCommit'),40,'Invalid provenance source')
    _transport_require(type(git_parents) is list and 1 <= len(git_parents) <= 8,
                       'Invalid artifact parent list')
    for parent in git_parents:
        _transport_identity(parent,40,'Invalid artifact parent identity')
    _transport_require(git_parents[0] == release['sourceCommit'], 'Artifact first parent differs from source')
    _transport_require(type(local_manifest_raw) is bytes and type(git_manifest_raw) is bytes
                       and len(local_manifest_raw) <= MAX_MANIFEST_BYTES
                       and local_manifest_raw == git_manifest_raw,
                       'Immutable artifact manifest bytes differ')
    build = transport_strict_json(git_manifest_raw)
    _transport_require(type(build) is dict, 'Immutable build manifest object required')
    for key, release_key in (('sourceCommit','sourceCommit'),('runId','buildRunId'),('runAttempt','buildRunAttempt')):
        _transport_require(type(build.get(key)) is str and type(release.get(release_key)) is str
                           and build[key] == release[release_key], 'Immutable artifact identity differs: '+key)
    _transport_positive_decimal(build['runId'],'Invalid immutable artifact run')
    _transport_positive_decimal(build['runAttempt'],'Invalid immutable artifact attempt')
    _transport_require(type(build.get('version')) is str and build['version'] == release.get('version')
                       and type(build.get('versionCode')) is int and type(release.get('versionCode')) is int
                       and build['versionCode'] == release['versionCode'], 'Immutable artifact version differs')
    _transport_require(type(build.get('artifacts')) is list and len(build['artifacts']) == 1,
                       'Immutable artifact count differs')
    unsigned = build['artifacts'][0]
    _transport_require(type(unsigned) is dict and unsigned.get('abi') == 'arm64-v8a'
                       and unsigned.get('signing') == 'unsigned', 'Immutable unsigned artifact identity differs')
    _transport_exact_int(unsigned.get('bytes'),1,MAX_APK_BYTES,'Immutable unsigned artifact size invalid')
    _transport_digest(unsigned.get('sha256'),'Immutable unsigned artifact SHA256 invalid')
    _transport_require(unsigned['sha256'] == release.get('unsignedSha256'),
                       'Immutable unsigned artifact SHA256 differs from release')
    return {'artifactCommit':expected,'sourceCommit':build['sourceCommit'],'runId':build['runId'],
            'runAttempt':build['runAttempt'],'manifestSha256':hashlib.sha256(git_manifest_raw).hexdigest(),
            'unsignedSha256':unsigned['sha256'],'firstParentVerified':True}


def restore_signed_transport(release, source_dir):
    """Optionally restore original signed part files before existing validation.

    An absent field is the unchanged historical transport. Presence requires the
    full strict schema. This is never an exception to a release or signature gate.
    """
    artifact_commit = signed_transport_artifact_commit(release)
    if artifact_commit is None:
        return None
    record = release['signedTransportArtifact']
    ref = {key:record[key] for key in ('file','bytes','sha256')}
    root = _transport_source_directory(source_dir)
    transport = transport_strict_json(_transport_read_small(root,ref,MAX_MANIFEST_BYTES))
    with tempfile.TemporaryDirectory(prefix='verified-signed-parts-') as temporary:
        parts = Path(temporary)/'parts'
        result = assemble_signed_transport(transport,release,root,parts,
                    expected_source=release.get('sourceCommit'),expected_run=release.get('buildRunId'),
                    expected_attempt=release.get('buildRunAttempt'),
                    expected_artifact=record['unsignedArtifactCommit'])
        # Existing signed parts make the two transports ambiguous. Never replace
        # an existing part or a symlink, even if its bytes happen to match.
        for item in result['parts']:
            _transport_require(not os.path.lexists(root/item['file']), 'Signed destination already exists')
        created = []
        try:
            for item in result['parts']:
                target = root/item['file']
                fd = os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                created.append(target)
                with os.fdopen(fd,'wb') as out, (parts/item['file']).open('rb') as stream:
                    shutil.copyfileobj(stream,out,length=1_048_576)
        except BaseException:
            for path in created:
                path.unlink()
            raise
    return dict(result,transportArtifactSha256=ref['sha256'])
