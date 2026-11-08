"""Host regression for preserving raw pre-IME and fresh hierarchy identities.

The XML bytes are the unchanged failed 06a802 Android observations. The IME
window and clock are explicit host models, not evidence of a new device run.
"""
import ast
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import glass_ui_validation as glass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Transport:
    def __init__(self, value, fail_input=False):
        self.value = value
        self.now = 100.0
        self.taps = []
        self.fail_input = fail_input

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def adb(self, *parts, **kwargs):
        self.now += .02
        if parts == ('shell', 'dumpsys', 'input_method'):
            return b'  mInputShown=true\n'
        if parts == ('shell', 'dumpsys', 'window', 'displays'):
            return b'  InsetsSource id=3 type=ime frame=[0,1371][960,2220] visible=true\n'
        raise AssertionError(parts)

    def read(self, deadline=None):
        self.now += .02
        return self.value

    def tap(self, node, reason):
        self.taps.append((node.get('bounds'), reason))
        if self.fail_input:
            raise ValueError('Host fault after the only input injection')


class KeyboardArtifactIdentityTest(unittest.TestCase):
    def setUp(self):
        fixtures = ROOT / 'tests/fixtures'
        self.early = (fixtures / 'glass-keyboard-narrow-before.xml').read_bytes()
        self.fresh = (fixtures / 'glass-keyboard-narrow-after.xml').read_bytes()
        self.assertEqual(hashlib.sha256(self.early).hexdigest(),
                         'b216dc3ef0c9d34185353b8c20468aa603dd2ee65be46b06149e898e841913d6')
        self.assertEqual(hashlib.sha256(self.fresh).hexdigest(),
                         '59024e96a4ec25488f41e77bc4ff313421ccd47585ced440f36b1265110803f2')

    def acquire(self, out, stem, model):
        with mock.patch.object(glass.time, 'monotonic', model.monotonic), \
                mock.patch.object(glass.time, 'sleep', model.sleep):
            return glass.cancel_keyboard_editor(capture=model, adb=model.adb, tap=model.tap,
                out=out, stem=stem, width=960, height=2220, density=480, sha=digest,
                predicate=lambda value: '打开网址' in value and '取消' in value, deadline=130.0)

    def test_real_early_scene_and_its_digest_survive_stable_fresh_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            scene = out / 'default-light-url-keyboard.xml'
            scene.write_bytes(self.early)
            original = dict(file=scene.name, sha256=digest(scene))
            model = Transport(self.fresh.decode())
            result = self.acquire(out, scene.stem, model)
            self.assertEqual(scene.read_bytes(), self.early)
            self.assertEqual(digest(scene), original['sha256'])
            self.assertEqual(len(model.taps), 1)
            self.assertEqual(result['hierarchy'], result['attempts'][-1]['hierarchy'])
            self.assertEqual(result['hierarchy']['file'],
                             'default-light-url-keyboard-keyboard-fresh-2.xml')
            self.assertNotEqual(result['hierarchy']['file'], original['file'])
            self.assertEqual((out / result['hierarchy']['file']).read_bytes(), self.fresh)
            for record in [original, result['hierarchy']]:
                self.assertEqual(digest(out / record['file']), record['sha256'])
            for row in result['attempts']:
                for key in ('inputMethod', 'window', 'hierarchy'):
                    self.assertEqual(digest(out / row[key]['file']), row[key]['sha256'])

    def test_two_configuration_stems_keep_separate_original_and_fresh_raw_files(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            finals = []
            for stem in ('default-light-url-keyboard', 'narrow-light-url-keyboard'):
                original = out / (stem + '.xml')
                original.write_bytes(self.early)
                result = self.acquire(out, stem, Transport(self.fresh.decode()))
                self.assertEqual(original.read_bytes(), self.early)
                finals.append(result['hierarchy']['file'])
            self.assertEqual(len(set(finals)), 2)
            self.assertTrue(all((out / name).read_bytes() == self.fresh for name in finals))

    def test_input_failure_does_not_overwrite_original_scene_or_replay_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            scene = out / 'default-light-url-keyboard.xml'
            scene.write_bytes(self.early)
            model = Transport(self.fresh.decode(), fail_input=True)
            with self.assertRaisesRegex(ValueError, 'after the only input'):
                self.acquire(out, scene.stem, model)
            self.assertEqual(scene.read_bytes(), self.early)
            self.assertEqual(len(model.taps), 1)
            self.assertEqual(len(list(out.glob('*-keyboard-fresh-*.xml'))), 2)

    def test_actual_interaction_keeps_original_scene_observation_immutable(self):
        tree = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())
        suite = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'capture_acceptance_suite')
        interaction = next(node for node in ast.walk(suite) if isinstance(node, ast.FunctionDef)
                           and node.name == 'interactions')
        # This used to change only the case digest while the independent
        # navigationGeometryObservations still referred to the overwritten XML.
        for node in ast.walk(interaction):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                target = ast.unparse(node.func.value)
                self.assertFalse(node.func.attr == 'update'
                    and target == "case['observations']['url-keyboard']")
        calls = [node for node in ast.walk(interaction) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'cancel_keyboard_editor']
        self.assertEqual(len(calls), 1)
        self.assertEqual(ast.unparse(next(k.value for k in calls[0].keywords if k.arg == 'stem')),
                         "case['name'] + '-url-keyboard'")


if __name__ == '__main__':
    unittest.main()
