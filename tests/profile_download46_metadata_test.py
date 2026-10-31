"""46 byte receipts, cached metadata and bounded worker-prepared native pages."""
import json,os,shutil,subprocess,unittest
from pathlib import Path
from experience46_host_evidence import INVOCATION_FILES, emit_evidence, new_attempt, run_recorded
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'tests/download46-host'
OUTPUT_FILES=('results.json','compile.stdout.txt','compile.stderr.txt','stdout.txt','stderr.txt',
              'DownloadRecoveryHostTest.stdout.txt','DownloadRecoveryHostTest.stderr.txt',
              'Metadata46Cases.stdout.txt','Metadata46Cases.stderr.txt',*INVOCATION_FILES)

class Download46Behavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        java=os.environ.get('PROFILE_JAVA')or shutil.which('java')
        if not java:raise RuntimeError('Existing Java17 required')
        cls.java_home=Path(java).resolve().parents[1]
        desktop=[os.environ.get('PROFILE_JSON_JAR',''),str(ROOT/'work/profile-host/json.jar'),str(ROOT/'work/gecko-integration/catalog-json.jar')]
        android=[os.environ.get('PROFILE_ANDROID_JSON_JAR',''),str(ROOT/'work/profile-host/android-json.jar'),str(ROOT/'work/gecko-integration/sharing-android-json.jar')]
        cls.jars=[(label,next((Path(p)for p in choices if p and Path(p).is_file()),None))for label,choices in [('desktop',desktop),('android',android)]]
        if any(jar is None for _,jar in cls.jars):raise RuntimeError('Both existing pinned desktop and Android JSON dependencies required')
        cls.output=Path(os.environ.get('PROFILE_DOWNLOAD46_OUTPUT',str(ROOT/'work/profile-host/experience46-downloads')));cls.output.mkdir(parents=True,exist_ok=True)
    def run_host(self,script):
        reports=[]
        for label,jar in self.jars:
            with self.subTest(script=script,json=label):
                name=Path(script).stem+'-'+label;out=new_attempt(self.output,name)
                try:
                    result=run_recorded([shutil.which('python3')or'python3',str(HERE/script),'--java-home',str(self.java_home),'--json-jar',str(jar),'--output',str(out)],out,cwd=ROOT,timeout=100)
                    self.assertEqual(result.returncode,0,'Complete controlled output is retained in CI evidence: '+str(out));report=json.loads((out/'results.json').read_text());self.assertEqual(report['status'],'passed');self.assertTrue(report['executionInputsUnchanged']);self.assertIs(report['actualAndroidExecution'],False);reports.append(report)
                finally:
                    emit_evidence(out,OUTPUT_FILES,label='downloads-'+name)
        self.assertEqual(len(reports),2)
        return reports
    def test_actual_copy_metadata_and_publication_barriers(self):
        for report in self.run_host('run.py'):
            self.assertEqual([part['total']for part in report['reports']],[42,341])
            for part in report['reports']:self.assertTrue(all(case['pass']is True for case in part['checks']))
    def test_actual_worker_reads_names_times_and_package_status(self):
        for report in self.run_host('worker.py'):
            self.assertEqual(report['total'],29)
            for measurement in report['measurements']:
                for key in ['mainSqlCalls','mainProviderCalls','mainEnvironmentQueries']:self.assertEqual(measurement[key],0)
    def test_current_renderer_bounds_and_byte_labels(self):
        for report in self.run_host('display.py'):self.assertEqual(report['total'],27)

if __name__=='__main__':unittest.main()
