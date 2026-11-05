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
    'void retireTimeZone(', 'void retireTimeZones(', 'void finishTimeZone(', 'void releaseIpRoute(',
    'void sendTimeZone(', 'void prepareTimeZone(', 'private void startTimeZone(',
    'void revalidateTimeZone(', 'void completeTimeZoneRequests(', 'void completeTimeZoneProofs(',
    'boolean waitForDocumentTimeZone(', 'GeckoResult<Object> guardedRoute(',
    'GeckoResult<Object> guardedRequestHeaderPolicy(', 'void loadSessionUri(',
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
    ('window-port', 'private void startTimeZone(', '&&routePort==port;', ';', 'Changed native port cannot enter controller preparation'),
    ('window-session', 'private void startTimeZone(', 'return timeZoneSessionAlive(session)&&', 'return ', 'Closed native session cannot enter controller preparation'),
    ('navigation-epoch', 'void loadSessionUri(', '(!foreground||session!=current||navigation==owner.navigationEpoch)', 'true', 'A queued URI cannot load after its navigation epoch changes'),
    ('restore-epoch', 'void restoreCheckpoint(', '&&navigation==owner.navigationEpoch', '', 'A checkpoint cannot restore after its navigation epoch changes'),
    ('restore-current', 'void restoreCheckpoint(', '&&current==target', '', 'A checkpoint cannot restore into a replaced current surface'),
    ('after-worker-gate', 'void restoreCheckpoint(', 'if(!timeZoneAllows(target)){prepareTimeZone(target,', 'if(false){prepareTimeZone(target,', 'Writer completion rechecks timezone permission before restoring SDK state'),
    ('send-port', 'void sendTimeZone(', '||routePort!=port', '', 'A changed port is rejected before posting a native timezone request'),
    ('reply-port', 'void sendTimeZone(', '||routePort!=port||value==null', '||value==null', 'A reply on a retired port cannot complete native timezone access'),
    ('explicit-native-queue', 'public GeckoResult<AllowOrDeny> onLoadRequest(', 'if(!hasTimeZoneIntent(s))loadSessionUri(s,request.uri);', 'loadSessionUri(s,request.uri);', 'Explicit load intent prevents a second native reload queue'),
    ('claim-clears-native-queue', 'Object claimTimeZoneIntent(', 'timeZoneLoads.remove(session);', '', 'An explicit target supersedes an already deferred native reload'),
    ('restore-clears-main-queue', 'Object claimTimeZoneIntent(', 'if(restore&&session==current)queued="";', '', 'A restored checkpoint cannot revive the earlier main URL on protection retry'),
    ('worker-intent-owner', 'void restoreCheckpoint(', 'timeZoneIntents.get(target)!=intent||', '', 'A superseded writer cannot restore its checkpoint after a newer explicit load'),
    ('secondary-epoch', 'void loadSessionUri(', '(!foreground||session!=current||navigation==owner.navigationEpoch)', '(navigation==owner.navigationEpoch)', 'A secondary session replays its newest target despite the primary navigation epoch advancing'),
    ('native-same-url-intent', 'void loadSessionUri(', 'nativeTimeZoneIntents.get(session)!=intent||', '', 'Old same-URL native completion cannot consume the newer exact intent'),
    ('document-serial', 'private void startTimeZone(', '&&gate.documentSerial==document)finishTimeZone', ')finishTimeZone', 'Old document callback cannot finish its newer gate'),
    ('held-route', 'GeckoResult<Object> guardedRoute(', 'if(waitForDocumentTimeZone(', 'if(false&&waitForDocumentTimeZone(', 'Committed-document route waits without invoking the inner policy'),
    ('held-header', 'GeckoResult<Object> guardedRequestHeaderPolicy(', 'if(waitForDocumentTimeZone(', 'if(false&&waitForDocumentTimeZone(', 'Committed-document header request waits without invoking the inner policy'),
    ('held-queue-cap', 'boolean waitForDocumentTimeZone(', 'if(gate.networkWaiting.size()>=128)', 'if(false)', 'Document resource queue rejects its overflow without replacing existing requests'),
    ('held-identity', 'boolean waitForDocumentTimeZone(', '&&identityPolicyRevision==identity', '', 'Held requests reject changed identity ownership'),
    ('held-desired', 'boolean waitForDocumentTimeZone(', '&&owner.timeZone.status().optLong("desiredRevision",-1)==desired', '', 'Held requests reject changed desired ownership'),
    ('proof-before-requests', 'void finishTimeZone(', 'completeTimeZoneProofs(gate,gate.ready);completeTimeZoneRequests(gate,gate.ready);', 'completeTimeZoneRequests(gate,gate.ready);completeTimeZoneProofs(gate,gate.ready);', 'Native document proofs complete before held HTTP policies are retried'),
)


