"""An additional dashboard check preserves every existing workload and gate."""
import hashlib,unittest
from pathlib import Path
from historical_source_inputs import historical_bytes
import ui_visual_preservation_contract as original

ROOT=Path(__file__).resolve().parents[1]
EXTRA="            subprocess.run(['python3', str(root/'tests/gecko/run_environment_dashboard.py'), '--adb', args.adb, '--serial', args.serial], check=True)\n"

# Test-only source restoration: the actual current runner must execute its
# browser notification contract, never these retired completion assertions.
BROWSER_QUIET_CHANGE = {'previous': (4465, 'f989851909c61f2d59db4fe605694d4c19fba50bd20b209b2ad85f838af9af7a'),
 'current': (3266, '1ecc1fb85660cd9ceacdcaf1f73c9bd6ae9bcfa73a97595bf9968457203d562c'),
 'deltas': [('#!/usr/bin/env python3\n'
             '"""Verify real Android notification channels and production service behavior."""\n'
             'import argparse,json,pathlib,subprocess,time,sys\n'
             '\n'
             'root=pathlib.Path(__file__).resolve().parents[2]\n'
             "sys.path.insert(0,str(root/'tools/gecko'))\n"
             'from browser_observation_contract_v2 import verify_browser_notifications\n'
             "out=root/'work/gecko-integration'\n"
             'out.mkdir(parents=True,exist_ok=True)\n'
             'for stale in '
             "['quiet-notification-results.json','quiet-notification-failure-log.txt']:(out/stale).unlink(missing_ok=True)\n",
             '#!/usr/bin/env python3\n'
             '"""Verify real Android notification channels and production service behavior."""\n'
             'import argparse,json,pathlib,subprocess,time\n'
             '\n'
             'root=pathlib.Path(__file__).resolve().parents[2]\n'
             "out=root/'work/gecko-integration'\n"
             'out.mkdir(parents=True,exist_ok=True)\n'
             'for stale in '
             "['quiet-notification-results.json','quiet-notification-failure-log.txt']:(out/stale).unlink(missing_ok=True)\n"),
            ('            '
             "result['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()\n"
             '            '
             "(out/'quiet-notification-results.json').write_text(json.dumps(result,indent=2)+'\\n')\n"
             '            print(json.dumps(result,indent=2),flush=True)\n'
             '            verify_browser_notifications(result)\n'
             "            foreground,home=result['foregroundEvidence'],result['homeEvidence']\n"
             "            assert foreground['known'] and foreground['foreground'] and any(row['visible'] and "
             "row['process']==package+':profile7' for row in foreground['processes']),foreground\n"
             "            assert home['known'] and not home['foreground'] and all(not row['visible'] for row "
             "in home['processes']),home\n",
             '            '
             "result['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()\n"
             '            '
             "(out/'quiet-notification-results.json').write_text(json.dumps(result,indent=2)+'\\n')\n"
             '            print(json.dumps(result,indent=2),flush=True)\n'
             "            assert result['status']=='passed' and result['actualAndroidExecution'] and "
             "result['checkCount']==len(checks) and len(checks)>=35 and all(c['pass'] for c in "
             "result['checks']),result\n"
             '            required={\n'
             "                'Background completion reminders are off by default',\n"
             "                'Browser and network child processes cannot count as visible UI',\n"
             "                'Foreground replies and downloads stay quiet even after opting in',\n"
             "                'Real Home leaves the UI in background while required services keep running',\n"
             "                'Background completion stays quiet until the user opts in',\n"
             "                'Foreground completions never become delayed background alerts',\n"
             "                'Opted-in background file completion opens the exact saved task',\n"
             "                'The notified local file is fully published and readable',\n"
             "                'Opting out removes completion cards across environments',\n"
             "                'A visible Activity is proved by real started lifecycle count',\n"
             "                'A private visibility endpoint rejects an obsolete process PID',\n"
             "                'An already running default process exposes real zero-Activity lifecycle over "
             "private IPC',\n"
             "                'Real Home is proved by stopped Activity lifecycle despite browser process "
             "priority',\n"
             '            }\n'
             '            assert required<=set(checks),result\n'
             "            foreground,home=result['foregroundEvidence'],result['homeEvidence']\n"
             "            assert foreground['known'] and foreground['foreground'] and any(row['visible'] and "
             "row['process']==package+':profile7' for row in foreground['processes']),foreground\n"
             "            assert home['known'] and not home['foreground'] and all(not row['visible'] for row "
             "in home['processes']),home\n")]}

def browser_quiet_input(source):
    raw=source.encode()
    item=BROWSER_QUIET_CHANGE
    identity=(len(raw),hashlib.sha256(raw).hexdigest())
    if identity==item["previous"]:
        return source
    assert identity==item["current"],"Unreviewed browser notification runner"
    restored=source
    for current,previous in item["deltas"]:
        assert restored.count(current)==1
        restored=restored.replace(current,previous,1)
    raw=restored.encode()
    assert (len(raw),hashlib.sha256(raw).hexdigest())==item["previous"]
    forward=restored
    for current,previous in item["deltas"]:
        assert forward.count(previous)==1
        forward=forward.replace(previous,current,1)
    assert forward==source
    return restored

def inverse(source):
    source=browser_quiet_input(source)
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
        self.assertTrue(original.verify_shared_ui_source(historical_bytes('tests/gecko/run_ui_visuals.py').decode('utf-8'))['originalWorkloadSemanticsPreserved'])
        self.assertTrue(original.verify_download_visual_fixture_source(historical_bytes('tests/gecko/UiVisualIntegrationActivity.java'))['fourSyntheticRowsAndProductionRendererPreserved'])

    def test_browser_contract_change_is_exact_and_cannot_weaken_current_checks(self):
        source=(ROOT/'tests/gecko/run_quiet_notifications.py').read_text()
        restored=browser_quiet_input(source)
        self.assertEqual(browser_quiet_input(restored),restored)
        self.assertEqual(hashlib.sha256(inverse(source).encode()).hexdigest(),
                         '72e6468c4a90b41deee4043e917ff5619eb32cc09aeedbd9d8243f1d77059760')
        for current,_ in BROWSER_QUIET_CHANGE['deltas']:
            for altered in (source.replace(current,'',1),source.replace(current,current*2,1),
                            source.replace(current,'',1)+current):
                with self.assertRaises(AssertionError):browser_quiet_input(altered)
        altered=source.replace('verify_browser_notifications(result)','pass',1)
        self.assertNotEqual(altered,source)
        with self.assertRaises(AssertionError):browser_quiet_input(altered)

    def test_removal_duplication_movement_or_original_workload_edits_reject(self):
        source=(ROOT/'tests/gecko/run_quiet_notifications.py').read_text()
        for value in (source.replace(EXTRA,''),source.replace(EXTRA,EXTRA*2),source.replace('check=True','check=False'),source.replace('deadline=time.monotonic()+120','deadline=time.monotonic()+121'),source.replace(EXTRA+'            raise SystemExit(0)\n','            raise SystemExit(0)\n'+EXTRA)):
            with self.assertRaises(AssertionError):inverse(value)

if __name__=='__main__':unittest.main(verbosity=2)
