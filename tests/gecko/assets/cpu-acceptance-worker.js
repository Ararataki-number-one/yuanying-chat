/* Test-only. The native getter is sampled when this worker global first runs. */
'use strict';
function first(){
  const hardwareConcurrency=navigator.hardwareConcurrency;
  let holder=navigator,descriptor=null;
  for(let depth=0;holder&&depth<5;depth++,holder=Object.getPrototypeOf(holder)){descriptor=Object.getOwnPropertyDescriptor(holder,'hardwareConcurrency');if(descriptor)break;}
  const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
  return {hardwareConcurrency,nativeGetter:!!descriptor&&typeof descriptor.get==='function'&&/\[native code\]/.test(Function.prototype.toString.call(descriptor.get)),firstInline:true,bootNonce:Array.from(bytes,v=>v.toString(16).padStart(2,'0')).join('')};
}
const FIRST=first();
const answer=data=>data&&data.kind==='cpu-first-inline'&&/^[0-9a-f]{32}$/.test(data.caseNonce||'')?{kind:'cpu-first-inline-result',caseNonce:data.caseNonce,observation:FIRST}:null;
if(typeof ServiceWorkerGlobalScope!=='undefined'&&self instanceof ServiceWorkerGlobalScope){
  self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
  self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
  self.addEventListener('message',event=>{const value=answer(event.data);if(value&&event.ports.length===1)event.ports[0].postMessage(value);});
}else if(typeof SharedWorkerGlobalScope!=='undefined'&&self instanceof SharedWorkerGlobalScope){
  self.addEventListener('connect',event=>{const port=event.ports[0];port.onmessage=event=>{const value=answer(event.data);if(value)port.postMessage(value);};port.start();});
}else self.onmessage=event=>{const value=answer(event.data);if(value)self.postMessage(value);};
