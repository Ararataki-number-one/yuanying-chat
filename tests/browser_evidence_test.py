"""Offline rejection tests for the additional browser evidence gate; no Android claim."""
import copy,hashlib,importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('browser_evidence',ROOT/'tools/browser/check_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

class BrowserEvidenceTests(unittest.TestCase):
    def document(self):
        source='a'*40;nonce='b'*32;sha=hashlib.sha256(b'controlled source').hexdigest()
        checks=[dict(name=name,pass_=True) for name in gate.REQUIRED]
        checks=[{'name':c['name'],'pass':c['pass_']} for c in checks]
        actions=[dict(kind='tap',stage=s,x=20,y=30) for s in ['file-picker-1','file-picker-2','download-click']]+[dict(kind='back',stage=s,actualDocumentsUiObserved=True) for s in ['file-picker-1','file-picker-2']]+[dict(kind='rotation',stage='rotate-landscape',value=1),dict(kind='rotation',stage='rotate-portrait',value=0)]+[dict(kind='engine-roundtrip',actualEnhancedActivityResumed=True,browserTaskId=2,enhancedTaskId=3)]
        return dict(status='passed',sourceCommit=source,runNonce=nonce,executionInputsUnchanged=True,actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualDesktopChromiumExecution=False,actualPublicWebsiteExecution=False,actualDevicePerformanceMeasurement=False,actualAndroidTaps=3,trustedAndroidActions=actions,sourceFiles={p:sha for p in gate.SOURCE_INPUTS},result=dict(status='passed',sourceCommit=source,runNonce=nonce,taskId=2,actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualGeckoExecution=False,actualPublicWebsiteExecution=False,actualDevicePerformanceMeasurement=False,provider={'package':'controlled.webview','version':'fixture'},checks=checks,leaseObservations=[dict(stage=s,surfaces=a,downloads=b,changes=0,held=bool(a or b),nativeRouteBusy=bool(a or b)) for s,a,b in [('first-surface',1,0),('two-surfaces',2,0),('download-in-flight',2,1),('download-complete',2,0),('route-blocked',0,0),('route-restored',1,0),('engine-roundtrip',1,0)]],layoutObservations=[dict(orientation=o,fontScale=2.0,controls=[dict(name=n,shown=True,minimum=40,visibleWidth=48,visibleHeight=48) for n in ['address','back','forward','tabs','reload']]) for o in [2,1]],passed=len(checks),total=len(checks),proxy=dict(upstreamConnections=0,forwardingImplemented=False,downloadRequests=1)))
    def validate(self,value):return gate.validate_behavior(value,'a'*40,lambda source,path:b'controlled source')
    def test_valid_behavior_structure(self):self.assertEqual(self.validate(self.document())['status'],'passed')
    def test_reject_incomplete_or_mis_scoped_evidence(self):
        mutations=[lambda r:r.update(status='failed'),lambda r:r.update(sourceCommit='c'*40),lambda r:r.update(executionInputsUnchanged=False),lambda r:r.update(actualAndroidWebViewExecution=False),lambda r:r.update(actualDesktopChromiumExecution=True),lambda r:r['result'].update(runNonce='d'*32),lambda r:r['result'].update(provider={}),lambda r:r['result'].update(actualGeckoExecution=True),lambda r:r['result'].update(actualPublicWebsiteExecution=True),lambda r:r['result'].update(actualDevicePerformanceMeasurement=True),lambda r:r['result'].update(taskId=9),lambda r:r['result']['leaseObservations'].pop(),lambda r:r['result']['leaseObservations'][0].update(nativeRouteBusy=False),lambda r:r['result']['leaseObservations'][2].update(downloads=0),lambda r:r['result']['layoutObservations'][0].update(fontScale=1.0),lambda r:r['result']['layoutObservations'][0]['controls'][0].update(visibleHeight=1),lambda r:r['trustedAndroidActions'][-1].update(enhancedTaskId=2),lambda r:r['result']['checks'][0].update({'pass':False}),lambda r:r['result']['checks'][0].update(name='unrelated'),lambda r:r['trustedAndroidActions'].pop(),lambda r:r.update(actualAndroidTaps=0),lambda r:r['result']['proxy'].update(upstreamConnections=1),lambda r:r['sourceFiles'].clear(),lambda r:r['sourceFiles'].update({'../escape':'e'*64}),lambda r:r['sourceFiles'].update({next(iter(r['sourceFiles'])):'f'*64})]
        for index,change in enumerate(mutations):
            with self.subTest(index=index):
                value=self.document();change(value)
                with self.assertRaises(ValueError):self.validate(value)

if __name__=='__main__':unittest.main(verbosity=2)
