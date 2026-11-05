'use strict';
const bootNonce=crypto.randomUUID().replaceAll('-','');
self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('message',event=>{
  const c=event.data,port=event.ports?.[0];
  if(!port||c?.schema!==1||!Number.isInteger(c.slot)||![1,2].includes(c.slot)||!/^[0-9a-f]{32}$/.test(c.runNonce)||!/^[0-9a-f]{32}$/.test(c.caseNonce)||!/^[0-9a-f]{40}$/.test(c.sourceCommit))return;
  event.waitUntil((async()=>{
    const prefix='/tls-product/slot'+c.slot+'/';
    if(new URL(self.registration.scope).pathname!==prefix||new URL(self.location.href).pathname!==prefix+'service.js')throw new Error('WorkerScope');
    const query=new URLSearchParams({run:c.runNonce,case:c.caseNonce,source:c.sourceCommit,boot:bootNonce});
    const response=await fetch(prefix+'sw-fetch?'+query,{cache:'no-store',credentials:'same-origin'});
    const matched=response.ok&&(await response.text())===c.caseNonce;
    port.postMessage({schema:1,caseNonce:c.caseNonce,bootNonce,fetchNonceMatched:matched});
  })());
});
