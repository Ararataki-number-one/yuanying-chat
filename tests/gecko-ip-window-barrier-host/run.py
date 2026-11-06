#!/usr/bin/env python3
"""Execute the actual app IP lookup window gate at explicitly named JVM edges."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
BASE = '972b7767300587af98b3f4a2088a44dd30af8098'
SOURCE_PATH = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
MEMBERS = ('static final class TimeZoneGate', 'boolean timeZoneSessionAlive(',
           'boolean timeZoneAllows(', 'private void startTimeZone(')
module_spec = importlib.util.spec_from_file_location('window_gate_extraction', ROOT / 'tests/gecko-navigation-host/run.py')
extraction = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(extraction)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def declaration(source, needle):
    if source.count(needle) != 1:
        raise ValueError('Unique actual production member required: ' + needle)
    return extraction.member_at(source, source.index(needle))



def preserved_source_input(raw):
    """Metadata only; the actual compiled members always use current bytes."""
    if sha(raw) == 'c4a9a2e404ec18b4fad1ac252e9ea69af6e3a5763855f901d47c9b80d3337a3d':
        before, current = 'void finishIpNavigationFailure(GeckoSession session,TimeZoneGate gate,String issue){\n    if(destroyed||session!=current||timeZoneGates.get(session)!=gate||gate.ready||gate.revalidating||gate.documentSerial!=0||!autoIpMode()||!owner.navigating||timeZoneIntents.get(session)==null||hasVisibleDocument())return;\n    String location=locations.getOrDefault(session,"");if(!location.isEmpty()&&!"about:blank".equals(location))return;\n    if(owner.pending!=null||owner.submitting||owner.operation||owner.transferActive||owner.resourceChoosers>0||owner.resourceFilePreparations>0||owner.fileWorkActive())return;\n    String target=queued.isEmpty()?owner.navigationTarget:queued;if(!target.equals(owner.navigationTarget)||!allowedUrl(target)||!identityRequestAllowed(target))return;\n    queued=target;ipNavigationFailure=new IpNavigationFailure(session,gate,owner.navigationEpoch,target);\n    // A service/clock failure is not evidence that the admitted route died.\n    // Keep the exact target and task state; do not schedule network recovery.\n    owner.navigating=false;owner.navigationFailed=true;owner.pageError=issue;owner.setStatus(issue);\n  }'.encode(), 'void finishIpNavigationFailure(GeckoSession session,TimeZoneGate gate,String issue){\n    if(destroyed||session!=current||timeZoneGates.get(session)!=gate||gate.ready||gate.revalidating||gate.documentSerial!=0||!autoIpMode()||!owner.navigating||timeZoneIntents.get(session)==null)return;\n    boolean visible=hasVisibleDocument();if(visible&&!ipRouteNeedsReload)return;\n    String location=locations.getOrDefault(session,"");if(!visible&&!location.isEmpty()&&!"about:blank".equals(location))return;\n    if(owner.pending!=null||owner.submitting||owner.operation||owner.transferActive||owner.resourceChoosers>0||owner.resourceFilePreparations>0||owner.fileWorkActive())return;\n    String target=queued.isEmpty()?owner.navigationTarget:queued;if(!target.equals(owner.navigationTarget)||!allowedUrl(target)||!identityRequestAllowed(target))return;\n    queued=target;ipNavigationFailure=new IpNavigationFailure(session,gate,owner.navigationEpoch,target);\n    // A service/clock failure is not evidence that the admitted route died.\n    // Keep the exact target, any visible old document and task state; do not\n    // schedule network recovery or retry a route awaiting explicit rematching.\n    owner.navigating=false;owner.navigationFailed=true;owner.pageError=issue;owner.setStatus(issue);\n  }'.encode()
        if raw.count(current) != 1:raise ValueError('One exact independent spinner member required')
        raw = raw.replace(current, before, 1)
        if sha(raw) != '8812872161d8441e1ff4c41118ccfa50c992490caa703c855245c7ed0019f440':raise ValueError('Entire window-only source did not restore')
    return raw

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    jar = args.json_jar.resolve(strict=True)

    def java(name):
        selected = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not selected or not Path(selected).is_file():
            parser.error('Provide --java-home containing ' + name)
        return selected

    source = ROOT / SOURCE_PATH
    identity = ROOT / 'app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java'
    template_file = HERE / 'WindowBarrierHost.java.in'
    complete = [PROD / 'J.java']
    files = [source, identity, template_file, Path(__file__).resolve(), ROOT / 'tests/gecko-navigation-host/run.py'] + complete
    hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in files}
    jar_hash = sha(jar.read_bytes())
    selected = {name: declaration(source.read_text(), name) for name in MEMBERS}
    identity_body = declaration(identity.read_text(), 'public static String id(')
    template = template_file.read_text()
    replacements = (('GeckoWebView.this', 'WebBoundary.this'),
                    ('WebExtension.Port', 'PortBoundary'),
                    ('GeckoSession', 'SessionBoundary'), ('GeckoResult', 'ResultBoundary'),
                    ('GeckoTimeZoneController', 'ControllerBoundary'), ('AppSessionIdentity', 'IdentityBoundary'))
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(parents=True, exist_ok=True)

    def generate(members):
        text = template.replace('@METHODS@', '\n'.join(members.values())).replace('@IDENTITY@', identity_body)
        for before, after in replacements:
            text = text.replace(before, after)
        return text

    controls = []
    with tempfile.TemporaryDirectory(prefix='gecko-ip-window-') as directory:
        work = Path(directory)

        def execute(members, label, focus=None):
            out = artifacts / label
            out.mkdir(exist_ok=True)
            host = out / 'WindowBarrierHost.java'
            host.write_text(generate(members))
            classes = work / label
            command = [java('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(classes), str(host)] + [str(path) for path in complete]
            built = subprocess.run(command, text=True, capture_output=True, timeout=60)
            (out / 'compile.command.json').write_text(json.dumps(command) + '\n')
            (out / 'compile.stderr.log').write_text(built.stderr)
            if built.returncode:
                raise RuntimeError(label + ': compilation failed\n' + built.stderr)
            command = [java('java'), '-cp', str(classes) + os.pathsep + str(jar), 'local.pocketchat.WindowBarrierHost'] + ([focus] if focus else [])
            ran = subprocess.run(command, text=True, capture_output=True, timeout=30)
            (out / 'run.command.json').write_text(json.dumps(command) + '\n')
            (out / 'run.stdout.log').write_text(ran.stdout)
            (out / 'run.stderr.log').write_text(ran.stderr)
            return ran

        ran = execute(selected, 'current')
        if ran.returncode:
            raise RuntimeError(ran.stdout + ran.stderr)
        report = json.loads(ran.stdout)
        git_env = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        baseline_raw = subprocess.check_output(['git', 'show', BASE + ':' + SOURCE_PATH], cwd=ROOT, env=git_env, timeout=30)
        baseline = {name: declaration(baseline_raw.decode(), name) for name in MEMBERS}
        lookup_declaration = 'public void lookupIp('
        original_lookup = declaration(baseline_raw.decode(), lookup_declaration)
        current_lookup = declaration(source.read_text(), lookup_declaration)
        if preserved_source_input(source.read_bytes()).replace(current_lookup.encode(), original_lookup.encode(), 1) != baseline_raw:
            raise AssertionError('Production delta must be only the exact lookupIp member; initial consumer and all existing budgets stay byte-identical')
        control_specs = [('actual-before', baseline, 'pending', 'Pending window has zero IP transport invocations true')]
        before = 'if(!ready||!current()){fail.accept(new IOException("出口时区查询上下文已变化"))'
        method = 'private void startTimeZone('
        if selected[method].count(before) != 1:
            raise ValueError('Unique actual IP lookup guard required')
        for name, after, focus, assertion in (
            ('ignore-ready', 'if(!current()){fail.accept(new IOException("出口时区查询上下文已变化"))', 'false', 'False window never invokes IP lookup true error'),
            ('ignore-current', 'if(!ready){fail.accept(new IOException("出口时区查询上下文已变化"))', 'scope', 'Changed scope cannot invoke IP transport document'),
        ):
            counterfeit = dict(selected)
            counterfeit[method] = counterfeit[method].replace(before, after)
            control_specs.append((name, counterfeit, focus, assertion))
        for name, members, focus, assertion in control_specs:
            pristine = execute(selected, 'pristine-' + name, focus)
            if pristine.returncode:
                raise AssertionError('Pristine current control failed: ' + name + pristine.stderr)
            negative = execute(members, 'negative-' + name, focus)
            if negative.returncode == 0 or 'AssertionError: ' + assertion not in negative.stderr:
                raise AssertionError('Compiled negative must fail its exact behavioral oracle: ' + name + negative.stderr)
            controls.append(dict(case=name, compiled=True, pristinePassed=True, rejected=True, assertion=assertion))

    unchanged = all(sha(path.read_bytes()) == hashes[str(path.relative_to(ROOT))] for path in files) and sha(jar.read_bytes()) == jar_hash
    report.update(sourceFiles=hashes, sourceMethodHashes={name: sha(body.encode()) for name, body in selected.items()},
                  identityMethodSha256=sha(identity_body.encode()), jsonJarSha256=jar_hash,
                  lookupOnlyWholeFileInverseVerified=True, originalInitialConsumerPreserved=True,
                  baseline=dict(commit=BASE, sourceSha256=sha(baseline_raw), usage='Real Git before-image runs only as a separately compiled negative; current workload executes raw current methods'),
                  negativeControls=controls, executionInputsUnchanged=unchanged,
                  typeTokenSubstitutions=replacements,
                  boundaries=[
                      'Actual selected GeckoWebView members and AppSessionIdentity.id execute with only named SDK/controller type-token substitutions',
                      'ResultBoundary models queued Handler.post delivery for the pinned GeckoResult API; this is not execution inside Gecko SDK or Android',
                      'ControllerBoundary calls actual NativeAccess.lookupIp, tracks identical arguments/callback references, and scripts completion without a native ACK',
                      'The counted lookupIpTimeZone transport boundary records invocation only; HTTP, native timezone, lease and page outcomes are separate integration scopes',
                      'HandlerBoundary virtual clock preserves the original 5000ms deadline and exposes scope changes between window completion and lookup continuation',
                      'Initial window consumer remains byte-identical to the real before-image, preserving legacy system-fallback controller admission even when the window result is false',
                  ], scope='Actual app window/current gate before IP lookup. No Android, Gecko, HTTP, native-setting, Date/Intl, worker or wire execution claim.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'] if unchanged else 'source-changed', checks=report['passed'], negativeControls=len(controls), executionInputsUnchanged=unchanged, output=str(args.output))))
    if not unchanged:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
