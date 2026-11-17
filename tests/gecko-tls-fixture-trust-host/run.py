#!/usr/bin/env python3
"""Compile and execute the actual integration-only import protocol, never native evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', type=Path, required=True)
    parser.add_argument('--json-jar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = [ROOT/'tests/gecko/GeckoTlsFixtureTrustState.java', Path(__file__).with_name('TrustStateHost.java')]
    before = {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    jar = args.json_jar.resolve()
    if not jar.is_file(): raise ValueError('Actual host JSON dependency required')
    with tempfile.TemporaryDirectory(prefix='tls-trust-host-') as directory:
        command = [str(args.java_home/'bin/javac'), '-encoding', 'UTF-8', '--release', '17',
                   '-cp', str(jar), '-d', directory, *map(str, sources)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        executed = None
        if compiled.returncode == 0:
            executed = subprocess.run([str(args.java_home/'bin/java'), '-cp', directory+':'+str(jar),
                                       'local.pocketchat.TrustStateHost'], capture_output=True, text=True)
    stable = all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in before.items())
    result = json.loads(executed.stdout) if executed is not None and executed.returncode == 0 else None
    passed = stable and compiled.returncode == 0 and executed is not None and executed.returncode == 0 and result['status']=='passed'
    receipt = dict(status='passed' if passed else 'failed', sourceFiles=before, executionInputsUnchanged=stable,
        jsonJarSha256=hashlib.sha256(jar.read_bytes()).hexdigest(), compileExitCode=compiled.returncode,
        compileStdout=compiled.stdout, compileStderr=compiled.stderr,
        runtimeExitCode=executed.returncode if executed else None, runtimeStdout=executed.stdout if executed else '',
        runtimeStderr=executed.stderr if executed else '', result=result, actualAndroidExecution=False, actualGeckoExecution=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    return 0 if passed else 1


if __name__ == '__main__': raise SystemExit(main())
