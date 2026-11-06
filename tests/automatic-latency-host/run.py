#!/usr/bin/env python3
"""Run actual automatic-latency preferences/scheduling at named JVM boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROD = ROOT / 'app/src/main/java/local/pocketchat'
sys.path.insert(0, str(ROOT / 'tests/gecko-navigation-host'))
from run import member_at


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(text, needle):
    positions = [m.start() for m in re.finditer(re.escape(needle), text)
                 if not text[text.rfind('\n', 0, m.start())+1:m.start()].strip()]
    if len(positions) != 1:
        raise ValueError('One actual production declaration required: ' + needle)
    return member_at(text, positions[0])


def field(text, needle):
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(needle)]
    if len(lines) != 1 or not lines[0].endswith(';'):
        raise ValueError('One complete production field required: ' + needle)
    return lines[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    def java(name):
        value = str(args.java_home / 'bin' / name) if args.java_home else shutil.which(name)
        if not value:
            parser.error('Provide --java-home with ' + name)
        return value

    java_version = subprocess.run([java('java'), '-version'], text=True, capture_output=True, timeout=10)
    javac_version = subprocess.run([java('javac'), '-version'], text=True, capture_output=True, timeout=10)
    versions = java_version.stdout + java_version.stderr + javac_version.stdout + javac_version.stderr
    if java_version.returncode or javac_version.returncode or not re.search(r'version "17[.]', versions) or not re.search(r'javac 17[.]', versions):
        parser.error('This source-bound host control requires an actual JDK 17 (--java-home)')
    names = ('AppPrefs.java', 'NetworkRegion.java', 'NativeNetwork.java', 'EnvironmentEditorUi.java',
             'J.java', 'LatencyRefreshPolicy.java')
    inputs = [PROD / name for name in names] + [Path(__file__).resolve(), HERE / 'AutomaticLatencyHost.java.in',
        HERE / 'README.md', ROOT / 'tests/gecko-navigation-host/run.py']
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    jar_hash = digest(args.json_jar)
    prefs = (PROD / 'AppPrefs.java').read_text()
    region = (PROD / 'NetworkRegion.java').read_text()
    native = (PROD / 'NativeNetwork.java').read_text()
    editor = (PROD / 'EnvironmentEditorUi.java').read_text()
    selected = {
        'keys': field(prefs, 'static final String[] KEYS='),
        'labels': field(prefs, 'static final String[] LABELS='),
        'enabled': declaration(prefs, 'static boolean enabled('),
        'values': declaration(prefs, 'static JSONObject values('),
        'apply': declaration(prefs, 'static void apply('),
        'latency-route': declaration(region, 'static String latencyRoute('),
        'latency-cache': declaration(region, 'static JSONObject latency('),
        'proxy': declaration(region, 'static Proxy proxy('),
        'session-gate': declaration(region, 'static void latencyGate(ChatSession s,long epoch,String route)'),
        'automatic-gate': declaration(region, 'static void latencyGate(ChatSession s,long epoch,String route,boolean automatic)'),
        'refresh': declaration(region, 'static synchronized void refreshLatency('),
        'native-target': field(native, 'static final String PROBE='),
        'freshness': declaration(native, 'static boolean freshLatency('),
    }
    ui_method = declaration(editor, 'static void edit(MainActivity a,JSONObject initial,int tab)')
    start = ui_method.index('    CheckBox[] options=')
    end = ui_method.index('    DesignUi.note(preferences,', start)
    selected['editor-loop'] = ui_method[start:end]
    selected['editor-read'] = field(ui_method, 'for(int i=0;i<options.length;i++)')
    template = (HERE / 'AutomaticLatencyHost.java.in').read_text()
    aliases = (
        ('android.os.SystemClock', 'ClockBoundary'),
        ('System.currentTimeMillis()', 'ClockBoundary.wallMillis()'),
        ('android.net.ConnectivityManager', 'ConnectivityBoundary'),
        ('android.net.Network', 'BoundNetworkBoundary'),
        ('android.net.Uri', 'UriBoundary'),
        ('SharedPreferences.Editor', 'PreferencesBoundary.Editor'),
        ('SharedPreferences', 'PreferencesBoundary'),
        ('ChatSession', 'SessionBoundary'),
        ('NativeNetwork', 'NetworkBoundary'),
        ('RouteLatency', 'ProbeBoundary'),
        ('SecretStore', 'StoreBoundary'),
        ('WindowNetworkState', 'ProjectionBoundary'),
        ('BrowserNetworkGuard', 'GuardPolicyBoundary'),
        ('CheckBox', 'CheckBoxBoundary'),
        ('LinearLayout', 'LayoutBoundary'),
        ('DesignUi', 'DesignBoundary'),
        ('Context c', 'ContextBoundary c'),
    )

    def adapted(value):
        for before, after in aliases:
            value = re.sub(r'(?<![\w$])'+re.escape(before)+r'(?![\w$])', lambda _: after, value)
        return value

    def generate(members):
        return template.replace('@PREFS_MEMBERS@', adapted('\n'.join(members[k] for k in ('keys','labels','enabled','values','apply')))).replace(
            '@REGION_MEMBERS@', adapted('\n'.join(members[k] for k in ('latency-route','latency-cache','proxy','session-gate','automatic-gate','refresh')))).replace(
            '@NATIVE_MEMBERS@', adapted(members['native-target']+'\n'+members['freshness'])).replace(
            '@EDITOR_BLOCK@', adapted(members['editor-loop'])).replace('@EDITOR_READ@', adapted(members['editor-read']))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.parent / (args.output.stem + '-artifacts')
    artifacts.mkdir(exist_ok=True)
    controls = []
    with tempfile.TemporaryDirectory(prefix='automatic-latency-host-') as temporary:
        work = Path(temporary)

        def compile_members(members, label):
            out = artifacts / label
            out.mkdir(exist_ok=True)
            host = out / 'AutomaticLatencyHost.java'
            host.write_text(generate(members))
            classes = work / label
            command = [java('javac'), '--release', '17', '-encoding', 'UTF-8', '-cp', str(args.json_jar.resolve()),
                '-d', str(classes), str(host), str(PROD/'J.java'), str(PROD/'LatencyRefreshPolicy.java')]
            built = subprocess.run(command, text=True, capture_output=True, timeout=60)
            (out/'compile.command.json').write_text(json.dumps(command)+'\n')
            (out/'compile.stderr.log').write_text(built.stderr)
            if built.returncode:
                raise RuntimeError(built.stderr)
            return classes, out

        def execute(classes, out, focus=None):
            command = [java('java'), '-cp', str(classes)+os.pathsep+str(args.json_jar.resolve()), 'local.pocketchat.AutomaticLatencyHost']+([focus] if focus else [])
            result = subprocess.run(command, text=True, capture_output=True, timeout=20)
            suffix = '-'+focus if focus else ''
            (out/('run'+suffix+'.command.json')).write_text(json.dumps(command)+'\n')
            (out/('run'+suffix+'.stdout.log')).write_text(result.stdout)
            (out/('run'+suffix+'.stderr.log')).write_text(result.stderr)
            return result

        classes, current_out = compile_members(selected, 'current')
        ran = execute(classes, current_out)
        if ran.returncode:
            raise RuntimeError(ran.stdout+ran.stderr)
        report = json.loads(ran.stdout)
        # These hunks are intentionally exact production conditions, never a
        # replacement preference/network implementation or source-text oracle.
        mutations = [
            ('default-disabled', 'enabled', '{', '{if("automaticLatencyChecks".equals(key))return false;', 'preferences', 'A missing automatic latency preference defaults to enabled'),
            ('apply-drops-key', 'apply', 'for(String key:KEYS)if(', 'for(String key:KEYS)if(!"automaticLatencyChecks".equals(key)&&', 'preferences', 'The actual preference API persists an explicit automatic latency disable'),
            ('editor-hides-key', 'editor-loop', '{"automaticLatencyChecks"}', '{}', 'preferences', 'The actual environment editor renders the automatic latency checkbox'),
            ('foreign-route', 'session-gate', '||!route.equals(latencyRoute(s))', '', 'foreign-route', 'A queued probe cannot query a foreign current route'),
        ]
        # Final production bodies define the following new guard locations.
        entry = 'if(callback==null&&(!s.uiVisible||!s.prefs.getBoolean("automaticLatencyChecks",true)))return;'
        queued = 'latencyGate(s,epoch,route,callback==null);'
        mutations += [
            ('disabled-entry', 'refresh', entry, 'if(callback==null&&!s.uiVisible)return;', 'disabled', 'Disabled automatic latency queues no work and opens no probe'),
            ('queued-setting', 'refresh', 'if(callback==null&&!s.prefs.getBoolean("automaticLatencyChecks",true))return;', '', 'queued-disable', 'Disabling a queued automatic job prevents even probe invocation'),
            ('completed-setting', 'refresh', 'boolean stored=false;try{'+queued, 'boolean stored=false;try{latencyGate(s,epoch,route);', 'completed-disable', 'Disabling before persistence prevents the old automatic sample from being saved'),
            ('notification-setting', 'refresh', 'final boolean saved=stored;s.handler.post(()->{try{'+queued, 'final boolean saved=stored;s.handler.post(()->{try{latencyGate(s,epoch,route);', 'completed-disable', 'Disabling before UI dispatch suppresses the old automatic notification'),
            ('manual-setting', 'automatic-gate', 'if(automatic&&', 'if(', 'manual', 'Manual latency still opens once when automatic latency is disabled'),
        ]
        for label, member, before, after, focus, assertion in mutations:
            if selected[member].count(before) != 1:
                raise ValueError('One exact current mutation hunk required: '+label)
            pristine = execute(classes, current_out, focus)
            if pristine.returncode:
                raise AssertionError('Pristine focused control failed: '+label+pristine.stderr)
            mutant_members = dict(selected)
            mutant_members[member] = mutant_members[member].replace(before, after, 1)
            mutant_classes, out = compile_members(mutant_members, 'mutant-'+label)
            mutant = execute(mutant_classes, out, focus)
            if mutant.returncode == 0 or 'AssertionError: '+assertion not in mutant.stderr:
                raise AssertionError('Precise behavioral mutation must fail: '+label+mutant.stderr)
            controls.append(dict(case=label, pristinePassed=True, mutantRejected=True, assertion=assertion))
    stable = all(digest(path) == hashes[str(path.relative_to(ROOT))] for path in inputs) and digest(args.json_jar) == jar_hash
    report.update(sourceFiles=hashes, jsonJarSha256=jar_hash, javaVersion=versions.strip(),
        executionInputsUnchanged=stable, negativeControls=controls,
        productionMembers=list(selected),
        boundaries=[
            'Actual AppPrefs inventory/enabled/values/apply and actual EnvironmentEditorUi checkbox/read loops execute with named preference/view boundaries.',
            'Actual NetworkRegion latencyRoute/cache filtering/proxy/gates/refreshLatency and NativeNetwork PROBE/freshLatency execute; Android type tokens become named Boundary types.',
            'Executor/handler and clocks are deterministic queues; the probe boundary counts invocations/open decisions and scripts one completion race, without sockets or native transport.',
            'SecretStore/cache publication and status projection are counted storage boundaries, not actual encrypted disk or Android execution.',
            'Public-HTTPS admission, network capabilities and session guard are explicitly scripted collaborators; no fake Android/Gecko SDK package is compiled.',
        ], scope='Actual user preference and automatic/manual external latency control flow at named JVM boundaries. No Android, Gecko, sockets, public geo service, native probe, release acceptance or wire execution claim.')
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'] if stable else 'source-changed', passed=report['passed'], negativeControls=len(controls), executionInputsUnchanged=stable, output=str(args.output))))
    if not stable:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
