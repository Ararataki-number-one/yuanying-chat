#!/usr/bin/env python3
"""Worker-only extension of the strict synthetic two-host proxy.

The original fingerprint PATHS/server/tests are unchanged. TLS keys stay only
inside EphemeralCertificates' /tmp directory; this module exports no key bytes.
Both engine receipt buckets are retained for future actual Gecko Worker probes.
"""
import json
import re
from urllib.parse import parse_qs,urlsplit
from fingerprint_fixture_server import FingerprintServer,HOSTS,HEADERS,require

PHASES=('allow','restrict','restrict-route','restore','gecko-native','gecko-system','gecko-new-york','gecko-kathmandu','gecko-desktop','gecko-restored','gecko-reload','gecko-reopen','gecko-private','gecko-popup','gecko-rfp-conflict','gecko-system-mobile','gecko-ny-mobile','gecko-kathmandu-mobile','gecko-restore','gecko-mobile-restored','gecko-coop')
REALMS=('document','frame-dedicated','dedicated-classic','dedicated-module','dedicated-blob','shared-worker','shared-blob','service-worker','service-worker-install','service-worker-fetch')
PATHS=('/worker-document','/worker-frame','/env-policy','/env-frame','/gecko-environment-policy','/gecko-environment-frame','/dedicated.js','/module.js','/shared.js','/service.js','/worker-probe','/sw-cached','/favicon.ico')
NETWORK_BODY='worker-network-synthetic-v1'
CACHE_BODY='worker-cache-synthetic-v1'
TOKEN='__WORKER_POLICY_FIXTURE__'
TIMEZONE_SOURCE="function nativeZone(){function sample(month){const value=new Date(Date.UTC(2026,month,15,12,0,0));return {offsetMinutes:value.getTimezoneOffset(),year:value.getFullYear(),month:value.getMonth()+1,day:value.getDate(),hour:value.getHours(),minute:value.getMinutes()};}return {timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone,january:sample(0),july:sample(6)};}"


