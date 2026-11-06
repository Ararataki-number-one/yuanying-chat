#!/usr/bin/env python3
"""Actual fixture startup method and CPU filesystem policy; modeled Android/UI only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(text, signature):
    start = text.index(signature)
    line = text.rfind('\n', 0, start) + 1
    opening = text.index('{', start)
    depth = 0
    quote = None
    escaped = False
    comment = None
    index = opening
    while index < len(text):
        char = text[index]
        pair = text[index:index + 2]
        if comment == '//':
            if char == '\n':
                comment = None
        elif comment == '/*':
            if pair == '*/':
                comment = None
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif pair in ('//', '/*'):
            comment = pair
            index += 1
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[line:index + 1]
        index += 1
    raise ValueError('Unclosed actual Java declaration: ' + signature)


STUBS = {
    'android/content/pm/ApplicationInfo.java': 'package android.content.pm;public final class ApplicationInfo{public String dataDir;}',
    'android/content/Context.java': '''package android.content;public abstract class Context {
      public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();
      public abstract android.content.pm.ApplicationInfo getApplicationInfo();public abstract SharedPreferences getSharedPreferences(String name,int mode); }''',
    'android/content/ContextWrapper.java': '''package android.content;public class ContextWrapper extends Context {
      private final Context base;public ContextWrapper(Context base){this.base=base;}public Context getBaseContext(){return base;}
      public Context getApplicationContext(){return base.getApplicationContext();}public java.io.File getNoBackupFilesDir(){return base.getNoBackupFilesDir();}
      public android.content.pm.ApplicationInfo getApplicationInfo(){return base.getApplicationInfo();}
      public SharedPreferences getSharedPreferences(String name,int mode){return base.getSharedPreferences(name,mode);} }''',
    'android/content/SharedPreferences.java': '''package android.content;public final class SharedPreferences {
      public Editor edit(){return new Editor();}public static final class Editor {public Editor putString(String k,String v){return this;}
      public Editor putBoolean(String k,boolean v){return this;}public Editor putInt(String k,int v){return this;}public boolean commit(){return true;}}}''',
    'android/app/Activity.java': '''package android.app;public class Activity extends android.content.ContextWrapper {
      public Object content;public Activity(android.content.Context context){super(context);}public void setContentView(Object value){content=value;} }''',
    'android/app/Application.java': 'package android.app;public final class Application {public static String process;public static String getProcessName(){return process;}}',
    'android/os/Build.java': 'package android.os;public final class Build {public static final class VERSION{public static final int SDK_INT=35;}}',
    'android/widget/LinearLayout.java': '''package android.widget;public final class LinearLayout {
      public static final int VERTICAL=1;public LinearLayout(android.content.Context c){}public void setOrientation(int v){}public void addView(Object child,Object...params){}
      public static final class LayoutParams{public LayoutParams(int w,int h,float weight){}} }''',
    'android/widget/TextView.java': 'package android.widget;public final class TextView{public TextView(android.content.Context c){}public void setText(String value){}}',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', required=True, type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    app = ROOT / 'app/src/main/java/local/pocketchat'
    fixture_path = ROOT / 'tests/gecko/GeckoIdentityPrototypeIntegrationActivity.java'
    related_paths = [ROOT / 'tests/gecko' / (name + '.java') for name in ('FingerprintFollowupIntegrationActivity', 'NetworkProtectionIntegrationActivity')]
    source_paths = [fixture_path, app / 'Profiles.java', app / 'ProfileContext.java']
    production = [app / name for name in ('GeckoCpuProfile.java', 'GeckoCpuSpec.java', 'GeckoTimeZoneSpec.java', 'J.java')]
    inputs = source_paths + related_paths + production + [Path(__file__), HERE / 'Host.java.in']
    before = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    fixture, profiles, profile_context = [path.read_text() for path in source_paths]
    methods = {
        'openBrowser': declaration(fixture, 'void openBrowser()'),
        'PrivateContext': declaration(fixture, 'static final class PrivateContext'),
    }
    for key, path, signature in zip(('followupContext', 'protectionContext'), related_paths, ('void open()', 'void openBrowser()')):
        method = declaration(path.read_text(), signature)
        matches = re.findall(r'Context context=[^;]+;', method)
        if len(matches) != 1:
            raise ValueError('Expected exactly one actual fixture context declaration')
        methods[key] = matches[0]
    profiles_methods = '\n'.join(declaration(profiles, signature) for signature in
        ('static int processSlot()', 'static int slot(', 'static Context global(', 'static Context context('))
    context_methods = '\n'.join(declaration(profile_context, signature) for signature in
        ('@Override public Context getApplicationContext()', 'File directory(', '@Override public File getNoBackupFilesDir()'))
    template = (HERE / 'Host.java.in').read_text()
    actual = template.replace('@@OPEN_BROWSER@@', methods['openBrowser']).replace('@@PRIVATE_CONTEXT@@', methods['PrivateContext']).replace('@@PROFILES_METHODS@@', profiles_methods).replace('@@PROFILE_CONTEXT_METHODS@@', context_methods)
    actual = actual.replace('@@FOLLOWUP_CONTEXT@@', methods['followupContext']).replace('@@PROTECTION_CONTEXT@@', methods['protectionContext'])
    actual = actual.replace('import android.app.Activity;', 'import android.app.Activity;\nimport android.os.Build;')
    def execute(work, name, text):
        directory = work / name
        directory.mkdir()
        host = directory / 'FixtureRootHost.java'
        host.write_text(text)
        stubs = []
        for relative, content in STUBS.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content + '\n')
            stubs.append(path)
        classes = directory / 'classes'
        command = [str(args.java_home / 'bin/javac'), '-source', '8', '-target', '8', '-encoding', 'UTF-8', '-cp', str(args.json_jar), '-d', str(classes), *map(str, production + stubs + [host])]
        result = subprocess.run(command, text=True, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError(name + ' compilation failed: ' + result.stderr)
        result = subprocess.run([str(args.java_home / 'bin/java'), '-cp', str(classes) + ':' + str(args.json_jar), 'local.pocketchat.FixtureRootHost', str(directory / 'files')], text=True, capture_output=True, timeout=30)
        return result
    with tempfile.TemporaryDirectory(prefix='fixture-framework-root-') as temporary:
        work = Path(temporary)
        result = execute(work, 'current', actual)
        if result.returncode:
            raise RuntimeError(result.stderr)
        report = json.loads(result.stdout)
        old = 'Profiles.context(getApplicationContext(),Profiles.processSlot())'
        if actual.count(old) != 3:
            raise ValueError('Actual context selection must occur exactly once in each of three entries')
        controls = []
        scenarios = [('original-nested-wrapper', actual.replace(old, 'new PrivateContext(getApplicationContext())', 1), 'Actual fixture startup admits the anchored framework profile slot 0'),
            ('foreign-profile-slot', actual.replace(old, 'Profiles.context(getApplicationContext(),1)', 1), 'Actual fixture passes the selected profile to ChatSession slot 0')]
        for key, label in [('followupContext', 'followup'), ('protectionContext', 'protection')]:
            declaration_text = '  Context ' + key + '(){' + methods[key]
            if actual.count(declaration_text) != 1:
                raise ValueError('Actual related declaration is not unique')
            scenarios.append((label + '-nested-wrapper', actual.replace(declaration_text, declaration_text.replace(old, 'new PrivateContext(getApplicationContext())'), 1), 'Actual ' + label + ' entry declaration uses the owned profile'))
        for name, counterfeit, expected in scenarios:
            result = execute(work, name, counterfeit)
            if result.returncode == 0 or expected not in result.stderr:
                raise AssertionError('Actual context-selection semantic counterfeit escaped: ' + name + '\n' + result.stderr)
            controls.append({'name': name, 'actualCompilation': True, 'rejectedByActualAssertion': True, 'stderr': result.stderr})
    stable = all(sha(ROOT / relative) == digest for relative, digest in before.items())
    if not stable:
        raise AssertionError('Execution sources changed')
    report.update(schema=1, sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), sourceFiles=before,
        methodSha256={name: hashlib.sha256(value.encode()).hexdigest() for name, value in methods.items()},
        jsonJarSha256=sha(args.json_jar), executionInputsUnchanged=True, compiledCounterfeits=controls,
        scope='Verbatim actual prototype openBrowser/old wrapper, actual context declarations from followup/protection entries, Profiles selection/global/slot/process and selected ProfileContext accessors; full current CPU filesystem profile policy/spec and timezone spec. Android Activity/UI/session/catalog collaborators and separate cleared-package invocation roots are explicit models; related-entry callbacks are not executed. Real files/AtomicMove. No Gecko runtime, native CPU/TLS/TZ acknowledgement, Android or public-IP execution.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'passed': report['passed'], 'compiledCounterfeits': len(controls), 'executionInputsUnchanged': stable}))


if __name__ == '__main__':
    main()
