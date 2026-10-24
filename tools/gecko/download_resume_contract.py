"""Strict synthetic Android F06 receipts; host metadata tests are not device evidence."""
import hashlib
import json
import re

CHECK_NAMES = (
    'F06 executes in an attached Android Activity and isolated profile 7',
    *(name for code in (206, 200) for name in (
        f'HTTP {code} paused task renders the real continue-download action',
        f'HTTP {code} continuation sends exact Range and validator through a real socket',
        f'HTTP {code} continuation publishes exact bytes without a duplicate task',
        f'HTTP {code} retired-partial cleanup cannot delete the published destination')),
    'Native web response renders re-download instead of continue-download',
    'Cancelling re-download preserves the exact selected partial',
    'Confirmed re-download retires only the selected app-private incomplete bytes',
    'Next SDK response creates a new task rather than guessing a retired URL binding',
    'Recreated owner waits inside the real partial lease while the old SDK writer is blocked',
    'Late continue-saving menu callback cannot replace the retiring task or its generation',
    'Old writer late bytes cannot resurrect a retired partial or publish a destination',
    'Old failure callback leaves the new task receipt and complete copy unchanged',
    'Completed private copies are not eligible for partial retirement',
    'A pending published destination blocks partial retirement',
    'Retirement refuses paths outside the app-private partial directory',
)
MENU_LABELS = ('继续下载', '继续下载', '重新下载', '保留副本', '重新下载', '清理旧副本并重新下载', '关闭')
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, expected=None):
    require(type(value) is int and (expected is None or value == expected), 'Strict integer field required')


def sha(values):
    return hashlib.sha256(bytes(values)).hexdigest()


