"""The real publication copy block must retain the current native-proof reader.

These checks exercise an empty stage and isolated imports. They do not create
Android acceptance evidence or substitute for the driver's device execution.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from profile_release_navigation_v2_test import ROOT, stage_actual_reader_blocks


IMPORT_CURRENT = '''
import importlib, pathlib, sys
stage = pathlib.Path.cwd().resolve()
for directory in (stage, stage/'tools', stage/'tools/gecko'):
    sys.path.insert(0, str(directory))
names = ('chrome_collapse_contract_v3', 'ui_hierarchy_driver')
for prefix in ('tools.gecko.', 'gecko.', ''):
    for name in names:
        module = importlib.import_module(prefix + name)
        assert pathlib.Path(module.__file__).resolve().is_relative_to(stage)
    contract = importlib.import_module(prefix + names[0])
    driver = importlib.import_module(prefix + names[1])
    assert contract.hierarchy_driver is driver
print('current native hierarchy proof reader imports from actual release stage')
'''


class HierarchyReleaseStaging(unittest.TestCase):
    def probe(self, stage):
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        return subprocess.run([sys.executable, '-I', '-c', IMPORT_CURRENT], cwd=stage,
                              env=environment, text=True, capture_output=True, timeout=30)

    def test_actual_copy_block_keeps_exact_current_readers_in_an_empty_stage(self):
        with tempfile.TemporaryDirectory(prefix='hierarchy-release-stage-') as temporary:
            stage = Path(temporary)
            stage_actual_reader_blocks(stage)
            for name in ('chrome_collapse_contract_v3.py', 'ui_hierarchy_driver.py'):
                self.assertEqual((stage/'tools/gecko'/name).read_bytes(),
                                 (ROOT/'tools/gecko'/name).read_bytes())
            result = self.probe(stage)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('actual release stage', result.stdout)

    def test_missing_native_reader_cannot_import_from_the_source_checkout(self):
        with tempfile.TemporaryDirectory(prefix='hierarchy-release-missing-') as temporary:
            stage = Path(temporary)
            stage_actual_reader_blocks(stage)
            (stage/'tools/gecko/ui_hierarchy_driver.py').unlink()
            result = self.probe(stage)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn('ui_hierarchy_driver', result.stderr)
            self.assertRegex(result.stderr, 'ImportError|ModuleNotFoundError')


if __name__ == '__main__':
    unittest.main()
