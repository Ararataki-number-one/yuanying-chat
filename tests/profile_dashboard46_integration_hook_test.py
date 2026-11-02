"""An additional dashboard check preserves every existing workload and gate."""
import hashlib,unittest
from pathlib import Path
import ui_visual_preservation_contract as original

ROOT=Path(__file__).resolve().parents[1]
EXTRA="            subprocess.run(['python3', str(root/'tests/gecko/run_environment_dashboard.py'), '--adb', args.adb, '--serial', args.serial], check=True)\n"

def inverse(source):
    anchor=EXTRA+'            raise SystemExit(0)\n'
    assert source.count('tests/gecko/run_environment_dashboard.py')==source.count(anchor)==1,'Exactly one required dashboard check after the complete successful original quiet flow'
    assert hashlib.sha256(EXTRA.encode()).hexdigest()=='dd35ae5e488edfd8daa4a9c339fb2ceca9944bcb9641855ef4d21b076b4c6e91'
    result=source.replace(EXTRA,'',1)
    assert hashlib.sha256(result.encode()).hexdigest()=='72e6468c4a90b41deee4043e917ff5619eb32cc09aeedbd9d8243f1d77059760','Original complete quiet runner changed'
    return result

class DashboardIntegrationHook(unittest.TestCase):
    def test_original_ui_fixture_workflow_and_quiet_body_are_unchanged(self):
        inverse((ROOT/'tests/gecko/run_quiet_notifications.py').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'.github/workflows/gecko-integration.yml').read_bytes()).hexdigest(),'22f507ecac58d307a237b666460e74c4bd47804c56e9bdd8f3cfed64efcb1578')
        self.assertTrue(original.verify_shared_ui_source((ROOT/'tests/gecko/run_ui_visuals.py').read_text())['originalWorkloadSemanticsPreserved'])
        self.assertTrue(original.verify_download_visual_fixture_source((ROOT/'tests/gecko/UiVisualIntegrationActivity.java').read_bytes())['fourSyntheticRowsAndProductionRendererPreserved'])

    def test_removal_duplication_movement_or_original_workload_edits_reject(self):
        source=(ROOT/'tests/gecko/run_quiet_notifications.py').read_text()
        for value in (source.replace(EXTRA,''),source.replace(EXTRA,EXTRA*2),source.replace('check=True','check=False'),source.replace('deadline=time.monotonic()+120','deadline=time.monotonic()+121'),source.replace(EXTRA+'            raise SystemExit(0)\n','            raise SystemExit(0)\n'+EXTRA)):
            with self.assertRaises(AssertionError):inverse(value)

if __name__=='__main__':unittest.main(verbosity=2)