def same(left, right):
    return json.dumps(left,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(right,sort_keys=True,separators=(',',':'),allow_nan=False)


def verify_download_resume(report, identity=None, expected_source=None):
    try:
        integer(report['schema'], 1)
        require(report['status'] == 'passed' and not any(key in report for key in ('error', 'cleanupError')), 'F06 execution failed')
        for key in ('actualAndroidExecution', 'actualDialogPerformClick', 'ownedCleanupCompleted'):
            require(report[key] is True, 'Missing Android file lifecycle evidence: ' + key)
        require(report['actualAdbTouchExecution'] is False, 'Synthetic dialog clicks cannot claim ADB input')
        integer(report['processSlot'], 7)
        integer(report['filePrepareCallbacks'], 2)
        require(re.fullmatch('[0-9a-f]{32}', report['runNonce']) is not None, 'Missing owned invocation nonce')
        build = report['buildIdentity']
        for key, count in (('sourceCommit', 40), ('sourceTree', 40), ('apkSha256', 64), ('buildStampSha256', 64)):
            require(re.fullmatch('[0-9a-f]{%d}' % count, build[key]) is not None, 'Missing build identity: ' + key)
            if identity is not None:
                require(build[key] == identity[key], 'Different Android source/APK: ' + key)
        if expected_source is not None:
            require(build['sourceCommit'] == expected_source, 'F06 source differs from release evidence')
        integer(build['versionCode'])
        require(build['versionCode'] >= 71 and re.fullmatch(r'[0-9]+[.][0-9]+[.][0-9]+', build['version']) is not None, 'F06 requires an applicable source version')
        integer(report['checkCount'], len(CHECK_NAMES))
        require(type(report['checks']) is list and len(report['checks']) == len(CHECK_NAMES), 'Incomplete F06 cases')
        for actual, name in zip(report['checks'], CHECK_NAMES):
            require(actual['name'] == name and actual['pass'] is True, 'Missing/changed/failed F06 check: ' + name)
        require(type(report['menus']) is list and len(report['menus']) == len(MENU_LABELS), 'Missing actual dialog callbacks')
        for actual, label in zip(report['menus'], MENU_LABELS):
            require(actual['label'] == label and actual['performClick'] is True, 'Dialog callback differs from the controlled sequence')
        require(type(report['http']) is list and len(report['http']) == 2, 'Both HTTP response paths are required')
        cookies=report['syntheticCookieReads']
        require(type(cookies) is list and len(cookies)==2, 'Both owned synthetic empty-Cookie callbacks are required')
        for cookie,http_case in zip(cookies,report['http']):
            require(type(cookie) is dict and set(cookie)=={'runNonce','processSlot','taskId','url','ticket','emptyCookie','realCookieBridge'}, 'Unexpected synthetic Cookie evidence shape')
            require(cookie['runNonce']==report['runNonce'] and cookie['taskId']==http_case['taskIdBefore'] and cookie['url']==http_case['mappedFrom'], 'Synthetic Cookie callback owner differs')
            integer(cookie['processSlot'],7);integer(cookie['ticket'])
            require(cookie['ticket']>0 and cookie['emptyCookie'] is True and cookie['realCookieBridge'] is False, 'Synthetic empty Cookie callback cannot claim real bridge evidence')
        task_ids = []
        for row, code in zip(report['http'], (206, 200)):
            integer(row['code'], code)
            require(re.fullmatch(r'https://download-fixture[.]example/' + UUID + r'[.]bin', row['mappedFrom']) is not None, 'Unowned synthetic HTTPS mapping')
            require(re.fullmatch(r'http://127[.]0[.]0[.]1:([0-9]{1,5})/owned[.]bin', row['mappedTo']) is not None, 'Mapping left loopback')
            port = int(row['mappedTo'].split(':')[2].split('/')[0])
            require(0 < port < 65536, 'Invalid loopback port')
            require(row['request'] == 'GET /owned.bin HTTP/1.1' and row['method'] == 'GET', 'Wrong actual HTTP request')
            require(row['range'] == 'bytes=4-' and row['ifRange'] == '"f06-v1"', 'Range/validator not sent')
            expected = [1, 2, 3, 4, 5, 6, 7, 8, 9] if code == 206 else [5, 6, 7, 8, 9]
            integer(row['responseBytes'], 5)
            integer(row['expectedBytes'], len(expected))
            integer(row['savedBytes'], len(expected))
            for key in ('expectedSha256', 'savedSha256', 'afterRetireSha256'):
                require(row[key] == sha(expected), 'Published bytes were lost/duplicated/changed: ' + key)
            require(re.fullmatch(UUID, row['taskIdBefore']) is not None and row['taskIdBefore'] == row['taskIdAfter'], 'Continuation created a new task')
            task_ids.append(row['taskIdBefore'])
            require(row['state'] == 'saved' and row['uri'].startswith('content://media/') and row['sourcePartialExists'] is False and row['indexedAfterRetire'] is True, 'Publication was not preserved')
        require(len(set(task_ids)) == 2, 'HTTP cases reuse one task receipt')
        retired = report['retirement']
        require(all(re.fullmatch(UUID, retired[key]) is not None for key in ('oldTaskId', 'newTaskId')) and retired['oldTaskId'] != retired['newTaskId'], 'Next response was guessed into the old task')
        require(retired['selectedAbsent'] is True and retired['otherBytesSha256'] == sha([21, 22]), 'Unrelated partial changed')
        require(retired['oldState'] == 'cancelled' and retired['oldUri'] == retired['retiredMarker'] == '' and retired['nextState'] == 'saved', 'Retirement did not finish before the next task')
        writer = report['writer']
        for key in ('taskId', 'generation'):
            require(re.fullmatch(UUID, writer[key]) is not None, 'Missing writer ownership: ' + key)
        require(writer['generationAfterLateMenu'] == writer['generation'] and writer['taskIdAfterLateMenu'] == writer['taskId'], 'Late menu replaced ownership')
        integer(writer['oldTicket']);integer(writer['oldTicketAfterDestroy'])
        require(writer['oldTicket'] > 0 and writer['oldTicketAfterDestroy'] == writer['oldTicket'] + 1, 'Old writer was not invalidated')
        for key in ('waitedInsideLease', 'lateBytesReturned', 'lateCallbackUnchanged', 'lateMenuPerformClick'):
            require(writer[key] is True, 'Writer race did not execute: ' + key)
        require(type(writer['workerStack']) is list and all(type(frame) is str for frame in writer['workerStack']), 'Missing real waiting stack')
        require(any('local.pocketchat.SealedFileIo.lease(' in frame for frame in writer['workerStack']) and any('java.util.concurrent.locks.ReentrantLock.lockInterruptibly(' in frame for frame in writer['workerStack']), 'Cleanup never waited on the actual file lease')
        require(writer['beforeBytesSha256'] == sha([7, 7, 7, 7]) and writer['completeCopySha256'] == sha([41, 42, 43]), 'Writer or complete-copy bytes changed')
        require(writer['partialExistsAfter'] is False and writer['retiringAfter'] is False and writer['uriAfter'] == writer['retiredMarkerAfter'] == '', 'Old writer revived partial/publication or cleanup remained pending')
        return dict(checks=len(CHECK_NAMES), httpCases=2, dialogCallbacks=len(MENU_LABELS), actualAndroidExecution=True)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Incomplete Android F06 receipt: ' + str(error)) from error


def verify_download_resume_invocation(device, source):
    """Recheck original complete bytes at release time, not just the copied summary."""
    if __package__:
        from .integration_event_contract import decode_event
    else:
        from integration_event_contract import decode_event
    try:
        transport=device['eventTransport'];integer(transport['schema'],1)
        identity=transport['buildIdentity'];require(identity['sourceCommit']==source,'F06 installed source differs')
        value=device['savedFileDeletion']['downloadResume']
        summary=verify_download_resume(value,identity,source)
        require(same(value['buildIdentity'],identity),'F06 nested installed identity differs')
        invocations=transport['invocations'];require(type(invocations) is list and all(type(row) is dict for row in invocations),'F06 invocation list missing')
        owned=[row for row in invocations if row.get('fixtureAction')=='downloadResume']
        nonce=[row for row in invocations if row.get('runNonce')==value['runNonce']]
        require(len(owned)==len(nonce)==1 and owned==nonce,'F06 invocation nonce is missing/duplicated/foreign')
        invocation=owned[0];integer(invocation['processSlot'],7)
        records=invocation['events'];require(type(records) is list and len(records)==1,'F06 complete terminal event must be unique')
        record=records[0];receipt=record['receipt'];integer(receipt['sequence'],1)
        require(type(record['rawUtf8']) is str,'F06 original raw UTF-8 missing')
        event=decode_event(receipt,record['rawUtf8'].encode('utf-8'),identity=identity,
                           nonce=value['runNonce'],slot=7,action='downloadResume',command=1)
        require(event['kind']=='downloadResume' and same(event['result'],value),'F06 summary differs from original complete event')
        steps=device['steps'];require(type(steps) is list,'F06 raw step list missing')
        completed=[row for row in steps if type(row) is dict and row.get('kind')=='downloadResume']
        require(same(completed,[event]),'F06 original step missing/duplicated/changed')
        return summary
    except (KeyError,TypeError,AttributeError) as error:
        raise ValueError('Incomplete F06 original event binding: '+str(error)) from error
