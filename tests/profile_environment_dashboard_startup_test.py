"""Real native startup methods and wait policy on explicit JVM platform doubles.

No Android frame timing, actual Gecko initialization or phone speed is claimed.
"""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
PROD=ROOT/'app/src/main/java/local/pocketchat'

def member(source,signature):
    start=source.index(signature);opening=source.index('{',start);depth=0
    for at in range(opening,len(source)):
        if source[at]=='{':depth+=1
        elif source[at]=='}':
            depth-=1
            if depth==0:return source[start:at+1]
    raise ValueError('Missing Java method boundary')

class DashboardStartup(unittest.TestCase):
    def test_real_entry_lifecycle_and_wait_boundaries(self):
        java=Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        source=(PROD/'MainActivity.java').read_text()
        methods='\n'.join(member(source,x) for x in ['  @Override public void onCreate(', '  void prepareBrowserAfterOverview(', '  void startBrowserAfterOverview(', '  @Override protected void onResume(', '  @Override protected void onNewIntent('])
        host=(ROOT/'tests/overview-dashboard-host/StartupHost.java').read_text().replace('/*ACTUAL_ENTRY_METHODS*/',methods)
        with tempfile.TemporaryDirectory(prefix='overview-dashboard-startup-') as folder:
            folder=Path(folder);(folder/'StartupHost.java').write_text(host)
            for name in ['BrowserStartupGate.java','PageLoadingWait.java']:(folder/name).write_bytes((PROD/name).read_bytes())
            compiled=subprocess.run([str(java.with_name('javac')),'-encoding','UTF-8','-d',str(folder),*map(str,folder.glob('*.java'))],capture_output=True,text=True,timeout=40)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run([str(java),'-cp',str(folder),'local.pocketchat.StartupHost'],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads(result.stdout);self.assertGreaterEqual(report['checks'],30)
            report.update(status='passed',scope=__doc__.strip(),sourceSha256={name:hashlib.sha256((PROD/name).read_bytes()).hexdigest() for name in ['MainActivity.java','BrowserStartupGate.java','PageLoadingWait.java']})
            output=os.environ.get('DASHBOARD_STARTUP_REPORT')
            if output:Path(output).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':unittest.main(verbosity=2)
