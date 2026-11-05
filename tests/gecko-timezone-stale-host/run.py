#!/usr/bin/env python3
"""Execute actual stale-ticket fixture wiring against the complete current store."""
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
EXTRACTOR = ROOT / 'tests/gecko-timezone-flow-host/run.py'
spec = importlib.util.spec_from_file_location('timezone_stale_declaration_boundary', EXTRACTOR)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

MEMBERS = ('void newYork(', 'void staleNativeTicket(', 'void staleRevisionTicket(')
OLD_ASSERT = 'stale.actual-store-record-rejected'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def replace_unique(value, before, after, label):
    if value.count(before) != 1:
        raise ValueError('Unique actual bounded mutation hunk required: ' + label)
    return value.replace(before, after, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()

    def tool(name):
        value = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not value:
            parser.error('Provide --java-home containing JDK17 ' + name)
        return value

    fixture = ROOT / 'tests/gecko/GeckoEnvironmentPolicyIntegrationActivity.java'
    template_path = HERE / 'StaleTicketHost.java.in'
    adapters = ROOT / 'tests/gecko-timezone-host/GeckoTimeZoneHost.java'
    sources = [PROD / name for name in ('GeckoTimeZoneSpec.java', 'GeckoTimeZoneStore.java',
               'GeckoTimeZonePolicy.java', 'GeckoIpTimeZonePolicy.java', 'EnvironmentSpec.java', 'NetworkShareJson.java', 'J.java')]
    inputs = sources + [fixture, template_path, adapters, EXTRACTOR, Path(__file__).resolve(), HERE / 'README.md']
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    jar_hash = digest(args.json_jar)
    fixture_text = fixture.read_text()
    selected = {marker: extractor.block(fixture_text, marker) for marker in MEMBERS}
    template = template_path.read_text()
    if template.count('@METHODS@') != 1:
        raise ValueError('Exactly one actual-method insertion boundary is required')
    store = PROD / 'GeckoTimeZoneStore.java'
    store_text = store.read_text()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    controls = []
    with tempfile.TemporaryDirectory(prefix='gecko-timezone-stale-') as temporary:
        work = Path(temporary)

        def execute(methods, actual_store, label, focus='full'):
            out = artifacts / label
            out.mkdir(exist_ok=True)
            host = out / 'StaleTicketHost.java'
            host.write_text(template.replace('@METHODS@', '\n'.join(methods.values())))
            source_store = out / store.name
            source_store.write_text(actual_store)
            context = out / 'android/content/Context.java'
            context.parent.mkdir(parents=True, exist_ok=True)
            context.write_text('package android.content; public abstract class Context {public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();}\n')
            classes = work / label / 'classes'
            command = [tool('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()), '-d', str(classes),
                       *[str(path) for path in sources if path != store], str(source_store), str(adapters), str(context), str(host)]
            built = subprocess.run(command, text=True, capture_output=True, timeout=60)
            (out / 'compile.command.json').write_text(json.dumps(command) + '\n')
            (out / 'compile.stdout.log').write_text(built.stdout)
            (out / 'compile.stderr.log').write_text(built.stderr)
            if built.returncode:
                raise RuntimeError(label + ' must compile before any behavioral claim:\n' + built.stderr)
            command = [tool('java'), '-cp', str(classes) + os.pathsep + str(args.json_jar.resolve()), 'local.pocketchat.StaleTicketHost', str(work / label / 'state'), focus]
            ran = subprocess.run(command, text=True, capture_output=True, timeout=30)
            (out / 'run.command.json').write_text(json.dumps(command) + '\n')
            (out / 'run.stdout.log').write_text(ran.stdout)
            (out / 'run.stderr.log').write_text(ran.stderr)
            return ran, dict(hostSha256=digest(host), executedStoreSha256=digest(source_store))

        current, generated = execute(selected, store_text, 'current')
        if current.returncode:
            raise RuntimeError('Current actual fixture/store failed:\n' + current.stdout + current.stderr)
        result = json.loads(current.stdout)

        # Restore the actual faulty ordering in the currently compiled newYork
        # method, rather than merely checking for the spelling of its call.
        correct = 'staleNativeTicket(coop.getJSONObject("native"),()->saveZone("Asia/Kathmandu",()->capture("kathmandu",true,this::kathmandu)));'
        old_order = 'saveZone("Asia/Kathmandu",()->capture("kathmandu",true,current->{try{staleNativeTicket(current.getJSONObject("native"),()->kathmandu(current));}catch(Exception error){failed(error);}}));'
        misplaced = dict(selected)
        misplaced['void newYork('] = replace_unique(selected['void newYork('], correct, old_order, 'stale-native-after-desired-save')
        missing_current = replace_unique(store_text, 'if(!r.current(ticket))throw new IOException("时区上下文已变化，旧确认未保存");', '', 'record-current-ticket-guard')
        last = extractor.block(store_text, 'static JSONObject lastReceipt(')
        missing_revision = replace_unique(store_text, last, replace_unique(last, 'revision(state,ticket.revision);', '', 'last-receipt-revision-guard'), 'last-receipt-method')
        mutations = [
            ('stale-native-after-desired-save', 'orchestration', misplaced, store_text, OLD_ASSERT),
            ('record-current-ticket-guard', 'same-revision', selected, missing_current, OLD_ASSERT),
            ('last-receipt-revision-guard', 'revision', selected, missing_revision, 'stale.old-revision-receipt-rejected'),
        ]
        for label, focus, methods, mutated_store, assertion in mutations:
            pristine, _ = execute(selected, store_text, 'pristine-' + label, focus)
            if pristine.returncode:
                raise AssertionError('Pristine focused control must pass: ' + label + pristine.stderr)
            mutated, executed = execute(methods, mutated_store, 'mutant-' + label, focus)
            if mutated.returncode != 1 or 'java.lang.AssertionError: ' + assertion not in mutated.stderr:
                raise AssertionError('Compiled semantic mutant must fail its exact assertion: ' + label + '\n' + mutated.stdout + mutated.stderr)
            controls.append(dict(name=label, focus=focus, compiled=True, pristinePassed=True, mutantRejected=True,
                                 runtimeExitCode=mutated.returncode, assertion=assertion, **executed))
            result['checks'].append('Compiled actual semantic mutant rejected: ' + label)
        result['passed'] += len(controls)
        result['total'] += len(controls)

    stable = all(digest(path) == hashes[str(path.relative_to(ROOT))] for path in inputs) and digest(args.json_jar) == jar_hash
    result.update(schema=1, status='passed' if stable else 'source-changed',
                  sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  sourceFiles=hashes, fixtureMethodSha256={key: sha_text(value) for key, value in selected.items()},
                  generatedCurrentSources=generated, compiledSemanticMutants=controls,
                  executionInputsUnchanged=stable, jsonJarSha256=jar_hash,
                  actualAndroidExecution=False, actualGeckoNativeSettingExecution=False,
                  actualDateIntlExecution=False, actualWorkerExecution=False,
                  actualSqliteExecution=False, actualAesKeystoreExecution=False,
                  boundaries=[
                      'Complete actual current Store/Spec/Policy/EnvironmentSpec/NetworkShareJson/J compile unchanged; the only store changes are separately compiled and rejected semantic mutants',
                      'Current fixture newYork/staleNativeTicket/staleRevisionTicket declarations are inserted verbatim, hashed and executed; no historical implementation replaces current logic',
                      'The complete existing GeckoTimeZoneHost supplies explicit Context/catalog/plain atomic-vault adapters; temp filesystem, atomic move and FileLock are real, SQLite/Android Keystore are not',
                      'Queued writer/probe, navigate/capture/saveZone and synthetic native ACK/page/clock data are named boundaries; saveZone performs the actual desired CAS and actual current ticket publication',
                      'The native/page/clock prerequisites of newYork are controlled dependencies, not actual Date/Intl, native setting or network observations; the host stops before the later Android reload/restore workload',
                  ], scope='Same-revision replaced-context rejection and after-save revision rejection are distinct actual-store contracts. Executes actual current fixture orchestration and helpers, reproduces the old after-revision assertion failure, refuses a mislabeled live ticket/read failure/counterfeit current receipt, and rejects three compiled wiring/store regressions. Host-only control-flow/storage evidence; no native or Android acceptance claim.')
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], passed=result['passed'], total=result['total'],
                          compiledSemanticMutants=len(controls), executionInputsUnchanged=stable,
                          actualAndroidExecution=False, output=str(args.output))))
    if not stable:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
