"""Source-bound DDS and carrier preparation inside the existing QEMU budget.

The device's own named Binder APIs perform DDS initialization and normal carrier
configuration reload. This module neither changes mobile-data/provisioning
settings nor supplies network acceptance evidence.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
from zipfile import ZipFile

import prepare_emulator as normal
from caret_build_identity import dex_definitions

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'tools/gecko/EmulatorDataSubscription.java'
CLASS = 'org.pocketchat.synthetic.EmulatorDataSubscription'
D8_SHA256 = 'a26ee56252adcff6752c379ae255a0ad538ebec60189e078ec6855487107637d'
MAX_OUTPUT = 262144


def require(value, message):
    if not value:
        raise ValueError('Cellular subscription preparation: ' + message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    require(type(raw) is str and 0 < len(raw.encode('utf-8')) <= 16384, 'bounded actual helper JSON required')
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'duplicate helper JSON field')
            value[key] = item
        return value
    def constant(unused):
        raise ValueError('Nonfinite helper JSON value')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def validate_receipt(raw, nonce):
    value = decode(raw)
    fields = {'schema', 'kind', 'runNonce', 'status', 'uid', 'androidSdk', 'qemu', 'abi', 'hardware',
              'initial', 'beforeWrite', 'after', 'setCalls', 'carrierConfig', 'applicationAcceptance',
              'physicalPhoneAcceptance', 'networkAcceptance'}
    require(type(value) is dict and set(value) == fields, 'exact helper success fields required')
    require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce)
            and value['runNonce'] == nonce and type(value['schema']) is int and value['schema'] == 2
            and value['kind'] == 'synthetic-default-data-subscription' and value['status'] == 'passed',
            'helper invocation or status differs')
    require(type(value['uid']) is int and value['uid'] == 2000
            and type(value['androidSdk']) is int and value['androidSdk'] == 35
            and value['qemu'] is True and value['abi'] == 'x86_64' and value['hardware'] == 'ranchu',
            'actual fixed QEMU shell identity required')
    require(all(value[key] is False for key in ('applicationAcceptance', 'physicalPhoneAcceptance', 'networkAcceptance')),
            'subscription helper cannot assert network or application acceptance')
    sole = None
    for name in ('initial', 'beforeWrite', 'after'):
        row = value[name]
        require(type(row) is dict and set(row) == {'activeSubscriptionIds', 'defaultDataSubId', 'phoneId', 'slotSubscriptionId'},
                'exact subscription snapshot fields required')
        ids = row['activeSubscriptionIds']
        require(type(ids) is list and len(ids) == 1 and type(ids[0]) is int and 0 < ids[0] < 2147483647,
                'one actual positive subscription required')
        sole = ids[0] if sole is None else sole
        require(ids == [sole] and type(row['phoneId']) is int and row['phoneId'] == 0
                and type(row['slotSubscriptionId']) is int and row['slotSubscriptionId'] == sole,
                'subscription mapping changed or is not slot zero')
        require(type(row['defaultDataSubId']) is int and row['defaultDataSubId'] in (-1, sole),
                'foreign or malformed default data subscription')
    initial, before, after = (value[name]['defaultDataSubId'] for name in ('initial', 'beforeWrite', 'after'))
    require(before == initial or (initial == -1 and before == sole), 'existing valid default regressed')
    require(type(value['setCalls']) is int and value['setCalls'] == (1 if before == -1 else 0)
            and after == sole, 'single initialization/readback relation differs')
    carrier = value['carrierConfig']
    require(type(carrier) is dict and set(carrier) == {
        'subscriptionId', 'slotIndex', 'simStateBefore', 'simStateAfter',
        'appliedBefore', 'appliedAfter', 'refreshCalls', 'asynchronous'},
        'exact carrier configuration observation fields required')
    require(type(carrier['subscriptionId']) is int and carrier['subscriptionId'] == sole
            and type(carrier['slotIndex']) is int and carrier['slotIndex'] == 0
            and all(type(carrier[key]) is int and carrier[key] == 10
                    for key in ('simStateBefore', 'simStateAfter')),
            'same loaded single SIM required for carrier configuration')
    require(type(carrier['appliedBefore']) is bool and type(carrier['appliedAfter']) is bool
            and carrier['asynchronous'] is True,
            'actual typed asynchronous carrier configuration observations required')
    require(type(carrier['refreshCalls']) is int
            and carrier['refreshCalls'] == (1 if initial == -1 or not carrier['appliedBefore'] else 0),
            'single normal carrier refresh relation differs')
    # A false appliedAfter is a valid immediate readback of an asynchronous
    # reload. Only the unchanged later CM observations can prove the network.
    return value


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError('Original cellular preparation deadline expired during subscription initialization')
    return value


def host_run(command, entry, deadline):
    timeout = min(8, remaining(deadline))
    row = dict(command=[str(x) for x in command], timeoutSeconds=timeout,
               deadlineMonotonic=deadline, startedAt=time.monotonic())
    entry['hostCommands'].append(row)
    environment = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_NO_REPLACE_OBJECTS='1', GIT_OPTIONAL_LOCKS='0')
    def capture(name, raw):
        row[name + 'Bytes'], row[name + 'Sha256'] = len(raw), digest(raw)
        if len(raw) > MAX_OUTPUT:
            row[name + 'OmittedOversize'] = True
        else:
            try:
                row[name + 'Utf8'] = raw.decode('utf-8')
            except UnicodeDecodeError:
                row[name + 'Base64'] = base64.b64encode(raw).decode('ascii')
    try:
        completed = subprocess.run(row['command'], cwd=ROOT, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def raw(value):
            return value.encode() if isinstance(value, str) else (value or b'')
        out, err = raw(error.stdout), raw(error.stderr)
        capture('stdout', out)
        capture('stderr', err)
        row.update(exitCode=None, timedOut=True, completedAt=time.monotonic())
        raise
    out, err = completed.stdout, completed.stderr
    require(type(out) is bytes and type(err) is bytes, 'host command must preserve raw bytes')
    capture('stdout', out)
    capture('stderr', err)
    row.update(exitCode=completed.returncode, timedOut=False, completedAt=time.monotonic())
    require(len(out) <= MAX_OUTPUT and len(err) <= MAX_OUTPUT, 'host command output exceeded bound')
    completed.check_returncode()
    remaining(deadline)
    return out, err


def ordinary(path, maximum):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            'ordinary bounded source/tool file required')
    return path.read_bytes()


def compile_helper(directory, entry, deadline):
    source = ROOT / SOURCE
    raw = ordinary(source, 65536)
    selected, unused = host_run(['git', '--no-replace-objects', 'show', entry['sourceCommit'] + ':' + SOURCE], entry, deadline)
    require(raw == selected, 'helper source differs from installed APK source')
    home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
    sdk = os.environ.get('ANDROID_HOME')
    require(home and sdk, 'original JDK17/Android SDK environment required')
    java, javac = ((Path(home) / 'bin' / name).resolve() for name in ('java', 'javac'))
    build = Path(sdk) / 'build-tools/37.0.0'
    d8 = build / 'lib/d8.jar'
    tools = {'java': java, 'javac': javac, 'd8': d8}
    pins = {name: dict(path=str(path), bytes=len(data), sha256=digest(data))
            for name, path in tools.items() for data in (ordinary(path, 32 * 1024 * 1024),)}
    require(pins['d8']['sha256'] == D8_SHA256, 'pinned build-tools 37 D8 bytes required')
    properties = ordinary(build / 'source.properties', 4096)
    require(re.findall(rb'^Pkg.Revision=(.*)$', properties, re.M) == [b'37.0.0'], 'exact build-tools revision required')
    version, version_error = host_run([java, '-version'], entry, deadline)
    require(re.search(rb'version "17[.\"]', version + version_error), 'original JDK17 required')
    entry.update(sourceFile=dict(path=SOURCE, bytes=len(raw), sha256=digest(raw)), toolchain=pins,
                 toolPropertiesSha256=digest(properties), javaVersionSha256=digest(version + version_error),
                 compilerCacheUsed=False)
    classes = directory / 'classes'
    classes.mkdir()
    host_run([javac, '--release', '8', '-encoding', 'UTF-8', '-d', classes, source], entry, deadline)
    files = sorted(classes.rglob('*.class'))
    require(1 <= len(files) <= 16, 'bounded actual helper classes required')
    prefix = CLASS.replace('.', '/')
    compiled, definitions = {}, set()
    for path in files:
        name = path.relative_to(classes).as_posix()
        require(re.fullmatch(re.escape(prefix) + r'(?:\$[A-Za-z0-9_]+)?\.class', name),
                'unexpected helper class output')
        content = ordinary(path, MAX_OUTPUT)
        require(content[:8] == b'\xca\xfe\xba\xbe\x00\x00\x00\x34', 'actual Java 8 helper class required')
        compiled[name] = dict(bytes=len(content), sha256=digest(content))
        definitions.add('L' + name[:-6] + ';')
    require('L' + prefix + ';' in definitions, 'helper entry class absent')
    jar = directory / 'helper.jar'
    host_run([java, '-cp', d8, 'com.android.tools.r8.D8', '--min-api', '35', '--release',
              '--output', jar, *files], entry, deadline)
    content = ordinary(jar, MAX_OUTPUT)
    with ZipFile(jar) as archive:
        require(archive.namelist() == ['classes.dex'] and archive.testzip() is None, 'exact helper DEX jar required')
        dex = archive.read('classes.dex')
    require(dex_definitions(dex) == definitions, 'actual DEX definitions differ from helper classes')
    require(ordinary(source, 65536) == raw, 'helper source changed during compilation')
    entry.update(classes=compiled, jar=dict(bytes=len(content), sha256=digest(content)),
                 dex=dict(bytes=len(dex), sha256=digest(dex), definitions=sorted(definitions)))
    remaining(deadline)
    return jar


def initialize(commands, record, identity):
    """Run once only after a validated empty post-teardown CM observation."""
    require(commands.record is record and commands.serial in ('emulator-5556', 'emulator-5554')
            and record.get('confirmedQemu') is True and record.get('networkMode') == 'cellular'
            and record.get('packagePresent') is True and record.get('disabledStateConfirmed') is True,
            'only confirmed cellular QEMU SDK teardown may initialize DDS')
    stage = record['cellularPreparation']
    require('subscriptionInitialization' not in stage, 'subscription initialization already attempted')
    rows = record['networkObservations']
    require(rows and stage.get('emptyDefaultNetworkObservationIndices', [])[-1:] == [len(rows) - 1],
            'actual triggering empty observation required')
    row = rows[-1]
    value = row['value']
    require(row['phase'] == 'after-setup-package-handling-cellular'
            and normal.validate_observation(value, identity, row['runNonce']) is False
            and value.get('activeNetwork') == value.get('activeNetworkAfter') == ''
            and type(value.get('schema')) is int and value['schema'] == 1
            and type(value.get('androidSdk')) is int and value['androidSdk'] == 35
            and type(value.get('transports')) is list and value['transports'] == []
            and type(value.get('capabilities')) is str and value['capabilities'] == ''
            and all(value.get(key) is False for key in ('capabilitiesPresent', 'internetCapability', 'stableDuringRead', 'usable')),
            'only exact validated empty default permits DDS initialization')
    source, tree, apk = (identity.get(key) for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
    require(all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in (source, tree))
            and type(apk) is str and re.fullmatch('[0-9a-f]{64}', apk)
            and record.get('sourceCommit') == source and record.get('sourceTree') == tree,
            'actual source/APK identity required')
    run, attempt = record.get('runId'), record.get('runAttempt')
    require(all(type(v) is str and re.fullmatch('[1-9][0-9]*', v) for v in (run, attempt)), 'original CI run identity required')
    sdk = identity.get('sdkBuildIdentity')
    require(sdk is None or (sdk.get('runId') == run and sdk.get('runAttempt') == attempt), 'SDK execution identity differs')
    nonce = secrets.token_hex(16)
    require(re.fullmatch('[0-9a-f]{32}', nonce) and nonce not in {x['runNonce'] for x in rows}, 'fresh helper nonce required')
    entry = dict(schema=1, status='failed', attempted=True, sourceCommit=source, sourceTree=tree,
        integrationApkSha256=apk, runId=run, runAttempt=attempt, runNonce=nonce, serial=commands.serial,
        triggerObservationIndex=len(rows) - 1, startedAt=time.monotonic(), deadlineMonotonic=commands.deadline,
        hostCommands=[], commandStartIndex=len(record['commands']), applicationAcceptance=False,
        physicalPhoneAcceptance=False, networkAcceptance=False, setterInvocationsInferred=False,
        adapterSha256=digest(Path(__file__).read_bytes()))
    stage['subscriptionInitialization'] = entry
    remote = '/data/local/tmp/pocketchat-cellular-subscription-' + nonce + '.jar'
    entry['deviceJarPath'] = remote
    pushed = False
    try:
        remaining(commands.deadline)
        work = ROOT / 'work/cellular-subscription'
        require(not work.is_symlink() and not work.parent.is_symlink(), 'ordinary helper working directory required')
        work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=nonce + '-', dir=work) as temporary:
            jar = compile_helper(Path(temporary), entry, commands.deadline)
            entry['pushCommandIndex'] = len(record['commands'])
            # Mark ownership before push, so a partial upload is still cleaned.
            pushed = True
            commands.run('push', str(jar), remote)
            entry['deviceHashCommandIndex'] = len(record['commands'])
            observed = commands.run('shell', 'sha256sum', remote)
            require(re.fullmatch(re.escape(entry['jar']['sha256']) + r'\s+' + re.escape(remote), observed),
                    'actual uploaded helper digest differs')
            entry['deviceSizeCommandIndex'] = len(record['commands'])
            size = commands.run('shell', 'stat', '-c', '%s', remote)
            require(size == str(entry['jar']['bytes']), 'actual uploaded helper byte count differs')
            entry['invocationCommandIndex'] = len(record['commands'])
            commands.run('shell', 'env', 'CLASSPATH=' + remote, 'app_process', '/system/bin', CLASS, nonce)
            raw = record['commands'][entry['invocationCommandIndex']]['stdout']
            entry['rawReceipt'] = raw
            entry['rawReceiptSha256'] = digest(raw.encode('utf-8'))
            entry['receipt'] = validate_receipt(raw, nonce)
            remaining(commands.deadline)
            entry['status'] = 'passed'
    except BaseException as error:
        entry.update(status='failed', failureType=type(error).__name__, reason=str(error))
        raise
    finally:
        try:
            if pushed:
                try:
                    remaining(commands.deadline)
                    entry['cleanupCommandIndex'] = len(record['commands'])
                    commands.run('shell', 'rm', '-f', remote)
                    remaining(commands.deadline)
                    entry['deviceJarRemoved'] = True
                except BaseException as error:
                    entry['deviceJarRemoved'] = False
                    entry['cleanupFailure'] = dict(failureType=type(error).__name__, reason=str(error))
                    if entry['status'] == 'passed':
                        entry.update(status='failed', failureType=type(error).__name__, reason=str(error))
                        raise
        finally:
            entry.update(completedAt=time.monotonic(), commandEndIndex=len(record['commands']))
