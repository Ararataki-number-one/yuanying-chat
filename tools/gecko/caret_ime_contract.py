"""Validate recorded emulator IME isolation; never treats host controls as Android."""
import importlib.util
from pathlib import Path
import re
import shlex
import sys

_spec = importlib.util.spec_from_file_location('caret_ime_record_parser', Path(__file__).with_name('caret_ime_guard.py'))
G = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = G
_spec.loader.exec_module(G)


def require(value, message):
    if not value:
        raise ValueError('Controlled IME evidence: ' + message)


def stamp(value):
    return type(value) is int and 0 < value < 2**63


def snapshot(value):
    require(isinstance(value, dict), 'snapshot missing')
    settings = value.get('settings')
    require(isinstance(settings, dict) and set(settings) == set(G.KEYS), 'exact four secure settings required')
    require(all(isinstance(v, str) and len(v) <= 8192 and not any(c in v for c in '\r\n\0')
                for v in settings.values()), 'bounded raw secure setting values required')
    selected = G.canonical_component(settings['default_input_method'])
    enabled = list(G.enabled_entries(settings['enabled_input_methods']))
    if settings['selected_input_method_subtype'] != 'null':
        G.subtype(settings['selected_input_method_subtype'])
    G.valid_history(settings['input_methods_subtype_history'])
    actual = list(G.component_list(value.get('enabledImeListRaw')))
    registered = list(G.component_list(value.get('allImeListRaw')))
    current = G.current_method(value.get('inputMethodDumpRaw'))
    require(value.get('selectedComponent') == value.get('actualSelectedComponent') == current == selected,
            'raw selected setting/dump and recorded identities differ')
    require(value.get('enabledComponents') == enabled and value.get('actualEnabledComponents') == actual
            and value.get('registeredComponents') == registered, 'raw actual method lists differ')
    require(selected in enabled and set(enabled) == set(actual) and set(enabled) <= set(registered),
            'selected/enabled/registered state disagrees')
    return settings, selected, enabled, actual, registered


def command_snapshot(rows, value):
    """Require each snapshot to come from one complete actual seven-read group."""
    operations = [('shell','settings','--user','0','get','secure',key) for key in G.KEYS]
    operations += [('shell','ime','list','-a','-s','--user','0'),
                   ('shell','ime','list','-s','--user','0'), G.METHOD_DUMP_COMMAND]
    wanted = [value['settings'][key] for key in G.KEYS]
    wanted += [value['allImeListRaw'],value['enabledImeListRaw'],value['inputMethodDumpRaw']]
    matches = []
    for start in range(len(rows) - len(operations) + 1):
        group = rows[start:start+len(operations)]
        if [tuple(row['parts']) for row in group] != operations:
            continue
        outputs = [row['stdout'].removesuffix('\n').removesuffix('\r') for row in group[:4]]
        outputs += [row['stdout'] for row in group[4:]]
        if outputs == wanted:
            matches.append((start,start+len(operations)-1))
    return matches


def workload_commands(workloads):
    """Bind the recorded argv to the two unchanged coordinator commands."""
    ordered = [('--adb','--serial','--root','--out','--build-receipt','--sdk-receipt',
                '--sdk-aar','--official-sdk-aar','--integration-apk'),
               ('--adb','--serial','--root','--out','--sdk-receipt','--build-receipt',
                '--sdk-aar','--official-sdk-aar','--integration-apk','--release-apk')]
    values = []
    commands = []
    for index,row in enumerate(workloads):
        command = row.get('command')
        require(isinstance(command,list) and all(isinstance(x,str) and x and not any(c in x for c in '\r\n\0')
                for x in command), 'actual workload argv missing')
        offset = 2 if index == 0 else 3
        require(len(command)==offset+2*len(ordered[index])
                and tuple(command[offset::2])==ordered[index], 'exact ordered workload flags required')
        require(Path(command[0]).is_absolute() and re.fullmatch(r'python3(?:\.\d+)?',Path(command[0]).name),
                'actual Python interpreter required')
        if index == 1:
            require(command[2]=='--normal-acceptance', 'normal caret acceptance must remain enabled')
        fields = dict(zip(command[offset::2],command[offset+1::2]))
        require(fields['--serial']==G.SERIAL and Path(fields['--root']).is_absolute(), 'workload root/device differs')
        for flag,path in fields.items():
            if flag not in ('--adb','--serial'):
                require('..' not in Path(path).parts and not path.startswith('--'), 'safe workload path required')
        require(Path(fields['--out']).is_absolute(), 'owned workload output must be absolute')
        script = ('run_caret_bound_performance.py','run_gecko_caret_compat.py')[index]
        require(command[1]==str(Path(fields['--root'])/'tests/gecko'/script), 'unchanged fixture runner path required')
        values.append(fields); commands.append(command)
    require(commands[0][0]==commands[1][0] and all(values[0][key]==values[1][key]
            for key in ordered[0] if key!='--out'), 'both workloads must share interpreter/source/SDK/build/APK')
    require(values[1]['--out']==str(Path(values[0]['--out'])/'caret-compat'), 'controlled fixture must use owned child output')


