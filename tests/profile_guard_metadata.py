"""Counterfeit metadata builders for validator unit tests; never Android evidence."""
from copy import deepcopy

GUARD_NAMES = [
    'Closed guard route evidence did not overflow',
    'Closed guard returns the blocked actual route for fetch GET',
    'Closed guard returns the blocked actual route for HTTP Worker',
    'Closed guard receives owned actual native callback',
    'Closed guard fetch terminates in an actual network rejection',
    'Closed guard HTTP Worker terminates in a trusted error event',
    'Closed guard accepts no new controlled TCP connection',
    'Closed guard parses no new controlled request',
    'Controlled listener remains bound after actual guard rejection',
]


def prototype_metadata(identity, nonce='e'*32):
    """A well-formed fake report for acceptance/rejection of metadata only."""
    origin='http://127.0.0.1:43123';fresh='f'*32
    document=origin+'/page?run='+nonce+'&case=4&session=primary'
    fetch=origin+'/echo?run='+fresh+'&case=4&session=primary&kind=guard-fetch'
    worker=origin+'/worker?run='+fresh+'&case=4&session=primary'
    names=['metadata-only original prototype check '+str(i) for i in range(129)]+GUARD_NAMES
    mobile='Mozilla/5.0 (Android 15; Mobile; rv:157.0) Gecko/157.0 Firefox/157.0'
    desktop='Mozilla/5.0 (X11; Linux x86_64; rv:157.0) Gecko/20100101 Firefox/157.0'
    coordinate=identity.get('sdkCoordinate','org.mozilla.geckoview:geckoview:157.0.20261005135250')
    aar='15f1edf3c58abcdaf2783f299b8c19c3a36272d348969106a9009671fef8d268'
    baseline=dict(api='GeckoSession.getDefaultUserAgent()',scope='sdk-build-mobile-default',
        userAgent=mobile,sdkCoordinate=coordinate,sdkAarSha256=aar,androidSdk=35,
        androidRelease='15',ignoresSessionOverrides=True,runtimeAcknowledgement=False)
    cases=[];all_headers=[]
    for index in range(4):
        sessions=[];mismatches=[]
        for name in ['primary','secondary'] if index==3 else ['primary']:
            ua=desktop if index==1 or name=='secondary' else mobile
            mismatch=ua!=mobile
            if mismatch:mismatches.append(name)
            language=['en-US','ja-JP','zh-TW','en-US'][index]
            signal=dict(ua=ua,language=language,languages=[language],zone='UTC',offset=0,at=20.0)
            headers=[]
            for role,path in [('page','/page'),('frame','/frame'),('worker-script','/worker'),
                    ('page-fetch','/echo'),('worker-fetch','/echo'),('blob-worker-fetch','/echo')]:
                query='?run='+nonce+'&case='+str(index+1)+'&session='+name
                if path=='/echo':query+='&kind='+role
                row=dict(sequence=len(all_headers)+1,case=index+1,session=name,role=role,
                    method='GET',path=path+query,userAgent=mobile if role in ('worker-fetch','blob-worker-fetch') else ua,
                    acceptLanguage=language,at=10*index+1)
                headers.append(deepcopy(row));all_headers.append(row)
            sessions.append(dict(name=name,native=dict(session=5001 if name=='primary' else 5002,
                runtime=9001,userAgent=ua,expectedSdkNormalizedLanguage=language,
                getterScope='Java requested value; not content acknowledgement',userAgentMode=1 if mismatch else 0),
                observed=dict(run=nonce,case=index+1,session=name,
                    **{context:deepcopy(signal) for context in ('parent','frame','worker','blobWorker')}),
                requestHeaders=headers,userAgentScope=dict(documentHeadersMatchSession=True,
                    workerFetchHeadersMatchSdkDefault=True,workerFetchHeadersMatchSession=not mismatch,
                    workerFetchHeaderMismatch=mismatch,observedUserAgentUniform=not mismatch,fullTemplateAcceptance=False)))
        cases.append(dict(index=index,serial=index+1,status='passed',requestedAt=10*index,
            completedAt=10*index+5,sessions=sessions,workerFetchMismatchSessions=mismatches,fullTemplateAcceptance=False))
    before=dict(address='127.0.0.1',port=43123,bound=True,closed=False,
        acceptedConnections=35,parsedRequests=35,completedConnections=34,
        rejectedConnections=0,failures=[],failuresDropped=0)
    # Earlier handlers may retire after the snapshot; that is not a new request.
    after=dict(before,completedConnections=35)
    blocked=[dict(url=url,guardAllowed=False,at=115,
        route=dict(type='socks',host='127.0.0.1',port=9,proxyDNS=True,failoverTimeout=1))
        for url in (fetch,worker)]
    guard=dict(status='passed',nonce=fresh,document=document,nativeSession=5001,
        fetchUrl=fetch,workerUrl=worker,requestedAt=100,
        nativePort=dict(nativeSession=5001,senderUrl=document,topLevel=True,
            environmentType=2,connectedAt=110),armCallback='"guard-armed"',
        nativeCallbackAt=120,completedAt=130,
        observed=dict(nonce=fresh,fetchUrl=fetch,workerUrl=worker,at=32.5,
            fetch=dict(outcome='network-error',name='TypeError',message='metadata-only rejection',at=30.0),
            worker=dict(outcome='error',trusted=True,message='',at=31.0)),
        blockedRoutes=blocked,blockedRoutesDropped=0,beforeServer=before,
        afterServer=after,beforeHeaderCount=30,afterHeaderCount=30)
    return dict(schema=1,status='passed',synthetic=True,actualAndroidExecution=True,
        sourceCommit=identity['sourceCommit'],runNonce=nonce,buildIdentity=deepcopy(identity),androidSdk=35,
        passed=len(names),total=len(names),executed=len(names),
        checks=[{'name':n,'pass':True} for n in names],origin=origin,cases=cases,
        diagnosticOnly=True,releaseAcceptance=False,actualGeckoExecution=True,
        publicNetworkTraffic=False,independentTimezone='unsupported',uncovered=['Service Worker'],
        sdkCoordinate=coordinate,sdkAarSha256=aar,sdkUserAgentBaseline=baseline,
        userAgentCapability=dict(sessionSettingsScope='top-browsing-context',workerFetchHeaderScope='sdk-build-mobile-default',
            runtimeUserAgentSetterAvailable=False,fullTemplateAcceptance=False),
        engineVersion='GeckoView 157.0.1',guardEvidence=guard,
        allRequestHeaders=all_headers)
