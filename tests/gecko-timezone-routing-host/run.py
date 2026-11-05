#!/usr/bin/env python3
"""Execute actual GeckoWebView timezone/navigation methods at named JVM boundaries."""
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
    'static final class TimeZoneGate', 'static final class ProtectionRestore',
    'boolean timeZoneSessionAlive(', 'boolean timeZoneAllows(',
    'void retireTimeZone(', 'void retireTimeZones(', 'void finishTimeZone(',
    'void sendTimeZone(', 'void prepareTimeZone(', 'void loadSessionUri(',
    'Object claimTimeZoneIntent(', 'boolean hasTimeZoneIntent(', 'void clearTimeZoneIntent(',
    'public void loadUrl(', 'void restoreCheckpoint(', 'static String stateUrl(',
    'public GeckoResult<AllowOrDeny> onLoadRequest(',
    'private void resumeProtectedLoads(',
)
# Each control removes one production condition, and must fail its own behavioral
# assertion after a separately compiled pristine focused control passes.
MUTATIONS = (
    ('load-first-gate', 'public void loadUrl(', 'if(!timeZoneAllows(current)){', 'if(false){', 'First navigation waits for the SDK window barrier'),
    ('restore-first-gate', 'void restoreCheckpoint(', 'if(!timeZoneAllows(target)){', 'if(false){', 'Checkpoint restoration waits for the SDK window barrier'),
    ('navigation-first-gate', 'public GeckoResult<AllowOrDeny> onLoadRequest(', '&&!timeZoneAllows(s)', '&&false', 'First browser navigation is denied while its timezone is pending'),
    ('ready-gate', 'boolean timeZoneAllows(', 'gate.ready&&', '', 'A controller permission alone cannot bypass the unfinished UI gate'),
    ('controller-gate', 'boolean timeZoneAllows(', '&&owner.timeZone.allowed(session,gate.epoch)', '', 'Ready UI gate still requires exact controller session and epoch permission'),
    ('retired-gate', 'void finishTimeZone(', 'if(timeZoneGates.get(session)!=gate)return;', '', 'A retired gate callback cannot finish or notify its replacement'),
    ('window-port', 'void prepareTimeZone(', '||routePort!=port', '', 'Changed native port cannot enter controller preparation'),
    ('window-session', 'void prepareTimeZone(', '!timeZoneSessionAlive(session)||', '', 'Closed native session cannot enter controller preparation'),
    ('navigation-epoch', 'void loadSessionUri(', 'navigation==owner.navigationEpoch&&', '', 'A queued URI cannot load after its navigation epoch changes'),
    ('restore-epoch', 'void restoreCheckpoint(', '&&navigation==owner.navigationEpoch', '', 'A checkpoint cannot restore after its navigation epoch changes'),
    ('restore-current', 'void restoreCheckpoint(', '&&current==target', '', 'A checkpoint cannot restore into a replaced current surface'),
    ('after-worker-gate', 'void restoreCheckpoint(', 'if(!timeZoneAllows(target)){prepareTimeZone(target,', 'if(false){prepareTimeZone(target,', 'Writer completion rechecks timezone permission before restoring SDK state'),
    ('send-port', 'void sendTimeZone(', '||routePort!=port', '', 'A changed port is rejected before posting a native timezone request'),
    ('reply-port', 'void sendTimeZone(', '||routePort!=port||value==null', '||value==null', 'A reply on a retired port cannot complete native timezone access'),
    ('explicit-native-queue', 'public GeckoResult<AllowOrDeny> onLoadRequest(', 'if(!hasTimeZoneIntent(s))loadSessionUri(s,request.uri);', 'loadSessionUri(s,request.uri);', 'Explicit load intent prevents a second native reload queue'),
    ('claim-clears-native-queue', 'Object claimTimeZoneIntent(', 'timeZoneLoads.remove(session);', '', 'An explicit target supersedes an already deferred native reload'),
    ('restore-clears-main-queue', 'Object claimTimeZoneIntent(', 'if(restore&&session==current)queued="";', '', 'A restored checkpoint cannot revive the earlier main URL on protection retry'),
    ('worker-intent-owner', 'void restoreCheckpoint(', 'timeZoneIntents.get(target)!=intent||', '', 'A superseded writer cannot restore its checkpoint after a newer explicit load'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(source, needle):
    if source.count(needle) != 1:
        raise ValueError('Unique actual production declaration required: ' + needle)
    return member_at(source, source.index(needle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    def java(name):
        selected = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not selected:
            parser.error('Provide --java-home containing ' + name)
        return selected

    source = PROD / 'GeckoWebView.java'
    identity = ROOT / 'app/src/main/java/org/mozilla/geckoview/PocketSessionIdentity.java'
    complete = [PROD / name for name in ('J.java', 'BrowserBridgeRequests.java', 'BrowserRuntimePolicy.java', 'BrowserAddressPolicy.java', 'GeckoNavigationPolicy.java')]
    files = [source, identity, HERE / 'RoutingHost.java.in', Path(__file__).resolve(), ROOT / 'tests/gecko-navigation-host/run.py'] + complete
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in files}
    jar_hash = digest(args.json_jar)
    text = source.read_text()
    selected = {name: declaration(text, name) for name in MEMBERS}
    identity_body = declaration(identity.read_text(), 'public static String id(')
    template = (HERE / 'RoutingHost.java.in').read_text()
    replacements = (
        ('WebExtension.Port', 'PortBoundary'),
        ('GeckoSession.SessionState', 'StateBoundary'),
        ('GeckoSession', 'SessionBoundary'),
        ('GeckoResult', 'ResultBoundary'),
        ('GeckoTimeZoneController', 'ControllerBoundary'),
        ('PocketSessionIdentity', 'IdentityBoundary'),
        ('LocalDraftPolicy', 'DraftPolicyBoundary'),
    )

    def generate(members):
        value = template.replace('@METHODS@', '\n'.join(members.values())).replace('@IDENTITY_METHOD@', identity_body)
        for before, after in replacements:
            value = value.replace(before, after)
        return value

    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    controls = []
    with tempfile.TemporaryDirectory(prefix='gecko-timezone-routing-') as temporary:
        work = Path(temporary)

        def execute(members, label, focus=None):
            out = artifacts / label
            out.mkdir(exist_ok=True)
            host = out / 'RoutingHost.java'
            host.write_text(generate(members))
            classes = work / label
            command = [java('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()), '-d', str(classes), str(host)] + [str(path) for path in complete]
            built = subprocess.run(command, text=True, capture_output=True, timeout=60)
            (out / 'compile.command.json').write_text(json.dumps(command) + '\n')
            (out / 'compile.stderr.log').write_text(built.stderr)
            if built.returncode:
                raise RuntimeError(built.stderr)
            command = [java('java'), '-cp', str(classes) + os.pathsep + str(args.json_jar.resolve()), 'local.pocketchat.RoutingHost'] + ([focus] if focus else [])
            ran = subprocess.run(command, text=True, capture_output=True, timeout=30)
            (out / 'run.command.json').write_text(json.dumps(command) + '\n')
            (out / 'run.stdout.log').write_text(ran.stdout)
            (out / 'run.stderr.log').write_text(ran.stderr)
            return ran

        ran = execute(selected, 'current')
        if ran.returncode:
            raise RuntimeError(ran.stdout + ran.stderr)
        report = json.loads(ran.stdout)
        for case, member, before, after, assertion in MUTATIONS:
            # Some conditions occur twice in a method. The chosen first hunk is
            # intentional; reply-port/after-worker-gate use longer unique hunks.
            if before not in selected[member]:
                raise ValueError('Exact mutation hunk required: ' + case)
            pristine = execute(selected, 'pristine-' + case, case)
            if pristine.returncode:
                raise AssertionError('Pristine control failed: ' + case + pristine.stderr)
            mutant_members = dict(selected)
            mutant_members[member] = selected[member].replace(before, after, 1)
            mutant = execute(mutant_members, 'mutant-' + case, case)
            if mutant.returncode == 0 or 'AssertionError: ' + assertion not in mutant.stderr:
                raise AssertionError('Precise mutation must fail: ' + case + mutant.stderr)
            controls.append(dict(case=case, pristinePassed=True, mutantRejected=True, assertion=assertion))

    unchanged = all(digest(path) == hashes[str(path.relative_to(ROOT))] for path in files) and digest(args.json_jar) == jar_hash
    report.update(sourceFiles=hashes, jsonJarSha256=jar_hash, productionMembers=MEMBERS,
                  negativeControls=controls, executionInputsUnchanged=unchanged,
                  boundaries=[
                      'SDK GeckoSession/GeckoResult/SessionState/WebExtension.Port type tokens become named Session/Result/State/PortBoundary doubles; no org.mozilla fake package',
                      'ControllerBoundary scripts prepare and allowed decisions for exact session/epoch; production controller and persistent store are separate test scopes',
                      'HandlerBoundary virtual clock and ExecutorBoundary queue expose SDK-window timeout and restoration interleavings',
                      'Guard, route lease, protection, app owner, draft policy, metadata status and serialized SDK state are explicit app/SDK boundaries',
                      'Actual BrowserBridgeRequests, PocketSessionIdentity.id method, JSON and public URL policies execute unchanged except SDK type names',
                  ], scope='Actual GeckoWebView first-load, restore, navigation-delegate and timezone-route adapter control flow. No Android/Gecko execution, native setting readback, Date/Intl effect, worker effect or wire claim.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'] if unchanged else 'source-changed', passed=report['passed'], negativeControls=len(controls), executionInputsUnchanged=unchanged, output=str(args.output))))
    if not unchanged:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
