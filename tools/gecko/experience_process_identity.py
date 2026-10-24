"""Fail-closed serial PSS observations for the frozen Android 35 experiment.

AM owns attribution. A truncated argv is never an ownership credential. The
99-byte argv constraint is specific to the controlled image observed in A0;
AndroidRuntime::setArgv0 supports the byte-prefix/15-byte-comm representation,
but does not promise that capacity on arbitrary Android devices.
"""
import copy
import re
import subprocess
import time

PROTOCOL = 'android35-am-owner-pid-generation-pss-v1'
ARG_BLOCK_BYTES = 99


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_stat(raw):
    left, right = raw.find('('), raw.rfind(')')
    require(left >= 0 and right > left, 'Invalid proc stat')
    fields = raw[right + 2:].split()
    require(len(fields) >= 22, 'Truncated proc stat')
    return dict(pid=int(raw[:left].strip()), name=raw[left + 1:right], ppid=int(fields[1]),
                userTicks=int(fields[11]), systemTicks=int(fields[12]), startTicks=int(fields[19]),
                rssPages=int(fields[21]))


def one(pattern, raw, message, flags=0):
    rows = list(re.finditer(pattern, raw, flags))
    require(len(rows) == 1, message)
    return rows[0]


def package_uid(raw, package):
    rows = re.findall(r'^package:' + re.escape(package) + r' uid:(\d+)\s*$', raw, re.M)
    require(len(rows) == 1, 'Exact installed package UID is missing or ambiguous')
    return int(rows[0])


def am_processes(raw):
    """Parse the full, unfiltered ProcessList.dumpProcessesLSP APP/PERS blocks."""
    header = re.compile(r'^( +)\*(?:APP|PERS)\* UID (\d+) ProcessRecord\{([^\s{}]+) (\d+):([^/\s{}]+)/([^\s{}]+)\}\s*$', re.M)
    require(len(list(header.finditer(raw))) == len(re.findall(r'^ +\*(?:APP|PERS)\*', raw, re.M)),
            'An AM process block header is incomplete or unparsed')
    result = {}
    for h in header.finditer(raw):
        indent = len(h[1]); body = []
        for line in raw[h.end():].splitlines():
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                break
            body.append(line)
        text = '\n'.join(body)
        user = one(r'^\s+user #(\d+) uid=(\d+)(?: ISOLATED uid=(\d+))? gids=\{[^{}]*\}\s*$', text,
                   'AM hosting UID record missing or ambiguous', re.M)
        packages = one(r'^\s+packageList=\{([^{}]*)\}\s*$', text,
                       'AM hosting packageList missing or ambiguous', re.M)
        pid = int(h[4]); runtime_uid = int(h[2]); owner_uid = int(user[2])
        require(int(one(r'^\s+pid=(\d+)\s*$', text, 'AM PID missing or ambiguous', re.M)[1]) == pid,
                'AM header/body PID differs')
        require((int(user[3]) == runtime_uid if user[3] is not None else owner_uid == runtime_uid),
                'AM owner/runtime UID fields differ')
        start = int(one(r'^\s+startSeq=(\d+)\s*$', text, 'AM startSeq missing or ambiguous', re.M)[1])
        key = pid if pid else ('unstarted', h[3])
        require(pid >= 0 and start >= 0 and key not in result, 'AM duplicate PID or invalid generation')
        names = [name.strip() for name in packages[1].split(',') if name.strip()]
        require(names and len(names) == len(set(names)), 'AM packageList empty or duplicated')
        result[key] = dict(pid=pid, process=h[5], recordToken=h[3], runtimeUid=runtime_uid,
                           ownerUid=owner_uid, userId=int(user[1]), isolated=user[3] is not None,
                           packages=sorted(names), startSeq=start)
    require(bool(result), 'No complete ActivityManager process blocks')
    return result


