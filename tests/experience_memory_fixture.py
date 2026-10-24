"""Explicit synthetic parser controls, not an Android AM/device capture.

The textual AM layout follows Android15 ProcessRecord/ProcessList.dump sources.
Runtime negative controls separately derive copies of newly collected device raw.
"""
import copy
import hashlib
import json

PACKAGE = 'local.pocketchat.test'
ISOLATED = PACKAGE + ':isolatedTab_disable_art_image_0:org.mozilla.gecko.process.GeckoChildProcessServices$isolatedTab0:environment0_0123456789abcdef0123456789abcdef'


def stat(pid, name, start=900, parent=357):
    fields = ['S'] + ['0'] * 21
    fields[1], fields[11], fields[12], fields[19], fields[21] = str(parent), '123', '45', str(start), '60'
    return str(pid) + ' (' + name + ') ' + ' '.join(fields) + '\n'


def status(pid, uid):
    return 'Name:\ttest\nTgid:\t%d\nPid:\t%d\nPPid:\t357\nUid:\t%d\t%d\t%d\t%d\n' % (pid, pid, uid, uid, uid, uid)


def block(pid, name, runtime_uid, *, owner_uid=10210, packages=PACKAGE, token=None, start_seq=7):
    isolated = ' ISOLATED uid=' + str(runtime_uid) if runtime_uid != owner_uid else ''
    return ('  *APP* UID %d ProcessRecord{%s %d:%s/u0a210}\n'
            '    user #0 uid=%d%s gids={3003}\n'
            '    packageList={%s}\n'
            '    thread=android.app.IApplicationThread$Stub$Proxy@123\n'
            '    pid=%d\n'
            '    startSeq=%d\n') % (runtime_uid, token or hex(pid)[2:], pid, name, owner_uid, isolated, packages, pid, start_seq)


def raw_snapshot(protocol):
    records = [(11, PACKAGE, 10210, 'AndroidUI'), (12, ISOLATED, 99001, ISOLATED[-15:])]
    raw = dict(protocol=protocol, before={}, after={}, processes=[],
               fixtureProvenance='synthetic host parser control; AM was not captured on a device')
    global_raw = dict(packageUidRaw='package:%s.other uid:10211\npackage:%s uid:10210\n' % (PACKAGE, PACKAGE),
                      amRaw='ACTIVITY MANAGER RUNNING PROCESSES\n  All known processes:\n' + ''.join(block(pid,name,uid) for pid,name,uid,comm in records),
                      psRaw='PID PPID UID NAME\n' + ''.join('%d 357 %d %s\n' % (pid,uid,name[:98]) for pid,name,uid,comm in records))
    raw['before'] = copy.deepcopy(global_raw); raw['after'] = copy.deepcopy(global_raw)
    for pid,name,uid,comm in records:
        argv = (name.encode()[:98] + b'\0').ljust(99,b'\0')
        raw['processes'].append(dict(pid=pid, rawStatBefore=stat(pid,comm), rawStatAfter=stat(pid,comm),
                                    rawStatusBefore=status(pid,uid), rawStatusAfter=status(pid,uid),
                                    rawCmdlineBeforeHex=argv.hex(), rawCmdlineAfterHex=argv.hex(),
                                    rawMeminfo='** MEMINFO in pid %d [%s] **\n TOTAL PSS: %d TOTAL RSS: 99999\n' % (pid,name,pid*1000)))
    return raw


def snapshot(module, parse_pss):
    raw = raw_snapshot(module.PROTOCOL)
    result = module.evaluate(raw,PACKAGE,module.parse_stat,parse_pss)
    assert result['available'], result
    result['rawEvidence'] = raw
    return result


def attach_memory(module, report, directory):
    for row in report['iterations']:
        row.update(memoryReady=snapshot(module.memory_identity,module.scenarios.pss_value),
                   memoryFinal=snapshot(module.memory_identity,module.scenarios.pss_value))
    original=report['iterations'][0]['memoryReady']
    cases=module.memory_identity.negative_controls(original['rawEvidence'],PACKAGE,
        module.memory_identity.parse_stat,module.scenarios.pss_value)
    name='pss-identity-negative-controls.json'
    raw=(json.dumps(dict(schema=1,originalSnapshot=original,cases=cases),indent=2)+'\n').encode()
    (directory/name).write_bytes(raw)
    report.setdefault('rawEvidence',[]).append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    report['pssIdentityNegativeControls']=dict(path=name,count=6,afterTimedIterations=True,
        extraDeviceReads=0,originalSnapshot='iteration-01.memoryReady')
