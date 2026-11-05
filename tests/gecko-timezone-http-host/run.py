#!/usr/bin/env python3
"""Execute actual GeckoWebView HTTP wait/gate methods at declared JVM boundaries.

No Android or org.mozilla SDK replacements are compiled. This suite verifies
queue/callback behavior, not native timezone implementation or network security.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
sys.path.insert(0, str(ROOT / 'tests/gecko-navigation-host'))
from run import member_at

MEMBERS = (
    'static final class TimeZoneGate',
    'boolean timeZoneSessionAlive(',
    'boolean timeZoneAllows(',
    'void finishTimeZone(',
    'void releaseIpRoute(',
    'void completeTimeZoneRequests(',
    'void completeTimeZoneProofs(',
    'boolean waitForDocumentTimeZone(',
    'GeckoResult<Object> guardedRoute(',
    'GeckoResult<Object> guardedRequestHeaderPolicy(',
)
WAIT = 'boolean waitForDocumentTimeZone('
ALLOW = 'boolean timeZoneAllows('
MUTATIONS = (
    ('bootstrap-revalidation', WAIT, '||!gate.revalidating', '', 'entry', 'Only committed native revalidation holds HTTP: bootstrap'),
    ('current-surface', WAIT, 'current==session&&', '', 'fence:current', 'Held HTTP denies changed fence before either helper: current'),
    ('gate-object', WAIT, 'timeZoneGates.get(session)==gate&&', '', 'fence:gate', 'Held HTTP denies changed fence before either helper: gate'),
    ('document-serial', WAIT, 'gate.documentSerial==document&&', '', 'fence:document', 'Held HTTP denies changed fence before either helper: document'),
    ('native-port', WAIT, '&&routePort==port', '', 'fence:port', 'Held HTTP denies changed fence before either helper: port'),
    ('navigation-epoch', WAIT, '&&owner.navigationEpoch==navigation', '', 'fence:navigation', 'Held HTTP denies changed fence before either helper: navigation'),
    ('connection-epoch', WAIT, '&&owner.connectionEpoch==connection', '', 'fence:connection', 'Held HTTP denies changed fence before either helper: connection'),
    ('identity-policy', WAIT, '&&identityPolicyRevision==identity', '', 'fence:identity-policy', 'Held HTTP denies changed fence before either helper: identity-policy'),
    ('protection-token', WAIT, '&&nativeProtection.token()==protection', '', 'fence:protection', 'Held HTTP denies changed fence before either helper: protection'),
    ('desired-revision', WAIT, '&&owner.timeZone.status().optLong("desiredRevision",-1)==desired', '', 'fence:desired-revision', 'Held HTTP denies changed fence before either helper: desired-revision'),
    ('gate-ready', ALLOW, 'gate.ready&&', '', 'fence:gate-readiness', 'Held HTTP denies changed fence before either helper: gate-readiness'),
    ('controller-open-epoch', ALLOW, '&&owner.timeZone.allowed(session,gate.epoch)', '', 'fence:controller-open-epoch', 'Held HTTP denies changed fence before either helper: controller-open-epoch'),
    ('queue-cap', WAIT, 'gate.networkWaiting.size()>=128', 'gate.networkWaiting.size()>=129', 'cap', 'The 129th HTTP waiter is denied without growing the 128-entry queue'),
    ('timeout-cleanup', WAIT, 'gate.networkWaiting.remove(finished[0]);', '', 'timeout', 'At four seconds timed-out HTTP waiters are removed and denied once'),
    ('once-only', WAIT, 'if(!once.compareAndSet(false,true))return;', '', 'race', 'HTTP completion and a dequeued timeout resolve only once: true'),
    ('route-helper-recheck', 'GeckoResult<Object> guardedRoute(', 'ready?route(target):blocked()', 'ready?J.obj("allowed",true):blocked()', 'helpers', 'Successful release reruns current target and application helpers: target'),
    ('private-proof-before-http', 'void finishTimeZone(', 'completeTimeZoneProofs(gate,gate.ready);completeTimeZoneRequests(gate,gate.ready);', 'completeTimeZoneRequests(gate,gate.ready);completeTimeZoneProofs(gate,gate.ready);', 'proof-order', 'Private document proof callbacks run before public HTTP helpers'),
    ('ip-lease-close', 'void releaseIpRoute(', 'lease.close();', ';', 'ip-lease', 'Actual IP lease release closes its real registry handle'),
    ('ip-lease-remove', 'void releaseIpRoute(', 'ipRouteLeases.remove(gate)', 'ipRouteLeases.get(gate)', 'ip-lease', 'Actual IP lease release removes its exact gate entry'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(source, needle):
    if source.count(needle) != 1:
        raise ValueError('Unique complete production declaration required: ' + needle)
    return member_at(source, source.index(needle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='JSON receipt, with adjacent source and command logs')
    args = parser.parse_args()

    def tool(name):
        selected = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not selected:
            parser.error('Provide --java-home containing ' + name)
        return selected

    source = PROD / 'GeckoWebView.java'
    files = [source, PROD / 'J.java', PROD / 'ChromiumRouteLease.java', HERE / 'HttpWaitHost.java.in', Path(__file__).resolve(), ROOT / 'tests/gecko-navigation-host/run.py']
    contents = {path: path.read_bytes() for path in files}
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(value).hexdigest() for path, value in contents.items()}
    jar_hash = digest(args.json_jar)
    source_text = contents[source].decode('utf-8')
    selected = {name: declaration(source_text, name) for name in MEMBERS}
    fields = [line.strip() for line in source_text.splitlines() if line.strip().startswith('final Map<TimeZoneGate,ChromiumRouteLease.Handle> ipRouteLeases=')]
    if len(fields) != 1 or not fields[0].endswith(';'):
        raise ValueError('Unique complete actual IP lease map field required')
    template = contents[HERE / 'HttpWaitHost.java.in'].decode('utf-8')
    substitutions = [('WebExtension.Port', 'PortBoundary'), ('GeckoSession', 'SessionBoundary'), ('GeckoResult', 'ResultBoundary')]

    def generate(members):
        body = '\n'.join(members.values())
        for before, after in substitutions:
            body = body.replace(before, after)
        return template.replace('@METHODS@', body).replace('@IP_ROUTE_FIELDS@', fields[0])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    controls = []
    with tempfile.TemporaryDirectory(prefix='gecko-timezone-http-') as temporary:
        work = Path(temporary)

        def compile_host(members, label):
            out = artifacts / label
            out.mkdir(exist_ok=True)
            host = out / 'HttpWaitHost.java'
            host.write_text(generate(members))
            classes = work / label
            command = [tool('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()), '-d', str(classes), str(host), str(PROD / 'J.java'), str(PROD / 'ChromiumRouteLease.java')]
            run = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (out / 'compile.command.json').write_text(json.dumps(command) + '\n')
            (out / 'compile.stdout.log').write_text(run.stdout)
            (out / 'compile.stderr.log').write_text(run.stderr)
            if run.returncode:
                raise RuntimeError('Actual-method host compile failed: ' + label + '\n' + run.stderr)
            return classes

        def execute(classes, label, focus=None):
            out = artifacts / label
            out.mkdir(exist_ok=True)
            command = [tool('java'), '-cp', str(classes) + os.pathsep + str(args.json_jar.resolve()), 'local.pocketchat.HttpWaitHost'] + ([focus] if focus else [])
            run = subprocess.run(command, capture_output=True, text=True, timeout=30)
            (out / 'run.command.json').write_text(json.dumps(command) + '\n')
            (out / 'run.stdout.log').write_text(run.stdout)
            (out / 'run.stderr.log').write_text(run.stderr)
            return run

        classes = compile_host(selected, 'current')
        current = execute(classes, 'current')
        if current.returncode:
            raise AssertionError('Actual production workload failed:\n' + current.stdout + current.stderr)
        workload = json.loads(current.stdout)
        if workload.get('status') != 'passed' or not workload.get('checks') or workload['passed'] != workload['total'] or not all(row['pass'] is True for row in workload['checks']):
            raise AssertionError('Incomplete actual-method workload')
        for case, member, before, after, focus, assertion in MUTATIONS:
            pristine = execute(classes, 'pristine-' + case, focus)
            if pristine.returncode or json.loads(pristine.stdout)['status'] != 'passed':
                raise AssertionError('Pristine focused assertion failed: ' + case + pristine.stderr)
            if selected[member].count(before) != 1:
                raise ValueError('Exact one-hunk mutation anchor changed: ' + case)
            changed = dict(selected)
            changed[member] = changed[member].replace(before, after, 1)
            mutant_classes = compile_host(changed, 'mutation-' + case)
            mutant = execute(mutant_classes, 'mutation-' + case, focus)
            if mutant.returncode == 0 or 'AssertionError: ' + assertion not in mutant.stderr:
                raise AssertionError('Focused assertion did not reject its intended missing fence: ' + case + '\n' + mutant.stderr)
            controls.append(dict(case=case,productionMember=member,before=before,after=after,focus=focus,expectedAssertion=assertion,pristinePassed=True,mutantRejected=True,mutantExitCode=mutant.returncode))

    changed_inputs = [name for name, value in hashes.items() if digest(ROOT / name) != value]
    if digest(args.json_jar) != jar_hash:
        changed_inputs.append(str(args.json_jar))
    report = dict(schema=1,status='passed' if not changed_inputs else 'failed',passed=workload['passed'],total=workload['total'],checks=workload['checks'],negativeControls=controls,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),files=hashes,selectedProductionMembers={name: hashlib.sha256(value.encode()).hexdigest() for name,value in selected.items()},declaredSubstitutions=substitutions,jsonJar=dict(path=str(args.json_jar.resolve()),sha256=jar_hash),javaHome=str(args.java_home.resolve()) if args.java_home else None,executionInputsUnchanged=not changed_inputs,changedInputs=changed_inputs,actualJavaIpLeaseReleaseExecution=True,actualIpTransportExecution=False,actualAndroidExecution=False,actualGeckoExecution=False,actualNetworkExecution=False,scope=workload['scope'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],passed=report['passed'],total=report['total'],negativeControls=len(controls),executionInputsUnchanged=report['executionInputsUnchanged'],output=str(args.output))))
    if changed_inputs:
        raise ValueError('Actual execution inputs changed; receipt cannot pass')


if __name__ == '__main__':
    main()