def owned(am, package, uid):
    result = {pid: row for pid, row in am.items() if package in row['packages']}
    require(bool(result), 'No ActivityManager process owns the exact target package')
    for row in result.values():
        require(row['pid'] > 0 and row['startSeq'] > 0, 'Owned AM process has not started')
        require(row['packages'] == [package] and row['ownerUid'] == uid,
                'AM hosting package/owner UID is not exclusively the installed target')
        require(row['userId'] == uid // 100000, 'AM hosting user differs from installed target')
        require(row['process'] == package or row['process'].startswith(package + ':'),
                'AM target process is outside the frozen target namespace')
    require(sum(row['process'] == package for row in result.values()) == 1,
            'Exactly one AM target main process is required')
    return result


def ps_processes(raw, package):
    rows = {}
    for line in raw.splitlines()[1:]:
        fields = line.split(None, 3)
        require(len(fields) == 4, 'Malformed original ps process row')
        pid, ppid, uid = (int(value) for value in fields[:3])
        require(pid not in rows, 'Duplicate ps PID')
        rows[pid] = dict(pid=pid, ppid=ppid, uid=uid, process=fields[3])
    selected = {pid for pid, row in rows.items()
                if row['process'] == package or row['process'].startswith(package + ':')}
    for _ in rows:
        descendants = {pid for pid, row in rows.items() if row['ppid'] in selected}
        if descendants <= selected:
            break
        selected |= descendants
    return {pid: rows[pid] for pid in selected}


def proc_status(raw, pid):
    actual_pid = int(one(r'^Pid:\s*(\d+)\s*$', raw, 'Missing proc status PID', re.M)[1])
    tgid = int(one(r'^Tgid:\s*(\d+)\s*$', raw, 'Missing proc status TGID', re.M)[1])
    parent = int(one(r'^PPid:\s*(\d+)\s*$', raw, 'Missing proc status parent', re.M)[1])
    uids = tuple(int(value) for value in one(r'^Uid:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', raw,
                                           'Missing proc status UID credentials', re.M).groups())
    require(actual_pid == tgid == pid, 'Proc status PID/TGID differs')
    return dict(pid=pid, ppid=parent, uids=uids)


def argv_identity(raw_hex, full_name, comm, *, main=False):
    raw = bytes.fromhex(raw_hex); full = full_name.encode('utf-8')
    require(len(raw) == ARG_BLOCK_BYTES and raw[-1:] == b'\0',
            'Controlled Android35 argv block capacity/termination differs')
    if len(full) < ARG_BLOCK_BYTES:
        require(raw == full + b'\0' * (ARG_BLOCK_BYTES - len(full)),
                'Exact proc cmdline differs from complete AM process name')
        return 'exact-full-name-and-zero-padding'
    require(not main and full_name.isascii(), 'Unexpected truncated main/non-ASCII process name')
    require(raw == full[:ARG_BLOCK_BYTES - 1] + b'\0' and comm.encode() == full[-15:],
            'Truncated argv/15-byte comm does not match complete AM-owned process')
    return 'controlled-99-byte-argv-and-exact-15-byte-comm-with-AM-owner-proof'


def evaluate(raw, package, parse_stat, parse_pss):
    """Recompute solely from retained original raw; never repair an old snapshot."""
    rows = []
    try:
        require(raw.get('protocol') == PROTOCOL, 'PSS protocol missing or different')
        before, after = raw['before'], raw['after']
        uid = package_uid(before['packageUidRaw'], package)
        require(package_uid(after['packageUidRaw'], package) == uid, 'Installed package UID changed')
        am_before = owned(am_processes(before['amRaw']), package, uid)
        am_after = owned(am_processes(after['amRaw']), package, uid)
        require(am_before == am_after, 'AM process set/owner/generation changed during serial PSS observation')
        ps_before, ps_after = ps_processes(before['psRaw'], package), ps_processes(after['psRaw'], package)
        require(set(ps_before) == set(ps_after) == set(am_before),
                'Process-family coverage differs or descendant lacks complete AM owner proof')
        observations = raw['processes']
        require([r['pid'] for r in observations] == sorted(am_before), 'PSS PID coverage missing/reordered/duplicated')
        main_checked = False
        for observation in observations:
            pid = observation['pid']; am = am_before[pid]
            require(not observation.get('error'), 'Original PID observation failed: ' + str(observation.get('error')))
            first, last = parse_stat(observation['rawStatBefore']), parse_stat(observation['rawStatAfter'])
            first_status = proc_status(observation['rawStatusBefore'], pid)
            last_status = proc_status(observation['rawStatusAfter'], pid)
            require(first['pid'] == last['pid'] == pid and first['startTicks'] == last['startTicks']
                    and first['name'] == last['name'] and first['startTicks'] > 0,
                    'Proc PID/startTicks/comm generation changed around PSS')
            require(first['ppid'] == last['ppid'] == first_status['ppid'] == last_status['ppid']
                    == ps_before[pid]['ppid'] == ps_after[pid]['ppid'], 'Proc/ps parent changed around PSS')
            require(first_status['uids'] == last_status['uids'] == (am['runtimeUid'],) * 4
                    and ps_before[pid]['uid'] == ps_after[pid]['uid'] == am['runtimeUid'],
                    'AM/proc/ps runtime UID differs around PSS')
            require(last['userTicks'] >= first['userTicks'] and last['systemTicks'] >= first['systemTicks'],
                    'Proc CPU counters decreased around PSS')
            main = am['process'] == package
            before_mode = argv_identity(observation['rawCmdlineBeforeHex'], am['process'], first['name'], main=main)
            after_mode = argv_identity(observation['rawCmdlineAfterHex'], am['process'], last['name'], main=main)
            require(before_mode == after_mode and observation['rawCmdlineBeforeHex'] == observation['rawCmdlineAfterHex'],
                    'Proc argv changed around PSS')
            main_checked |= main
            value = parse_pss(observation['rawMeminfo'], pid)
            require(value['observedProcess'] == am['process'], 'PSS full process name differs from AM owner proof')
            rows.append(dict(value, pid=pid, process=am['process'], startTicks=first['startTicks'],
                             runtimeUid=am['runtimeUid'], ownerUid=am['ownerUid'], amRecordToken=am['recordToken'],
                             amStartSeq=am['startSeq'], packages=am['packages'], argvIdentity=before_mode))
        require(main_checked, 'Main argv capacity was not observed in this snapshot')
        return dict(available=True, totalPssKb=sum(row['pssKb'] for row in rows), processes=rows,
                    protocol=PROTOCOL, observedArgBlockBytes=ARG_BLOCK_BYTES,
                    scope='Serial actual dumpsys values; complete AM-owned target process set stable before/after, each PID/status/argv/startTicks bracketed. Not atomic, not peak memory; births and exits between observations can still be missed.')
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        return dict(available=False, totalPssKb=None, processes=rows, protocol=PROTOCOL,
                    error=type(error).__name__ + ': ' + str(error),
                    scope='Unavailable total retained; partial rows are not a complete total or zero.')


def collect(adb, package, parse_stat, parse_pss):
    """Keep each actual raw read, including all partial/failed observations."""
    raw = dict(protocol=PROTOCOL, before={}, after={}, processes=[])
    started = time.monotonic()
    def read_global(where):
        for key, command in (('packageUidRaw', ('shell', 'cmd', 'package', 'list', 'packages', '-U', package)),
                             ('amRaw', ('shell', 'dumpsys', 'activity', 'processes')),
                             ('psRaw', ('shell', 'ps', '-A', '-o', 'PID,PPID,UID,NAME'))):
            raw[where][key] = adb(*command)
    try:
        read_global('before')
        uid = package_uid(raw['before']['packageUidRaw'], package)
        records = owned(am_processes(raw['before']['amRaw']), package, uid)
        for pid in sorted(records):
            row = dict(pid=pid); raw['processes'].append(row)
            try:
                row['rawStatBefore'] = adb('exec-out', 'cat', '/proc/%d/stat' % pid)
                row['rawStatusBefore'] = adb('exec-out', 'cat', '/proc/%d/status' % pid)
                row['rawCmdlineBeforeHex'] = adb('exec-out', 'cat', '/proc/%d/cmdline' % pid, binary=True).hex()
                row['rawMeminfo'] = adb('shell', 'dumpsys', 'meminfo', str(pid), timeout=20)
                row['rawStatusAfter'] = adb('exec-out', 'cat', '/proc/%d/status' % pid)
                row['rawCmdlineAfterHex'] = adb('exec-out', 'cat', '/proc/%d/cmdline' % pid, binary=True).hex()
                row['rawStatAfter'] = adb('exec-out', 'cat', '/proc/%d/stat' % pid)
            except (ValueError, UnicodeError, subprocess.SubprocessError) as error:
                value = getattr(error, 'output', None)
                row.update(error=str(error), failedRaw=value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value)
    except (KeyError, TypeError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        raw['collectionError'] = str(error)
        value = getattr(error, 'output', None)
        raw['collectionErrorRaw'] = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
    finally:
        try:
            read_global('after')
        except (KeyError, TypeError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
            raw['after']['collectionError'] = str(error)
            value = getattr(error, 'output', None)
            raw['after']['failedRaw'] = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
    result = evaluate(raw, package, parse_stat, parse_pss)
    result.update(rawEvidence=raw, hostStartedMonotonic=started, hostObservedMonotonic=time.monotonic())
    return result


def verify(snapshot, package, parse_stat, parse_pss):
    actual = evaluate(snapshot['rawEvidence'], package, parse_stat, parse_pss)
    require(actual['available'], 'PSS identity/coverage did not verify: ' + actual.get('error', ''))
    for key, value in actual.items():
        require(snapshot.get(key) == value, 'PSS claimed observation differs from original raw: ' + key)
    return actual


def negative_controls(raw, package, parse_stat, parse_pss):
    """Derived copies of a newly captured valid snapshot; original is untouched."""
    require(evaluate(raw, package, parse_stat, parse_pss)['available'], 'Valid original snapshot required for raw negative controls')
    def status_uid(value):
        return re.sub(r'(?m)^Uid:\s*\d+\s+\d+\s+\d+\s+\d+\s*$', 'Uid:\t1\t1\t1\t1', value)
    mutations = {
        'other-package-with-same-prefix': lambda r: [r[side].update(amRaw=r[side]['amRaw'].replace('packageList={' + package + '}', 'packageList={' + package + '.other}')) for side in ('before', 'after')],
        'cross-UID-before': lambda r: r['processes'][0].update(rawStatusBefore=status_uid(r['processes'][0]['rawStatusBefore'])),
        'cross-UID-after': lambda r: r['processes'][0].update(rawStatusAfter=status_uid(r['processes'][0]['rawStatusAfter'])),
        'PID-reused-after': lambda r: r['processes'][0].update(rawStatAfter=_changed_start(r['processes'][0]['rawStatAfter'])),
        'process-exited-after': lambda r: r['processes'][0].update(rawStatAfter=''),
        'AM-generation-changed-after': lambda r: r['after'].update(amRaw=_changed_am_start(r['after']['amRaw'], r['processes'][0]['pid'])),
    }
    result = []
    for name, mutate in mutations.items():
        altered = copy.deepcopy(raw); mutate(altered)
        require(altered != raw, 'Negative control did not change its input: ' + name)
        observed = evaluate(altered, package, parse_stat, parse_pss)
        require(not observed['available'] and observed['totalPssKb'] is None,
                'Identity negative control was accepted: ' + name)
        result.append(dict(name=name, derivedRawEvidence=altered, observed=observed))
    return result


def _changed_start(raw):
    right = raw.rfind(')'); fields = raw[right + 2:].split()
    require(len(fields) >= 22, 'Original valid stat required')
    fields[19] = str(int(fields[19]) + 1)
    return raw[:right + 2] + ' '.join(fields) + '\n'


def _changed_am_start(raw, pid):
    header = one(r'^( +)\*(?:APP|PERS)\* UID \d+ ProcessRecord\{[^\s{}]+ ' + str(pid)
                 + r':[^\s{}]+\}\s*$', raw, 'Exact target AM block required for control', re.M)
    end = len(raw)
    for match in re.finditer(r'^\S|^ {1,' + str(len(header[1])) + r'}\S', raw[header.end():], re.M):
        end = header.end() + match.start();break
    fragment = raw[header.end():end]
    match = one(r'^(\s+startSeq=)(\d+)', fragment, 'Target startSeq required for control', re.M)
    fragment = fragment[:match.start(2)] + str(int(match[2])+1) + fragment[match.end(2):]
    return raw[:header.end()] + fragment + raw[end:]
