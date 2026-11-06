#!/usr/bin/env python3
"""Execute the actual app IP lookup window gate at explicitly named JVM edges."""
import argparse
import hashlib
import importlib.util
import inspect
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
COMPOSED_SOURCE = '12a45fb8a1343bbe5767bdf6c3fba54519650fa1'
COMPOSED_GV_SHA256 = '34a651c3ccc50499dd5c720c370353600ccf20669df5393ccbf68d6a689f9670'
CURRENT_GV_SHA256 = '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364'
WINDOW_LOOKUP_SHA256 = '181b9349f1330e64eb174d7995030b2785c157351a9a47dee44fa481184f018e'
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


def verify_recovery_source(raw,composed_raw):
    if type(raw) is not bytes or len(raw)!=128874 or sha(raw)!=CURRENT_GV_SHA256:
        raise AssertionError('Unknown composed raw recovery image')
    current=b'initialize();if(!resourceDeferred&&!failed){if(!target.isEmpty())owner.beginNavigation'
    previous=b'initialize();if(!resourceDeferred&&!failed&&runtime!=null){if(!target.isEmpty())owner.beginNavigation'
    if raw.count(current)!=1:
        raise AssertionError('Unique composed raw recovery context required')
    restored=raw.replace(current,previous,1)
    if type(composed_raw) is not bytes or restored!=composed_raw or len(restored)!=128889 or sha(restored)!='34a651c3ccc50499dd5c720c370353600ccf20669df5393ccbf68d6a689f9670':
        raise AssertionError('Exact composed raw recovery predecessor required')
    return dict(currentSha256=sha(raw),currentBytes=len(raw),previousSha256=sha(restored),previousBytes=len(restored),removedBytes=15,proofOnly=True,currentJavaUnchanged=True)


def verify_source_delta(current_raw, baseline_raw, composed_raw):
    current = current_raw.decode('utf-8')
    baseline = baseline_raw.decode('utf-8')
    lookup = 'public void lookupIp('
    original_lookup = declaration(baseline, lookup)
    current_lookup = declaration(current, lookup)
    # Preserve the original complete window-only inverse as the first branch.
    if current_raw.replace(current_lookup.encode(), original_lookup.encode(), 1) == baseline_raw:
        return dict(scope='lookup-only-whole-file-inverse', lookupOnlyWholeFileInverseVerified=True,
                    composedWholeImageVerified=False, originalInitialConsumerPreserved=True,
                    originalFiveEightAndEightPointFiveSecondBudgetsPreserved=True)
    recovery_scope=None
    if sha(current_raw)==CURRENT_GV_SHA256:
        recovery_scope=verify_recovery_source(current_raw,composed_raw)
        # Proof comparison only. The actual Java members above/main remain raw.
        current_raw=current_raw.replace(b'initialize();if(!resourceDeferred&&!failed){if(!target.isEmpty())owner.beginNavigation',b'initialize();if(!resourceDeferred&&!failed&&runtime!=null){if(!target.isEmpty())owner.beginNavigation',1)
    if current_raw != composed_raw or sha(current_raw) != COMPOSED_GV_SHA256 or sha(composed_raw) != COMPOSED_GV_SHA256:
        raise AssertionError('Unknown composed raw whole-source image')
    composed_lookup = declaration(composed_raw.decode('utf-8'), lookup)
    if current_lookup != composed_lookup or sha(current_lookup.encode()) != WINDOW_LOOKUP_SHA256:
        raise AssertionError('Exact published window lookup member required')
    original_start = declaration(baseline, 'private void startTimeZone(')
    current_start = declaration(current, 'private void startTimeZone(')
    if current_start.replace(current_lookup, original_lookup, 1) != original_start:
        raise AssertionError('Original initial consumer and five-second window budget must remain byte-identical')
    for inherited in ('static final class IpLookup {', 'void lookupIpTimeZone('):
        if declaration(current, inherited) != declaration(baseline, inherited):
            raise AssertionError('Original native IP lookup eight/eight-point-five-second members must remain byte-identical')
    return dict(scope='exact-recovery-successor-of-published-composed-image'if recovery_scope else'exact-published-composed-whole-image', lookupOnlyWholeFileInverseVerified=False,
                composedWholeImageVerified=True, originalInitialConsumerPreserved=True,
                originalFiveEightAndEightPointFiveSecondBudgetsPreserved=True,
                composedSource=COMPOSED_SOURCE, composedSourceSha256=COMPOSED_GV_SHA256,
                windowLookupSha256=WINDOW_LOOKUP_SHA256,resourceRecoveryWholeProof=recovery_scope)


