#!/usr/bin/env python3
"""Execute production Gecko navigation policy and source-bound driver methods.

The Web/Handler/clock interfaces are declared JVM boundaries. This workload does
not initialize Android, GeckoView, a WebExtension, a website, or a network route.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
MEMBERS = (
    'static final class DriverTarget',
    'boolean chatAutomationAllowed(',
    'DriverTarget driverTarget(',
    'boolean driverTargetCurrent(',
    'void runDriver(',
    'void evaluateDriver(',
    'void asyncDriver(',
    'void waitResult(',
)
MUTATIONS = (
    ('same-URL-new-epoch', '&&target.epoch==navigationEpoch', ''),
    ('same-path-new-query', '&&target.url.equals(web.getUrl())', ''),
    ('surface-replaced', '&&target.surface==web.current', ''),
    ('port-replaced', '&&target.port==web.ports.get(web.current)', ''),
    ('deleted', 'return !deleted&&MainActivity.chatUrl(web.getUrl());',
     'return MainActivity.chatUrl(web.getUrl());'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def member_at(source, at):
    """Read a complete declaration, respecting Java strings and comments."""
    brace = source.index('{', at)
    depth, index = 1, brace + 1
    quote, escaped, line, block = None, False, False, False
    while depth:
        if index >= len(source):
            raise ValueError('Unterminated production declaration')
        char, following = source[index], source[index + 1:index + 2]
        if line:
            if char == '\n':
                line = False
        elif block:
            if char == '*' and following == '/':
                block = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char == '/' and following == '/':
            line = True
            index += 1
        elif char == '/' and following == '*':
            block = True
            index += 1
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        index += 1
    return source[at:index]


def production_members(source):
    values = []
    for needle in MEMBERS:
        positions, offset = [], 0
        while True:
            at = source.find(needle, offset)
            if at < 0:
                break
            # These declarations start a line; a reference or quoted string
            # must not become a replacement for an actual method body.
            if source[source.rfind('\n', 0, at) + 1:at].strip() == '':
                positions.append(at)
            offset = at + len(needle)
        if not positions:
            raise ValueError('Missing production declaration: ' + needle)
        for at in positions:
            values.append(member_at(source, at))
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='JSON report file; compile/run logs are adjacent')
    args = parser.parse_args()
    def tool(name):
        selected = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not selected:
            parser.error('Provide --java-home containing ' + name)
        return selected

    files = [PROD / name for name in (
        'ChatSession.java', 'GeckoNavigationPolicy.java', 'BrowserAddressPolicy.java',
        'BrowserRuntimePolicy.java', 'J.java')]
    files += [HERE / 'DriverHost.java.in', HERE / 'NavigationHost.java',
              Path(__file__).resolve()]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in files}
    json_hash = digest(args.json_jar)
    selected = production_members((PROD / 'ChatSession.java').read_text())
    body = '\n'.join(selected).replace('System.currentTimeMillis()', 'Clock.wallMillis()')
    generated = (HERE / 'DriverHost.java.in').read_text().replace(
        '@PRODUCTION_MEMBERS@', body)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / 'DriverHost.java').write_text(generated)
    reports = {}
    mutations = []
    with tempfile.TemporaryDirectory(prefix='gecko-navigation-host-') as temporary:
        work = Path(temporary)
        source = work / 'DriverHost.java'
        source.write_text(generated)
        classes = work / 'classes'
        compile_command = [tool('javac'), '-encoding', 'UTF-8', '-cp',
                           str(args.json_jar.resolve()), '-d', str(classes), str(source),
                           str(HERE / 'NavigationHost.java')]
        compile_command += [str(PROD / name) for name in (
            'J.java', 'GeckoNavigationPolicy.java', 'BrowserAddressPolicy.java',
            'BrowserRuntimePolicy.java')]
        (artifacts / 'compile.command.json').write_text(json.dumps(compile_command) + '\n')
        compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
        (artifacts / 'compile.stdout.log').write_text(compiled.stdout)
        (artifacts / 'compile.stderr.log').write_text(compiled.stderr)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        for name in ('DriverHost', 'NavigationHost'):
            command = [tool('java'), '-cp', str(classes) + ':' + str(args.json_jar.resolve()),
                       'local.pocketchat.' + name]
            (artifacts / (name + '.command.json')).write_text(json.dumps(command) + '\n')
            ran = subprocess.run(command, capture_output=True, text=True, timeout=30)
            (artifacts / (name + '.stdout.log')).write_text(ran.stdout)
            (artifacts / (name + '.stderr.log')).write_text(ran.stderr)
            if ran.returncode:
                raise RuntimeError(ran.stdout + ran.stderr)
            reports[name] = json.loads(ran.stdout)
            if reports[name]['status'] != 'passed' or not reports[name]['checks'] or not all(
                    row['pass'] is True for row in reports[name]['checks']):
                raise AssertionError('Production host assertions failed: ' + name)
        for index, (case, before, after) in enumerate(MUTATIONS):
            focus_command = [tool('java'), '-cp', str(classes) + ':' + str(args.json_jar.resolve()),
                             'local.pocketchat.DriverHost', case]
            pristine = subprocess.run(focus_command, capture_output=True, text=True, timeout=30)
            if pristine.returncode or json.loads(pristine.stdout)['status'] != 'passed':
                raise AssertionError('Pristine focused case failed: ' + case + pristine.stderr)
            if body.count(before) != 1:
                raise ValueError('Review the exact one-predicate negative control: ' + case)
            mutant_body = body.replace(before, after, 1)
            mutant = (HERE / 'DriverHost.java.in').read_text().replace(
                '@PRODUCTION_MEMBERS@', mutant_body)
            mutation_dir = artifacts / ('mutation-' + str(index) + '-' + case)
            mutation_dir.mkdir(parents=True, exist_ok=True)
            mutant_source = work / ('mutation-' + str(index)) / 'DriverHost.java'
            mutant_source.parent.mkdir(parents=True)
            mutant_source.write_text(mutant)
            (mutation_dir / 'DriverHost.java').write_text(mutant)
            mutant_classes = mutant_source.parent / 'classes'
            mutant_compile = [tool('javac'), '-encoding', 'UTF-8', '-cp',
                              str(args.json_jar.resolve()), '-d', str(mutant_classes),
                              str(mutant_source), str(PROD / 'J.java'),
                              str(PROD / 'BrowserRuntimePolicy.java')]
            changed = subprocess.run(mutant_compile, capture_output=True, text=True, timeout=60)
            (mutation_dir / 'compile.command.json').write_text(json.dumps(mutant_compile) + '\n')
            (mutation_dir / 'compile.stdout.log').write_text(changed.stdout)
            (mutation_dir / 'compile.stderr.log').write_text(changed.stderr)
            if changed.returncode:
                raise RuntimeError('Negative control did not compile: ' + changed.stderr)
            mutant_command = [tool('java'), '-cp', str(mutant_classes) + ':' + str(args.json_jar.resolve()),
                              'local.pocketchat.DriverHost', case]
            rejected = subprocess.run(mutant_command, capture_output=True, text=True, timeout=30)
            (mutation_dir / 'run.command.json').write_text(json.dumps(mutant_command) + '\n')
            (mutation_dir / 'run.stdout.log').write_text(rejected.stdout)
            (mutation_dir / 'run.stderr.log').write_text(rejected.stderr)
            (mutation_dir / 'pristine.stdout.log').write_text(pristine.stdout)
            expected_assertion = ('Focused expired poll performs no deletion: ' if case == 'port-replaced'
                                  else 'Focused expired compact response performs no fallback: ') + case
            if rejected.returncode == 0 or 'AssertionError: ' + expected_assertion not in rejected.stderr:
                raise AssertionError('Focused workload did not reject the intended missing guard: ' + case)
            mutations.append(dict(case=case, pristinePassed=True, mutantRejected=True,
                                  removed=before, replacement=after,
                                  mutantGeneratedSha256=hashlib.sha256(mutant.encode()).hexdigest(),
                                  expectedAssertion=expected_assertion))
    unchanged = all(digest(path) == hashes[str(path.relative_to(ROOT))] for path in files)
    unchanged = unchanged and digest(args.json_jar) == json_hash
    report = dict(
        status='passed' if unchanged else 'source-changed',
        passed=sum(value['passed'] for value in reports.values()),
        total=sum(value['total'] for value in reports.values()),
        reports=reports, negativeControls=mutations, sourceFiles=hashes,
        sourceCommit=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        generatedSourceSha256=hashlib.sha256(generated.encode()).hexdigest(),
        jsonJarSha256=json_hash,
        javaVersion=subprocess.check_output([tool('java'), '-version'],
                                            stderr=subprocess.STDOUT, text=True).strip(),
        executionInputsUnchanged=unchanged, productionMembers=MEMBERS,
        boundarySubstitutions=[
            'System.currentTimeMillis() → deterministic Clock.wallMillis()',
            'SystemClock → deterministic elapsed clock',
            'Web surface/port/evaluateJavascript callbacks are explicit controlled JVM boundaries',
            'Handler scheduled callbacks are manually advanced without sleeping',
            'MainActivity.chatUrl delegates to actual BrowserRuntimePolicy.official on a JVM URI',
            'Driver JS strings and optional-observation policy are explicit controlled inputs'],
        actualAndroidExecution=False, actualGeckoExecution=False,
        actualWebsiteExecution=False, actualNetworkExecution=False,
        scope='Complete production Gecko navigation policy plus extracted actual ChatSession driver methods; deterministic controlled JVM callback and scheduling workload. No Android, GeckoView, WebExtension, website, or network acceptance.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], passed=report['passed'],
                          total=report['total'], executionInputsUnchanged=unchanged,
                          output=str(args.output)), ensure_ascii=False))
    if not unchanged:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
