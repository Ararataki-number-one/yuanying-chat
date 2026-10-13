#!/usr/bin/env python3
"""Build a tainted, integration-only log witness from the pinned official SDK.

This is not an SDK fix. DEBUG, input predicates, dispatch, and native libraries
remain unchanged. The resulting AAR must never satisfy official release gates.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = '1f970ea51f90466fb69fc282692ecb535c38ce64'
CLASS = 'org/mozilla/geckoview/GeckoEditable'
SOURCE = CLASS + '.java'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def exactly(source, before, after, count=1):
    if source.count(before) != count:
        raise ValueError('Official source anchor changed: ' + before[:100])
    return source.replace(before, after)


def transform(source):
    # Each existing LOGGING block only constructs and emits a log message.
    # DEBUG stays false: in particular, no IC wrapper/debug proxy is enabled.
    source = exactly(source, 'private static final boolean LOGGING = BuildConfig.NIGHTLY_BUILD;',
                     'private static final boolean LOGGING = true;')
    source = source.replace('MozLog.d(MOZLOGTAG,', 'diagnosticLog(MOZLOGTAG,')
    helper = '''
  // DIAGNOSTIC ONLY: logs do not replace the IC, listener, or native delegate.
  private static final AtomicInteger DIAGNOSTIC_SEQUENCE = new AtomicInteger();
  private static void diagnosticLog(final String module, final String message) {
    Log.d("PocketSDKIME", "seq=" + DIAGNOSTIC_SEQUENCE.incrementAndGet()
        + " uptimeMs=" + SystemClock.uptimeMillis()
        + " threadId=" + Thread.currentThread().getId() + " " + message);
  }
  private static void diagnosticReplace(final Action action, final int start, final int end) {
    diagnosticLog(MOZLOGTAG, "outboundReplace actionId=" + System.identityHashCode(action)
        + " start=" + start + " end=" + end + " length=" + action.mSequence.length()
        + " charCode=" + (action.mSequence.length() == 1 ? (int) action.mSequence.charAt(0) : -1));
  }
'''
    source = exactly(source, '  private static final long DISMISS_VKB_DELAY_MS = 100;',
                     helper + '\n  private static final long DISMISS_VKB_DELAY_MS = 100;')
    source = exactly(source,
        '          mFocusedChild.onImeReplaceText(action.mStart, action.mEnd, action.mSequence.toString());',
        '          diagnosticReplace(action, action.mStart, action.mEnd);\n'
        '          mFocusedChild.onImeReplaceText(action.mStart, action.mEnd, action.mSequence.toString());')
    source = exactly(source,
        '        mFocusedChild.onImeReplaceText(actionStart, actionEnd, action.mSequence.toString());',
        '        diagnosticReplace(action, actionStart, actionEnd);\n'
        '        mFocusedChild.onImeReplaceText(actionStart, actionEnd, action.mSequence.toString());')
    source = exactly(source,
        '    if (LOGGING) {\n      final StringBuilder sb = new StringBuilder("reply: action=");',
        '    diagnosticLog(MOZLOGTAG, "nativeAck actionId=" + System.identityHashCode(action)\n'
        '        + " action=" + action.toString() + " ignoreSelection=" + mIgnoreSelectionChange);\n'
        '    if (LOGGING) {\n      final StringBuilder sb = new StringBuilder("reply: action=");')
    source = exactly(source,
        '    if (mIgnoreSelectionChange) {\n      mIgnoreSelectionChange = false;',
        '    diagnosticLog(MOZLOGTAG, "nativeSelectionAccepted start=" + start + " end=" + end\n'
        '        + " ignored=" + mIgnoreSelectionChange + " compositionOnly=" + causedOnlyByComposition);\n'
        '    if (mIgnoreSelectionChange) {\n      mIgnoreSelectionChange = false;')
    if 'private static final boolean DEBUG = false;' not in source:
        raise ValueError('DEBUG changed')
    return source


def class_members(jar, name):
    raw = command('javap', '-classpath', str(jar), '-p', '-s', '-constants', name)
    result = {}
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        if index + 1 >= len(lines) or not lines[index + 1].strip().startswith('descriptor:'):
            continue
        member = line.strip()
        if member.startswith('private static final boolean LOGGING '):
            member = re.sub(r' = (true|false);$', ';', member)
        result[member] = lines[index + 1].strip()
    return result


def rewrite_archive(original, destination, replacements):
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(destination, 'w') as target:
        for entry in source.infolist():
            data = replacements.get(entry.filename)
            if data is None:
                data = source.read(entry.filename)
            target.writestr(entry, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['aar', 'sources', 'output', 'receipt', 'classpath-json']:
        parser.add_argument('--' + name, required=True, type=pathlib.Path)
    args = parser.parse_args()
    pinned = json.loads((ROOT / 'third-party/sdk/geckoview-157.0.1-official.json').read_text())
    aar_hash = digest(args.aar.read_bytes())
    sources_hash = digest(args.sources.read_bytes())
    if aar_hash != pinned['aar']['sha256'] or sources_hash != pinned['sources']['sha256']:
        raise ValueError('Diagnostic input is not the pinned official SDK')
    classpath = json.loads(args.classpath_json.read_text())
    source_commit = command('git', '-C', str(ROOT), 'rev-parse', 'HEAD').strip()
    if command('git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=normal').strip():
        raise ValueError('SDK diagnostic compilation requires a clean committed source tree')
    if source_commit != classpath['sourceCommit']:
        raise ValueError('Classpath receipt belongs to another source')
    if args.output.resolve() == args.aar.resolve():
        raise ValueError('Never overwrite the official AAR')
    if digest(pathlib.Path(classpath['androidJar']).read_bytes()) != classpath['androidJarSha256']:
        raise ValueError('Android compile API changed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ime-writer-compile-', dir=args.output.parent) as temporary:
        temporary = pathlib.Path(temporary)
        with zipfile.ZipFile(args.aar) as archive:
            official_jar = temporary / 'official-classes.jar'
            official_jar.write_bytes(archive.read('classes.jar'))
        if digest(official_jar.read_bytes()) != pinned['classesJarSha256']:
            raise ValueError('Official classes.jar mismatch')
        with zipfile.ZipFile(args.sources) as archive:
            original = archive.read(SOURCE)
        if digest(original) != pinned['geckoEditableSourceSha256']:
            raise ValueError('Official GeckoEditable source mismatch')
        modified = transform(original.decode())
        java_file = temporary / 'source' / SOURCE
        java_file.parent.mkdir(parents=True)
        java_file.write_text(modified)
        compile_paths = [official_jar, pathlib.Path(classpath['androidJar'])]
        for index, item in enumerate(classpath['artifacts']):
            path = pathlib.Path(item['path'])
            if digest(path.read_bytes()) != item['sha256']:
                raise ValueError('Verified compile dependency changed: ' + str(path))
            if path.suffix == '.aar':
                with zipfile.ZipFile(path) as archive:
                    if 'classes.jar' not in archive.namelist():
                        continue
                    extracted = temporary / ('dependency-' + str(index) + '.jar')
                    extracted.write_bytes(archive.read('classes.jar'))
                    compile_paths.append(extracted)
            else:
                compile_paths.append(path)
        compiled = temporary / 'compiled'
        compiled.mkdir()
        javac_output = command('javac', '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                               '-proc:none', '-classpath', ':'.join(map(str, compile_paths)),
                               '-d', str(compiled), str(java_file))
        replacements = {str(path.relative_to(compiled)): path.read_bytes()
                        for path in compiled.rglob('*.class')}
        with zipfile.ZipFile(official_jar) as archive:
            expected = {name for name in archive.namelist()
                        if name == CLASS + '.class' or name.startswith(CLASS + '$') and name.endswith('.class')}
        if set(replacements) != expected:
            raise ValueError('Recompile emitted a different GeckoEditable class family')
        diagnostic_jar = temporary / 'diagnostic-classes.jar'
        rewrite_archive(official_jar, diagnostic_jar, replacements)
        for name in sorted(expected):
            java_name = name[:-6].replace('/', '.')
            before, after = class_members(official_jar, java_name), class_members(diagnostic_jar, java_name)
            if any(after.get(member) != descriptor for member, descriptor in before.items()):
                raise ValueError('Original Java/native member shape changed: ' + name)
            added = set(after) - set(before)
            if (name != CLASS + '.class' and added) or any('DIAGNOSTIC_SEQUENCE' not in x and 'diagnosticLog(' not in x and 'diagnosticReplace(' not in x for x in added):
                raise ValueError('Unexpected additional Java members: ' + name)
        dump = command('javap', '-classpath', str(diagnostic_jar), '-p', '-constants', CLASS.replace('/', '.'))
        if 'private static final boolean DEBUG = false;' not in dump:
            raise ValueError('Compiled DEBUG must remain false')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        rewrite_archive(args.aar, args.output, {'classes.jar': diagnostic_jar.read_bytes()})
        with zipfile.ZipFile(args.aar) as before, zipfile.ZipFile(args.output) as after:
            if before.namelist() != after.namelist():
                raise ValueError('AAR entry inventory changed')
            native = {}
            for name in before.namelist():
                if name != 'classes.jar' and before.read(name) != after.read(name):
                    raise ValueError('Non-class AAR bytes changed: ' + name)
                if name.startswith('jni/') and not name.endswith('/'):
                    native[name] = digest(before.read(name))
        receipt = dict(schema=1, diagnosticOnly=True, releaseAcceptance=False,
            sdkInputWriterDiagnosticsEnabled=True, sourceCommit=source_commit,
            sourceTree=command('git', '-C', str(ROOT), 'rev-parse', 'HEAD^{tree}').strip(), baseSourceCommit=BASE,
            sdkCoordinate=pinned['coordinate'], officialAarSha256=aar_hash,
            officialSourcesSha256=sources_hash, officialClassesJarSha256=pinned['classesJarSha256'],
            officialGeckoEditableSourceSha256=digest(original),
            modifiedGeckoEditableSourceSha256=digest(modified.encode()),
            diagnosticAarSha256=digest(args.output.read_bytes()),
            diagnosticClassesJarSha256=digest(diagnostic_jar.read_bytes()),
            sourceTransformPath=str(pathlib.Path(__file__).resolve().relative_to(ROOT)),
            sourceTransformSha256=digest(pathlib.Path(__file__).read_bytes()),
            nativeArchivesIdentical=True, nativeArchiveSha256=native, javaApiIdentical=True,
            debugFalsePreserved=True, inputBehaviorChanged=False,
            transformedClassFiles=sorted(expected),
            loggingOnlyChanges=['Enable existing LOGGING blocks and route them to Android logcat',
                'Record actual ranges immediately before both unchanged onImeReplaceText calls',
                'Record action identity at native ACK and accepted native selection callback'],
            javacVersion=command('javac', '-version').strip(), javacOutput=javac_output,
            scope='Tainted log-only Java SDK diagnostic. Native libraries, input predicates, IC, delegates and burst are unchanged. Not official SDK or release acceptance.')
        args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'diagnosticOnly': True, 'releaseAcceptance': False,
                          'diagnosticAarSha256': receipt['diagnosticAarSha256'],
                          'receipt': str(args.receipt)}))


if __name__ == '__main__':
    main()
