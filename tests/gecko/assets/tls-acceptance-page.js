(async()=>{
  'use strict';
  const c=globalThis.__tlsProduct;
  if(!c?.service)return;
  const prefix='/tls-product/slot'+c.slot+'/',scope=new URL(prefix,location.href).href,script=new URL(prefix+'service.js',location.href).href;
  const existing=await navigator.serviceWorker.getRegistration(scope),controlled=!!navigator.serviceWorker.controller;
  const registration=existing||await navigator.serviceWorker.register(script,{scope:prefix});
  const ready=await navigator.serviceWorker.ready;
  if(ready.scope!==scope||!registration.active||registration.active.scriptURL!==script)throw new Error('WorkerBinding');
  const channel=new MessageChannel();
  const actual=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('WorkerTimeout')),12000);channel.port1.onmessage=e=>{clearTimeout(timer);resolve(e.data);};registration.active.postMessage({schema:1,runNonce:c.runNonce,caseNonce:c.caseNonce,sourceCommit:c.sourceCommit,slot:c.slot},[channel.port2]);});
  if(actual?.schema!==1||actual.caseNonce!==c.caseNonce||actual.fetchNonceMatched!==true||!/^[0-9a-f]{32}$/.test(actual.bootNonce))throw new Error('WorkerReply');
  const packet={schema:1,runNonce:c.runNonce,caseNonce:c.caseNonce,sourceCommit:c.sourceCommit,slot:c.slot,existingRegistration:!!existing,controlledBeforeRegistration:controlled,scriptPath:prefix+'service.js',scopePath:prefix,bootNonce:actual.bootNonce,fetchNonceMatched:true};
  const query=new URLSearchParams({run:c.runNonce,case:c.caseNonce,source:c.sourceCommit});
  const response=await fetch(prefix+'service-report?'+query,{method:'POST',body:JSON.stringify(packet),cache:'no-store',credentials:'same-origin'});
  if(!response.ok)throw new Error('ReportRejected');
})().catch(()=>{});