LEASE_MUTATIONS = (
    ('ip-lease-close', 'void releaseIpRoute(', 'lease.close();', ';', 'Actual IP lease release closes its real registry handle'),
    ('ip-lease-remove', 'void releaseIpRoute(', 'ipRouteLeases.remove(gate)', 'ipRouteLeases.get(gate)', 'Actual IP lease release removes its exact gate entry'),
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
    identity = ROOT / 'app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java'
    complete = [PROD / name for name in ('J.java', 'BrowserBridgeRequests.java', 'BrowserRuntimePolicy.java', 'BrowserAddressPolicy.java', 'GeckoNavigationPolicy.java', 'ChromiumRouteLease.java')]
    files = [source, identity, HERE / 'RoutingHost.java.in', Path(__file__).resolve(), ROOT / 'tests/gecko-navigation-host/run.py'] + complete
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in files}
    jar_hash = digest(args.json_jar)
    text = source.read_text()
    selected = {name: declaration(text, name) for name in MEMBERS}
    fields = [line.strip() for line in text.splitlines() if line.strip().startswith('final Map<TimeZoneGate,ChromiumRouteLease.Handle> ipRouteLeases=')]
    if len(fields) != 1 or not fields[0].endswith(';'):
        raise ValueError('Unique complete actual IP route lease map field required')
    identity_body = declaration(identity.read_text(), 'public static String id(')
    template = (HERE / 'RoutingHost.java.in').read_text()
    replacements = (
        ('GeckoWebView.this', 'WebBoundary.this'),
        ('WebExtension.Port', 'PortBoundary'),
        ('GeckoSession.SessionState', 'StateBoundary'),
        ('GeckoSession', 'SessionBoundary'),
        ('GeckoResult', 'ResultBoundary'),
        ('GeckoTimeZoneController', 'ControllerBoundary'),
        ('AppSessionIdentity', 'IdentityBoundary'),
        ('LocalDraftPolicy', 'DraftPolicyBoundary'),
    )

    def generate(members):
        value = template.replace('@METHODS@', '\n'.join(members.values())).replace('@IP_ROUTE_FIELDS@', fields[0]).replace('@IDENTITY_METHOD@', identity_body)
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
        for case, member, before, after, assertion in (*MUTATIONS, *LEASE_MUTATIONS):
            # Some conditions occur twice in a method. The chosen first hunk is
            # intentional; reply-port/after-worker-gate use longer unique hunks.
            if case == 'window-port' and before not in selected[member]:
                if (before, after) != ('&&routePort==port;', ';'):
                    raise ValueError('Original port mutation contract differs')
                before, after = '&&routePort==port&&(!autoIpMode()', '&&(!autoIpMode()'
                if selected[member].count(before) != 1:
                    raise ValueError('Unique actual expanded port guard required')
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
    report.update(sourceFiles=hashes, jsonJarSha256=jar_hash, productionMembers=MEMBERS,actualJavaIpLeaseReleaseExecution=True,actualIpTransportExecution=False,
                  negativeControls=controls, executionInputsUnchanged=unchanged,
                  boundaries=[
                      'SDK GeckoSession/GeckoResult/SessionState/WebExtension.Port type tokens become named Session/Result/State/PortBoundary doubles; no org.mozilla fake package',
                      'GeckoWebView.this becomes the same enclosing WebBoundary.this; original manual-timezone cases declare no IP lookup, and unexpected IP collaborators throw instead of simulating success',
                      'The current IP lease map/release member and complete actual Java ChromiumRouteLease execute; IP route admission/lookup/native transport are not modeled',
                      'ControllerBoundary scripts prepare and allowed decisions for exact session/epoch; production controller and persistent store are separate test scopes',
                      'HandlerBoundary virtual clock and ExecutorBoundary queue expose SDK-window timeout and restoration interleavings',
                      'Guard, route lease, protection, app owner, draft policy, metadata status and serialized SDK state are explicit app/SDK boundaries',
                      'Actual BrowserBridgeRequests, AppSessionIdentity.id method, JSON and public URL policies execute unchanged except SDK type names',
                      'Addon navigation readiness is an explicit default-enabled counted dependency; refusal cases execute current entry guards, not the independent addon terminal implementation',
                      'Guarded HTTP route/header coordination executes current methods with counted inner policy boundaries; native document-proof queue ordering is checked without claiming native proof execution',
                  ], scope='Actual GeckoWebView first-load, restore, navigation-delegate and timezone-route adapter control flow. No Android/Gecko execution, native setting readback, Date/Intl effect, worker effect or wire claim.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'] if unchanged else 'source-changed', passed=report['passed'], negativeControls=len(controls), executionInputsUnchanged=unchanged, output=str(args.output))))
    if not unchanged:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