class WorkerFixtureServer(FingerprintServer):
    def __init__(self,certificates,script,binding,gecko_script=None):
        require(script.count(TOKEN)==1,'exact Worker page config placeholder required')
        if gecko_script is not None:require(type(gecko_script) is str and 0<len(gecko_script)<=32768 and gecko_script.count(TOKEN)==1 and '</script' not in gecko_script.lower(),'independent Gecko page script invalid')
        self.gecko_script=gecko_script
        super().__init__(certificates,script,binding)

    def close(self):
        # The legacy server's bounded joins do not assert thread termination.
        # Both new policy gates require a final snapshot with no later writers.
        # Never hold the receipt lock while the legacy close joins workers.
        with self._lock:workers=set(self._threads)
        super().close()
        with self._lock:workers.update(self._threads)
        require(not self.thread.is_alive() and not any(thread.is_alive() for thread in workers),
                'Worker fixture connections did not quiesce; final evidence is unavailable')

    def _respond(self,connection,engine,host,secure,method,target,headers):
        require(method=='GET','only synthetic Worker GET permitted');uri=urlsplit(target)
        require(uri.path in PATHS and not uri.fragment,'target outside Worker fixture paths')
        require(secure or engine=='gecko','Chromium Worker fixture requires real native TLS')
        require(headers.get('host') in (host,host+(':443' if secure else ':80')),'Worker HTTP authority differs')
        parameters=parse_qs(uri.query,strict_parsing=True)
        require(all(len(v)==1 for v in parameters.values()),'duplicate Worker query')
        if uri.path=='/favicon.ico':require(not parameters,'favicon query differs');self._send(connection,'image/x-icon',b'');return
        require(parameters.get('phase',[''])[0] in PHASES,'Worker phase invalid');phase=parameters['phase'][0]
        page=uri.path in ('/worker-document','/worker-frame','/env-policy','/env-frame','/gecko-environment-policy','/gecko-environment-frame')
        if page:
            require(set(parameters)=={'phase'},'Worker document query differs');realm='document' if uri.path in ('/worker-document','/env-policy','/gecko-environment-policy') else 'frame';document=''
        else:
            require(set(parameters)=={'phase','realm','documentId'},'Worker resource query differs');realm=parameters['realm'][0];document=parameters['documentId'][0]
            require(realm in REALMS and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',document),'Worker realm/document invalid')
            expected={'/dedicated.js':('dedicated-classic','frame-dedicated'),'/module.js':('dedicated-module',),'/shared.js':('shared-worker',),'/service.js':('service-worker',),'/sw-cached':('service-worker-install',),'/worker-probe':REALMS}
            require(realm in expected[uri.path],'Worker path/realm differs')
        origin=('https' if secure else 'http')+'://'+host
        observed=dict(origin=origin,path=uri.path,tls=secure,method='GET',phase=phase,realm=realm,documentId=document)
        observed.update({key:headers[key] for key in HEADERS if key in headers})
        with self._lock:
            row=self.rows[engine];require(len(row['requests'])<200,'Worker request receipt bound exceeded');row['requests'].append(observed);row['accepted']+=1
        if page:
            config=dict(runNonce=self.binding['runNonce'],sourceCommit=self.binding['sourceCommit'],origins=[('https' if secure else 'http')+'://'+value for value in HOSTS])
            selected_script=self.gecko_script if engine=='gecko' and self.gecko_script is not None else self.script
            script=selected_script.replace(TOKEN,json.dumps(config,separators=(',',':')))
            frame_path={'/env-policy':'/env-frame','/gecko-environment-policy':'/gecko-environment-frame'}.get(uri.path,'/worker-frame')
            other=HOSTS[1] if host==HOSTS[0] else HOSTS[0]
            frames="<iframe src='"+origin+frame_path+"?phase="+phase+"'></iframe><iframe src='"+('https' if secure else 'http')+"://"+other+frame_path+"?phase="+phase+"'></iframe>" if uri.path in ('/worker-document','/env-policy','/gecko-environment-policy') else ''
            form="<form><textarea id='gecko-policy-draft' name='geckoPolicyDraft'></textarea></form>" if uri.path=='/env-policy' else ''
            body=("<!doctype html><html><head><script>"+script+"</script><meta name='viewport' content='width=device-width,initial-scale=1'><title>Worker policy fixture</title></head><body><h1>Synthetic Worker policy</h1>"+form+frames+'</body></html>').encode();kind='text/html; charset=UTF-8'
        elif uri.path in ('/worker-probe','/sw-cached'):
            body=(NETWORK_BODY if uri.path=='/worker-probe' else CACHE_BODY).encode();kind='text/plain'
        elif uri.path=='/service.js':
            query='phase='+phase+'&realm=service-worker-install&documentId='+document
            body=(TIMEZONE_SOURCE+"const cacheName='pocketchat-worker-policy-v1',cacheKey='/worker-policy-cached-value';"
                  "addEventListener('install',event=>{event.waitUntil((async()=>{const response=await fetch('/sw-cached?"+query+"',{cache:'no-store'});if(!response.ok)throw Error('Synthetic cache fill failed');const cache=await caches.open(cacheName);await cache.put(cacheKey,response);await skipWaiting();})());});"
                  "addEventListener('activate',event=>event.waitUntil(clients.claim()));"
                  "addEventListener('message',event=>{event.waitUntil((async()=>{const result={executed:true,nativeUserAgent:navigator.userAgent,nativeTimeZone:nativeZone(),sourceRole:'service-worker'};if(event.data.action==='cached'){const cache=await caches.open(cacheName),response=await cache.match(cacheKey);result.cacheRead=!!response&&(await response.text())==='"+CACHE_BODY+"';}else{let allowed=false;try{const response=await fetch('/worker-probe?phase='+encodeURIComponent(event.data.phase)+'&realm=service-worker-fetch&documentId='+encodeURIComponent(event.data.documentId),{cache:'no-store'});allowed=response.ok&&(await response.text())==='"+NETWORK_BODY+"';}catch(_){}result.networkAllowed=allowed;}event.ports[0].postMessage(result);})());});").encode();kind='text/javascript'
        else:
            probe="'/worker-probe?phase="+phase+"&realm="+realm+"&documentId="+document+"'"
            result="let ok=false;try{const response=await fetch("+probe+",{cache:'no-store'});ok=response.ok&&(await response.text())==='"+NETWORK_BODY+"';}catch(_){}const result={executed:true,networkAllowed:ok,nativeUserAgent:navigator.userAgent,nativeTimeZone:nativeZone(),sourceRole:'"+realm+"',documentGuard:globalThis[Symbol.for('local.pocketchat.chromiumFingerprint.v1')]===true,auditAvailable:typeof globalThis.__pocketchatChromiumFingerprintObserve==='function'};"
            text=TIMEZONE_SOURCE+("onconnect=event=>{const port=event.ports[0];port.onmessage=async()=>{"+result+"port.postMessage(result)};port.start()};" if uri.path=='/shared.js' else "onmessage=async()=>{"+result+"postMessage(result)};")
            body=text.encode();kind='text/javascript'
        coop=engine=='gecko' and uri.path=='/env-policy' and phase=='gecko-coop'
        self._send(connection,kind,body,coop=coop)
        # Only a completed socket write attests that this response included COOP.
        # A parsed request or a failed send is deliberately insufficient.
        if coop:
            with self._lock:observed['responseCoop']='same-origin'

    @staticmethod
    def _send(connection,kind,body,coop=False):
        header='HTTP/1.1 200 OK\r\nContent-Type: '+kind+'\r\nContent-Length: '+str(len(body))+'\r\nCache-Control: no-store\r\nService-Worker-Allowed: /sw-scope/\r\nAccept-CH: Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform, Sec-CH-UA-Platform-Version, Sec-CH-UA-Model, Sec-CH-UA-Arch, Sec-CH-UA-Bitness, Sec-CH-UA-Full-Version-List\r\n'+('Cross-Origin-Opener-Policy: same-origin\r\n' if coop else '')+'Connection: close\r\n\r\n'
        connection.sendall(header.encode('ascii')+body)
