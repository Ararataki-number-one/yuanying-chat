"""Add exact formal45 input availability without editing old history oracles."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dashboard46_history_preparer',ROOT/'tests/gecko/prepare_dashboard46_history.py')
preparation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)
# Discovery imports every module before executing original source-oracle tests.
PREPARED=preparation.prepare_dashboard_history(ROOT)

class DashboardHistoryPreparation(unittest.TestCase):
    def test_exact_original_three_and_formal45_fourth_group(self):
        self.assertEqual([len(row['files']) for row in PREPARED['groups']],[3,9,12,14])
        self.assertEqual(preparation.DASHBOARD_GROUP[:2],('e15147246ceff2e1ed2ffd9a18df1fd17b03ddee','cbb37b32ad11ec52bc91216185a033bf1d475e08'))
        self.assertFalse(PREPARED['originalAssertionsExecuted'])
        self.assertFalse(PREPARED['actualAndroidExecution'])

    def test_missing_fourth_group_cannot_fetch_in_an_unowned_local_context(self):
        real=preparation.history.verify_group
        def verify(root,group):
            if group[0]==preparation.DASHBOARD_GROUP[0]:raise preparation.history.MissingHistoricalInput('controlled missing input')
            return real(root,group)
        with patch.object(preparation.history,'verify_group',side_effect=verify):
            with self.assertRaises(RuntimeError):preparation.prepare_dashboard_history(ROOT,{})

if __name__=='__main__':unittest.main(verbosity=2)
