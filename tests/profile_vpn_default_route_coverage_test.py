"""Execute the production VPN route policy on controlled snapshots, not a VPN."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'app/src/main/java/local/pocketchat/VpnDefaultRouteCoverage.java'
HOST=ROOT/'tests/vpn-default-route-host/VpnDefaultRouteCoverageHost.java'

def execute():
 java=os.environ.get('PROFILE_JAVA')or shutil.which('java')
 if not java:raise RuntimeError('Java required for VPN default-route host policy checks')
 with tempfile.TemporaryDirectory(prefix='vpn-default-route-host-')as temp:
  compile_run=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-d',temp,str(POLICY),str(HOST)],capture_output=True,text=True,timeout=30)
  if compile_run.returncode:raise AssertionError(compile_run.stdout+compile_run.stderr)
  result=subprocess.run([java,'-cp',temp,'local.pocketchat.VpnDefaultRouteCoverageHost'],capture_output=True,text=True,timeout=15)
  if result.returncode:raise AssertionError(result.stdout+result.stderr)
  return json.loads(result.stdout)

class VpnDefaultRouteCoverageTest(unittest.TestCase):
 def test_real_policy_requires_confirmed_dual_default_routes(self):
  report=execute();self.assertEqual(report['status'],'passed');self.assertEqual(report['passed'],23)
  self.assertEqual(len(report['results']),23);self.assertTrue(all(r['pass']for r in report['results']))
  report.update(scope='Real production pure-Java policy with controlled route snapshots only; no CM, VPN, Android or real route execution',sourceSha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [POLICY,HOST,Path(__file__)]})
  output=ROOT/'work/profile-host/vpn-default-route-coverage-results.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':unittest.main()
