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
    implement_and_publish = command in ("做这个然后发布", '做完上面的给我继续优化网络体验我现在的网络延迟还是400多。给我降到200左右。不管你用什么办法，用最高级的，最先进的架构也好，修修补补改进也好。然后再发布你优化后的版本')
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
