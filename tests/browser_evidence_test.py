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
    def current_document(self):
        value=self.document()
        value['result']['layoutObservations']=[dict(navigationContract=3,orientation=o,fontScale=2.0,density=3.0,
            controls=[dict(name=n,shown=True,minimum=144,visibleWidth=216 if n=='address' else 144,visibleHeight=144)
                      for n in ['back','home','address','reload','menu']]) for o in [2,1]]
        return value
    def test_current_bottom_toolbar_keeps_both_real_orientation_requirements(self):
        self.assertEqual(self.validate(self.current_document())['status'],'passed')
    def test_current_layout_rejects_mixed_legacy_small_or_missing_targets(self):
        mutations=[lambda r:r['result']['layoutObservations'][0].update(navigationContract=1),
                   lambda r:r['result']['layoutObservations'][0].update(navigationContract=True),
                   lambda r:r['result']['layoutObservations'][0]['controls'][1].update(name='forward'),
                   lambda r:r['result']['layoutObservations'][0]['controls'][0].update(minimum=120,visibleWidth=120),
                   lambda r:r['result']['layoutObservations'][0]['controls'][0].update(visibleHeight=143),
                   lambda r:r['result']['layoutObservations'][0].pop('density'),
                   lambda r:r['result']['layoutObservations'][0].update(density=True),
                   lambda r:r['result']['layoutObservations'][0]['controls'].reverse(),
                   lambda r:r['result']['layoutObservations'][0]['controls'].pop()]
        for index,change in enumerate(mutations):
            with self.subTest(index=index):
                value=self.current_document();change(value)
                with self.assertRaises(ValueError):self.validate(value)
    def test_reject_incomplete_or_mis_scoped_evidence(self):
        mutations=[lambda r:r.update(status='failed'),lambda r:r.update(sourceCommit='c'*40),lambda r:r.update(executionInputsUnchanged=False),lambda r:r.update(actualAndroidWebViewExecution=False),lambda r:r.update(actualDesktopChromiumExecution=True),lambda r:r['result'].update(runNonce='d'*32),lambda r:r['result'].update(provider={}),lambda r:r['result'].update(actualGeckoExecution=True),lambda r:r['result'].update(actualPublicWebsiteExecution=True),lambda r:r['result'].update(actualDevicePerformanceMeasurement=True),lambda r:r['result'].update(taskId=9),lambda r:r['result']['leaseObservations'].pop(),lambda r:r['result']['leaseObservations'][0].update(nativeRouteBusy=False),lambda r:r['result']['leaseObservations'][2].update(downloads=0),lambda r:r['result']['layoutObservations'][0].update(fontScale=1.0),lambda r:r['result']['layoutObservations'][0]['controls'][0].update(visibleHeight=1),lambda r:r['trustedAndroidActions'][-1].update(enhancedTaskId=2),lambda r:r['result']['checks'][0].update({'pass':False}),lambda r:r['result']['checks'][0].update(name='unrelated'),lambda r:r['trustedAndroidActions'].pop(),lambda r:r.update(actualAndroidTaps=0),lambda r:r['result']['proxy'].update(upstreamConnections=1),lambda r:r['sourceFiles'].clear(),lambda r:r['sourceFiles'].update({'../escape':'e'*64}),lambda r:r['sourceFiles'].update({next(iter(r['sourceFiles'])):'f'*64})]
        for index,change in enumerate(mutations):
            with self.subTest(index=index):
                value=self.document();change(value)
                with self.assertRaises(ValueError):self.validate(value)

class PortraitEvidenceTests(unittest.TestCase):
    """Synthetic rejection cases; only the Android jobs supply execution evidence."""
    @staticmethod
    def reading(control, rotation):
        landscape=bool(control and rotation==1)
        w,h=(1920,1080) if landscape else (1080,1920)
        cls='RotationControlActivity' if control else 'BrowserIntegrationActivity'
        return dict(component='local.pocketchat.test/local.pocketchat.'+cls,
                    orientation='landscape' if landscape else 'portrait',bounds=[0,0,w,h],
                    accelerometerRotation='0',userRotation=str(rotation),
                    activityConfig='mCurrentConfig={ '+('land' if landscape else 'port')+
                                   f' winConfig={{ mBounds=Rect(0, 0 - {w}, {h}) }} }}')

    def current(self):
        row=BrowserEvidenceTests().current_document()
        for entry in row['result']['checks']:
            if entry['name']=='Large-font landscape keeps address and navigation targets visible':
                entry['name']='Large-font locked portrait keeps address and navigation targets visible while the device requests landscape'
            if entry['name']=='Large-font orientation changes preserve the live website draft and document':
                entry['name']='Device rotation requests preserve the portrait website draft and document'
        row['rotationCalibration']=dict(controlPortrait=self.reading(True,0),controlLandscape=self.reading(True,1))
        actions=[a for a in row['trustedAndroidActions'] if a['kind']=='rotation']
        for a in actions:a['systemUserRotation']=str(a['value'])
        for n,layout in enumerate(row['result']['layoutObservations']):
            layout.update(orientation=1,rootWidth=1080,rootHeight=1920,deviceUserRotation=1-n,
                          component=self.reading(False,1)['component'])
        row['sourceFiles']['tools/gecko/portrait_orientation.py']=hashlib.sha256(b'controlled source').hexdigest()
        return row

    def test_calibration_and_portrait_gate_are_independent(self):
        check=lambda row:gate.validate_behavior(row,'a'*40,lambda source,path:b'controlled source',portrait_only=True)
        self.assertEqual(check(self.current())['status'],'passed')
        changes=[
            lambda v:v.pop('rotationCalibration'),
            lambda v:v['rotationCalibration'].update(controlLandscape=self.reading(True,0)),
            lambda v:v['rotationCalibration']['controlLandscape'].update(component=self.reading(False,1)['component']),
            lambda v:v['rotationCalibration']['controlLandscape'].update(bounds=[0,0,1080,1920]),
            lambda v:v['rotationCalibration']['controlLandscape'].update(activityConfig=self.reading(True,0)['activityConfig']),
            lambda v:v['result']['layoutObservations'][0].update(orientation=2),
            lambda v:v['result']['layoutObservations'][0].update(rootWidth=1920,rootHeight=1080),
            lambda v:v['result']['layoutObservations'][0].update(deviceUserRotation=0),
            lambda v:v['result']['layoutObservations'][0].update(component=self.reading(True,0)['component']),
            lambda v:v['sourceFiles'].pop('tools/gecko/portrait_orientation.py'),
            lambda v:next(a for a in v['trustedAndroidActions'] if a['kind']=='rotation').update(systemUserRotation='0'),
        ]
        for change in changes:
            doc=self.current();change(doc)
            with self.subTest(change=change),self.assertRaises(ValueError):check(doc)
        with self.assertRaises(ValueError):check(BrowserEvidenceTests().current_document())

if __name__=='__main__':unittest.main(verbosity=2)
