"""Require real swipe/native-layout evidence and complete bound Android payloads."""
if __package__:
    from .integration_event_contract import EventTransfer,event_uri
else:
    from integration_event_contract import EventTransfer,event_uri

NAMES={
    'Actual Gecko document starts with collapsed environment controls',
    'Tapping compact environment name expands controls without replacing the document',
    'Trusted upward reading swipe compacts chrome only after the gesture',
    'Downward reading preserves the compact environment bar',
    'Compact environment remains tappable after a webpage swipe',
    'Horizontal scrolling does not collapse environment controls',
    'Short gestures do not collapse environment controls',
    'Tapping the already selected Chat tab reveals environment controls',
    'Returning from native settings reveals chrome without reloading chat',
    'Activity resume preserves the collapsed controls and live SDK page',
    'Explicit Chat tap reveals controls after resume',
    'Upward swipe on native environment controls collapses only after release',
    'Native header swipe starts inside an actual expanded button touch region',
    'All chrome interactions use one controlled actual document without navigation or send',
}

def verify_auto_collapse(report,source,apk_sha):
    assert report['status']=='passed' and report['sourceCommit']==source
    assert all(report[k] is True for k in ['actualAndroidExecution','actualGeckoExecution','actualAndroidTouchExecution'])
    identity=report['buildIdentity'];assert identity['sourceCommit']==source and identity['apkSha256']==apk_sha
    assert {(c['viewport'],c['fontScale']) for c in report['cases']}=={(360,1),(412,1),(360,2)} and len(report['cases'])==3
    phases={'ready','initialChat','resumeChat','headerUp','up','down','compactExpand','horizontal','short','upBeforeChat','selectedChat','upBeforeNative','settings','nativeReturn','upBeforeResume','activityResume'}
    for case in report['cases']:
        assert case['sourceCommit']==source and all(case[k] is True for k in ['actualAndroidExecution','actualGeckoExecution','actualAndroidTouchExecution'])
        assert NAMES<={check['name'] for check in case['checks']} and all(check['pass'] is True for check in case['checks'])
        owned=case['eventTransfer'];assert owned['runNonce']==case['runNonce'] and owned['fixtureAction']=='chromeCollapse' and owned['processSlot']==0
        rows=owned['events'];payloads={event_uri(row['receipt']):row['rawUtf8'].encode('utf-8') for row in rows}
        assert len(rows)==len(payloads)==len(phases)
        transfer=EventTransfer(identity=identity,nonce=case['runNonce'],slot=0,action='chromeCollapse',fetch=lambda uri:payloads[uri])
        snapshots={}
        for row in rows:
            event=transfer.read(row['receipt']);assert event['kind']=='collapseSnapshot'
            sample=event['result'];assert sample['command'] not in snapshots;snapshots[sample['command']]=sample
        assert snapshots==case['observations'] and set(snapshots)==phases
        cold=snapshots['ready'];initial=snapshots['initialChat']
        assert not cold['expanded'] and cold['toolbarVisibility']==0 and cold['compactVisibility']==0 and cold['topVisibility']==8 and cold['networkVisibility']==0 and cold['compactName']==cold['environmentName'] and cold['compactHeight']>0 and cold['visibleDocument'] and cold['loadingCoverVisibility']==8
        assert cold['webHeight']==initial['webHeight']+initial['toolbarHeight']-cold['toolbarHeight']
        assert initial['expanded'] and initial['toolbarVisibility']==0 and initial['toolbarHeight']>0
        assert initial['visibleDocument'] and initial['loadingCoverVisibility']==8 and initial['documents']==1
        ready=initial['documentReadyEvidence']
        actual='http://127.0.0.1:8765/c/reload-collapse';virtual='https://chatgpt.com/c/reload-collapse'
        assert ready['rawMessage']['kind']=='documentReady' and ready['rawMessage']['url']==actual
        assert ready['senderUrl']==ready['actualUrl']==actual and ready['visibleUrl']==virtual
        assert ready['normalizedMessage']==dict(ready['rawMessage'],url=virtual)
        assert ready['topLevel'] is True and ready['contentScript'] is True and ready['acceptedByProduction'] is True
        assert ready['nativeSession']==ready['currentSession']==initial['sdkSession']
        assert initial['loads']==initial['stops']==initial['sendCount']==0 and initial['sdkSession']==initial['attachedSession']
        assert len(initial['document'])==32 and initial['draft']=='unsent controlled browser draft' and initial['pending']['confirmed']
        stable=['surface','sdkSession','attachedSession','document','draft','cookie','sendCount','path','loads','stops','documents','pending','pendingStored','activityStarts','menuOpens']
        for sample in snapshots.values():
            assert sample['networkVisibility']==0, 'Network information must stay visible in both chrome states'
            assert all(sample[k]==initial[k] for k in stable),sample['command']
            telemetry=sample['fixtureInputTelemetry']
            assert sample['telemetryReady'] is True and telemetry['schema']==1 and telemetry['realm']=='page-main-world'
            assert telemetry['document']==sample['document'] and 'touchend' in telemetry['listenerTypes']
            assert telemetry['events']==sample['trusted'] and len(telemetry['events'])<=256
            assert telemetry['count']==len(telemetry['events'])+telemetry['dropped']
            assert all(isinstance(row['trusted'],bool) and row['type'] in telemetry['listenerTypes'] for row in telemetry['events'])
        for before_key,after_key,expanded in [('initialChat','up',False),('up','down',False),('compactExpand','horizontal',True)]:
            before,after=snapshots[before_key],snapshots[after_key];touches=after['touches']
            assert len(touches)>=3 and touches[0]['action']==0 and touches[-1]['action']==1 and any(t['action']==2 for t in touches)
            assert all(t['pointers']==1 and t['width']==before['webWidth'] and t['height']==before['webHeight'] and t['expanded']==before['expanded'] for t in touches)
            assert after['expanded'] is expanded
        assert snapshots['up']['webHeight']==initial['webHeight']+initial['toolbarHeight']-cold['toolbarHeight'] and snapshots['up']['toolbarVisibility']==0 and snapshots['up']['compactVisibility']==0
        assert snapshots['up']['scrollY']>initial['scrollY'] and any(t['trusted'] is True and t['type']=='touchend' for t in snapshots['up']['trusted'])
        assert not snapshots['down']['expanded'] and snapshots['down']['compactVisibility']==0 and snapshots['down']['webHeight']==cold['webHeight']
        assert snapshots['compactExpand']['expanded'] and snapshots['compactExpand']['compactVisibility']==8 and snapshots['compactExpand']['topVisibility']==0 and snapshots['compactExpand']['networkVisibility']==0 and snapshots['compactExpand']['webHeight']==initial['webHeight']
        assert initial['toolbarHeight']>cold['toolbarHeight'] and initial['compactVisibility']==8
        assert snapshots['short']['expanded'] and snapshots['short']['webHeight']==initial['webHeight']
        for key,prior in [('selectedChat','upBeforeChat'),('nativeReturn','upBeforeNative'),('resumeChat','upBeforeResume')]:
            assert snapshots[prior]['expanded'] is False and snapshots[key]['expanded'] and snapshots[key]['page']==0 and snapshots[key]['webHeight']==initial['webHeight']
        assert not snapshots['activityResume']['expanded'] and snapshots['activityResume']['webHeight']==snapshots['upBeforeResume']['webHeight']
        header=snapshots['headerUp'];touches=header['nativeTouches']
        assert not header['expanded'] and header['toolbarVisibility']==0 and header['compactVisibility']==0 and header['webHeight']==cold['webHeight'] and header['windowFocus'] and header['activityStarts']==header['menuOpens']==0
        left,top,right,bottom=snapshots['resumeChat']['headerButtonTouch'];start=snapshots['resumeChat']['headerSwipeFrom']
        assert left<=start[0]<right and top<=start[1]<bottom
        assert len(touches)>=3 and touches[0]['action']==0 and touches[-1]['action']==1 and any(t['action']==2 for t in touches)
        assert all(t['pointers']==1 and t['height']==initial['webHeight'] and t['expanded'] for t in touches)
        assert snapshots['settings']['page']==3 and len(case['fixtureRequests'])==1 and case['fixtureRequests'][0]['documentMarker']==initial['document']
        gestures=case['actualAndroidInputs'];assert len(gestures)==14 and all(g['actualAndroidInput'] is True for g in gestures)
        assert [g['kind'] for g in gestures].count('swipe')==8 and [g['kind'] for g in gestures].count('tap')==6
    return {'cases':3,'actualAndroidExecution':True,'actualGeckoExecution':True,'checks':sum(len(c['checks']) for c in report['cases'])}
