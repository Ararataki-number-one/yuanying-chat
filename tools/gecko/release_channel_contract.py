"""Keep public candidates separate from verified stable app updates."""
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
