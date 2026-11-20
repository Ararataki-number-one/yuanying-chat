#!/usr/bin/env python3
"""Run production environment editor persistence against synthetic transaction/preference adapters."""
import argparse
import importlib.util
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROD = ROOT / 'app/src/main/java/local/pocketchat'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-jar', required=True, type=pathlib.Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('editor_members', ROOT / 'tests/default-environment-host/run.py')
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    editor = (PROD / 'EnvironmentEditorUi.java').read_text()
    preferences = (PROD / 'AppPrefs.java').read_text()
    editor_members = [
        'static boolean validMetadata(', 'static EnvironmentSpec.Identity editorIdentity(', 'static boolean editorCurrent(',
        'static void unavailable(', 'static void saveFailed(', 'static boolean applyNative(',
        'static boolean apply(MainActivity a,JSONObject value,EditText name)', 'static boolean archiveEditorDraft(']
    preference_members = [
        'static final String[] KEYS=', 'static boolean enabled(',
        'static boolean apply(', 'static SharedPreferences.Editor edit(']
    prefs = preferences[preferences.index(preference_members[0]):].split('\n', 1)[0]
    prefs += '\n' + '\n'.join(extractor.member(preferences, name) for name in preference_members[1:])
    fixture = (HERE / 'EnvironmentEditorSaveHost.java').read_text()
    fixture = fixture.replace('/* EDITOR_MEMBERS */', '\n'.join(extractor.member(editor, name) for name in editor_members))
    fixture = fixture.replace('/* PREFS_MEMBERS */', prefs)
    with tempfile.TemporaryDirectory(prefix='environment-editor-save-host-') as raw:
        root = pathlib.Path(raw)
        source = root / 'EnvironmentEditorSaveHost.java'
        source.write_text(fixture)
        jar = str(args.json_jar.resolve())
        subprocess.run(['javac', '-cp', jar, '-encoding', 'UTF-8', '-d', str(root), str(source),
                        str(PROD / 'BrowserEditIntent.java')], check=True)
        args = ['java', '-cp', str(root) + ':' + jar, 'local.pocketchat.EnvironmentEditorSaveHost']
        raise SystemExit(subprocess.run(args, check=False).returncode)

if __name__ == '__main__':
    main()
