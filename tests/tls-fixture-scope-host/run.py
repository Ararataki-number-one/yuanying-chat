#!/usr/bin/env python3
"""Execute the complete current TLS fixture scope and real desired timezone store.

Android Context/process/clock/AtomicFile, profile preparation/catalog and a plain
atomic file vault are explicit host boundaries. This is not Android/TLS proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

STUBS = {
    'android/content/Context.java': '''package android.content;
import java.io.*;
public class Context {
 public static String packageName="local.pocketchat.test";
 public String getPackageName(){return packageName;}
 public Context getApplicationContext(){return this;}
 public File getNoBackupFilesDir(){throw new UnsupportedOperationException("Explicit host context required");}
}
''',
    'android/app/Application.java': '''package android.app;
public class Application extends android.content.Context {
 public static String processName;
 public static String getProcessName(){return processName;}
}
''',
    'android/os/SystemClock.java': '''package android.os;
public final class SystemClock {public static long now=5000;public static long elapsedRealtime(){return now;}}
''',
    'android/util/AtomicFile.java': '''package android.util;
import java.io.*;import java.nio.file.*;
public final class AtomicFile {
 private final File file;
 public AtomicFile(File file){this.file=file;}
 public FileInputStream openRead()throws IOException{return new FileInputStream(file);}
 public FileOutputStream startWrite()throws IOException{file.getParentFile().mkdirs();return new FileOutputStream(new File(file+".new"));}
 public void finishWrite(FileOutputStream out)throws IOException{out.close();Files.move(new File(file+".new").toPath(),file.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
 public void failWrite(FileOutputStream out){try{out.close();}catch(Exception ignored){}new File(file+".new").delete();}
 public void delete(){file.delete();new File(file+".new").delete();new File(file+".bak").delete();}
}
''',
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', required=True, type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    app = ROOT / 'app/src/main/java/local/pocketchat'
    sources = [ROOT / 'tests/gecko/GeckoTlsFixtureScopes.java'] + [app / name for name in (
        'GeckoTimeZoneStore.java', 'GeckoTimeZoneSpec.java', 'GeckoTimeZonePolicy.java',
        'GeckoIpTimeZonePolicy.java', 'EnvironmentSpec.java', 'NetworkShareJson.java', 'J.java')]
    # Pin the original setup host without changing it or borrowing its pass count.
    preserved = [ROOT / 'tests/ip-timezone-fixture-setup-host' / name for name in ('run.py', 'Host.java.in', 'README.md')]
    inputs = sources + [HERE / 'Host.java.in', Path(__file__).resolve(), HERE / 'README.md'] + preserved
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    jar_before = sha(args.json_jar)
    mutants = [
        ('foreign-source', '!source.equals(build.getString("sourceCommit"))', 'false'),
        ('retained-user-preparse', 'systemSpec(value.getJSONObject("spec"));long revision=', 'long revision='),
        ('exact-process', '!android.app.Application.getProcessName().equals(context.getPackageName()+":profile"+slot)', 'false'),
        ('exact-activity', '!target.equals(context.getClass().getName())', 'false'),
        ('warm-claim', 'expectedClaim!=null&&!claim.equals(expectedClaim)', 'false'),
        ('case-replay', 'seen.size()>=256||!seen.add(caseNonce)', 'false'),
        ('explicit-clear', 'if(read(context,slot)!=null)', 'if(false)'),
        ('scope-not-native', '!Boolean.FALSE.equals(marker.opt("nativeAdmissionGranted"))', 'false'),
    ]
    negative = []
    with tempfile.TemporaryDirectory(prefix='tls-fixture-scope-host-') as temporary:
        base = Path(temporary)
        def execute(label, mutation=None):
            folder = base / label
            folder.mkdir()
            copied = []
            def write(name, text):
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
                copied.append(target)
            for name, text in STUBS.items():
                write(name, text)
            write('local/pocketchat/Host.java', (HERE / 'Host.java.in').read_text())
            for source in sources:
                text = source.read_text()
                if mutation and source.name == 'GeckoTlsFixtureScopes.java':
                    old, new = mutation
                    if text.count(old) != 1:
                        raise ValueError('Unique current semantic mutation required: ' + label)
                    text = text.replace(old, new, 1)
                write('local/pocketchat/' + source.name, text)
            compiled = subprocess.run([str(args.java_home / 'bin/javac'), '--release', '11', '-encoding', 'UTF-8',
                '-cp', str(args.json_jar.resolve()), '-d', str(folder / 'classes'), *map(str, copied)],
                text=True, capture_output=True, timeout=40)
            if compiled.returncode:
                raise RuntimeError('Actual current Java compile failed (' + label + '):\n' + compiled.stderr[-12000:])
            return subprocess.run([str(args.java_home / 'bin/java'), '-cp', str(folder / 'classes') + os.pathsep + str(args.json_jar.resolve()),
                'local.pocketchat.Host'], text=True, capture_output=True, timeout=40)
        current = execute('current')
        if current.returncode:
            raise RuntimeError(current.stdout + current.stderr)
        report = json.loads(current.stdout)
        for label, old, new in mutants:
            result = execute(label, (old, new))
            if result.returncode == 0 or 'AssertionError:' not in result.stderr:
                raise AssertionError('Compiled semantic false-proof escaped: ' + label + '\n' + result.stdout + result.stderr[-3000:])
            negative.append(dict(name=label, compileSucceeded=True, runtimeRejected=True,
                assertion=result.stderr.split('AssertionError:', 1)[1].splitlines()[0].strip()))
    stable = all(path.is_file() and sha(path) == before[str(path.relative_to(ROOT))] for path in inputs) and sha(args.json_jar) == jar_before
    report.update(schema=1, sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        sourceFiles=before, jsonJarSha256=jar_before, executionInputsUnchanged=stable, negativeControls=negative,
        originalIpSetupHostUnmodified=True, originalIpSetupHostExecuted=False,
        actualAndroidExecution=False, actualGeckoExecution=False, actualNativeTimezoneReadback=False,
        actualNetworkRequestsSent=False, actualColdRuntimeProven=False, actualAesKeystoreExecution=False,
        scope='Complete current GeckoTlsFixtureScopes, GeckoTimeZoneStore/Spec/Policy/IpPolicy, strict JSON/J and EnvironmentSpec. Real temporary files, FileLock, actual Store load/save CAS, strict record parsing and AtomicFile publication. Explicit host Context/process/clock, profile preparation/catalog and plain file vault collaborators. Original IP setup host is pinned only, not modified or credited. A fixture marker grants scope only: no native admission, Android lifecycle, TLS/wire, real vault encryption or cold-runtime proof.')
    if not stable:
        report['status'] = 'source-changed'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'passed', 'total', 'executionInputsUnchanged', 'actualAndroidExecution')}))
    if not stable:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
