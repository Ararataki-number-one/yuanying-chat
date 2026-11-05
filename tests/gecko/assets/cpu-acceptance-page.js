/* Integration-only first inline script. No navigator/Worker prototype is changed. */
'use strict';
(() => {
  function first(){
    const hardwareConcurrency=navigator.hardwareConcurrency;
    let holder=navigator,descriptor=null;
    for(let depth=0;holder&&depth<5;depth++,holder=Object.getPrototypeOf(holder)){descriptor=Object.getOwnPropertyDescriptor(holder,'hardwareConcurrency');if(descriptor)break;}
    const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
    return {hardwareConcurrency,nativeGetter:!!descriptor&&typeof descriptor.get==='function'&&/\[native code\]/.test(Function.prototype.toString.call(descriptor.get)),firstInline:true,bootNonce:Array.from(bytes,v=>v.toString(16).padStart(2,'0')).join('')};
  }
  const FIRST=first(),config=globalThis.__cpuAcceptance,prefix='/cpu/slot'+config.slot+'/',query='?run='+config.runNonce+'&case='+config.caseNonce;
  const message={kind:'cpu-first-inline',caseNonce:config.caseNonce};
  const valid=value=>value&&value.kind==='cpu-first-inline-result'&&value.caseNonce===config.caseNonce;
  const unsupported=()=>({status:'unsupported',observation:null,error:'Unavailable'});
  const observed=observation=>({status:'observed',observation,error:null});
  async function report(role,value,service=null){
    const packet={schema:1,...config,role,...value,service};
    const response=await fetch(prefix+'report'+query,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(packet),cache:'no-store'});
    if(!response.ok)throw Error('controlled-report-rejected');
  }
  const bounded=operation=>new Promise(resolve=>{let done=false,dispose=()=>{};const finish=value=>{if(done)return;done=true;clearTimeout(timer);dispose();resolve(value);};const timer=setTimeout(()=>finish({status:'failed',observation:null,error:'TimeoutError'}),12000);try{dispose=operation(finish)||dispose;}catch(_){finish({status:'failed',observation:null,error:'WorkerError'});}});
  const deliver=(finish,value)=>finish(valid(value)?observed(value.observation):{status:'failed',observation:null,error:'InvalidReply'});
  async function dedicated(blob){
    if(typeof Worker!=='function')return unsupported();let target=prefix+'worker.js',revoke=false;
    if(blob){const response=await fetch(target,{cache:'no-store'});if(!response.ok)throw Error('worker-script');target=URL.createObjectURL(new Blob([await response.text()],{type:'application/javascript'}));revoke=true;}
    return bounded(finish=>{const worker=new Worker(target);worker.onmessage=event=>deliver(finish,event.data);worker.onerror=()=>finish({status:'failed',observation:null,error:'WorkerError'});worker.postMessage(message);return()=>{worker.terminate();if(revoke)URL.revokeObjectURL(target);};});
  }
  function shared(){if(typeof SharedWorker!=='function')return Promise.resolve(unsupported());return bounded(finish=>{const worker=new SharedWorker(prefix+'worker.js','cpu-'+config.caseNonce);worker.port.onmessage=event=>deliver(finish,event.data);worker.onerror=()=>finish({status:'failed',observation:null,error:'WorkerError'});worker.port.start();worker.port.postMessage(message);return()=>worker.port.close();});}
  async function service(){
    if(!isSecureContext||!('serviceWorker'in navigator))return {value:unsupported(),proof:null};
    const existing=await navigator.serviceWorker.getRegistration(prefix),controlled=!!navigator.serviceWorker.controller;
    const registration=existing||await navigator.serviceWorker.register(prefix+'service.js',{scope:prefix});
    const value=await bounded(finish=>{let sent=false,channel;const deliverNow=()=>{const worker=registration.active;if(sent||!worker||worker.state!=='activated')return;sent=true;channel=new MessageChannel();channel.port1.onmessage=event=>deliver(finish,event.data);worker.postMessage(message,[channel.port2]);};const worker=registration.installing||registration.waiting||registration.active;if(worker)worker.addEventListener('statechange',deliverNow);deliverNow();return()=>{if(worker)worker.removeEventListener('statechange',deliverNow);if(channel)channel.port1.close();};});
    // Deliberately keep this registration and origin for a real app process restart.
    return {value,proof:{existingRegistration:!!existing,controlledBeforeRegistration:controlled,scriptPath:prefix+'service.js',scopePath:prefix}};
  }
  async function execute(role,operation){try{await report(role,await operation());}catch(_){await report(role,{status:'failed',observation:null,error:'WorkerError'});}}
  (async()=>{await report('page',observed(FIRST));await Promise.all([execute('dedicated',()=>dedicated(false)),execute('blob',()=>dedicated(true)),execute('shared',shared),(async()=>{try{const result=await service();await report('service',result.value,result.value.status==='observed'?result.proof:null);}catch(_){await report('service',{status:'failed',observation:null,error:'WorkerError'});}})()]);})().catch(()=>{});
})();