def verify_ime_environment(value, phase, *, identity, nonce, raw_sha256):
    require(isinstance(raw_sha256,str) and re.fullmatch('[0-9a-f]{64}',raw_sha256), 'actual raw guard SHA-256 required')
    require(type(value.get('schema')) is int and value['schema'] == 1 and value.get('status') == 'passed', 'completed successful guard required')
    require(value.get('identity') == identity and all(value.get(k) == v for k,v in identity.items()), 'source/tree/run/attempt/APK/SDK binding differs')
    require(value.get('runNonce') == nonce and isinstance(nonce,str) and re.fullmatch('[0-9a-f]{32}',nonce), 'actual fixture nonce differs')
    require(value.get('serial') == G.SERIAL and type(value.get('user')) is int and value['user'] == 0
            and value.get('exactFixtureComponent') == G.COMPONENT, 'exact device/user/component required')
    require(value.get('confirmedQemu') is True and value.get('confirmedUser0') is True
            and type(value.get('confirmedAndroidSdk')) is int and value['confirmedAndroidSdk'] == 35, 'actual fixed emulator preflight missing')
    require(value.get('mutationAttempted') is True and value.get('restorationVerified') is True
            and type(value.get('workloadInvocationCount')) is int and value['workloadInvocationCount'] == 1
            and type(value.get('workloadExitCode')) is int and value['workloadExitCode'] == 0
            and value.get('workloadStatus') == 'passed', 'once-only workload or exact restoration failed')
    for key in ('fatal','error','restoreError','failureStage'):
        require(not value.get(key), 'failure marker ' + key)
    require(all(value.get(key) is False for key in ('applicationAcceptance','physicalPhoneAcceptance','vendorKeyboardUiAcceptance')),
            'environment isolation cannot claim phone/vendor/application acceptance')
    initial = snapshot(value.get('initial')); during = snapshot(value.get('during')); restored = snapshot(value.get('restored'))
    require(initial == restored, 'exact raw settings or actual methods not restored')
    require(initial[1] != G.COMPONENT and G.COMPONENT in initial[4], 'stock original and installed fixture required')
    expected = initial[0]['enabled_input_methods']
    if G.COMPONENT not in initial[2]:
        expected += ':' + G.COMPONENT
    require(during[0]['enabled_input_methods'] == expected and during[1] == G.COMPONENT
            and during[4] == initial[4], 'only the owned fixture may be enabled/selected')
    names = ('prepareStartedAtMonotonicNanos','preparedAtMonotonicNanos','workloadStartedAtMonotonicNanos',
             'workloadCompletedAtMonotonicNanos','restoreStartedAtMonotonicNanos','restoredAtMonotonicNanos')
    times = [value.get(key) for key in names]
    require(all(stamp(x) for x in times) and times == sorted(times), 'six actual phases must be ordered')
    rows = value.get('commands')
    require(isinstance(rows,list) and 0 < len(rows) <= 100, 'bounded actual command ledger required')
    previous = times[0]
    for row in rows:
        require(isinstance(row,dict) and row.get('status') == 'passed' and isinstance(row.get('stdout'),str)
                and len(row['stdout']) <= 131072 and stamp(row.get('startedAtMonotonicNanos'))
                and stamp(row.get('completedAtMonotonicNanos'))
                and previous <= row['startedAtMonotonicNanos'] <= row['completedAtMonotonicNanos'] <= times[-1], 'actual command timing/result differs')
        previous = row['completedAtMonotonicNanos']
        parts = row.get('parts')
        require(isinstance(parts,list) and parts and all(isinstance(x,str) and len(x)<=8192 for x in parts), 'actual command argument vector missing')
    require([row['parts'] for row in rows[:3]] == [
        ['shell','getprop','ro.kernel.qemu'], ['shell','am','get-current-user'], ['shell','getprop','ro.build.version.sdk']], 'actual emulator preflight command order differs')
    require([row['stdout'].strip() for row in rows[:3]] == ['1','0','35'], 'actual emulator preflight values differ')
    groups = [command_snapshot(rows,value[name]) for name in ('initial','during','restored')]
    valid = [(a,b,c) for a in groups[0] for b in groups[1] for c in groups[2] if a[1]<b[0] and b[1]<c[0]]
    require(len(valid)==1, 'three unique actual snapshot read groups required')
    first,middle,last = valid[0]
    require(rows[middle[1]]['completedAtMonotonicNanos'] <= times[1]
            and times[4] <= rows[last[0]]['startedAtMonotonicNanos'], 'snapshot read outside prepare/restore')
    active = value.get('activeInputMethod')
    require(isinstance(active,dict) and active.get('status')=='passed'
            and not active.get('error') and not active.get('errorType')
            and stamp(active.get('startedAtMonotonicNanos'))
            and stamp(active.get('completedAtMonotonicNanos'))
            and times[2]<=active['startedAtMonotonicNanos']<=active['completedAtMonotonicNanos']<=times[3],
            'actual end-of-protocol binding observation required within workload phase')
    observed = G.active_method(active.get('inputMethodDumpRaw'))
    require(all(active.get(key)==val for key,val in observed.items())
            and observed['selectedComponent']==observed['boundComponent']==G.COMPONENT
            and observed['haveConnection'] is True and observed['boundToMethod'] is True,
            'raw selected/bound IME identity and connection flags disagree')
    active_rows = [i for i,row in enumerate(rows) if tuple(row['parts'])==G.METHOD_DUMP_COMMAND
                   and row['stdout']==active['inputMethodDumpRaw']
                   and active['startedAtMonotonicNanos']<=row['startedAtMonotonicNanos']
                   <=row['completedAtMonotonicNanos']<=active['completedAtMonotonicNanos']]
    require(len(active_rows)==1 and middle[1]<active_rows[0]<last[0],
            'one actual critical dump must back the active binding observation')
    writes=[]
    reads = {tuple(row['parts']) for row in rows[:3]}
    reads.update(('shell','settings','--user','0','get','secure',key) for key in G.KEYS)
    reads.update((('shell','ime','list','-a','-s','--user','0'),('shell','ime','list','-s','--user','0'),G.METHOD_DUMP_COMMAND))
    for i,row in enumerate(rows):
        p=row['parts']
        if tuple(p) in reads:
            continue
        if len(p)==6 and p[:2]==['shell','ime'] and p[3:5]==['--user','0']:
            arg=shlex.split(p[5]);require(len(arg)==1,'single literal IME component required')
            component=G.canonical_component(arg[0]);operation=p[2]
            if operation in ('enable','disable'):
                require(component==G.COMPONENT and G.COMPONENT not in initial[2], 'only newly enabled fixture may be disabled/enabled')
            else:
                require(operation=='set' and component in (initial[1],G.COMPONENT), 'foreign IME mutation')
            if component==G.COMPONENT and operation!='disable':
                require(first[1]<i<middle[0] and row['completedAtMonotonicNanos']<=times[1], 'fixture selection outside prepare')
            else:
                require(times[4]<=row['startedAtMonotonicNanos'] and i<last[0], 'stock restoration outside restore')
            writes.append((operation,component))
        elif len(p) in (7,8) and p[:4]==['shell','settings','--user','0'] and p[5]=='secure':
            key=p[6];require(key in ('selected_input_method_subtype','input_methods_subtype_history') and times[4]<=row['startedAtMonotonicNanos'] and i<last[0], 'unowned setting write')
            original=initial[0][key]
            require((p[4]=='delete' and len(p)==7 and original=='null') or
                    (p[4]=='put' and len(p)==8 and shlex.split(p[7])==[original] and original!='null'), 'setting write differs from captured original')
        else:
            require(False,'unexpected environment command')
    expected_writes=[]
    if G.COMPONENT not in initial[2]:expected_writes.append(('enable',G.COMPONENT))
    expected_writes += [('set',G.COMPONENT),('set',initial[1])]
    if G.COMPONENT not in initial[2]:expected_writes.append(('disable',G.COMPONENT))
    require(writes==expected_writes, 'exact once-only component switches required')
    require(phase.get('status')=='passed' and phase.get('phaseStatus')=='passed'
            and phase.get('restorationVerified') is True and phase.get('imeRestorationVerified') is True
            and phase.get('imeEnvironmentReceiptSha256')==raw_sha256
            and phase.get('imeEnvironmentReceipt')=='caret-compat/caret-ime-environment.json', 'parent coordinator did not verify this restored receipt')
    require(all(phase.get(key)==identity[key] for key in ('sourceCommit','sourceTree','runId','runAttempt'))
            and all(phase.get('identity',{}).get(key)==v for key,v in identity.items()), 'parent invocation binding differs')
    workloads=phase.get('workloads')
    require(isinstance(workloads,list) and len(workloads)==2 and
            [x.get('name') for x in workloads]==['original-performance-wrapper','caret-compatibility'], 'both original workloads required in original order')
    workload_commands(workloads)
    require(all(type(x.get('invocationCount')) is int and x['invocationCount']==1
                and type(x.get('exitCode')) is int and x['exitCode']==0
                and stamp(x.get('startedAtMonotonicNanos')) and stamp(x.get('completedAtMonotonicNanos'))
                and x['startedAtMonotonicNanos']<=x['completedAtMonotonicNanos'] for x in workloads), 'workload replay/failure/timing')
    require(workloads[0]['completedAtMonotonicNanos']<=workloads[1]['startedAtMonotonicNanos']<=times[0]
            and times[-1]<=workloads[1]['completedAtMonotonicNanos'], 'stock performance must finish before controlled IME prepare, and restore before runner exit')
    return dict(status='passed',exactFixtureComponent=G.COMPONENT,stockInputMethod=initial[1],
                restorationVerified=True,originalStockWorkloadFirst=True,workloadInvocationCount=1,
                endOfProtocolBindingVerified=True,
                applicationAcceptance=False,physicalPhoneAcceptance=False,vendorKeyboardUiAcceptance=False)