def source_metadata_controls(composed_raw, baseline_raw):
    # Counterfeit inputs come only from the published composed image. This
    # preserves the independently accepted original window-only branch; no
    # candidate is ever a source for the current Java workload.
    current_raw = composed_raw
    controls = []
    lookup = 'public void lookupIp('
    current = current_raw.decode('utf-8')
    selected_lookup = declaration(current, lookup)
    original_lookup = declaration(baseline_raw.decode('utf-8'), lookup)
    window_only = baseline_raw.replace(original_lookup.encode(), selected_lookup.encode(), 1)
    if not verify_source_delta(window_only, baseline_raw, composed_raw)['lookupOnlyWholeFileInverseVerified']:
        raise AssertionError('Original lookup-only whole-file branch must remain available')
    # Isolated validator copies permit a forged metadata digest solely to show
    # the independent member guards reject it. No app source or Git input is
    # changed, projected or used for current Java generation.
    def copied(function_source=None, digest=None):
        namespace = dict(verify_source_delta.__globals__)
        if digest is not None:
            namespace['COMPOSED_GV_SHA256'] = digest
        exec(compile(function_source or inspect.getsource(verify_source_delta), '<isolated-source-metadata-validator>', 'exec'), namespace)
        return namespace['verify_source_delta']
    def denied(name, validator, candidate, reference, message):
        try:
            validator(candidate, baseline_raw, reference)
        except AssertionError as error:
            if message not in str(error):
                raise AssertionError('Wrong metadata rejection boundary: ' + name + ': ' + str(error))
            controls.append(dict(case=name, rejected=True, message=message, javaGeneratedFromCandidate=False))
            return
        raise AssertionError('Source metadata false-proof escaped: ' + name)
    unknown = current_raw + b'\n// Unknown source outside the selected window methods.\n'
    denied('unknown-whole-image', verify_source_delta, unknown, composed_raw, 'Unknown composed raw whole-source image')
    denied('wrong-published-whole-image', verify_source_delta, current_raw, composed_raw+b'\n', 'Unknown composed raw whole-source image')
    broken_lookup = selected_lookup.replace('if(!ready||!current())', 'if(!current())', 1)
    if broken_lookup == selected_lookup:
        raise AssertionError('Unique ready/current lookup guard required')
    changed_lookup = current_raw.replace(selected_lookup.encode(), broken_lookup.encode(), 1)
    denied('forged-whole-metadata-cannot-hide-lookup-change', copied(digest=sha(changed_lookup)), changed_lookup, changed_lookup, 'Exact published window lookup member required')
    start = declaration(current, 'private void startTimeZone(')
    changed_initial = current_raw.replace(start.encode(), start.replace('if(!access.current()){finished.accept(false);return;}', 'if(false){finished.accept(false);return;}', 1).encode(), 1)
    if changed_initial == current_raw:
        raise AssertionError('Unique original initial window consumer required')
    denied('forged-whole-metadata-cannot-hide-initial-consumer-change', copied(digest=sha(changed_initial)), changed_initial, changed_initial, 'Original initial consumer and five-second window budget')
    changed_five = current_raw.replace(start.encode(), start.replace('deadline[0],5000', 'deadline[0],5001', 1).encode(), 1)
    if changed_five == current_raw:
        raise AssertionError('Unique original five-second window deadline required')
    denied('forged-whole-metadata-cannot-hide-window-budget-change', copied(digest=sha(changed_five)), changed_five, changed_five, 'Original initial consumer and five-second window budget')
    for name, marker, old, new in [('eight-second','static final class IpLookup {','+8000','+8001'), ('eight-point-five-second','void lookupIpTimeZone(', '},8500', '},8501')]:
        member = declaration(current, marker)
        if member.count(old) != 1:
            raise AssertionError('Unique original lookup budget required: ' + name)
        changed = current_raw.replace(member.encode(), member.replace(old,new,1).encode(),1)
        denied('forged-whole-metadata-cannot-hide-'+name+'-change', copied(digest=sha(changed)), changed, changed, 'Original native IP lookup eight/eight-point-five-second members')
    source = inspect.getsource(verify_source_delta)
    mutants = [
        ('removed-raw-whole-pin', "    if current_raw != composed_raw or sha(current_raw) != COMPOSED_GV_SHA256 or sha(composed_raw) != COMPOSED_GV_SHA256:\n        raise AssertionError('Unknown composed raw whole-source image')\n", unknown, composed_raw, None),
        ('removed-exact-lookup-pin', "    if current_lookup != composed_lookup or sha(current_lookup.encode()) != WINDOW_LOOKUP_SHA256:\n        raise AssertionError('Exact published window lookup member required')\n", changed_lookup, changed_lookup, sha(changed_lookup)),
        ('removed-original-initial-window-body-guard', "    if current_start.replace(current_lookup, original_lookup, 1) != original_start:\n        raise AssertionError('Original initial consumer and five-second window budget must remain byte-identical')\n", changed_initial, changed_initial, sha(changed_initial)),
    ]
    counterfeits = []
    for name, removed, candidate, reference, digest in mutants:
        if source.count(removed) != 1:
            raise AssertionError('Unique source metadata counterfeit required: ' + name)
        mutant = copied(source.replace(removed, '', 1), digest)
        try:
            denied(name, mutant, candidate, reference, '')
        except AssertionError as error:
            if 'Source metadata false-proof escaped: '+name not in str(error):
                raise
            counterfeits.append(dict(case=name, pythonCompiled=True, sameNegativeExpectationRejected=True,
                                     productionOrGitInputChanged=False, javaGeneratedFromCandidate=False))
        else:
            raise AssertionError('Metadata counterfeit did not exercise the expected missing guard: ' + name)
    return dict(legacyWindowOnlyBranchVerified=True, counterfeitMetadataUsesPublishedComposedImage=True, rejectedInputs=controls,
                pythonGuardCounterfeits=counterfeits, actualCurrentJavaUsesRawSource=True)


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
        composed_raw = subprocess.check_output(['git', 'show', COMPOSED_SOURCE + ':' + SOURCE_PATH], cwd=ROOT, env=git_env, timeout=30)
        delta_scope = verify_source_delta(source.read_bytes(), baseline_raw, composed_raw)
        recovery_scope = None if delta_scope['lookupOnlyWholeFileInverseVerified'] else verify_recovery_source(source.read_bytes(),composed_raw)
        metadata_controls = source_metadata_controls(composed_raw, baseline_raw)
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
                  lookupOnlyWholeFileInverseVerified=delta_scope['lookupOnlyWholeFileInverseVerified'], originalInitialConsumerPreserved=True,
                  sourceDeltaScope=delta_scope, sourceMetadataControls=metadata_controls, resourceRecoveryWholeProof=recovery_scope,
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
